"""Development-only public action constraints, never an A or candidate chooser."""
from pathlib import Path
import argparse,hashlib,json,math
from scidiscovery.research_loop import selection


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def public_only(value):
    selection._public_keys(value)
    if isinstance(value,dict):
        if 'official_reward' in value:raise ValueError('non_public_field')
        for item in value.values():public_only(item)
    elif isinstance(value,list):
        for item in value:public_only(item)


def allowed_actions(view, *, request=None, source_status='unknown'):
    """Advice only: callers retain scientific judgment and all execution guards."""
    public_only(view);public_only(request)
    if source_status not in ('unknown','audit_pending','unavailable'):raise ValueError('Invalid public source status')
    if request is not None and (not isinstance(request,dict) or set(request)!={'action','candidate_id'}
            or request['action'] not in ('audit','recommend') or not isinstance(request['candidate_id'],str) or not request['candidate_id']):
        raise ValueError('Invalid declared public request')
    cid=request['candidate_id'] if request else None
    audit=next((item['status'] for item in view.get('public_audits',[]) if item['candidate_id']==cid),'unknown')
    next_step=('author_judgment' if cid is None else 'review_public_audit_failure' if audit=='public_audit_failed'
               else 'author_judgment' if audit=='public_audit_passed' else 'request_audit' if source_status=='audit_pending'
               else 'resolve_source_or_defer')
    return dict(scope='development_advice_only',target_rank='unknown',automatic_swap=False,automatic_elimination=False,
        target_support='author_must_explain_scope',audit_required=cid is not None and audit=='unknown',
        requested_audit_target=cid if request and request['action']=='audit' else None,
        audit_request_is_final_recommendation=False,next_step=next_step,
        unverified_resubmit_allowed=False,scientific_continuation_allowed=True,
        observed_proxy_groups=len(view.get('proxy_highest',[])),coverage=view.get('coverage','unknown'))


def export_public(manifest):
    """Only public ledgers and explicitly historical unbound audit metadata."""
    groups={}
    for group,meta in manifest['groups'].items():
        root=Path(meta['instance']);ledger=root/'runs/results.jsonl'
        if ledger.is_symlink() or ledger.resolve()!=ledger or ledger.stat().st_size>selection.MAX_INPUT_BYTES:raise ValueError('Bounded original public ledger required')
        data=ledger.read_bytes()
        if hashlib.sha256(data).hexdigest()!=meta['ledger_sha256']:raise ValueError('Frozen public ledger changed')
        rows=[json.loads(line) for line in data.splitlines() if line.strip()]
        seen=set();candidates=[];audit_records=[]
        # Public scoring implementation/data identity; no hidden conditions or scores.
        conditions={name:meta['public_conditions'][name] for name in ('train.csv','val.csv','meta.json','runner.py','exp_cli.py')}
        if any(not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value) for value in conditions.values()):raise ValueError('Invalid frozen public evaluation identity')
        version=hashlib.sha256(json.dumps(conditions,sort_keys=True).encode()).hexdigest()
        historical={row['run_id']:row.get('audit') for row in meta.get('candidates',[])}
        for row in rows:
            rid=row.get('run_id')
            if type(rid) is not int or rid<1 or rid in seen:raise ValueError('Ambiguous public run identity')
            seen.add(rid);metric=row.get('val_score',row.get('val_acc'))
            if metric is not None and (type(metric) not in (int,float) or not math.isfinite(metric)):raise ValueError('Invalid public metric')
            cid=f'run-{rid}'
            candidates.append(dict(id=cid,label=f'Public run {rid}',evaluation_key='public-val-'+version,
                metric=metric,direction='max',status='ok' if row.get('ok') is True else 'failed' if row.get('ok') is False else 'unknown'))
            historic=historical.get(rid)
            recorded=(isinstance(historic,dict) and type(historic.get('audit_score')) in (int,float) and math.isfinite(historic['audit_score']) and type(historic.get('leakage_flag')) is bool)
            audit_records.append(dict(candidate_id=cid,recorded_audit='recorded_unbound' if recorded else 'not_recorded',exact_audit='unknown'))
        actual=meta.get('actual_submission');actual_id=f'run-{actual}' if type(actual) is int and actual in seen else None
        record=dict(step=1,role='W',recommendation=None,coverage='partial',candidates=candidates,current_candidate=None,
                    actual_submission=dict(candidate_id=actual_id,artifact_retention='unknown') if actual_id else None)
        groups[group]=dict(records=[record],audits=[],delivery=None,historical_audits=audit_records,
            source_status='unknown',public_ledger_sha256=meta['ledger_sha256'],
            limitation='Final public pool snapshot, not a decision-time prefix. Historical audit does not bind the exact candidate. No A judgment is reconstructed.')
    return dict(scope='public_snapshot_development_only',groups=groups)


def replay(public):
    output={}
    for group,data in public['groups'].items():
        view=selection.project(data['records'],audits=data['audits'],delivery=data['delivery'])
        probes=[]
        for record in data['records']:
            for candidate in record['candidates']:
                request=dict(action='audit',candidate_id=candidate['id'])
                probes.append(dict(candidate_id=candidate['id'],synthetic_request=request,
                    advice=allowed_actions(view,request=request,source_status=data['source_status'])))
        output[group]=dict(candidate_count=view['candidate_count'],view=view,probes=probes,
            historical_audits=data['historical_audits'],choice_generated=False,reward_generated=False)
    return output


def main():
    p=argparse.ArgumentParser();p.add_argument('--pool-manifest',type=Path,required=True)
    p.add_argument('--rules-sha256',required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    if sha(__file__)!=args.rules_sha256:raise ValueError('Freeze rule source hash before opening development pool')
    if args.pool_manifest.stat().st_size>selection.MAX_INPUT_BYTES:raise ValueError('Bounded pool manifest required')
    manifest_data=args.pool_manifest.read_bytes();public=export_public(json.loads(manifest_data))
    args.output.mkdir(parents=True,exist_ok=False);write(args.output/'public-inputs.json',public)
    result=replay(public);write(args.output/'replay.json',result)
    report=dict(passed=True,rules_sha256=args.rules_sha256,manifest_sha256=hashlib.sha256(manifest_data).hexdigest(),model_requests=0,
        candidates=sum(data['candidate_count'] for data in result.values()),choices_generated=0,rewards_generated=0,
        limitation='Constraint/information-gap replay only. No A simulation, new choice, hidden scoring, tuning, or independent efficacy validation.')
    write(args.output/'report.json',report);print(json.dumps(report))


if __name__=='__main__':main()
