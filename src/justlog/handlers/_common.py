"""Shared helpers for Janitor-bound log handlers.

Deze module is de enige plek waar de fingerprint wordt uitgerekend. Janitor
rekent hem niet na maar leest de X-Janitor-Fingerprint-header; er is dus geen
tweede implementatie meer die uit de pas kan lopen.
"""
from __future__ import annotations

import hashlib
import logging
import re
import traceback


SUBJECT_PREVIEW_CHARS = 80
MESSAGE_TEMPLATE_CHARS = 200
EXC_MESSAGE_CHARS = 200

_VARIABLE = re.compile(
    r'"[^"\n]*"'                                                  # hostnamen, rolnamen
    r"|(?<![A-Za-z])'[^'\n]*[./@\\\d][^'\n]*'"                    # paden, hosts, id's
    r'|\b[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\b'  # uuid
    r'|[\w.+-]+@[\w-]+\.[A-Za-z]{2,}'                             # e-mailadres
    r'|0x[0-9a-fA-F]+'                                            # hex
    r'|(?<![\w.])\d+(?:\.\d+)*'                                   # getallen, IP, poort, versie
)

_LIBRARY = re.compile(r'(?:^|/)(?:site|dist)-packages/|/lib/python\d')


class RateLimiter:
    """Per-fingerprint venster, met een begrensde administratie.

    De sleutelruimte was begrensd door (exception-klasse x frame) en dus klein.
    Met de boodschap erbij is hij zo groot als het aantal verschillende
    genormaliseerde boodschappen, en de dict verwijderde nooit iets. Bij
    onvoldoende normalisatie is dat twee problemen tegelijk: het geheugen loopt
    op én het venster onderdrukt niets meer, dus er gaat een bericht per fout
    de deur uit.

    Beide handlers gebruiken deze klasse, zodat er één venster-implementatie is.
    """

    MAX_ENTRIES = 512

    def __init__(self, window: float, clock):
        self.window = window
        self._clock = clock
        self._last_sent: dict[str, float] = {}

    def is_limited(self, fingerprint: str) -> bool:
        last = self._last_sent.get(fingerprint)
        return last is not None and (self._clock() - last) < self.window

    def record(self, fingerprint: str) -> None:
        if len(self._last_sent) >= self.MAX_ENTRIES:
            self._evict()
        self._last_sent[fingerprint] = self._clock()

    def _evict(self) -> None:
        """Gooi verlopen entries weg; helpt dat niet, dan de oudste helft.

        Entries ouder dan het venster doen niets meer, dus die weggooien is
        gratis. Zijn ze allemaal vers, dan is er een stroom van steeds nieuwe
        fingerprints — precies het explosiegeval — en is de meest recente helft
        bewaren beter dan alles weggooien.
        """
        cutoff = self._clock() - self.window
        self._last_sent = {f: t for f, t in self._last_sent.items() if t > cutoff}
        if len(self._last_sent) >= self.MAX_ENTRIES:
            newest = sorted(self._last_sent.items(), key=lambda item: item[1])
            self._last_sent = dict(newest[len(newest) // 2:])


def normalize_exc_message(text: str) -> str:
    """Strip variabele data, zodat één fout één fingerprint blijft.

    Zonder normalisatie opent elke sessie-id, host en poort een eigen issue.
    Overnormaliseren is even schadelijk en gevaarlijker, omdat het stil is:
    Python zet de onderscheidende inhoud van zijn meestvoorkomende exceptions
    tussen enkele quotes (`KeyError: 'user_id'`), dus die worden alleen
    gemaskeerd als er iets variabels in staat.

    De lookbehind voor de enkele quote houdt Engelse samentrekkingen heel:
    zonder die grens paart de apostrof van `Can't` met de openingsquote van de
    volgende waarde en blijft juist de variabele waarde staan. `0x...` staat
    vóór de cijferregel, anders eet `\\d+` de nul van `0xdeadbeef`.
    """
    return ' '.join(_VARIABLE.sub('?', text).split()).lower()[:EXC_MESSAGE_CHARS]


def _is_library_frame(filename: str) -> bool:
    """Of dit frame in een library of de stdlib zit in plaats van in eigen code.

    Het cijfer achter `/lib/python` is een anker: zonder dat valt eigen code in
    `/app/lib/python_helpers/` er ook onder en verdwijnt het echte frame.
    """
    path = filename.replace('\\', '/')
    return path.startswith('<') or bool(_LIBRARY.search(path))


def message_template(record: logging.LogRecord) -> str:
    """De logregel zoals hij in de code staat, met de placeholders nog erin.

    Whitespace wordt platgeslagen en de lengte begrensd, zodat de waarde veilig als
    e-mailheader mee kan. Beide kanten moeten exact deze waarde gebruiken, anders
    rekent janitor een andere fingerprint uit dan de handler meestuurt.
    """
    return ' '.join(str(record.msg).split())[:MESSAGE_TEMPLATE_CHARS]


def fingerprint_key(exc_class: str, top_frame: str, message: str) -> tuple[str, str]:
    """De twee sleutelvelden van de fingerprint, met het logtemplate als terugval.

    Zonder exception zijn exc_class en top_frame allebei leeg, waardoor álle
    exception-loze errors van een project dezelfde fingerprint krijgen. Dat is
    niet alleen samenvoegen tot één issue: de rate limit in de handlers werkt
    per fingerprint, dus een tweede soort fout binnen het window wordt helemaal
    niet verstuurd. Daarom valt de sleutel dan terug op de logregel, net zoals
    build_subject dat al doet.

    De 'msg:'-prefix voorkomt dat een logregel die toevallig 'ValueError' heet
    botst met een echte ValueError zonder traceback.

    `message` is het template, niet de ingevulde regel: dezelfde foutsoort met een
    andere waarde erin is één issue. Zou de ingevulde regel de sleutel zijn, dan
    opent één vastgelopen spool tientallen issues zonder rate limiting.

    Deze regel moet gelijk blijven aan janitor.dedup.fingerprint_for_justlog.
    """
    if exc_class:
        return exc_class, top_frame
    return f'msg:{message}', ''


def _exc_message(record: logging.LogRecord) -> str:
    """De genormaliseerde exception-boodschap, of leeg als die er niet is.

    `str(exc)` wordt afgeschermd: een exception met een `__str__` die zelf gooit
    (lazy vertaalobjecten, ORM-objecten op een gesloten verbinding) mag de
    alertering niet stilzetten. `emit` vangt alles in een kale `except Exception`
    en print naar stderr, dus de melding zou geruisloos verdwijnen.
    """
    if not record.exc_info or record.exc_info[0] is None:
        return ''
    try:
        return normalize_exc_message(str(record.exc_info[1]))
    except Exception:
        return ''


def fingerprint_from_record(record: logging.LogRecord, project: str) -> str:
    """SHA-1 over (project, logger, exception class, eigen frame, boodschap).

    De boodschap is een apart vijfde veld, niet door de andere heen. Zonder dat
    veld delen twee verschillende fouten uit hetzelfde frame één fingerprint, en
    concludeert janitor dat een fix niet gewerkt heeft terwijl er iets anders
    stuk is.
    """
    logger = record.name or ''
    exc_class, top_frame = _exception_signature(record)
    key, frame = fingerprint_key(exc_class, top_frame, message_template(record))
    payload = '\x00'.join([project, logger, key, frame, _exc_message(record)]).encode('utf-8')
    return hashlib.sha1(payload).hexdigest()


def build_subject(record: logging.LogRecord, project: str) -> str:
    """Subject that Gmail can thread meaningfully.

    With an exception: `[LEVEL] project: ExcClass in file:func` — stable across
    retries of the same bug, distinct across bugs.
    Without: `[LEVEL] project: message[:80]` — falls back to the log message.
    """
    prefix = f'[{record.levelname}] {project}'
    exc_class, top_frame = _exception_signature(record)
    if exc_class:
        tail = f'{exc_class} in {top_frame}' if top_frame else exc_class
        return f'{prefix}: {tail}'
    return f'{prefix}: {record.getMessage()[:SUBJECT_PREVIEW_CHARS]}'


def format_body(record: logging.LogRecord) -> str:
    parts: list[str] = [record.getMessage()]
    parts.extend(str(arg) for arg in getattr(record, '_extra_args', None) or ())
    parts.extend(f'{key}: {value}' for key, value in (getattr(record, '_extra_kwargs', None) or {}).items())
    if record.exc_info and record.exc_info[0] is not None:
        parts.append('')
        parts.append('Traceback:')
        parts.append(''.join(traceback.format_exception(*record.exc_info)))
    return '\n'.join(parts)


def _exception_signature(record: logging.LogRecord) -> tuple[str, str]:
    """Exception-klasse plus het diepste frame in eigen code.

    Het binnenste frame identificeert bij een fout die in een library ontstaat
    welke library-functie gooide, niet waar onze code fout ging: #00092 en
    #00093 komen uit hetzelfde punt in de worker maar kregen
    `psycopg2/__init__.py:connect` tegen `django/db/backends/utils.py:_execute`.

    Zijn álle frames library, dan valt hij terug op het binnenste. Dat is het
    gedrag van vandaag, dus een misser in de heuristiek degradeert netjes; van
    de drie gemelde tracebacks heeft #00089 nul eigen frames.
    """
    if not record.exc_info or record.exc_info[0] is None:
        return '', ''
    exc_type, _exc, tb = record.exc_info
    exc_class = exc_type.__name__
    if tb is None:
        return exc_class, ''
    frames = traceback.extract_tb(tb)
    if not frames:
        return exc_class, ''
    own = [f for f in frames if not _is_library_frame(f.filename)]
    frame = (own or frames)[-1]
    return exc_class, f'{_frame_label(frame.filename)}:{frame.name}'


def _frame_label(filename: str) -> str:
    """De laatste twee padsegmenten, zodat gelijke bestandsnamen niet botsen.

    Alleen de basename levert botsingen op zodra het label naar eigen code
    wijst: elk Django-project heeft `views.py`, `models.py` en `tasks.py`.
    `orders/views.py:post` en `billing/views.py:post` zijn twee bugs.
    """
    return '/'.join(filename.replace('\\', '/').rsplit('/', 2)[-2:])
