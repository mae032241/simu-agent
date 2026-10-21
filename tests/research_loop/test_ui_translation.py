"""Application translations: exact durable cache, explicit work, isolated transport."""
import json
import re
import sqlite3
import sys
import threading

import pytest

from scidiscovery.research_loop import backends, ui_translation as translation


@pytest.fixture
def services(tmp_path):
    opened = []

    def make(*, config=None, directory=None):
        service = translation.TranslationService(directory or tmp_path / ".scid-ui", config=config)
        opened.append(service)
        return service

    yield make
    for service in opened:
        service.close()


def settled(service, texts):
    with service._condition:
        assert service._condition.wait_for(
            lambda: service.lookup(texts)["counts"]["pending"] == 0, timeout=5), "translation worker did not settle"
    return service.lookup(texts)


def test_blank_startup_and_lookup_never_select_backend_or_model(services, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("a read selected a translation backend")

    monkeypatch.setattr(backends, "selected", forbidden)
    service = services()
    expected = dict(backend="codex", model=None, target_language="zh-CN",
        reasoning_effort=None, service_tier=None, timeout_seconds=120, enabled=False,
        configured=False, launcher_configured=False, config_generation=service.settings()["config_generation"])
    assert service.settings() == expected
    assert service.lookup(["Exact original"]) == dict(target_language="zh-CN", configured=False,
        config_generation=expected["config_generation"],
        entries=[dict(source="Exact original", translation=None, status="missing")],
        counts=dict(cached=0, pending=0, failed=0, missing=1))
    with pytest.raises(ValueError, match="Configure and enable"):
        service.start(["Exact original"])


def test_settings_persist_atomically_and_launcher_is_private(services, tmp_path):
    service = services()
    values = dict(backend="protocol", launcher_argv=["private-launcher", "private-token"],
                  model="translation-model", target_language="ja", reasoning_effort="low",
                  service_tier="priority", timeout_seconds=45)
    configured = service.configure(values)
    assert configured["configured"] and configured["enabled"]
    assert configured["launcher_configured"]
    assert "private" not in json.dumps(configured)
    assert (tmp_path / ".scid-ui/translation-config.json").stat().st_mode & 0o777 == 0o600
    service.close()
    restarted = services()
    assert restarted.settings()["config_generation"] != configured.pop("config_generation")
    assert {key: value for key, value in restarted.settings().items() if key != "config_generation"} == configured
    before = (tmp_path / ".scid-ui/translation-config.json").read_bytes()
    with pytest.raises(ValueError, match="timeout_seconds"):
        restarted.configure(dict(timeout_seconds=301))
    assert (tmp_path / ".scid-ui/translation-config.json").read_bytes() == before


def test_toml_reads_application_section_only(tmp_path):
    path = tmp_path / "application.toml"
    path.write_text('[science]\nmodel="never inherited"\n[translation]\nmodel="chosen"\ntarget_language="de"\n')
    assert translation.load_config(path) == dict(model="chosen", target_language="de")
    path.write_text('[science]\nmodel="never inherited"\n')
    assert translation.load_config(path) == {}
    path.write_text('translation = "invalid"\n')
    with pytest.raises(ValueError, match="table"):
        translation.load_config(path)


def test_exact_cache_survives_restart_and_operational_settings_changes(services, monkeypatch, tmp_path):
    launches = []

    def translate(self, config, texts):
        launches.append((config["model"], config["target_language"], list(texts)))
        return ["译：" + text for text in texts], dict(input_tokens=7, cached_input_tokens=0, output_tokens=3)

    monkeypatch.setattr(translation.TranslationService, "_translate", translate)
    service = services(config=dict(model="application-model"))
    originals = ["Result n=3", " Result n=3", "Result n=3\n"]
    service.start(originals)
    assert settled(service, originals)["counts"]["cached"] == 3
    for _ in range(3):
        assert service.lookup(originals)["entries"][0]["translation"] == "译：Result n=3"
    assert len(launches) == 1
    service.configure(dict(enabled=False, timeout_seconds=10))
    assert service.lookup(originals)["counts"]["cached"] == 3
    service.configure(dict(enabled=True))
    service.close()
    restarted = services()
    assert restarted.lookup(originals)["counts"]["cached"] == 3
    restarted.start(originals)
    assert len(launches) == 1
    with sqlite3.connect(tmp_path / ".scid-ui/translations.sqlite3") as database:
        assert database.execute("SELECT source FROM translations ORDER BY source").fetchall() == [(s,) for s in sorted(originals)]
        usage, = database.execute("SELECT usage FROM translation_invocations").fetchone()
        assert json.loads(usage)["input_tokens"] == 7
        assert all(row[0] > 0 for row in database.execute("SELECT translated_at FROM translations"))


@pytest.mark.parametrize("changed", [dict(model="other"), dict(target_language="fr"),
    dict(reasoning_effort="high"), dict(service_tier="priority"), dict(launcher_argv=["other"]),
    dict(backend="protocol", launcher_argv=["independent"])])
def test_generation_profile_partitions_cache_without_overwriting_original(services, monkeypatch, changed):
    monkeypatch.setattr(translation.TranslationService, "_translate",
                        lambda self, config, texts: (["translated"] * len(texts), None))
    service = services(config=dict(model="first"))
    service.start(["Original"])
    assert settled(service, ["Original"])["entries"][0]["translation"] == "translated"
    service.configure(changed)
    assert service.lookup(["Original"])["entries"][0]["status"] == "missing"
    service.configure(dict(backend="codex", launcher_argv=None, model="first", target_language="zh-CN",
                           reasoning_effort=None, service_tier=None))
    assert service.lookup(["Original"])["entries"][0]["translation"] == "translated"


def test_duplicate_inflight_requests_coalesce_and_capture_profile(services, monkeypatch):
    running, release = threading.Event(), threading.Event()
    launches = []

    def translate(self, config, texts):
        launches.append((config["target_language"], list(texts)))
        running.set()
        assert release.wait(timeout=5)
        return [config["target_language"] + ":" + text for text in texts], None

    monkeypatch.setattr(translation.TranslationService, "_translate", translate)
    service = services(config=dict(model="application-model"))
    try:
        assert service.start(["same", "same"])["counts"]["pending"] == 2
        assert running.wait(timeout=5)
        service.start(["same"])
        service.configure(dict(target_language="es"))
        assert service.lookup(["same"])["entries"][0]["status"] == "missing"
        service.start(["same"])
    finally:
        release.set()
    assert settled(service, ["same"])["entries"][0]["translation"] == "es:same"
    assert launches == [("zh-CN", ["same"]), ("es", ["same"])]
    service.configure(dict(target_language="zh-CN"))
    assert service.lookup(["same"])["entries"][0]["translation"] == "zh-CN:same"


def test_failed_work_is_durable_and_retries_only_on_explicit_start(services, monkeypatch):
    attempts = []

    def translate(self, config, texts):
        attempts.append(texts)
        if len(attempts) == 1:
            raise RuntimeError("private stderr token /science/private")
        return ["recovered"], None

    monkeypatch.setattr(translation.TranslationService, "_translate", translate)
    service = services(config=dict(model="application-model"))
    service.configure({})
    service.start(["source"])
    failed = settled(service, ["source"])
    assert failed["entries"][0]["status"] == "failed"
    assert "private" not in json.dumps(failed)
    message = failed["entries"][0]["error"]
    assert "[translation_internal_error]" in message
    reference = re.search(r"诊断编号：([0-9a-f]{32})", message).group(1)
    diagnostic = service.directory / "errors" / (reference + ".json")
    assert "private stderr token /science/private" in diagnostic.read_text()
    assert diagnostic.stat().st_mode & 0o777 == 0o600
    assert service._thread.is_alive()
    service.close()
    service = services()
    for _ in range(3):
        assert service.lookup(["source"])["entries"][0]["error"] == message
    assert len(attempts) == 1
    service.start(["source"])
    assert settled(service, ["source"])["entries"][0]["translation"] == "recovered"
    assert len(attempts) == 2


@pytest.mark.parametrize("result", [None, {}, {"translations": []},
    {"translations": [{"id": "0", "text": "x"}, {"id": "0", "text": "y"}]},
    {"translations": [{"id": "1", "text": "wrong ID"}]},
    {"translations": [{"id": "0", "text": 12}]},
    {"translations": [{"id": "0", "text": chr(0xD800)}]},
    {"translations": [{"id": "0", "text": "x", "extra": "invalid"}]}])
def test_invalid_response_mapping_cannot_overwrite_cached_success(services, monkeypatch, result):
    def invoke(self, adapter, args, request, work, pending, timeout):
        assert not work.is_relative_to(self.directory)
        assert "--sandbox" in args and args[args.index("--sandbox") + 1] == "read-only"
        assert "features.multi_agent=false" in args
        assert 'web_search="disabled"' in args
        assert "--ignore-user-config" in args
        return result, None

    monkeypatch.setattr(translation.TranslationService, "_invoke", invoke)
    service = services(config=dict(model="application-model"))
    profile = translation._profile(service._config)
    with service._condition, service._db:
        service._db.execute("INSERT INTO translations(profile, source, translation) VALUES (?, ?, ?)", (profile, "saved", "retained"))
    service.start(["saved", "new source"])
    response = settled(service, ["saved", "new source"])
    assert response["entries"][0] == dict(source="saved", translation="retained", status="cached")
    assert response["entries"][1]["status"] == "failed"


def test_invalid_unicode_response_leaves_worker_available_for_explicit_retry(services, monkeypatch):
    attempts = []

    def invoke(self, adapter, args, request, work, pending, timeout):
        attempts.append(request)
        return dict(translations=[dict(id="0", text=chr(0xD800) if len(attempts) == 1 else "recovered")]), None

    monkeypatch.setattr(translation.TranslationService, "_invoke", invoke)
    service = services(config=dict(model="application-model"))
    service.start(["source"])
    assert settled(service, ["source"])["entries"][0]["status"] == "failed"
    assert service._thread.is_alive()
    service.start(["source"])
    assert settled(service, ["source"])["entries"][0]["translation"] == "recovered"


def test_cache_write_failure_does_not_strand_pending_work_or_leak_errors(services, monkeypatch):
    monkeypatch.setattr(translation.TranslationService, "_translate",
                        lambda self, config, texts: (["translated"] * len(texts), None))
    service = services(config=dict(model="application-model"))
    with service._condition, service._db:
        service._db.execute("CREATE TRIGGER fail_save BEFORE UPDATE ON translations "
                            "BEGIN SELECT RAISE(ABORT, 'private-token /private/path'); END")
    service.start(["source"])
    response = settled(service, ["source"])
    assert response["entries"][0]["status"] == "failed"
    assert "[translation_cache_write]" in response["entries"][0]["error"]
    assert "写入权限" in response["entries"][0]["error"]
    assert "private" not in json.dumps(response)
    assert service._thread.is_alive()
    with service._condition, service._db:
        service._db.execute("DROP TRIGGER fail_save")
    service.start(["source"])
    assert settled(service, ["source"])["entries"][0]["translation"] == "translated"


def test_response_ids_map_to_exact_sources_even_when_reordered(services, monkeypatch):
    def invoke(self, adapter, args, request, work, pending, timeout):
        return dict(translations=[dict(id="1", text="second译"), dict(id="0", text="first译")]), None

    monkeypatch.setattr(translation.TranslationService, "_invoke", invoke)
    service = services(config=dict(model="application-model"))
    service.start(["first", "second"])
    assert [row["translation"] for row in settled(service, ["first", "second"])["entries"]] == ["first译", "second译"]


def test_batches_are_bounded_and_successes_remain_readable(services, monkeypatch):
    batches = []

    def translate(self, config, texts):
        assert len(texts) <= 32 and sum(map(len, texts)) <= 24000
        batches.append(list(texts))
        return list(texts), None

    monkeypatch.setattr(translation.TranslationService, "_translate", translate)
    service = services(config=dict(model="application-model"))
    texts = [str(index) + "a" * 999 for index in range(70)]
    service.start(texts)
    assert settled(service, texts)["counts"]["cached"] == 70
    assert sum(map(len, batches)) == 70


@pytest.mark.parametrize("texts, message", [(["x"] * 129, "128"), (["x" * 12001], "12000"),
    (["字" * 12000] * 6, "180000"), ([None], "string"), ("wrong", "list")])
def test_input_limits_fail_descriptively_without_launch(services, texts, message):
    service = services(config=dict(model="application-model"))
    with pytest.raises(ValueError, match=message):
        service.lookup(texts)
    with pytest.raises(ValueError, match=message):
        service.start(texts)
    assert service._thread is None


_PROTOCOL = r'''import json, pathlib, sys
request = json.load(sys.stdin)
assert request['protocol'] == 'scidiscovery-agent-v1'
assert request['profile'] == {'model': 'app-model'}
assert request['permissions']['requested'] == dict(workspace='read-only', network=False, web='disabled', subagents=False)
assert 'inert data' in request['prompt']
work = pathlib.Path(request['workspace'])
assert not list(work.glob('AGENTS.md'))
fields = json.loads(request['prompt'].split('\n', 1)[1])['fields']
assert fields == [{'id': '0', 'text': 'Original n=3'}]
print(json.dumps(dict(type='usage', usage=dict(input_tokens=8, output_tokens=4))), flush=True)
print(json.dumps(dict(type='result', result=dict(translations=[dict(id='0', text='译文 n=3')]))), flush=True)
print(json.dumps(dict(type='completed', usage=dict(input_tokens=8, output_tokens=4))), flush=True)
'''


@pytest.mark.process_e2e
def test_protocol_adapter_runs_fake_launcher_and_records_only_application_usage(services, tmp_path):
    script = tmp_path / "fake_translation.py"
    script.write_text(_PROTOCOL)
    science = tmp_path / "science-original.json"
    original = b'{"summary": "Original n=3", "budget": 100}\n'
    science.write_bytes(original)
    service = services(config=dict(backend="protocol", launcher_argv=[sys.executable, str(script)], model="app-model"))
    service.start(["Original n=3"])
    assert settled(service, ["Original n=3"])["entries"][0]["translation"] == "译文 n=3"
    assert science.read_bytes() == original
    with sqlite3.connect(tmp_path / ".scid-ui/translations.sqlite3") as database:
        status, usage = database.execute("SELECT status, usage FROM translation_invocations").fetchone()
        assert status == "completed"
        assert json.loads(usage) == dict(input_tokens=8, cached_input_tokens=0, output_tokens=4)


@pytest.mark.process_e2e
@pytest.mark.parametrize("program, timeout, expected", [
    ("import time; time.sleep(10)", 1, "translation_timeout"),
    ("import sys; sys.stdout.write('x' * 1100000); sys.stdout.flush()", 3, "translation_output_limit"),
    ("import json; print(json.dumps(dict(type='tool',tool='shell',status='started')),flush=True)", 3, "translation_tool_action"),
    ("import sys; sys.stderr.write('secret-token /private/science'); sys.exit(1)", 3, "translation_backend_exit"),
    ("import sys; sys.stdin.read()", 3, "translation_missing_completion"),
])
def test_process_failures_are_bounded_private_and_never_replayed(services, tmp_path, program, timeout, expected):
    script = tmp_path / "fake_translation.py"
    script.write_text(program)
    service = services(config=dict(backend="protocol", launcher_argv=[sys.executable, str(script)],
                                   model="app-model", timeout_seconds=timeout))
    service.start(["Original"])
    response = settled(service, ["Original"])
    assert response["entries"][0]["status"] == "failed"
    assert expected in response["entries"][0]["error"]
    assert "secret-token" not in json.dumps(response)
    assert "/private" not in json.dumps(response)
    assert service._process is None
    assert service.lookup(["Original"])["entries"][0]["status"] == "failed"


@pytest.mark.parametrize("details, code", [
    ("The requested model gpt6-luna does not exist", "model_rejected"),
    ("Unsupported_model: bad-model", "model_rejected"),
    ("401 invalid_api_key private-token", "authentication"),
    ("connection refused /private/proxy", "network"),
    ("429 insufficient_quota private-account", "rate_limit"),
    ("request timed out", "timeout"),
    ("unrecognized secret-token /private/path", "backend_exit"),
])
def test_backend_failure_categories_only_return_host_authored_codes(details, code):
    assert translation._failure_kind(details, "backend_exit") == code
    assert details not in translation._FAILURES[code]


def test_diagnostic_write_failure_keeps_worker_available_and_public_error_safe(services, monkeypatch):
    monkeypatch.setattr(translation.ui_errors, "record", lambda *args, **kwargs: None)
    monkeypatch.setattr(translation.TranslationService, "_translate",
        lambda *args: (_ for _ in ()).throw(RuntimeError("secret-token /private/path")))
    service = services(config=dict(model="app-model"))
    service.start(["source"])
    response = settled(service, ["source"])
    message = response["entries"][0]["error"]
    assert "[translation_internal_error]" in message
    assert "诊断未能保存" in message
    assert "secret-token" not in json.dumps(response)
    assert service._thread.is_alive()


@pytest.mark.process_e2e
@pytest.mark.parametrize("kind", ["error", "turn.failed"])
def test_native_codex_failures_keep_original_private_evidence_and_durable_safe_reason(services, tmp_path, kind):
    script = tmp_path / "fake_native_translation.py"
    private_message = "The requested model gpt6-luna does not exist; secret-token /private/science"
    script.write_text("import json,sys\nsys.stdin.read()\n"
        + "sys.stderr.write('discarded-prefix' + 'x' * 200000 + 'retained-stderr-tail')\n"
        + "print(json.dumps(" + repr(dict(type=kind, error=dict(message=private_message))) + "), flush=True)\n"
        + "sys.exit(7)\n")
    service = services(config=dict(backend="codex", launcher_argv=[sys.executable, str(script)], model="gpt6-luna"))
    service.start(["source"])
    response = settled(service, ["source"])
    message = response["entries"][0]["error"]
    assert "[translation_model_rejected]" in message
    assert "核对模型名称" in message
    assert all(secret not in json.dumps(response) for secret in ("secret-token", "/private", "gpt6-luna"))
    reference = re.search(r"诊断编号：([0-9a-f]{32})", message).group(1)
    diagnostic = tmp_path / ".scid-ui/errors" / (reference + ".json")
    evidence = json.loads(diagnostic.read_text())["traceback"]
    assert private_message in evidence
    assert kind in evidence
    assert '"returncode": 7' in evidence
    assert "retained-stderr-tail" in evidence
    assert "discarded-prefix" not in evidence
    assert diagnostic.stat().st_size <= 16384
    assert service._process is None and service._thread.is_alive()
    service.close()
    restarted = services()
    assert restarted.lookup(["source"])["entries"][0]["error"] == message
    with sqlite3.connect(tmp_path / ".scid-ui/translations.sqlite3") as database:
        assert database.execute("SELECT error FROM translations").fetchone()[0] == message
        assert database.execute("SELECT status,usage FROM translation_invocations").fetchone() == ("failed", None)


@pytest.mark.process_e2e
def test_protocol_failure_preserves_observed_usage_and_overrides_completion(services, tmp_path):
    script = tmp_path / "fake_failed_protocol.py"
    script.write_text("import json,sys\njson.load(sys.stdin)\n"
        "print(json.dumps(dict(type='usage',usage=dict(input_tokens=8,output_tokens=4))),flush=True)\n"
        "print(json.dumps(dict(type='result',result=dict(translations=[dict(id='0',text='must not cache')]))),flush=True)\n"
        "print(json.dumps(dict(type='error',message='401 invalid_api_key secret-token')),flush=True)\n"
        "print(json.dumps(dict(type='completed')),flush=True)\n")
    service = services(config=dict(backend="protocol", launcher_argv=[sys.executable, str(script)], model="app-model"))
    service.start(["source"])
    response = settled(service, ["source"])
    assert response["entries"][0]["translation"] is None
    assert "[translation_authentication]" in response["entries"][0]["error"]
    assert "secret-token" not in json.dumps(response)
    with sqlite3.connect(tmp_path / ".scid-ui/translations.sqlite3") as database:
        status, usage = database.execute("SELECT status,usage FROM translation_invocations").fetchone()
        assert status == "failed"
        assert json.loads(usage) == dict(input_tokens=8, cached_input_tokens=0, output_tokens=4)


@pytest.mark.process_e2e
def test_missing_launcher_has_private_original_and_actionable_reason(services, tmp_path):
    missing = tmp_path / "private-launcher-not-installed"
    service = services(config=dict(backend="protocol", launcher_argv=[str(missing)], model="app-model"))
    service.start(["source"])
    response = settled(service, ["source"])
    message = response["entries"][0]["error"]
    assert "[translation_launcher_unavailable]" in message
    assert "执行权限" in message
    assert str(missing) not in json.dumps(response)
    reference = re.search(r"诊断编号：([0-9a-f]{32})", message).group(1)
    assert str(missing) in (tmp_path / ".scid-ui/errors" / (reference + ".json")).read_text()


@pytest.mark.process_e2e
def test_close_stops_only_its_application_subprocess(services, tmp_path):
    import os
    import subprocess

    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
    script = tmp_path / "fake_translation.py"
    script.write_text("import json,sys,time; json.load(sys.stdin); time.sleep(30)")
    service = services(config=dict(backend="protocol", launcher_argv=[sys.executable, str(script)], model="app-model"))
    try:
        service.start(["Original"])
        with service._condition:
            assert service._condition.wait_for(lambda: service._process is not None, timeout=3)
            process = service._process
        service.close()
        assert process.poll() is not None
        assert unrelated.poll() is None
        with pytest.raises(ProcessLookupError):
            os.kill(process.pid, 0)
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=3)
