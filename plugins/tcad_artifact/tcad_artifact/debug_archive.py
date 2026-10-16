"""Read-only ownership of persisted diagnostics; no solver or reconciliation."""
from contextlib import ExitStack
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re

from scidiscovery.artifact_agent.schema.common import canonical_sha256
from scidiscovery.operations.runtime_plugins import ArchiveStorage, ArchiveStorageSelection

MAX_ENTRIES = 4096
MAX_LEDGER_BYTES = 1024 * 1024


def _children(path):
    result = []
    with os.scandir(path) as entries:
        for entry in entries:
            if entry.is_symlink() or len(result) >= MAX_ENTRIES:
                raise ValueError("debug_storage_shape_unknown")
            result.append(Path(entry.path))
    return result


def _json(path):
    if path.resolve() != path or not path.is_file() or path.stat().st_size > MAX_LEDGER_BYTES:
        raise ValueError("debug_original_unavailable")
    return json.loads(path.read_bytes())


def _verify(path, descriptor):
    if (path.resolve() != path or not path.is_file() or path.stat().st_size != descriptor['size_bytes']
            or path.stat().st_size > 64 * 1024 * 1024):
        raise ValueError("debug_original_changed")
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            digest.update(chunk)
    if digest.hexdigest() != descriptor['sha256']:
        raise ValueError("debug_original_changed")


def storage(root):
    root = Path(root)
    return ArchiveStorage(root, lambda instance, runs, owner: inspect(root, instance, runs, owner))


def inspect(root, instance_id, run_ids, run_owner):
    """Select whole original files only; mixed/unknown ledgers are never split."""
    if not root.exists():
        return ArchiveStorageSelection()
    try:
        return _inspect(root, instance_id, set(run_ids), run_owner)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError):
        return ArchiveStorageSelection(unsupported=("debug_ownership_or_writer_unconfirmed",), unowned=True)


def _inspect(root, instance_id, run_ids, run_owner):
    from .local_debug_service import _read_ledger
    if root.resolve() != root or not root.is_dir():
        raise ValueError("debug_storage_shape_unknown")
    top = _children(root)
    if not top:
        return ArchiveStorageSelection()
    budgets = root / 'budgets'
    if not budgets.is_dir():
        raise ValueError("debug_legacy_owner_unknown")
    budget_files = _children(budgets)
    ledgers = [path for path in budget_files if path.suffix == '.json']
    selected = set()
    exchanges = {}
    record_owners = {}
    known_budget_files = {budgets / 'receipts'}
    target_key = canonical_sha256({'subject': canonical_sha256({'instance': instance_id})})
    # The same budget lock is held by run/cancel/collection. A read cannot grant
    # quiescence while one of those original writers owns it.
    with ExitStack() as locks:
        for path in ledgers:
            if re.fullmatch(r'[0-9a-f]{64}\.json', path.name) is None:
                raise ValueError("debug_budget_identity_unknown")
            lock_path = path.with_suffix('.lock')
            fd = os.open(lock_path, os.O_RDONLY | os.O_NOFOLLOW)
            locks.callback(os.close, fd)
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
            _json(path)  # Enforce bounded original reads before the domain parser.
            ledger = _read_ledger(path)
            known_budget_files.update((path, lock_path))
            records = {key: value['record'] for key, value in ledger['reservations'].items()}
            records.update(ledger['runs'])
            if len(records) > MAX_ENTRIES:
                raise ValueError("debug_record_capacity")
            owners = {run_owner(record['run_id']) for record in records.values()}
            if not owners:
                if path.stem != target_key:
                    raise ValueError("debug_empty_legacy_owner_unknown")
                owners = {instance_id}
            if len(owners) != 1 or not all(isinstance(owner, str) and owner for owner in owners):
                raise ValueError("debug_mixed_owners")
            owner = next(iter(owners))
            expected_key = canonical_sha256({'subject': canonical_sha256({'instance': owner})})
            if path.stem != expected_key:
                raise ValueError("debug_budget_owner_mismatch")
            target = owner == instance_id
            if target:
                selected.update((path.relative_to(root).as_posix(), lock_path.relative_to(root).as_posix()))
            for key, record in records.items():
                if key in record_owners or len(record_owners) >= MAX_ENTRIES:
                    raise ValueError("debug_record_identity_or_capacity")
                record_owners[key] = owner
                reservation = ledger['reservations'].get(key)
                if reservation is None or reservation['record']['run_id'] != record['run_id']:
                    raise ValueError("debug_reservation_unknown")
                submission = reservation['submission']
                source = Path(submission['local_path'])
                if source.resolve() != source:
                    raise ValueError("debug_exchange_path_unknown")
                relative = source.relative_to(root)
                if len(relative.parts) < 3 or re.fullmatch(r'[0-9a-f]{32}', relative.parts[0]) is None:
                    raise ValueError("debug_exchange_owner_unknown")
                previous = exchanges.setdefault(relative.parts[0], owner)
                if previous != owner:
                    raise ValueError("debug_exchange_shared_owner")
                if not target:
                    continue
                if record['run_id'] not in run_ids or record.get('state') != 'collected':
                    raise ValueError("debug_work_pending")
                _verify(source, submission)
                receipt_dir = budgets / 'receipts' / key
                receipt = _json(receipt_dir / 'receipt.json')
                proof = receipt['proof']
                if (receipt['submission'] != submission or proof['run_id'] != record['run_id']
                        or proof['run_name'] != record['run_name'] or receipt['response'] != record.get('response')):
                    raise ValueError("debug_receipt_owner_mismatch")
                if not isinstance(proof['files'], list) or len(proof['files']) > MAX_ENTRIES:
                    raise ValueError("debug_receipt_capacity")
                for item in proof['files']:
                    if re.fullmatch(r'[0-9a-f]{64}', item['sha256']) is None:
                        raise ValueError("debug_receipt_identity_unknown")
                    _verify(receipt_dir / item['sha256'], item)
                selected.update((receipt_dir.relative_to(root).as_posix(), relative.parts[0]))
        if any(path not in known_budget_files for path in budget_files):
            raise ValueError("debug_unowned_budget_state")
        receipts = budgets / 'receipts'
        if receipts.exists() and any(path.name not in record_owners for path in _children(receipts)):
            raise ValueError("debug_unowned_receipt")
        if any(path.name != 'budgets' and path.name not in exchanges for path in top):
            raise ValueError("debug_unowned_exchange")
    return ArchiveStorageSelection(paths=tuple(sorted(selected)), unowned=any(owner != instance_id for owner in record_owners.values()))
