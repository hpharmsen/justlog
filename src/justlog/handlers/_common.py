"""Shared helpers for Janitor-bound log handlers.

Fingerprint and body formatting must match janitor.dedup.fingerprint_for_justlog
and Janitor's ingress parser byte-for-byte, so email and webhook variants
share this module.
"""
from __future__ import annotations

import hashlib
import logging
import traceback


SUBJECT_PREVIEW_CHARS = 80


def fingerprint_key(exc_class: str, top_frame: str, message: str) -> tuple[str, str]:
    """De twee sleutelvelden van de fingerprint, met de logregel als terugval.

    Zonder exception zijn exc_class en top_frame allebei leeg, waardoor álle
    exception-loze errors van een project dezelfde fingerprint krijgen. Dat is
    niet alleen samenvoegen tot één issue: de rate limit in de handlers werkt
    per fingerprint, dus een tweede soort fout binnen het window wordt helemaal
    niet verstuurd. Daarom valt de sleutel dan terug op de logregel, net zoals
    build_subject dat al doet.

    De 'msg:'-prefix voorkomt dat een logregel die toevallig 'ValueError' heet
    botst met een echte ValueError zonder traceback.

    Deze regel moet gelijk blijven aan janitor.dedup.fingerprint_for_justlog.
    """
    if exc_class:
        return exc_class, top_frame
    return f'msg:{message}', ''


def fingerprint_from_record(record: logging.LogRecord, project: str) -> str:
    """SHA-1 over (project, logger, exception class, normalized top frame)."""
    logger = record.name or ''
    exc_class, top_frame = _exception_signature(record)
    key, frame = fingerprint_key(exc_class, top_frame, record.getMessage())
    payload = '\x00'.join([project, logger, key, frame]).encode('utf-8')
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
    if not record.exc_info or record.exc_info[0] is None:
        return '', ''
    exc_type, _exc, tb = record.exc_info
    exc_class = exc_type.__name__
    if tb is None:
        return exc_class, ''
    frames = traceback.extract_tb(tb)
    if not frames:
        return exc_class, ''
    innermost = frames[-1]
    basename = innermost.filename.rsplit('/', 1)[-1]
    return exc_class, f'{basename}:{innermost.name}'
