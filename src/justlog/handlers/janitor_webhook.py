"""HTTP webhook handler that ships log records to Janitor via emailme.

Posts JSON to an emailme endpoint that turns the payload into a Gmail
message addressed to `errors+<project>@harmsen.nl` with the X-Janitor-*
headers Janitor's ingress parser expects. No SMTP credentials on the
client; auth is a shared secret in the X-Emailme-Token header.

Deduplicates bursts by fingerprint (60s sliding window per default) and
swallows transport failures so a network hiccup never crashes the host.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import urllib.request
from typing import Callable, Optional

from ._common import build_subject, fingerprint_from_record, format_body, message_template


DEFAULT_URL = 'https://www.harmsen.nl/emailme/'


class JanitorWebhookHandler(logging.Handler):
    def __init__(
        self,
        project: str,
        token: Optional[str] = None,
        url: str = DEFAULT_URL,
        recipient: Optional[str] = None,
        from_addr: Optional[str] = None,
        level: int = logging.ERROR,
        rate_limit_window: float = 60.0,
        request_timeout: float = 10.0,
        opener: Optional[Callable[..., object]] = None,
        clock: Optional[Callable[[], float]] = None,
    ):
        super().__init__(level=level)
        self.project = project
        self.token = token if token is not None else os.environ.get('EMAILME_TOKEN', '')
        self.url = url
        self.recipient = recipient or f'errors+{project}@harmsen.nl'
        self.from_addr = from_addr or f'{project}@harmsen.nl'
        self.rate_limit_window = rate_limit_window
        self.request_timeout = request_timeout
        self._opener = opener or urllib.request.urlopen
        self._clock = clock or time.monotonic
        self._last_sent: dict[str, float] = {}

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.levelno < self.level:
                return
            fingerprint = fingerprint_from_record(record, self.project)
            if self._is_rate_limited(fingerprint):
                return
            payload = self._build_payload(record, fingerprint)
            self._post(payload)
            self._last_sent[fingerprint] = self._clock()
        except Exception as exc:  # transport or build failure — never crash the host
            print(f'JanitorWebhookHandler: {exc}', file=sys.stderr)

    def _is_rate_limited(self, fingerprint: str) -> bool:
        last = self._last_sent.get(fingerprint)
        if last is None:
            return False
        return (self._clock() - last) < self.rate_limit_window

    def _build_payload(self, record: logging.LogRecord, fingerprint: str) -> dict:
        return {
            'subject': build_subject(record, self.project),
            'body': format_body(record),
            'sender_email': self.from_addr,
            'recipient': self.recipient,
            'headers': {
                'X-Janitor-Source': 'justlog',
                'X-Janitor-Project': self.project,
                'X-Janitor-Level': record.levelname,
                'X-Janitor-Logger': record.name,
                'X-Janitor-Fingerprint': fingerprint,
                'X-Janitor-Message-Template': message_template(record),
            },
        }

    def _post(self, payload: dict) -> None:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            self.url,
            data=data,
            headers={
                'Content-Type': 'application/json',
                'X-Emailme-Token': self.token,
                'User-Agent': 'justlog-webhook/1.0',
            },
            method='POST',
        )
        self._opener(req, timeout=self.request_timeout)
