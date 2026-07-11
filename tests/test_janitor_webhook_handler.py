"""Tests for justlog.handlers.janitor_webhook.JanitorWebhookHandler.

The handler posts JSON to an emailme endpoint. These tests cover the
contract Janitor's ingress parser depends on (X-Janitor-* headers as
payload fields, deterministic fingerprints), plus level filtering,
per-fingerprint rate-limiting, shared-secret auth via X-Emailme-Token,
and transport-failure swallowing.
"""
from __future__ import annotations

import json
import logging
import sys
import urllib.error
import urllib.request

import pytest

from justlog.handlers.janitor_webhook import JanitorWebhookHandler


class FakeOpener:
    """Stand-in for urllib.request.urlopen. Records each Request."""

    def __init__(self):
        self.requests: list[urllib.request.Request] = []

    def __call__(self, req: urllib.request.Request, timeout: float | None = None):
        self.requests.append(req)
        return None


class FakeFailingOpener:
    def __call__(self, req: urllib.request.Request, timeout: float | None = None):
        raise urllib.error.URLError('connection refused')


@pytest.fixture
def opener():
    return FakeOpener()


@pytest.fixture
def clock():
    state = {'t': 1000.0}

    def now() -> float:
        return state['t']

    def advance(seconds: float) -> None:
        state['t'] += seconds

    now.advance = advance
    return now


def _make_handler(opener, clock_fn, **overrides):
    kwargs = dict(
        project='website',
        token='shh',
        url='https://harmsen.nl/emailme/',
        opener=opener,
        clock=clock_fn,
    )
    kwargs.update(overrides)
    return JanitorWebhookHandler(**kwargs)


def _record_with_exception(logger_name: str = 'app') -> logging.LogRecord:
    try:
        1 / 0
    except ZeroDivisionError:
        exc_info = sys.exc_info()
    return logging.LogRecord(
        name=logger_name,
        level=logging.ERROR,
        pathname=__file__,
        lineno=42,
        msg='boom',
        args=(),
        exc_info=exc_info,
    )


def _payload_of(req: urllib.request.Request) -> dict:
    return json.loads(req.data.decode('utf-8'))


# ---------------------------------------------------------------------------
# Payload contract
# ---------------------------------------------------------------------------


def test_emit_posts_janitor_headers_in_payload(opener, clock):
    handler = _make_handler(opener, clock)
    handler.emit(_record_with_exception())

    assert len(opener.requests) == 1
    payload = _payload_of(opener.requests[0])
    headers = payload['headers']
    assert headers['X-Janitor-Source'] == 'justlog'
    assert headers['X-Janitor-Project'] == 'website'
    assert headers['X-Janitor-Level'] == 'ERROR'
    assert headers['X-Janitor-Logger'] == 'app'
    assert headers['X-Janitor-Fingerprint']  # non-empty


def test_emit_routes_to_project_recipient(opener, clock):
    handler = _make_handler(opener, clock)
    handler.emit(_record_with_exception())

    payload = _payload_of(opener.requests[0])
    assert payload['recipient'] == 'errors+website@harmsen.nl'
    assert payload['sender_email'] == 'website@harmsen.nl'
    assert payload['subject'].startswith('[ERROR] website:')


def test_emit_recipient_and_from_overridable(opener, clock):
    handler = _make_handler(
        opener, clock,
        recipient='errors+custom@example.com',
        from_addr='noreply@example.com',
    )
    handler.emit(_record_with_exception())

    payload = _payload_of(opener.requests[0])
    assert payload['recipient'] == 'errors+custom@example.com'
    assert payload['sender_email'] == 'noreply@example.com'


def test_emit_body_includes_traceback(opener, clock):
    handler = _make_handler(opener, clock)
    handler.emit(_record_with_exception())

    body = _payload_of(opener.requests[0])['body']
    assert 'ZeroDivisionError' in body
    assert 'boom' in body
    assert 'Traceback' in body


def test_emit_sends_json_and_shared_secret(opener, clock):
    handler = _make_handler(opener, clock, token='secret-abc')
    handler.emit(_record_with_exception())

    req = opener.requests[0]
    assert req.full_url == 'https://harmsen.nl/emailme/'
    assert req.get_method() == 'POST'
    # urllib lowercases header names in .headers dict.
    assert req.headers.get('Content-type') == 'application/json'
    assert req.headers.get('X-emailme-token') == 'secret-abc'


def test_token_falls_back_to_env(monkeypatch, opener, clock):
    monkeypatch.setenv('EMAILME_TOKEN', 'env-token')
    handler = JanitorWebhookHandler(
        project='website',
        opener=opener,
        clock=clock,
    )
    handler.emit(_record_with_exception())

    req = opener.requests[0]
    assert req.headers.get('X-emailme-token') == 'env-token'


# ---------------------------------------------------------------------------
# Fingerprint determinism (parity with the email handler)
# ---------------------------------------------------------------------------


def test_fingerprint_matches_email_handler(opener, clock):
    """Both handlers must produce identical fingerprints for the same record."""
    from justlog.handlers._common import fingerprint_from_record

    record = _record_with_exception(logger_name='app')
    handler = _make_handler(opener, clock)
    handler.emit(record)

    posted_fp = _payload_of(opener.requests[0])['headers']['X-Janitor-Fingerprint']
    expected = fingerprint_from_record(record, project='website')
    assert posted_fp == expected


def test_fingerprint_changes_with_exception_class(opener, clock):
    handler = _make_handler(opener, clock)

    try:
        raise ValueError('v')
    except ValueError:
        rec_value = logging.LogRecord(
            name='app', level=logging.ERROR, pathname=__file__, lineno=1,
            msg='m', args=(), exc_info=sys.exc_info(),
        )
    handler.emit(rec_value)

    try:
        raise KeyError('k')
    except KeyError:
        rec_key = logging.LogRecord(
            name='app', level=logging.ERROR, pathname=__file__, lineno=2,
            msg='m', args=(), exc_info=sys.exc_info(),
        )
    handler.emit(rec_key)

    assert len(opener.requests) == 2
    fp1 = _payload_of(opener.requests[0])['headers']['X-Janitor-Fingerprint']
    fp2 = _payload_of(opener.requests[1])['headers']['X-Janitor-Fingerprint']
    assert fp1 != fp2


# ---------------------------------------------------------------------------
# Level filter
# ---------------------------------------------------------------------------


def test_info_record_is_dropped(opener, clock):
    handler = _make_handler(opener, clock)
    info_record = logging.LogRecord(
        name='app', level=logging.INFO, pathname=__file__, lineno=1,
        msg='hello', args=(), exc_info=None,
    )
    handler.emit(info_record)
    assert opener.requests == []


def test_custom_level_threshold_can_lower_to_warning(opener, clock):
    handler = _make_handler(opener, clock, level=logging.WARNING)
    warn_record = logging.LogRecord(
        name='app', level=logging.WARNING, pathname=__file__, lineno=1,
        msg='hello', args=(), exc_info=None,
    )
    handler.emit(warn_record)
    assert len(opener.requests) == 1


def test_record_without_exception_still_emits(opener, clock):
    handler = _make_handler(opener, clock)
    rec = logging.LogRecord(
        name='app', level=logging.ERROR, pathname=__file__, lineno=1,
        msg='plain error', args=(), exc_info=None,
    )
    handler.emit(rec)
    assert len(opener.requests) == 1
    assert 'plain error' in _payload_of(opener.requests[0])['body']


# ---------------------------------------------------------------------------
# Rate-limit
# ---------------------------------------------------------------------------


def test_rate_limit_suppresses_repeats_within_window(opener, clock):
    handler = _make_handler(opener, clock, rate_limit_window=60.0)

    for _ in range(100):
        handler.emit(_record_with_exception())
        clock.advance(0.1)

    assert len(opener.requests) == 1


def test_rate_limit_allows_after_window_passes(opener, clock):
    handler = _make_handler(opener, clock, rate_limit_window=60.0)

    handler.emit(_record_with_exception())
    clock.advance(61.0)
    handler.emit(_record_with_exception())

    assert len(opener.requests) == 2


def test_rate_limit_is_per_fingerprint(opener, clock):
    handler = _make_handler(opener, clock, rate_limit_window=60.0)

    rec_a = _record_with_exception(logger_name='auth')
    rec_b = _record_with_exception(logger_name='billing')
    handler.emit(rec_a)
    handler.emit(rec_b)

    assert len(opener.requests) == 2


# ---------------------------------------------------------------------------
# Transport failure must not crash the host process
# ---------------------------------------------------------------------------


def test_transport_failure_swallowed_and_logged_to_stderr(clock, capsys):
    handler = _make_handler(FakeFailingOpener(), clock)
    handler.emit(_record_with_exception())  # must not raise

    captured = capsys.readouterr()
    assert 'JanitorWebhookHandler' in captured.err
    assert 'connection refused' in captured.err
