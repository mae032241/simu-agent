"""Instance-oriented CLI: no interactive scheduler session or MCP dispatch."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import contracts, controller, native


def status(root: Path):
    root = root.resolve()
    settings = contracts.read(root / 'settings.json')
    nodes = []
    for step in range(1, settings['max_steps'] + 1):
        job_path = root / 'jobs' / f'{step:03d}.json'
        if not job_path.exists():
            break
        work = contracts.workspace(root, step)
        record = contracts.host_record(work)
        job = contracts.read(job_path)
        state = ('seal_present_unverified' if (record / 'result-identity.json').exists() else
                 'native_outcome_unsealed' if (record / 'native-outcome.json').exists() else
                 'submitted_or_unknown' if (record / 'native-intent.json').exists() else 'prepared')
        nodes.append(dict(step=step, role=job['role'], state=state))
    return dict(instance=str(root), goal_id=settings['goal_id'], objective=settings['objective'],
                paused=(root / 'pause.request').exists(), nodes=nodes, usage=native.usage(root),
                goal_completion='not_asserted')


def main(argv=None):
    parser = argparse.ArgumentParser(prog='scid-research', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare', help='Create a fresh instance with explicit finite budgets')
    prepare.add_argument('--root', type=Path, required=True)
    prepare.add_argument('--objective', type=Path, required=True)
    prepare.add_argument('--user-update', type=Path, action='append', default=[], help='Freeze an additional user statement in global inputs; repeat for more')
    prepare.add_argument('--public-root', type=Path, required=True)
    prepare.add_argument('--native-launcher-json', required=True, help='An argv JSON array, e.g. ["codex"]')
    prepare.add_argument('--max-tokens', type=int, required=True)
    prepare.add_argument('--max-seconds', type=float, required=True)
    prepare.add_argument('--max-steps', type=int, required=True)
    prepare.add_argument('--model', default='gpt-6.1-sol')
    prepare.add_argument('--reasoning-effort', default='high')
    prepare.add_argument('--service-tier', default='default')
    for name, help_text in (
            ('run', 'Run or recover only completed sealed scientific handoffs'),
            ('status', 'Read instance state without changing or starting work'),
            ('pause', 'Let accepted work finish; prevent the next scientific node'),
            ('continue', 'Clear the next-node pause and run; never replay unknown work')):
        command = commands.add_parser(name, help=help_text)
        command.add_argument('--root', type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    try:
        if args.command == 'prepare':
            settings = controller.prepare(root, args.objective, args.public_root,
                json.loads(args.native_launcher_json), max_tokens=args.max_tokens, max_seconds=args.max_seconds,
                max_steps=args.max_steps, model=args.model, reasoning_effort=args.reasoning_effort,
                service_tier=args.service_tier, user_updates=args.user_update)
            result = dict(status='prepared', instance=str(root), goal_id=settings['goal_id'])
        elif args.command == 'status':
            result = status(root)
        elif args.command == 'pause':
            contracts.read(root / 'settings.json')
            contracts.write(root / 'pause.request', dict(reason='user_pause_at_next_node'))
            result = dict(status='pause_requested', accepted_work='allowed_to_finish_and_seal')
        elif args.command == 'continue':
            # Clear the marker only after obtaining the same per-instance writer
            # lock as run. A second caller cannot cancel a live owner's pause.
            with controller._writer(root):
                (root / 'pause.request').unlink(missing_ok=True)
                result = controller._run(root)
        else:
            result = controller.run(root)
    except (OSError, ValueError, RuntimeError) as error:
        print(json.dumps(dict(status='error', error=str(error)), ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get('status') in {None, 'prepared', 'finish', 'wait', 'paused', 'pause_requested'} else 2


if __name__ == '__main__':
    raise SystemExit(main())
