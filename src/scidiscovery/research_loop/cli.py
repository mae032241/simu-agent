"""Instance-oriented CLI: no interactive scheduler session or MCP dispatch."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import budget, contracts, controller, native, runtime, search, correction, execution


def status(root: Path):
    root = root.resolve()
    settings = contracts.read(root / 'settings.json')
    nodes = []
    for step in range(1, settings['max_steps'] + 1):
        job_path = root / 'jobs' / f'{step:03d}.json'
        if not job_path.exists():
            break
        job = contracts.read(job_path)
        state = runtime.node_state(root, step)
        state = {'sealed': 'seal_present_unverified', 'terminal': 'native_outcome_unsealed',
                 'unstarted': 'prepared'}.get(state, state)
        if state == 'native_outcome_unsealed':
            outcome = contracts.read(execution.record(root, step) / 'native-outcome.json')
            if outcome.get('native_started') is False:
                state = 'native_not_submitted'
        node = dict(step=step, role=job['role'], state=state)
        if settings.get('node_budget_policy') is not None:
            record = execution.record(root, step)
            intent = contracts.read(record / 'native-intent.json') if (record / 'native-intent.json').exists() else {}
            outcome = contracts.read(record / 'native-outcome.json') if (record / 'native-outcome.json').exists() else {}
            node.update(**(dict(node_budget_mode='soft') if budget.node_mode(root)=='soft' else {}), budget_slice=intent.get('budget_slice'), budget_report=outcome.get('budget_slice'), stop_reason=outcome.get('stop_reason'))
        if settings.get('resume_policy') is not None:
            node['continuations'] = len(execution.records(root, step)) - 1
        nodes.append(node)
    closeout = budget.closeout_state(root)
    return dict(instance=str(root), goal_id=settings['goal_id'], objective=settings['objective'],
                paused=(root / 'pause.request').exists(), nodes=nodes, usage=native.usage(root),
                goal_completion='not_asserted', budget=budget.snapshot(root),
                correction=correction.project(root, before_step=closeout['begin']['source_cutoff'] + 1 if closeout['begin'] else None),
                closeout=controller._closeout_result(root, 'closeout_status', read_only=True) if closeout['begin'] else None)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='scid-research', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare', help='Create a fresh instance with explicit finite budgets')
    prepare.add_argument('--root', type=Path, required=True)
    prepare.add_argument('--objective', type=Path, required=True)
    prepare.add_argument('--user-update', type=Path, action='append', default=[], help='Freeze an additional user statement in global inputs; repeat for more')
    prepare.add_argument('--public-root', type=Path, required=True)
    prepare.add_argument('--native-launcher-json', required=True, help='An argv JSON array, e.g. ["codex"]')
    prepare.add_argument('--history-observer-config', type=Path, help='Optional trusted host adapter/config JSON; frozen at preparation')
    prepare.add_argument('--search-policy', type=Path, help='Frozen W time/token targets (hard in hard mode) and hard requested-repair count')
    prepare.add_argument('--correction-policy', type=Path, help='Explicitly enable N4 with review_after/pause_after JSON thresholds (defaults 3/2)')
    prepare.add_argument('--node-budget-policy', type=Path, help='Explicit H/W/A/E time/token targets; hard ceilings only with --node-budget-mode hard; no delivery guarantee')
    prepare.add_argument('--node-budget-mode', choices=['soft','hard'], default='soft', help='Scientific node targets are soft by default; shared authorization stays hard')
    prepare.add_argument('--portfolio-review-after-cycles', type=int, help='Enable version2/protocol12 opportunity-cost review after this many unserved W+A cycles; recommended 3')
    prepare.add_argument('--exploration-order', action='store_true', help='Enable protocol13 execution of scientific exploration order; requires explicit portfolio review')
    prepare.add_argument('--decision-contract', action='store_true', help='Freeze protocol10 scientific A decision requests and exact repeat admission')
    prepare.add_argument('--enable-candidate-audit', action='store_true', help='Opt into protocol9 A audit requests; requires an isolated delivery adapter')
    prepare.add_argument('--delivery-policy', type=Path, help='Explicit frozen closeout reserve and isolated delivery adapter JSON')
    prepare.add_argument('--worker-resume-policy', type=Path, help='Explicit qualified same-thread finite continuation policy JSON')
    prepare.add_argument('--max-tokens', type=int, required=True)
    prepare.add_argument('--max-seconds', type=float, required=True, help='Maximum advancement seconds; explicit pauses do not consume this ceiling')
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
        if name == 'continue':
            command.add_argument('--ack-correction', help='Exact current published pause trigger ID; permits one nondeferred A cycle')
            command.add_argument('--authorization-note', help='External operator decision; not authentication or a budget amendment')
    amend = commands.add_parser('budget-amend', help='Record an external operator ceiling revision without resetting consumption')
    amend.add_argument('--root', type=Path, required=True)
    amend.add_argument('--max-tokens', type=int)
    amend.add_argument('--max-seconds', type=float)
    amend.add_argument('--authorization-note', required=True, help='Operator decision for the audit; this text is not authentication')
    closeout = commands.add_parser('closeout', help='Close exploration within the original remaining authorization')
    closeout.add_argument('--root', type=Path, required=True)
    closeout.add_argument('--export-only', action='store_true', help='Export existing verified results without sealing, launching science or delivering')
    resume = commands.add_parser('worker-resume', help='Continue one known local failed node in its exact original thread')
    resume.add_argument('--root', type=Path, required=True)
    resume.add_argument('--step', type=int, required=True)
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    try:
        if args.command == 'prepare':
            settings = controller.prepare(root, args.objective, args.public_root,
                json.loads(args.native_launcher_json), max_tokens=args.max_tokens, max_seconds=args.max_seconds,
                max_steps=args.max_steps, model=args.model, reasoning_effort=args.reasoning_effort, node_budget_mode=args.node_budget_mode,
                service_tier=args.service_tier, user_updates=args.user_update,
                candidate_audit_policy={'version':1} if args.enable_candidate_audit else None,
                decision_contract_version=1 if args.decision_contract else None,
                portfolio_policy=dict(review_after_cycles=args.portfolio_review_after_cycles) if args.portfolio_review_after_cycles is not None else None,
                exploration_order_version=1 if args.exploration_order else None,
                search_policy=contracts.read(contracts.regular(args.search_policy, limit=4096))
                    if args.search_policy is not None else search.DEFAULT_POLICY,
                correction_policy=contracts.read(contracts.regular(args.correction_policy, limit=4096))
                    if args.correction_policy is not None else None,
                node_budget_policy=contracts.read(contracts.regular(args.node_budget_policy, limit=4096))
                    if args.node_budget_policy is not None else None,
                delivery_policy=contracts.read(contracts.regular(args.delivery_policy, limit=64_000))
                    if args.delivery_policy is not None else None,
                resume_policy=contracts.read(contracts.regular(args.worker_resume_policy, limit=4096))
                    if args.worker_resume_policy is not None else None,
                history_observer=contracts.read(contracts.regular(args.history_observer_config, limit=64_000))
                    if args.history_observer_config is not None else None)
            result = dict(status='prepared', instance=str(root), goal_id=settings['goal_id'])
        elif args.command == 'worker-resume':
            result = controller.worker_resume(root, args.step)
        elif args.command == 'status':
            result = status(root)
        elif args.command == 'closeout':
            result = controller.closeout(root, export_only=args.export_only)
        elif args.command == 'budget-amend':
            result = budget.amend(root, max_tokens=args.max_tokens, max_seconds=args.max_seconds,
                                  authorization_note=args.authorization_note)
        elif args.command == 'pause':
            contracts.read(root / 'settings.json')
            contracts.write(root / 'pause.request', dict(reason='user_pause_at_next_node'))
            try:
                with controller._writer(root):
                    budget.inactive(root, 'operator_pause')
            except RuntimeError:
                pass  # Accepted work retains advance time; its owner will pause.
            result = dict(status='pause_requested', accepted_work='allowed_to_finish_and_seal')
        elif args.command == 'continue':
            # Clear the marker only after obtaining the same per-instance writer
            # lock as run. A second caller cannot cancel a live owner's pause.
            with controller._writer(root):
                if args.ack_correction is not None:
                    correction.acknowledge(root, args.ack_correction, args.authorization_note)
                elif args.authorization_note is not None:
                    raise ValueError('An authorization note requires an exact correction trigger')
                (root / 'pause.request').unlink(missing_ok=True)
                result = controller._run(root)
        else:
            result = controller.run(root)
    except (OSError, ValueError, RuntimeError) as error:
        print(json.dumps(dict(status='error', error=str(error)), ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get('status') in {None, 'prepared', 'finish', 'wait', 'paused', 'pause_requested', 'budget_amended', 'delivery_confirmed', 'exported_unsubmitted'} else 2


if __name__ == '__main__':
    raise SystemExit(main())
