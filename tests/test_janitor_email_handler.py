"""Tests for justlog.handlers.janitor_email.JanitorEmailHandler.

The handler ships log records to Janitor by SMTP. These tests cover the
contract Janitor's ingress parser depends on: X-Janitor-* headers,
deterministic fingerprints across dev/prod paths, level filtering,
per-fingerprint rate-limiting, and SMTP-failure swallowing.
"""
from __future__ import annotations

import hashlib
import logging
import sys
from email import message_from_string

import pytest

from justlog.handlers.janitor_email import JanitorEmailHandler


class FakeSMTP:
    """Stand-in for smtplib.SMTP used by the handler. Records sent mails."""

    def __init__(self, host: str, port: int, timeout: float | None = None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.logged_in: tuple[str, str] | None = None
        self.sent: list[tuple[str, list[str], str]] = []
        self.quit_called = False

    def starttls(self):
        self.started_tls = True

    def login(self, user: str, password: str):
        self.logged_in = (user, password)

    def sendmail(self, from_addr: str, to_addrs: list[str], msg: str):
        self.sent.append((from_addr, to_addrs, msg))

    def quit(self):
        self.quit_called = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.quit()


class FakeSMTPFailure(FakeSMTP):
    def sendmail(self, *args, **kwargs):
        raise OSError('connection refused')


@pytest.fixture
def smtp_log():
    """Capture each FakeSMTP instance the handler creates."""
    instances: list[FakeSMTP] = []

    def factory(host: str, port: int, timeout: float | None = None):
        s = FakeSMTP(host, port, timeout)
        instances.append(s)
        return s

    return instances, factory


@pytest.fixture
def clock():
    """Monotonic-clock stub the handler reads for rate-limiting."""
    state = {'t': 1000.0}

    def now() -> float:
        return state['t']

    def advance(seconds: float) -> None:
        state['t'] += seconds

    now.advance = advance
    return now


def _make_handler(smtp_factory, clock_fn, **overrides):
    kwargs = dict(
        project='website',
        to_addr='errors+website@harmsen.nl',
        from_addr='website@harmsen.nl',
        smtp_host='smtp.example.com',
        smtp_port=587,
        smtp_user='user',
        smtp_password='secret',
        smtp_factory=smtp_factory,
        clock=clock_fn,
    )
    kwargs.update(overrides)
    return JanitorEmailHandler(**kwargs)


def _record_with_exception(logger_name: str = 'app') -> logging.LogRecord:
    """Build a LogRecord carrying a ZeroDivisionError, captured here."""
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


def _parse_sent(sent_entry):
    _from, _to, raw = sent_entry
    return message_from_string(raw)


# ---------------------------------------------------------------------------
# Header contract
# ---------------------------------------------------------------------------


def test_emit_sets_janitor_headers(smtp_log, clock):
    instances, factory = smtp_log
    handler = _make_handler(factory, clock)
    handler.emit(_record_with_exception())

    assert len(instances) == 1
    msg = _parse_sent(instances[0].sent[0])
    assert msg['X-Janitor-Source'] == 'justlog'
    assert msg['X-Janitor-Project'] == 'website'
    assert msg['X-Janitor-Level'] == 'ERROR'
    assert msg['X-Janitor-Logger'] == 'app'
    assert msg['X-Janitor-Fingerprint']  # non-empty


def test_emit_addresses_and_subject(smtp_log, clock):
    instances, factory = smtp_log
    handler = _make_handler(factory, clock)
    handler.emit(_record_with_exception())

    from_addr, to_addrs, raw = instances[0].sent[0]
    assert from_addr == 'website@harmsen.nl'
    assert to_addrs == ['errors+website@harmsen.nl']
    msg = message_from_string(raw)
    assert msg['From'] == 'website@harmsen.nl'
    assert msg['To'] == 'errors+website@harmsen.nl'
    assert msg['Subject'].startswith('[ERROR] website:')


def test_emit_body_includes_traceback(smtp_log, clock):
    instances, factory = smtp_log
    handler = _make_handler(factory, clock)
    handler.emit(_record_with_exception())

    raw = instances[0].sent[0][2]
    msg = message_from_string(raw)
    body = msg.get_payload()
    assert 'ZeroDivisionError' in body
    assert 'boom' in body
    assert 'Traceback' in body


def test_smtp_auth_and_tls(smtp_log, clock):
    instances, factory = smtp_log
    handler = _make_handler(factory, clock)
    handler.emit(_record_with_exception())

    smtp = instances[0]
    assert smtp.host == 'smtp.example.com'
    assert smtp.port == 587
    assert smtp.started_tls is True
    assert smtp.logged_in == ('user', 'secret')
    assert smtp.quit_called is True


# ---------------------------------------------------------------------------
# Fingerprint determinism
# ---------------------------------------------------------------------------


def test_fingerprint_matches_sha1_of_project_logger_exc_frame(smtp_log, clock):
    instances, factory = smtp_log
    handler = _make_handler(factory, clock)
    record = _record_with_exception(logger_name='app')
    handler.emit(record)
    msg = _parse_sent(instances[0].sent[0])

    # The recorded record was created inside _record_with_exception, so the
    # innermost frame is in this test file under that helper.
    expected_frame = f'{"test_janitor_email_handler.py"}:_record_with_exception'
    expected_payload = '\x00'.join(['website', 'app', 'ZeroDivisionError', expected_frame]).encode('utf-8')
    expected = hashlib.sha1(expected_payload).hexdigest()
    assert msg['X-Janitor-Fingerprint'] == expected


def test_fingerprint_independent_of_absolute_path():
    """Two records whose tracebacks live under different absolute path prefixes
    but the same module + function must yield the same fingerprint."""
    from justlog.handlers.janitor_email import _fingerprint_from_record

    def fake_record(path: str) -> logging.LogRecord:
        try:
            # Craft a traceback that looks like it came from `path`.
            code = compile(
                'def f():\n    raise ValueError("x")\nf()',
                path,
                'exec',
            )
            exec(code, {})
        except ValueError:
            exc_info = sys.exc_info()
        return logging.LogRecord(
            name='app', level=logging.ERROR, pathname=path, lineno=1,
            msg='m', args=(), exc_info=exc_info,
        )

    fp_dev = _fingerprint_from_record(fake_record('/Users/hp/dev/project/app/views.py'), project='website')
    fp_prod = _fingerprint_from_record(fake_record('/srv/prod/app/views.py'), project='website')
    assert fp_dev == fp_prod


def test_fingerprint_changes_with_exception_class(smtp_log, clock):
    instances, factory = smtp_log
    handler = _make_handler(factory, clock)

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
    # Rate-limit is per fingerprint, so different classes must both go through.
    handler.emit(rec_key)

    assert len(instances) == 2
    fp1 = _parse_sent(instances[0].sent[0])['X-Janitor-Fingerprint']
    fp2 = _parse_sent(instances[1].sent[0])['X-Janitor-Fingerprint']
    assert fp1 != fp2


# ---------------------------------------------------------------------------
# Level filter
# ---------------------------------------------------------------------------


def test_info_record_is_dropped(smtp_log, clock):
    instances, factory = smtp_log
    handler = _make_handler(factory, clock)

    info_record = logging.LogRecord(
        name='app', level=logging.INFO, pathname=__file__, lineno=1,
        msg='hello', args=(), exc_info=None,
    )
    handler.emit(info_record)
    assert instances == []


def test_warning_with_default_error_level_is_dropped(smtp_log, clock):
    instances, factory = smtp_log
    handler = _make_handler(factory, clock)

    warn_record = logging.LogRecord(
        name='app', level=logging.WARNING, pathname=__file__, lineno=1,
        msg='hello', args=(), exc_info=None,
    )
    handler.emit(warn_record)
    assert instances == []


def test_custom_level_threshold_can_lower_to_warning(smtp_log, clock):
    instances, factory = smtp_log
    handler = _make_handler(factory, clock, level=logging.WARNING)

    warn_record = logging.LogRecord(
        name='app', level=logging.WARNING, pathname=__file__, lineno=1,
        msg='hello', args=(), exc_info=None,
    )
    handler.emit(warn_record)
    assert len(instances) == 1


def test_record_without_exception_still_emits(smtp_log, clock):
    instances, factory = smtp_log
    handler = _make_handler(factory, clock)
    rec = logging.LogRecord(
        name='app', level=logging.ERROR, pathname=__file__, lineno=1,
        msg='plain error', args=(), exc_info=None,
    )
    handler.emit(rec)
    assert len(instances) == 1
    msg = _parse_sent(instances[0].sent[0])
    assert 'plain error' in msg.get_payload()


# ---------------------------------------------------------------------------
# Rate-limit
# ---------------------------------------------------------------------------


def test_rate_limit_suppresses_repeats_within_window(smtp_log, clock):
    instances, factory = smtp_log
    handler = _make_handler(factory, clock, rate_limit_window=60.0)

    for _ in range(100):
        handler.emit(_record_with_exception())
        clock.advance(0.1)  # 10s total, well within the 60s window

    assert len(instances) == 1


def test_rate_limit_allows_after_window_passes(smtp_log, clock):
    instances, factory = smtp_log
    handler = _make_handler(factory, clock, rate_limit_window=60.0)

    handler.emit(_record_with_exception())
    clock.advance(61.0)
    handler.emit(_record_with_exception())

    assert len(instances) == 2


def test_rate_limit_is_per_fingerprint(smtp_log, clock):
    instances, factory = smtp_log
    handler = _make_handler(factory, clock, rate_limit_window=60.0)

    # Different logger names → different fingerprints.
    rec_a = _record_with_exception(logger_name='auth')
    rec_b = _record_with_exception(logger_name='billing')
    handler.emit(rec_a)
    handler.emit(rec_b)

    assert len(instances) == 2


# ---------------------------------------------------------------------------
# SMTP failure must not crash the host process
# ---------------------------------------------------------------------------


def test_smtp_failure_swallowed_and_logged_to_stderr(clock, capsys):
    def factory(host, port, timeout=None):
        return FakeSMTPFailure(host, port, timeout)

    handler = _make_handler(factory, clock)
    handler.emit(_record_with_exception())  # must not raise

    captured = capsys.readouterr()
    assert 'JanitorEmailHandler' in captured.err
    assert 'connection refused' in captured.err
