"""SMTP handler that ships log records to Janitor.

Builds an email with the X-Janitor-* headers Janitor's ingress parser
expects, deduplicates bursts by fingerprint with an in-process sliding
window, and never lets SMTP failures bubble up into the host process.
"""
from __future__ import annotations

import hashlib
import logging
import smtplib
import sys
import time
import traceback
from email.message import EmailMessage
from typing import Callable, Optional


_SUBJECT_PREVIEW_CHARS = 80


class JanitorEmailHandler(logging.Handler):
    def __init__(
        self,
        project: str,
        to_addr: str,
        from_addr: str,
        smtp_host: str,
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        use_tls: bool = True,
        level: int = logging.ERROR,
        rate_limit_window: float = 60.0,
        smtp_timeout: float = 10.0,
        smtp_factory: Optional[Callable[..., object]] = None,
        clock: Optional[Callable[[], float]] = None,
    ):
        super().__init__(level=level)
        self.project = project
        self.to_addr = to_addr
        self.from_addr = from_addr
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.use_tls = use_tls
        self.rate_limit_window = rate_limit_window
        self.smtp_timeout = smtp_timeout
        self._smtp_factory = smtp_factory or smtplib.SMTP
        self._clock = clock or time.monotonic
        self._last_sent: dict[str, float] = {}

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.levelno < self.level:
                return
            fingerprint = _fingerprint_from_record(record, self.project)
            if self._is_rate_limited(fingerprint):
                return
            msg = self._build_message(record, fingerprint)
            self._send(msg)
            self._last_sent[fingerprint] = self._clock()
        except Exception as exc:  # SMTP or build failure — never crash the host
            print(f'JanitorEmailHandler: {exc}', file=sys.stderr)

    def _is_rate_limited(self, fingerprint: str) -> bool:
        last = self._last_sent.get(fingerprint)
        if last is None:
            return False
        return (self._clock() - last) < self.rate_limit_window

    def _build_message(self, record: logging.LogRecord, fingerprint: str) -> EmailMessage:
        msg = EmailMessage()
        msg['From'] = self.from_addr
        msg['To'] = self.to_addr
        msg['Subject'] = f'[{record.levelname}] {self.project}: {record.getMessage()[:_SUBJECT_PREVIEW_CHARS]}'
        msg['X-Janitor-Source'] = 'justlog'
        msg['X-Janitor-Project'] = self.project
        msg['X-Janitor-Level'] = record.levelname
        msg['X-Janitor-Logger'] = record.name
        msg['X-Janitor-Fingerprint'] = fingerprint
        msg.set_content(_build_body(record))
        return msg

    def _send(self, msg: EmailMessage) -> None:
        smtp = self._smtp_factory(self.smtp_host, self.smtp_port, timeout=self.smtp_timeout)
        try:
            if self.use_tls:
                smtp.starttls()
            if self.smtp_user and self.smtp_password:
                smtp.login(self.smtp_user, self.smtp_password)
            smtp.sendmail(self.from_addr, [self.to_addr], msg.as_string())
        finally:
            smtp.quit()


# --- helpers ----------------------------------------------------------------


def _build_body(record: logging.LogRecord) -> str:
    parts: list[str] = [record.getMessage()]
    if record.exc_info and record.exc_info[0] is not None:
        parts.append('')
        parts.append('Traceback:')
        parts.append(''.join(traceback.format_exception(*record.exc_info)))
    return '\n'.join(parts)


def _fingerprint_from_record(record: logging.LogRecord, project: str) -> str:
    """SHA-1 over (project, logger, exception class, normalized top frame).

    Mirrors janitor.dedup.fingerprint_for_justlog so a JustLog client and
    the Janitor ingress always agree on what counts as "the same error".
    """
    logger = record.name or ''
    exc_class, top_frame = _exception_signature(record)
    payload = '\x00'.join([project, logger, exc_class, top_frame]).encode('utf-8')
    return hashlib.sha1(payload).hexdigest()


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
