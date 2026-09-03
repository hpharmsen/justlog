"""SMTP handler that ships log records to Janitor.

Builds an email with the X-Janitor-* headers Janitor's ingress parser
expects, deduplicates bursts by fingerprint with an in-process sliding
window, and never lets SMTP failures bubble up into the host process.
"""
from __future__ import annotations

import logging
import smtplib
import sys
import time
from email.message import EmailMessage
from typing import Callable, Optional

from ._common import (
    SUBJECT_PREVIEW_CHARS,
    RateLimiter,
    build_subject,
    fingerprint_from_record,
    format_body,
    message_template,
)

# Backward-compat re-exports (tests reach for the underscore names).
_SUBJECT_PREVIEW_CHARS = SUBJECT_PREVIEW_CHARS
_fingerprint_from_record = fingerprint_from_record
_build_body = format_body


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
        self._rate_limiter = RateLimiter(rate_limit_window, self._clock)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.levelno < self.level:
                return
            fingerprint = fingerprint_from_record(record, self.project)
            if self._rate_limiter.is_limited(fingerprint):
                return
            msg = self._build_message(record, fingerprint)
            self._send(msg)
            self._rate_limiter.record(fingerprint)
        except Exception as exc:  # SMTP or build failure — never crash the host
            print(f'JanitorEmailHandler: {exc}', file=sys.stderr)


    def _build_message(self, record: logging.LogRecord, fingerprint: str) -> EmailMessage:
        msg = EmailMessage()
        msg['From'] = self.from_addr
        msg['To'] = self.to_addr
        msg['Subject'] = build_subject(record, self.project)
        msg['X-Janitor-Source'] = 'justlog'
        msg['X-Janitor-Project'] = self.project
        msg['X-Janitor-Level'] = record.levelname
        msg['X-Janitor-Logger'] = record.name
        msg['X-Janitor-Fingerprint'] = fingerprint
        msg['X-Janitor-Message-Template'] = message_template(record)
        msg.set_content(format_body(record))
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
