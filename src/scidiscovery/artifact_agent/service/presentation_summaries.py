"""Disposable post-seal display copies, outside scientific state and model context."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
import threading

from ...agent_execution_settings import merge_helper_settings, parse_settings, PresentationSettings
from ..schema.common import canonical_json
from ..schema.refs import ArtifactRef

LOGGER = logging.getLogger(__name__)
VERSION = 1
TEXT_FIELDS = ("summary", "conclusion", "statement", "objective", "remaining_question", "limitations")


class SummaryStore:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise ValueError("display cache must not be a symlink")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=0.2)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE IF NOT EXISTS display_summaries(
                cache_key TEXT PRIMARY KEY, instance_id TEXT NOT NULL, source_ref TEXT NOT NULL,
                settings TEXT NOT NULL, profile TEXT NOT NULL, state TEXT NOT NULL,
                result TEXT, usage TEXT, error_code TEXT)""")
            if "retry_generation" not in {row[1] for row in db.execute("PRAGMA table_info(display_summaries)")}:
                db.execute("ALTER TABLE display_summaries ADD COLUMN retry_generation INTEGER NOT NULL DEFAULT 0")
            yield db
            db.commit()
        finally:
            db.close()

    def enqueue(self, instance_id, ref, settings, profile):
        key = hashlib.sha256(canonical_json({"version": VERSION, "instance": instance_id, "ref": ref.model_dump(),
            "settings": settings, "profile": profile})).hexdigest()
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO display_summaries(cache_key,instance_id,source_ref,settings,profile,state) "
                "VALUES(?,?,?,?,?,'queued')",
                (key, instance_id, ref.model_dump_json(), json.dumps(settings), json.dumps(profile)))
        return key

    def read(self, instance_id, ref):
        try:
            return self._read(instance_id, ref)
        except (sqlite3.Error, OSError, ValueError):
            return None

    def _read(self, instance_id, ref):
        if not self.path.exists():
            return None
        if self.path.is_symlink() or self.path.parent.is_symlink():
            return None
        # Rendering never queues a model call or creates/updates cache tables.
        from contextlib import closing
        with closing(sqlite3.connect(self.path.absolute().as_uri() + "?mode=ro", uri=True, timeout=0.2)) as db:
            try:
                row = db.execute("SELECT state,result,usage,error_code,cache_key,retry_generation FROM display_summaries "
                    "WHERE instance_id=? AND source_ref=? ORDER BY rowid DESC LIMIT 1",
                    (instance_id, ref.model_dump_json())).fetchone()
            except sqlite3.OperationalError:
                return None
        if row is None:
            return None
        return {"state": row[0], "items": json.loads(row[1]) if row[1] else [],
                "usage": json.loads(row[2]) if row[2] else {}, "error_code": row[3],
                "retry": {"cache_key": row[4], "generation": row[5]} if row[0] in {"failed", "ready"} else None}

    def retry(self, instance_id, key, generation):
        """One explicit regeneration of an exact copy; old forms cannot retry again."""
        with self.connect() as db:
            row = db.execute("SELECT * FROM display_summaries WHERE instance_id=? AND cache_key=?",
                (instance_id, key)).fetchone()
            if row is None:
                raise ValueError("没有找到该实例的展示整理记录。")
            if row["retry_generation"] != generation or row["state"] not in {"failed", "ready"}:
                return False
            # A newer settings-specific copy supersedes this old browser form.
            latest = db.execute("SELECT cache_key FROM display_summaries WHERE instance_id=? AND source_ref=? "
                "ORDER BY rowid DESC LIMIT 1", (instance_id, row["source_ref"])).fetchone()
            if latest[0] != key:
                return False
            db.execute("UPDATE display_summaries SET state='queued',retry_generation=retry_generation+1 "
                "WHERE cache_key=?", (key,))
            return True

    def claim(self):
        with self.connect() as db:
            row = db.execute("SELECT * FROM display_summaries WHERE state='queued' ORDER BY rowid LIMIT 1").fetchone()
            if row is not None:
                db.execute("UPDATE display_summaries SET state='running' WHERE cache_key=?", (row["cache_key"],))
                return dict(row)

    def finish(self, key, *, items=None, usage=None, error=None):
        with self.connect() as db:
            db.execute("UPDATE display_summaries SET state=?,result=?,usage=?,error_code=? WHERE cache_key=?",
                ("failed" if error else "ready", json.dumps(items or [], ensure_ascii=False), json.dumps(usage or {}), error, key))


def store_for(runs):
    return SummaryStore(runs.database_path.parent.parent / "ui" / "workbench.sqlite3")


def enqueue(runs, run, ref):
    """Best effort after commit. Cache/service failures cannot reject a submission."""
    try:
        overrides = parse_settings(runs.scheduler_bindings.agent_settings(run.instance_id)["settings"])
        settings = PresentationSettings.model_validate({**runs.agent_settings.presentation.model_dump(),
            **overrides.presentation.model_dump(exclude_unset=True)})
        if not settings.enabled:
            return
        helpers = merge_helper_settings(runs.agent_settings.helpers.model_dump(), overrides.helpers.model_dump(exclude_unset=True))
        profile = helpers["profiles"].get("lightweight")
        if profile is None or not profile.get("model"):
            return
        return store_for(runs).enqueue(run.instance_id, ref, settings.model_dump(), profile)
    except Exception as error:
        LOGGER.warning("Display summary enqueue failed (%s); sealed result retained", type(error).__name__)


def fragments(payload, *, max_bytes):
    """Select only narrative text. Never include tool contracts, bindings or logs."""
    selected, omitted = [], False
    def visit(value, path="", depth=0):
        nonlocal omitted
        if depth > 8:
            omitted = True
            return
        if isinstance(value, dict):
            for key in sorted(value, key=lambda key: TEXT_FIELDS.index(key) if key in TEXT_FIELDS else len(TEXT_FIELDS)):
                child = value[key]
                pointer = path + "/" + key.replace("~", "~0").replace("/", "~1")
                texts = child if key == "limitations" and isinstance(child, list) else [child]
                if key in TEXT_FIELDS:
                    for i, text in enumerate(texts):
                        if not isinstance(text, str) or not text.strip():
                            continue
                        item = {"source": pointer + ("/" + str(i) if texts is child else ""), "text": text[:2048]}
                        if len(selected) >= 16 or len(canonical_json(selected + [item])) > max_bytes:
                            omitted = True
                            continue
                        selected.append(item)
                        omitted |= len(text) > 2048
                elif key not in {"metadata", "bindings", "logs", "tool_contracts", "schema", "$defs"} and isinstance(child, (dict, list)):
                    visit(child, pointer, depth + 1)
        elif isinstance(value, list):
            for i, child in enumerate(value[:128]):
                visit(child, path + "/" + str(i), depth + 1)
            omitted |= len(value) > 128
    visit(payload)
    return {"fragments": selected, "source_excerpt_omitted": omitted}


def validate_copy(value, source):
    if not isinstance(value, dict) or set(value) != {"items"} or not isinstance(value["items"], list) or len(value["items"]) > 8:
        raise ValueError("display_copy_invalid")
    allowed = {item["source"] for item in source["fragments"]}
    seen = set()
    for item in value["items"]:
        if (not isinstance(item, dict) or set(item) != {"source", "title", "summary"}
                or item["source"] not in allowed or item["source"] in seen
                or not isinstance(item["title"], str) or not 1 <= len(item["title"]) <= 80
                or not isinstance(item["summary"], str) or not 1 <= len(item["summary"]) <= 600):
            raise ValueError("display_copy_invalid")
        seen.add(item["source"])
    return value["items"]


class SummaryWorker:
    def __init__(self, runs, *, project_root, invoke=None, writable=lambda _: True):
        from .presentation_summary_runner import invoke_codex
        self.runs, self.store = runs, store_for(runs)
        self.default_codex_home = Path(project_root).resolve() / ".scidiscovery-ui" / "display-codex"
        self.invoke = invoke or invoke_codex
        self.writable = writable
        self.stop_event = threading.Event()
        self.thread = None

    def process_one(self):
        self.store.path.parent.mkdir(parents=True, exist_ok=True)
        with self.store.path.with_suffix(".summary.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
            # A previous process died after claiming. Do not repeat an uncertain
            # external model request; the next sealed version gets a new job.
            with self.store.connect() as db:
                db.execute("UPDATE display_summaries SET state='failed',error_code='interrupted' WHERE state='running'")
            return self._process_one()

    def _process_one(self):
        job = self.store.claim()
        if job is None:
            return False
        try:
            if not self.writable(job["instance_id"]):
                raise ValueError("instance_not_active")
            settings = PresentationSettings.model_validate_json(job["settings"])
            if settings.codex_home is None:
                settings = settings.model_copy(update={"codex_home": str(self.default_codex_home)})
            ref = ArtifactRef.model_validate_json(job["source_ref"])
            if self.runs.artifacts.catalog(ref).size_bytes > settings.max_source_bytes:
                raise ValueError("display_source_limit")
            source = fragments(json.loads(self.runs.artifacts.read(ref)), max_bytes=settings.max_input_bytes)
            if source["fragments"]:
                value, usage = self.invoke(source, json.loads(job["profile"]), settings, self.stop_event)
                items = validate_copy(value, source)
            else:
                items, usage = [], {}
            usage["source_excerpt_omitted"] = bool(usage.get("source_excerpt_omitted") or source["source_excerpt_omitted"])
            self.store.finish(job["cache_key"], items=items, usage=usage)
        except Exception as error:
            # Do not forward CLI stderr, credentials or scientific payloads to UI.
            try:
                from .engineering_diagnostics import EngineeringDiagnostics
                evidence = EngineeringDiagnostics(self.runs.database_path.parent.parent / "engineering-diagnostics").capture(
                    error, scope="instance:" + job["instance_id"], layer="presentation_summary", action="generate")
                LOGGER.warning("Display summary failed (%s), diagnostic %s", type(error).__name__, evidence["reference"])
            except Exception:
                LOGGER.warning("Display summary failure diagnostics unavailable")
            self.store.finish(job["cache_key"], error=type(error).__name__)
        return True

    def start(self):
        if self.thread is not None or not self.runs.agent_settings.presentation.enabled:
            return
        def work():
            while not self.stop_event.is_set():
                try:
                    handled = self.process_one()
                except Exception:
                    LOGGER.exception("Display summary cache unavailable")
                    handled = False
                if not handled:
                    self.stop_event.wait(self.runs.agent_settings.presentation.interval_seconds)
        self.thread = threading.Thread(target=work, name="display-summary", daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=5)
