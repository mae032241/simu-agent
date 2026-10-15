"""Bounded token metadata observation for one exact native home/thread.

Session text is never exposed to a role. Cumulative counters cover reported model
usage only; a running request and platform reporting delay remain unmeasured.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re

FIELDS = ('input_tokens', 'cached_input_tokens', 'output_tokens')
READ_BYTES = 1024 * 1024
LINE_BYTES = 65536
DISCOVERY_ENTRIES = 256


def tokens(value):
    if (not isinstance(value, dict) or any(type(value.get(k)) is not int or value[k] < 0 for k in FIELDS)
            or value['cached_input_tokens'] > value['input_tokens']):
        return None
    return {key: value[key] for key in FIELDS}


def _counter(line):
    # Ignore all non-meter payloads; never retain or publish conversation text.
    if b'"token_count"' not in line:
        return None
    try:
        event = json.loads(line)
        payload = event.get('payload', {})
        if event.get('type') != 'event_msg' or payload.get('type') != 'token_count':
            return None
        info = payload.get('info')
        # Codex emits token_count with null info for rate-limit updates too.
        if info is None:
            return None
        return tokens(info.get('total_token_usage')) or 'invalid_token_counter'
    except (ValueError, AttributeError):
        return 'invalid_token_counter'


class SessionUsage:
    """Read an append-only session with fixed per-poll byte and line budgets."""

    def __init__(self, home, workspace, *, session=None):
        self.home, self.workspace = Path(home), Path(workspace)
        self.thread = session['thread_id'] if session else None
        self.path = Path(session['path']) if session else None
        self.identity = None
        self.offset = 0
        self.pending = b''
        self.skipping = False
        self.baseline = dict.fromkeys(FIELDS, 0)
        self.high = None
        self.known = dict.fromkeys(FIELDS, 0)
        self.reason = 'token_counter_unreported'
        self.fault = None
        self.unavailable = None
        self.resumed = session is not None
        if session:
            # Before launch, freeze both the counter baseline and append position.
            # Only a bounded tail is inspected, never the historical transcript.
            try:
                self._bind(self.path)
                with self.path.open('rb') as stream:
                    size = self.path.stat().st_size
                    start = max(self.offset, size - READ_BYTES)
                    stream.seek(start)
                    data = stream.read(READ_BYTES)
                if start > self.offset:
                    data = data.partition(b'\n')[2]
                lines = data.split(b'\n')
                self.pending = lines.pop()
                for line in lines:
                    value = _counter(line) if len(line) <= LINE_BYTES else None
                    if isinstance(value, str) or (isinstance(value, dict) and self.high is not None
                            and any(value[k] < self.high[k] for k in FIELDS)):
                        self.unavailable = self.reason = 'resume_usage_baseline_unavailable'
                        break
                    if isinstance(value, dict):
                        self.baseline = value
                        self.high = value
                self.offset = size
                if self.high is None or self.pending:
                    self.unavailable = self.reason = 'resume_usage_baseline_unavailable'
            except (OSError, ValueError):
                self.unavailable = self.reason = 'resume_usage_baseline_unavailable'

    def bind_thread(self, thread):
        if not isinstance(thread, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,256}', thread):
            self.fault = 'native_thread_identity_invalid'
        elif self.thread is not None and self.thread != thread:
            self.fault = 'native_thread_identity_changed'
        else:
            self.thread = thread

    def _bind(self, path):
        if (path.resolve() != path or not path.is_relative_to(self.home / 'sessions')
                or self.home.resolve() != self.home):
            raise ValueError('unsafe_session_path')
        with path.open('rb') as stream:
            line = stream.readline(LINE_BYTES + 1)
        if len(line) > LINE_BYTES:
            raise ValueError('session_header_oversized')
        event = json.loads(line)
        if not isinstance(event, dict) or not isinstance(event.get('payload'), dict):
            raise ValueError('session_header_invalid')
        payload = event['payload']
        if (event.get('type') != 'session_meta' or payload.get('id') != self.thread
                or payload.get('cwd') != str(self.workspace)):
            raise ValueError('session_identity_changed')
        stat = path.stat()
        self.identity = (stat.st_dev, stat.st_ino)
        self.path, self.offset = path, len(line)

    def _discover(self):
        if self.thread is None:
            return
        matches = []
        # Count every directory entry, including directories and unrelated files.
        # scandir is lazy: a large non-session tree cannot bypass the read budget.
        pending, visited = [self.home / 'sessions'], 0
        while pending:
            with os.scandir(pending.pop()) as entries:
                for entry in entries:
                    if visited >= DISCOVERY_ENTRIES:
                        self.reason = 'session_discovery_capacity'
                        return
                    visited += 1
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
                    elif (entry.name.endswith('.jsonl') and self.thread in entry.name
                            and entry.is_file(follow_symlinks=False)):
                        matches.append(Path(entry.path))
        if len(matches) != 1:
            self.reason = 'session_unavailable' if not matches else 'session_ambiguous'
            return
        self._bind(matches[0])

    def poll(self):
        if self.fault or self.unavailable:
            return self.snapshot()
        try:
            if self.path is None:
                self._discover()
            if self.path is None:
                return self.snapshot()
            stat = self.path.stat()
            if self.identity != (stat.st_dev, stat.st_ino) or stat.st_size < self.offset:
                self.fault = 'session_log_replaced_or_truncated'
                return self.snapshot()
            if self.high is not None:
                self.reason = None
            with self.path.open('rb') as stream:
                stream.seek(self.offset)
                data = stream.read(READ_BYTES)
            self.offset += len(data)
            for part in data.splitlines(keepends=True):
                complete = part.endswith(b'\n')
                if not self.skipping:
                    self.pending += part
                    if len(self.pending) > LINE_BYTES:
                        self.pending = b''
                        self.skipping = True
                if complete:
                    if not self.skipping:
                        value = _counter(self.pending)
                        if isinstance(value, str):
                            self.fault = value
                        elif value is not None:
                            if self.high is not None and any(value[k] < self.high[k] for k in FIELDS):
                                self.fault = 'token_counter_regressed'
                            else:
                                delta = {k: value[k] - self.baseline[k] for k in FIELDS}
                                if tokens(delta) is None:
                                    self.fault = 'invalid_token_delta'
                                else:
                                    self.high = value
                                    self.known = delta
                                    self.reason = None
                    self.pending = b''
                    self.skipping = False
            if self.pending or self.skipping:
                self.reason = 'session_partial_line'
            elif self.offset < stat.st_size:
                self.reason = 'session_read_backlog'
        except (OSError, ValueError, AttributeError):
            self.reason = 'session_unavailable'
        return self.snapshot()

    def snapshot(self):
        return dict(source='native_session_token_count', thread_id=self.thread,
                    coverage='unknown' if self.fault or self.reason else 'live',
                    reason=self.fault or self.reason, tokens=dict(self.known),
                    baseline_tokens=dict(self.baseline) if self.resumed and not self.unavailable else None,
                    has_observation=self.high is not None and not (self.resumed and self.high == self.baseline),
                    unreported_usage='Running requests and reporting delay are unmeasured.',
                    individual_request_usage='unavailable')
