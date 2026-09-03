"""Tests op de fingerprint-sleutel zelf: normalisatie en frame-selectie.

De sleutel bepaalt of één oorzaak één issue wordt. Te weinig normaliseren laat
de aanmaak exploderen (elke sessie-id een eigen issue); te veel normaliseren
voegt stil samen, en dat is erger omdat er niets van te zien is. Beide kanten
staan hieronder tegenover elkaar.
"""
from __future__ import annotations

import logging

import pytest

from justlog.handlers._common import (
    EXC_MESSAGE_CHARS,
    fingerprint_from_record,
    normalize_exc_message,
)
from tracebacks import (
    MSG_00089,
    MSG_00092,
    MSG_00093,
    TB_00089,
    TB_00092,
    TB_00093,
    exc_info_for,
)


def _record(msg='iets kapot', exc_info=None, logger_name='app'):
    record = logging.LogRecord(logger_name, logging.ERROR, __file__, 1, msg, (), exc_info)
    return record


def _fp(frames, exc, project='electudetranslate'):
    return fingerprint_from_record(_record(exc_info=exc_info_for(frames, exc)), project)


# ---------------------------------------------------------------------------
# A. De genormaliseerde boodschap hoort in de sleutel
# ---------------------------------------------------------------------------

def test_fingerprint_differs_on_exception_message():
    """#00089 en #00092 zijn twee fouten, geen twee meldingen van dezelfde.

    Ze delen exception-klasse en binnenste frame (psycopg2/__init__.py:connect)
    en kregen daardoor dezelfde fingerprint. Janitor concludeerde vervolgens dat
    #00089 een deploy had overleefd, terwijl er iets anders stuk was: de een is
    'too many connections', de ander 'Connection refused'.
    """
    assert _fp(TB_00089, Exception(MSG_00089)) != _fp(TB_00092, Exception(MSG_00092))


@pytest.mark.parametrize('template,a,b', [
    ('connection to server at "{}" failed', 'db-1.internal', 'db-2.internal'),
    ('connection to server at "10.0.0.1" ({}), port 5432 failed', '34.253.23.204', '52.18.7.9'),
    ('FATAL: too many connections for role "{}"', 'uaclmp4r0m67pj', 'x7k2plq9nn41ab'),
    ("could not open file '{}'", '/app/tmp/a.json', '/app/tmp/b.json'),
    ('session {} expired', 'bc2dc518-f088-4f8a-a905-a7069607c4a4',
     'f4b30f04-25d5-4805-916e-7d6018af060a'),
    ('segfault at {}', '0xdeadbeef', '0xcafebabe'),
    ('bounce from {}', 'kea.klaassen@electude.com', 'anna.daalderop@electude.com'),
    ('worker died after {} seconds', '300', '4711'),
    ('incompatibele versie {}', '4.0.6', '4.1.12'),
    ('poort {} bezet', '5432', '61234'),
])
def test_fingerprint_stable_across_variable_data(template, a, b):
    """Variabele data mag geen nieuwe issues openen. Dit is de explosiegrens."""
    assert normalize_exc_message(template.format(a)) == normalize_exc_message(template.format(b))


@pytest.mark.parametrize('a,b', [
    ("'user_id'", "'session_id'"),
    ("'NoneType' object has no attribute 'save'", "'NoneType' object has no attribute 'user'"),
    ('No module named requests', 'No module named urllib3'),
])
def test_normalize_keeps_quoted_identifiers(a, b):
    """De tegenhanger van de vorige test: dit zijn wél verschillende fouten.

    Python zet de onderscheidende inhoud van zijn meestvoorkomende exceptions
    tussen enkele quotes. Een regel die alles tussen enkele quotes wegstreept
    maakt van die hele familie één fingerprint.
    """
    assert normalize_exc_message(a) != normalize_exc_message(b)


def test_normalize_survives_apostrophes():
    """Engelse samentrekkingen mogen niet met de volgende quote paren.

    Zonder lookbehind paart de apostrof van `Can't` met de openingsquote van de
    waarde erna, wist de stabiele tekst en laat juist de variabele waarde staan.
    """
    a = normalize_exc_message("Can't connect to MySQL server on 'db-a.internal' (111)")
    b = normalize_exc_message("Can't connect to MySQL server on 'db-b.internal' (111)")
    assert a == b
    assert a.startswith("can't connect")


def test_normalize_masks_hex_before_digits():
    """`0x...` moet vóór de cijferregel matchen, anders blijft `?xdeadbeef` over."""
    assert normalize_exc_message('segfault at 0xdeadbeef') == 'segfault at ?'


@pytest.mark.parametrize('text', ['psycopg2', 'md5', 'ipv6', 'utf8'])
def test_normalize_keeps_digits_inside_identifiers(text):
    """Zonder woordgrens wordt `md5` `md?` en vallen md5 en md4 samen."""
    assert normalize_exc_message(text) == text


@pytest.mark.parametrize('text', ['', '   ', '\n\t '])
def test_normalize_empty_message(text):
    assert normalize_exc_message(text) == ''


def test_normalize_does_not_break_on_unstringable_exception():
    """Een exception waarvan __str__ gooit mag de melding niet laten verdwijnen.

    `emit` vangt alles in een kale `except Exception` en print naar stderr, dus
    een fout hier kost de hele alertering, niet alleen de boodschap.
    """
    class Unstringable(Exception):
        def __str__(self):
            raise RuntimeError('kan mezelf niet renderen')

    fingerprint = _fp(TB_00092, Unstringable())
    assert len(fingerprint) == 40


# ---------------------------------------------------------------------------
# B. Het diepste eigen frame, niet het binnenste
# ---------------------------------------------------------------------------

def test_frame_skips_library_frames():
    """#00092 ontstaat in de worker, niet in psycopg2."""
    from justlog.handlers._common import _exception_signature

    _exc_class, frame = _exception_signature(_record(exc_info=exc_info_for(TB_00092, Exception('x'))))
    assert frame == 'commands/run_translation_worker.py:_recover_stale_sessions'


def test_frame_falls_back_to_innermost_when_all_library():
    """#00089 heeft nul eigen frames: de traceback raakt nooit code van het project.

    Terugvallen op het binnenste frame is het gedrag van vandaag, dus een misser
    in de heuristiek degradeert netjes in plaats van te breken.
    """
    from justlog.handlers._common import _exception_signature

    _exc_class, frame = _exception_signature(_record(exc_info=exc_info_for(TB_00089, Exception('x'))))
    assert frame == 'psycopg2/__init__.py:connect'


def test_frame_distinguishes_same_basename():
    """Twee bugs, geen een. Elk Django-project heeft meerdere views.py."""
    orders = [('/app/orders/views.py', 'post')]
    billing = [('/app/billing/views.py', 'post')]
    assert _fp(orders, ValueError('zelfde melding')) != _fp(billing, ValueError('zelfde melding'))


def test_frame_handles_empty_traceback():
    """Geen IndexError als de traceback leeg of afwezig is."""
    from justlog.handlers._common import _exception_signature

    assert _exception_signature(_record(exc_info=(ValueError, ValueError('x'), None))) == ('ValueError', '')
    assert _exception_signature(_record(exc_info=None)) == ('', '')


# ---------------------------------------------------------------------------
# Vastgelegde grenzen: gedrag dat we bewust niet oplossen
# ---------------------------------------------------------------------------

def test_fingerprint_ignores_exception_chain():
    """`raise X from Y` fingerprint op de buitenste exception.

    `traceback.extract_tb` loopt niet over `__cause__`, dus twee verschillende
    oorzaken die als dezelfde wrapper naar boven komen worden één issue. Deze
    test legt dat vast zodat een latere refactor het niet ongemerkt verandert.
    """
    def wrapped(cause_message):
        """Een RuntimeError met een echte __cause__, zoals `raise X from Y` geeft."""
        try:
            raise ValueError(cause_message)
        except ValueError as cause:
            wrapper = RuntimeError('wrapper')
            wrapper.__cause__ = cause
            return wrapper

    a = _fp(TB_00092, wrapped('oorzaak a'))
    b = _fp(TB_00092, wrapped('oorzaak b'))
    assert a == b


def test_fingerprint_collides_past_the_cutoff():
    """Twee fouten die pas na EXC_MESSAGE_CHARS uiteenlopen worden één issue.

    Bekende grens, bewust vastgelegd: wie de constante bijstelt maakt de
    afweging opnieuw.
    """
    prefix = 'x' * EXC_MESSAGE_CHARS
    assert _fp(TB_00092, Exception(prefix + 'aaa')) == _fp(TB_00092, Exception(prefix + 'bbb'))


def test_fingerprint_of_the_three_real_issues_is_distinct():
    """De drie gemelde fouten zijn drie issues, ook na B.

    00092 en 00093 komen na B uit hetzelfde frame; alleen A houdt ze uit elkaar.
    Daarom mag B niet zonder A landen.
    """
    fingerprints = {
        _fp(TB_00089, Exception(MSG_00089)),
        _fp(TB_00092, Exception(MSG_00092)),
        _fp(TB_00093, Exception(MSG_00093)),
    }
    assert len(fingerprints) == 3
