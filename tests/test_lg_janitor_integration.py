"""End-to-end tests voor lg.error(...) -> JanitorWebhookHandler.

De handlers leiden fingerprint, subject en traceback af uit record.exc_info.
lg._log() moet die dus op de record zetten in plaats van de traceback als
string tussen de extra kwargs te stoppen. Gebeurt dat niet, dan krijgt elke
error van een project dezelfde fingerprint en dedupliceert Janitor alles weg.
"""
from __future__ import annotations

import json
import logging
import urllib.request

import pytest

from justlog import lg, setup_logging
from justlog.handlers import JanitorWebhookHandler


class FakeOpener:
    def __init__(self):
        self.payloads: list[dict] = []

    def __call__(self, req: urllib.request.Request, timeout: float | None = None):
        self.payloads.append(json.loads(req.data.decode('utf-8')))
        return None


@pytest.fixture
def janitor(tmp_path):
    """lg met een JanitorWebhookHandler die niets naar buiten stuurt."""
    opener = FakeOpener()
    setup_logging(log_file_path=tmp_path / 'app.log')
    handler = JanitorWebhookHandler(project='website', token='shh', opener=opener)
    lg.addHandler(handler)
    yield opener
    lg.removeHandler(handler)


def _raise_value_error():
    raise ValueError('kapot')


def test_exc_info_true_reaches_the_record(janitor):
    try:
        _raise_value_error()
    except ValueError:
        lg.error('reply generation failed', exc_info=True)

    payload = janitor.payloads[0]
    assert payload['subject'] == '[ERROR] website: ValueError in test_lg_janitor_integration.py:_raise_value_error'
    assert 'Traceback:' in payload['body']
    assert 'ValueError: kapot' in payload['body']


def test_exception_instance_is_accepted(janitor):
    try:
        _raise_value_error()
    except ValueError as exc:
        lg.error('reply generation failed', exc_info=exc)

    assert 'ValueError: kapot' in janitor.payloads[0]['body']


def test_distinct_exceptions_get_distinct_fingerprints(janitor):
    """Zonder echte exc_info kregen alle errors dezelfde fingerprint."""
    try:
        _raise_value_error()
    except ValueError:
        lg.error('reply generation failed', exc_info=True)
    try:
        1 / 0
    except ZeroDivisionError:
        lg.error('draft sync failed', exc_info=True)

    assert len(janitor.payloads) == 2
    fingerprints = {p['headers']['X-Janitor-Fingerprint'] for p in janitor.payloads}
    assert len(fingerprints) == 2


def test_extra_kwargs_end_up_in_the_body(janitor):
    lg.error('draft sync failed', draft_id=999, provider='gmail')

    body = janitor.payloads[0]['body']
    assert 'draft_id: 999' in body
    assert 'provider: gmail' in body


def test_extra_args_end_up_in_the_body(janitor):
    lg.error('draft sync failed', 'context-regel')

    assert 'context-regel' in janitor.payloads[0]['body']


def test_exc_info_true_outside_except_block_is_ignored(janitor):
    """Geen levende exception: geen 'NoneType: None' in de body."""
    lg.error('geen exception hier', exc_info=True)

    body = janitor.payloads[0]['body']
    assert 'Traceback:' not in body
    assert 'NoneType' not in body


def test_error_without_exception_still_ships(janitor):
    lg.error('config ontbreekt')

    payload = janitor.payloads[0]
    assert payload['subject'] == '[ERROR] website: config ontbreekt'
    assert payload['headers']['X-Janitor-Level'] == 'ERROR'


def test_warning_does_not_reach_janitor(janitor):
    lg.warning('tijdelijke fout, wordt opnieuw geprobeerd')

    assert janitor.payloads == []


def test_traceback_is_not_duplicated_in_the_kwargs(janitor):
    """exc_info hoort op de record, niet ook nog eens als losse kwarg-regel."""
    try:
        _raise_value_error()
    except ValueError:
        lg.error('reply generation failed', exc_info=True)

    body = janitor.payloads[0]['body']
    assert body.count('Traceback (most recent call last)') == 1
    assert 'exc_info:' not in body


def test_file_log_still_contains_the_traceback(tmp_path):
    log_file = tmp_path / 'app.log'
    setup_logging(log_file_path=log_file, level=logging.DEBUG)

    try:
        _raise_value_error()
    except ValueError:
        lg.error('reply generation failed', email_uid='123', exc_info=True)

    contents = log_file.read_text()
    assert 'ValueError: kapot' in contents
    assert 'email_uid: 123' in contents
