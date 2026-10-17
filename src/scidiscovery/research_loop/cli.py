"""Instance-oriented CLI: no interactive scheduler session or MCP dispatch."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import budget, contracts, controller, search
from .instance_control import status, request_pause, continue_instance


def main(argv=None):
    parser = argparse.ArgumentParser(prog='scid-research', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare', help='Create a fresh instance with explicit finite budgets')
    prepare.add_argument('--root', type=Path, required=True)
    prepare.add_argument('--objective', type=Path, required=True)
    prepare.add_argument('--user-update', type=Path, action='append', default=[], help='Freeze an additional user statement in global inputs; repeat for more')
    prepare.add_argument('--public-root', type=Path, required=True)
    prepare.add_argument('--source-restrictions', type=Path, help='Operator source declarations JSON array: exact absolute source, sha256, restriction (clear/restricted); source restrictions only, not review or execution permission')
    prepare.add_argument('--enable-formal-review', action='store_true', help='Allow an explicit A formal_review request for one selected scientific object; requires complete real native participant identities and grants no execution permission')
    prepare.add_argument('--enable-execution-authority', action='store_true', help='Freeze the optional execution request/decision contract; requires formal review and grants no execution without explicit resources and the trusted gate')
    prepare.add_argument('--execution-resource-policy', type=Path, help='Explicit version1 cumulative allowance JSON: wall_time_seconds/max_storage_bytes; no default grant')
    prepare.add_argument('--native-launcher-json', required=True, help='An argv JSON array, e.g. ["codex"]')
    prepare.add_argument('--history-observer-config', type=Path, help='Optional trusted host adapter/config JSON; frozen at preparation')
    prepare.add_argument('--experiment-mode', choices=['local', 'external'], help='Host-configured W execution (local) or launcher-owned execution (external); standard codex defaults to local, custom launchers to external')
    prepare.add_argument('--execution-config',type=Path,help='Public executor/configuration JSON for registered host-configured execution; no credentials or host identity fields; conflicts with external mode')
    prepare.add_argument('--search-policy', type=Path, help='Frozen W time/token targets (hard in hard mode) and hard requested-repair count')
    prepare.add_argument('--correction-policy', type=Path, help='Explicitly enable N4 with review_after/pause_after JSON thresholds (defaults 3/2)')
    prepare.add_argument('--node-budget-policy', type=Path, help='Explicit H/W/A/E time/token targets; hard ceilings only with --node-budget-mode hard; no delivery guarantee')
    prepare.add_argument('--node-budget-mode', choices=['soft','hard'], default='soft', help='Scientific node targets are soft by default; shared authorization stays hard')
    prepare.add_argument('--role-budget-policy', type=Path, help='Frozen W/H+A token shares and H/A node target JSON (null disables); disabled unless explicitly configured')
    prepare.add_argument('--selection-policy', type=Path, help='Frozen closeout shortlist size and smoke ceiling JSON (null disables); disabled unless explicitly configured')
    prepare.add_argument('--portfolio-review-after-cycles', type=int, help='Enable version2/protocol12 opportunity-cost review after this many unserved W+A cycles; recommended 3')
    prepare.add_argument('--decision-contract', action='store_true', help='Freeze protocol10 scientific A decision requests and exact repeat admission')
    prepare.add_argument('--enable-candidate-audit', action='store_true', help='Opt into protocol9 A audit requests; requires an isolated delivery adapter')
    prepare.add_argument('--delivery-policy', type=Path, help='Explicit frozen closeout reserve and isolated delivery adapter JSON')
    prepare.add_argument('--worker-context',choices=['same_session','new_context'],help='Qualified W fragments within the same stage; requires explicit resume policy and node budgets')
    prepare.add_argument('--worker-resume-policy', type=Path, help='Explicit qualified same-thread finite continuation policy JSON')
    prepare.add_argument('--max-output-item-bytes', type=int, help='Optional explicit per-file storage quota; default has no storage size cap')
    prepare.add_argument('--max-output-total-bytes', type=int, help='Optional explicit total deliverable storage quota; default has no storage size cap')
    prepare.add_argument('--max-tokens', type=int, required=True)
    prepare.add_argument('--max-seconds', type=float, required=True, help='Maximum authorized runtime: advancement and accepted execution waiting; idle pauses do not consume this ceiling')
    prepare.add_argument('--max-steps', type=int, required=True)
    prepare.add_argument('--model', default='gpt-6.1-sol')
    prepare.add_argument('--reasoning-effort', default='high')
    prepare.add_argument('--service-tier', default='default')
    prepare.add_argument('--role-profiles', type=Path, help='Optional H/W/A/E model, reasoning_effort and service_tier overrides; omitted roles/fields inherit global defaults')
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
    amend.add_argument('--execution-wall-seconds', type=int, help='Explicit cumulative execution ceiling; preserves prior reservations/usage and grants no exact-call permission')
    amend.add_argument('--execution-storage-bytes', type=int, help='Explicit cumulative execution storage ceiling; must accompany --execution-wall-seconds')
    amend.add_argument('--authorization-note', required=True, help='Operator decision for the audit; this text is not authentication')
    closeout = commands.add_parser('closeout', help='Close exploration within the original remaining authorization')
    closeout.add_argument('--root', type=Path, required=True)
    closeout.add_argument('--export-only', action='store_true', help='Export existing verified results without sealing, launching science or delivering')
    resume = commands.add_parser('worker-resume', help='Continue one known local failed node in its exact original thread')
    resume.add_argument('--root', type=Path, required=True)
    resume.add_argument('--step', type=int, required=True)
    recover=commands.add_parser('execution-recover',help='Append same-call terminal evidence for a sealed unknown; new nodes freeze its recovery prefix')
    recover.add_argument('--root',type=Path,required=True)
    recover.add_argument('--step',type=int,required=True)
    execution_resume=commands.add_parser('execution-resume',help='Explicit finite host progress of one original sealed W call; never replay uncertain preparation')
    execution_resume.add_argument('--root',type=Path,required=True)
    execution_resume.add_argument('--step',type=int,required=True)
    execution_resume.add_argument('--call-id',required=True)
    execution_resume.add_argument('--max-seconds',type=float,required=True,help='Current finite control operation window; does not extend solver or shared authorization')
    execution_resume.add_argument('--authorization-note',required=True,help='Operator audit note only; not an execution decision')
    execution_resume.add_argument('--request-valid-seconds',type=float,help='Explicit finite replacement request validity when old request expired; no new execution allowance')
    serve = commands.add_parser('serve-ui', help='Serve this explicit instance status and controls, with optional execution approval pages')
    serve.add_argument('--root', type=Path, required=True)
    serve.add_argument('--approval-secret-file', type=Path, required=True, help='Operator-owned regular 0600 browser host key; approval routes additionally require frozen authority')
    serve.add_argument('--port', type=int, default=0, help='Loopback port; default selects an available port')
    export = commands.add_parser('archive-export', help='Copy quiescent framework originals to a new inert read-only directory package; no writable restore')
    export.add_argument('--root', type=Path, required=True)
    export.add_argument('--output', type=Path, required=True)
    inspect = commands.add_parser('archive-inspect', help='Verify a read-only package and page its complete manifest without running code or importing plugins')
    inspect.add_argument('--package', type=Path, required=True)
    inspect.add_argument('--after', type=int, default=0, help='Exact prior entry index; default starts at the first entry')
    inspect.add_argument('--limit', type=int, default=20, help='Returned page size; all package bytes are still verified')
    inspect.add_argument('--section', choices=['manifest', 'dependencies'], default='manifest')
    args = parser.parse_args(argv)
    root = (args.root.expanduser().absolute() if args.command == 'archive-export' else
            args.root.expanduser().resolve()) if args.command != 'archive-inspect' else None
    try:
        if args.command not in {'prepare','status','archive-inspect'}:
            from .protocol import require_current
            require_current(root)
        if args.command == 'prepare':
            role_profiles = None
            if args.role_profiles is not None:
                role_profiles = contracts.read(contracts.regular(args.role_profiles, limit=4096))
                if not isinstance(role_profiles, dict):
                    raise ValueError('Role profiles file must contain a JSON object')
            settings = controller.prepare(root, args.objective, args.public_root,
                json.loads(args.native_launcher_json), max_tokens=args.max_tokens, max_seconds=args.max_seconds,
                max_steps=args.max_steps, max_output_item_bytes=args.max_output_item_bytes, max_output_total_bytes=args.max_output_total_bytes, model=args.model, reasoning_effort=args.reasoning_effort, node_budget_mode=args.node_budget_mode,
                service_tier=args.service_tier, user_updates=args.user_update,
                role_profiles=role_profiles,
                experiment_mode=args.experiment_mode,
                execution_config=contracts.read(contracts.regular(args.execution_config)) if args.execution_config is not None else None,
                source_restrictions=contracts.read(contracts.regular(args.source_restrictions)) if args.source_restrictions is not None else None,
                formal_review_policy=dict(version=1) if args.enable_formal_review else None,
                execution_authority_policy=dict(version=1) if args.enable_execution_authority else None,
                execution_resource_policy=contracts.read(contracts.regular(args.execution_resource_policy)) if args.execution_resource_policy is not None else None,
                candidate_audit_policy={'version':1} if args.enable_candidate_audit else None,
                decision_contract_version=1 if args.decision_contract else None,
                portfolio_policy=dict(review_after_cycles=args.portfolio_review_after_cycles) if args.portfolio_review_after_cycles is not None else None,
                search_policy=contracts.read(contracts.regular(args.search_policy, limit=4096))
                    if args.search_policy is not None else search.DEFAULT_POLICY,
                correction_policy=contracts.read(contracts.regular(args.correction_policy, limit=4096))
                    if args.correction_policy is not None else None,
                node_budget_policy=contracts.read(contracts.regular(args.node_budget_policy, limit=4096))
                    if args.node_budget_policy is not None else None,
                delivery_policy=contracts.read(contracts.regular(args.delivery_policy, limit=64_000))
                    if args.delivery_policy is not None else None,
                worker_fragment_policy=dict(context=args.worker_context) if args.worker_context else None,
                role_budget_policy=contracts.read(contracts.regular(args.role_budget_policy, limit=4096))
                    if args.role_budget_policy is not None else None,
                selection_policy=contracts.read(contracts.regular(args.selection_policy, limit=4096))
                    if args.selection_policy is not None else None,
                resume_policy=contracts.read(contracts.regular(args.worker_resume_policy, limit=4096))
                    if args.worker_resume_policy is not None else None,
                history_observer=contracts.read(contracts.regular(args.history_observer_config, limit=64_000))
                    if args.history_observer_config is not None else None)
            result = dict(status='prepared', instance=str(root), goal_id=settings['goal_id'])
            if settings.get('execution_config') is not None:
                result['execution']=dict(executor=settings['execution_config']['executor'],
                    capabilities_status='awaiting_host_task_configuration')
        elif args.command == 'serve-ui':
            if not 0 <= args.port <= 65535:
                raise ValueError('UI port must be between 0 and 65535')
            from . import instance_ui
            result = instance_ui.serve(root, secret_file=args.approval_secret_file, port=args.port)
        elif args.command == 'archive-export':
            from .instance_archive import archive_export
            result = archive_export(root, args.output)
        elif args.command == 'archive-inspect':
            from .instance_archive import archive_inspect
            result = archive_inspect(args.package, after=args.after, limit=args.limit, section=args.section)
        elif args.command == 'execution-recover':
            result=controller.execution_recover(root,args.step)
        elif args.command == 'execution-resume':
            result=controller.execution_resume(root,args.step,args.call_id,max_seconds=args.max_seconds,
                authorization_note=args.authorization_note,request_valid_seconds=args.request_valid_seconds)
        elif args.command == 'worker-resume':
            result = controller.worker_resume(root, args.step)
        elif args.command == 'status':
            result = status(root)
        elif args.command == 'closeout':
            result = controller.closeout(root, export_only=args.export_only)
        elif args.command == 'budget-amend':
            resource_change = args.execution_wall_seconds is not None or args.execution_storage_bytes is not None
            if resource_change and (args.execution_wall_seconds is None or args.execution_storage_bytes is None):
                raise ValueError('Execution resource amendment requires both explicit dimensions')
            if resource_change and (args.max_tokens is not None or args.max_seconds is not None):
                raise ValueError('Amend scientific or execution ceilings in one explicit operation at a time')
            if resource_change:
                grant = budget.amend_execution_grant(root, allowance=dict(wall_time_seconds=args.execution_wall_seconds,
                    max_storage_bytes=args.execution_storage_bytes), authorization_note=args.authorization_note)
                result = dict(status='budget_amended', execution_resources=grant,
                              permission='Ceiling configuration only; no exact-call execution decision')
            else:
                result = budget.amend(root, max_tokens=args.max_tokens, max_seconds=args.max_seconds,
                                      authorization_note=args.authorization_note)
        elif args.command == 'pause':
            result = request_pause(root)
        elif args.command == 'continue':
            result = continue_instance(root, ack_correction=args.ack_correction,
                                       authorization_note=args.authorization_note)
        else:
            result = controller.run(root)
    except (OSError, ValueError, RuntimeError) as error:
        from .protocol import UnsupportedProtocol
        print(json.dumps(dict(status='error',error=str(error),**(dict(code=error.code) if isinstance(error,UnsupportedProtocol) else {})), ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get('status') in {None, 'preserved_read_only', 'prepared', 'finish', 'wait', 'paused', 'pause_requested', 'budget_amended', 'delivery_confirmed', 'execution_recovered', 'execution_resume_recorded', 'exported_unsubmitted', 'ui_stopped', 'archive_exported', 'archive_inspected'} else 2


if __name__ == '__main__':
    raise SystemExit(main())
