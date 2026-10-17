"""Opt-in exact-subject review through the existing native A node lifecycle.

These host facts grant review qualification only. They do not grant execution,
renew budgets, or establish independence for unobserved native helpers.
"""
import hashlib
import json
from pathlib import Path
from typing import get_args

from ..operations import review_rules
from . import contracts as c, execution, qualification as q


def schema():
    fields = dict(verdict=dict(type='string', enum=list(get_args(review_rules.ReviewVerdict))),
        summary=dict(type='string', minLength=1), scientific_result=dict(type='string', minLength=1),
        limitations=dict(type='array', items=dict(type='string')))
    return dict(type='object', properties=fields, required=list(fields), additionalProperties=False)


def configuration(value):
    if value is not None and (not isinstance(value,dict) or value != {'version': 1} or type(value.get('version')) is not int):
        raise ValueError('Formal review requires the explicit version 1 operator policy')
    return value


def _contract():
    files = [Path(__file__), Path(review_rules.__file__), Path(c.__file__).with_name('native.py'),
             Path(c.__file__).with_name('continuation.py')]
    return dict(version=1, instruction=review_rules.REVIEW_INSTRUCTION,
        scope='Review only the exact supplied material and scientific question. Do not edit the subject. '
              'Use revise, blocked or inconclusive for unsupported claims. Review grants no execution permission.',
        schema=schema(), authors_contract='native_participants_and_selected_implementations_v1',
        implementation=[q._identity(path.resolve()) for path in files])


def freeze_contract(root):
    root = Path(root).resolve()
    return dict(version=1, contract=q._save(root, root / 'qualification/review-contract.json', _contract()))


def contract(root):
    policy = c.settings(root).get('formal_review_policy')
    if policy is None:
        return None
    if q._read(root, policy['contract']) != _contract():
        raise q.IntegrityError('Current formal review contract differs from its frozen original')
    return policy['contract']


def capture_participants(root, job):
    """Retain actual native identity, never inferred from role or subject inputs."""
    root = Path(root).resolve()
    from . import continuation
    rows, participants, complete = [], set(), True
    for number, record in enumerate(execution.records(root, job['step'])):
        outcome = c.read(c.regular(record / 'native-outcome.json'))
        row = dict(attempt=number, intent=q._ref(root, record / 'native-intent.json'),
                   outcome=q._ref(root, record / 'native-outcome.json'))
        binding = outcome.get('native_identity') or {}
        try:
            if binding.get('participant_scope') != 'codex_exec_single_agent_v1' or not binding.get('path'):
                raise ValueError('native_participant_identity_unsupported')
            original = continuation.session(root, job['step'], record, home=binding['home'],
                session_path=binding['path'], identity_proof=True)
            with c.regular(Path(original['path'])).open('rb') as stream:
                line = stream.readline()
            if hashlib.sha256(line).hexdigest() != original['header_sha256']:
                raise q.IntegrityError('Native session header changed before retention')
            path = c.host_record(c.workspace(root, job['step'])) / 'authorship' / f'{number:03d}.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                if c.regular(path).read_bytes() != line:
                    raise q.IntegrityError('Retained native identity changed')
            else:
                path.write_bytes(line)
                path.chmod(0o400)
            identity = ('codex_exec', original['thread_id'])
            participants.add(identity)
            row.update(status='known', participant=list(identity), session=original, header=q._ref(root, path))
        except q.IntegrityError:
            raise
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            complete = False
            row.update(status='unsupported', reason=str(error))
        rows.append(row)
    return q._save(root, c.host_record(c.workspace(root, job['step'])) / 'native-authorship.json',
        dict(version=1, complete=complete and bool(rows), participants=[list(row) for row in sorted(participants)],
             attempts=rows, scope='Actual controlled native participants only; arbitrary shell work remains outside this proof.'))


def participants(root, job, seal):
    ref = seal.get('native_authorship')
    if ref is None:
        return dict(complete=False, participants=[], reason='native_identity_unavailable')
    proof = q._read(root, ref)
    chain = execution.records(root, job['step'])
    if len(proof['attempts']) != len(chain):
        raise q.IntegrityError('Authorship omits a native attempt or context')
    found, complete = set(), True
    from . import continuation
    for number, (row, record) in enumerate(zip(proof['attempts'], chain)):
        if (row['attempt'] != number or row['intent'] != q._ref(root, record / 'native-intent.json')
                or row['outcome'] != q._ref(root, record / 'native-outcome.json')):
            raise q.IntegrityError('Authorship differs from its original native attempt')
        if row['status'] != 'known':
            complete = False
            continue
        outcome = q._read(root, row['outcome'])
        if outcome.get('native_identity', {}).get('participant_scope') != 'codex_exec_single_agent_v1':
            raise q.IntegrityError('Authorship has no complete native participant scope')
        identity = ('codex_exec', outcome['thread_id'])
        header = root / row['header']['path']
        q._check({**row['header'], 'path': str(header)})
        continuation.validate_session_header(header.read_bytes(), identity[1], c.workspace(root, job['step']))
        if row['participant'] != list(identity) or row['session']['thread_id'] != identity[1]:
            raise q.IntegrityError('Authorship participant identity changed')
        found.add(identity)
    expected = [list(row) for row in sorted(found)]
    if proof['participants'] != expected or proof['complete'] != (complete and bool(chain)):
        raise q.IntegrityError('Authorship completeness differs from its native originals')
    return dict(complete=proof['complete'], participants=expected,
                reason=None if proof['complete'] else 'native_identity_unavailable')


def authors(root, step, active=None, memo=None):
    """Only exact producer and declared implementation contributors are authors."""
    active, memo = set() if active is None else active, {} if memo is None else memo
    if step in active:
        return dict(complete=False, participants=[], reason='authorship_cycle')
    if step in memo:
        return memo[step]
    job = c.read(c.regular(root / 'jobs' / f'{step:03d}.json'))
    seal = c.read(c.regular(c.host_record(c.workspace(root, step)) / 'result-identity.json'))
    own = participants(root, job, seal)
    people = {tuple(row) for row in own['participants']}
    complete = own['complete']
    source = seal.get('source_provenance')
    if source is not None and q._read(root, source).get('missing_reason') is not None:
        complete = False  # No trusted authorship adapter for observed call inputs.
    if not job.get('formal_review'):
        for selected in job.get('selected_inputs', []):
            origin = selected['origin_step']
            origin_seal = c.read(c.regular(c.host_record(c.workspace(root, origin)) / 'result-identity.json'))
            if selected['material'] not in origin_seal['materials'] or selected['origin_result_sha256'] != origin_seal['sha256']:
                raise q.IntegrityError('Declared author contribution differs from its exact producer')
            contributor = authors(root, origin, {*active, step}, memo)
            complete = complete and contributor['complete']
            people.update(tuple(row) for row in contributor['participants'])
    value = dict(complete=complete, participants=[list(row) for row in sorted(people)],
                 reason=None if complete else 'subject_authorship_unsupported')
    memo[step] = value
    return value


def _subject(root, selected):
    if len(selected) != 1:
        return None
    item = selected[0]
    step = item['origin_step']
    c.validate(c.workspace(root, step))
    path = c.host_record(c.workspace(root, step)) / 'result-identity.json'
    seal = c.read(path)
    if item['material'] not in seal['materials'] or item['origin_result_sha256'] != seal['sha256']:
        raise q.IntegrityError('Formal review subject differs from its exact producer')
    return dict(producer_step=step, producer_seal=q._ref(root, path), material=item['material'])


def request_route(root, job, payload, parents):
    root = Path(root).resolve()
    current = contract(root)
    seal_path = c.host_record(c.workspace(root, job['step'])) / 'result-identity.json'
    seal = c.read(c.regular(seal_path))
    selected = seal.get('selected_inputs', [])
    subject = _subject(root, selected)
    identity = authors(root, subject['producer_step']) if subject else dict(complete=False, participants=[])
    launcher = c.settings(root)['native_launcher_argv']
    reason = ('formal_review_subject_missing_or_ambiguous' if subject is None else
              'subject_authorship_unsupported' if not identity['complete'] else
              'reviewer_identity_unsupported' if len(launcher)!=1 or Path(launcher[0]).name!='codex' else None)
    value = dict(contract=current, question=payload['route_reason'], subject=subject,
                 authors=identity, unresolved_selection=selected if subject is None else None, reason=reason)
    requester = dict(step=job['step'], seal=q._ref(root, seal_path))
    record = c.host_record(c.workspace(root, job['step']))
    if reason is not None:
        failure_key={key:value[key] for key in ('contract','subject','authors','unresolved_selection','reason')}
        previous = (job.get('evidence_return') or {}).get('unavailable')
        repeat = previous is not None and q._read(root, previous)['failure_key'] == failure_key
        ref = q._save(root, record / 'formal-review-unavailable.json', dict(requester=requester, failure=value,failure_key=failure_key))
        return (None if repeat else 'A', parents, 'Choose a scientific next action; formal review is unavailable: '+reason,
                dict(kind='formal_review_unavailable', unavailable=ref))
    ref = q._save(root, record / 'formal-review-request.json', dict(requester=requester, **value))
    return 'A', sorted(set([*parents, subject['producer_step']])), value['question'], dict(kind='formal_review', request=ref)


def bind_job(root, job):
    back = job.get('evidence_return') or {}
    if back.get('kind') != 'formal_review':
        return
    if job['role'] != 'A' or contract(root) is None:
        raise q.IntegrityError('Formal review requires its explicit frozen operator contract')
    request = q._read(root, back['request'])
    if request['contract'] != contract(root) or request['requester']['step'] >= job['step']:
        raise q.IntegrityError('Formal review request contract or requester changed')
    q._read(root, request['requester']['seal'])
    q._read(root, request['subject']['producer_seal'])
    job.update(purpose='formal_review', formal_review=back['request'])


def validate_job(root, job):
    back = job.get('evidence_return') or {}
    if job.get('formal_review') or back.get('kind')=='formal_review':
        expected=dict(job)
        bind_job(root,expected)
        if (expected.get('formal_review')!=job.get('formal_review') or job.get('purpose')!='formal_review'):
            raise q.IntegrityError('Formal review task differs from its frozen request')
        request=q._read(root,job['formal_review'])
        subject=request['subject']
        if job['instruction']!=request['question'] or subject['material'] not in job['direct_materials'] or not any(
                ref['path']==f'inputs/parents/{request["requester"]["step"]:03d}/conclusion.json' for ref in job['direct_refs']):
            raise q.IntegrityError('Formal review task omitted its exact subject or requester')
    if job.get('formal_review_version')==1 and contract(root) is None:
        raise q.IntegrityError('Formal review task lost its operator contract')


def feedback(root, job):
    back=job.get('evidence_return') or {}
    if back.get('kind')=='formal_review_unavailable':
        failure=q._read(root,back['unavailable'])['failure']
        return dict(status='unavailable',reason=failure['reason'],
                    instruction='Choose another scientific action unless the subject or missing identity evidence changes; an unchanged unavailable request waits without another native launch.')
    if back.get('kind')=='formal_review_return':
        proof=q._read(root,back['review'])
        return dict(status=proof['status'],verdict=proof['verdict'],independence=proof['independence'],
                    scope='This exact review only; no execution permission.')
    return None


def public(root, job):
    request = q._read(root, job['formal_review'])
    material = request['subject']['material']
    return dict(role='A', question=request['question'],
        review=dict(subject=material['path'], instruction=_contract()['instruction'],
                    scope=_contract()['scope']),
        global_inputs=[row['path'] for row in job['global_materials']],
        final_response=list(schema()['properties']), outputs='artifacts/')


def _qualification(root, job, payload, seal):
    request = q._read(root, job['formal_review'])
    subject = request['subject']
    q._read(root, subject['producer_seal'])
    current_authors = authors(root, subject['producer_step'])
    if request['contract'] != contract(root) or request['authors'] != current_authors:
        raise q.IntegrityError('Formal review contract or subject authors changed')
    reviewer = participants(root, job, seal)
    independent = review_rules.independence(
        [tuple(row) for row in current_authors['participants']], [tuple(row) for row in reviewer['participants']],
        authors_complete=current_authors['complete'], reviewers_complete=reviewer['complete'])
    return dict(version=1, review_step=job['step'], subject=subject, request=job['formal_review'],
        contract=request['contract'], authors=current_authors, reviewer=reviewer,
        native_authorship=seal.get('native_authorship'), raw_sha256=seal['raw_sha256'], result_sha256=seal['sha256'],
        verdict=payload['verdict'], independence=independent,
        status='passed' if independent=='independent' and payload['verdict']=='pass' else 'not_qualified')


def seal_review(root, job, payload, seal):
    return q._save(root, c.host_record(c.workspace(root, job['step'])) / 'formal-review.json',
                   _qualification(root, job, payload, seal))


def validate_seal(root, job, payload, seal):
    if job.get('formal_review_version')==1 and 'native_authorship' not in seal:
        raise q.IntegrityError('Sealed task lost its native authorship original')
    if 'native_authorship' in seal:
        participants(root, job, seal)
    if job.get('formal_review'):
        ref = seal.get('formal_review')
        if ref is None or q._read(root, ref) != _qualification(root, job, payload, seal):
            raise q.IntegrityError('Formal review qualification differs from its sealed originals')


def return_route(root, job, parents):
    request = q._read(root, job['formal_review'])
    seal = c.read(c.host_record(c.workspace(root, job['step'])) / 'result-identity.json')
    return 'A', sorted(set([*parents, request['requester']['step'], job['step']])), \
        'Use the exact formal review findings and limitations to choose the scientific next action.', \
        dict(kind='formal_review_return', review=seal['formal_review'])


def require_review(root, subject, receipt):
    """Future P3 gate consumes an explicit exact receipt; never a latest lookup."""
    root=Path(root).resolve()
    proof = q._read(root, receipt)
    job = c.read(c.regular(root / 'jobs' / f'{proof["review_step"]:03d}.json'))
    c.validate(c.workspace(root, job['step']))
    seal = c.read(c.host_record(c.workspace(root, job['step'])) / 'result-identity.json')
    if (seal.get('formal_review') != receipt or proof['subject'] != subject
            or proof['contract'] != contract(root) or proof['status'] != 'passed'):
        raise ValueError('Exact subject has no compatible independent sealed pass')
    return receipt
