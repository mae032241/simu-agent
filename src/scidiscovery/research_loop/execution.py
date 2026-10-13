"""One immutable execution-reference seam for initial and continued native work."""
from pathlib import Path

from . import contracts as c


def origin(root, step):
    return c.host_record(c.workspace(root, step))


def proof(record):
    return {name: c.digest(c.regular(record / name)) for name in
            ('native-intent.json', 'native-outcome.json', 'usage.json')}


def records(root, step):
    root = Path(root)
    first = origin(root, step)
    result = [first]
    directory = first / 'continuations'
    if not directory.exists():return result
    if directory.resolve() != directory:raise ValueError('Native continuation directory changed')
    limit = c.settings(root).get('resume_policy', {}).get('max_attempts', 0)
    task = c.digest(c.regular(root / 'jobs' / f'{step:03d}.json'))
    if c.read(c.regular(first / 'native-intent.json')).get('task_sha256') != task:
        raise ValueError('Original native task identity changed')
    for number, path in enumerate(sorted(directory.iterdir()), 1):
        if path.name != f'{number:03d}' or path.resolve() != path or not path.is_dir() or number > limit:
            raise ValueError('Native continuation identity or sequence changed')
        if not (path / 'native-intent.json').exists():
            if any(path.iterdir()):raise ValueError('Unaccepted continuation has unexpected execution facts')
            continue
        intent = c.read(c.regular(path / 'native-intent.json'))
        if (number != len(result) or intent.get('attempt') != number or intent.get('task_sha256') != task
                or intent.get('previous') != proof(result[-1])
                or intent.get('root_intent_sha256') != c.digest(c.regular(first / 'native-intent.json'))):
            raise ValueError('Native continuation chain changed')
        result.append(path)
    return result


def reference(root, step):
    chain = records(root, step)
    if len(chain) == 1:return None
    return dict(attempt=len(chain) - 1, chain=[proof(path) for path in chain])


def record(root, step, attempt=None):
    chain = records(root, step)
    if attempt is not None:
        if type(attempt) is not int or not 0 <= attempt < len(chain):
            raise ValueError('Unknown exact native attempt')
        return chain[attempt]
    seal = origin(root, step) / 'result-identity.json'
    if seal.exists() and c.read(c.regular(seal)).get('execution_ref') != reference(root, step):
        raise ValueError('Sealed native execution reference changed')
    current = chain[-1]
    if len(chain) > 1 and (current / 'native-outcome.json').exists():
        outcome = c.read(c.regular(current / 'native-outcome.json'))
        if outcome.get('returncode') == 0 and not outcome.get('stop_reason'):
            _terminal(root, step, chain, outcome)
    return current


def raw(root, step):
    return record(root, step) / 'science-output.json'


def identity(root, step, attempt=None):
    path = record(root, step, attempt)
    return c.digest(path / 'native-intent.json') if path != origin(root, step) else c.digest(root / 'jobs' / f'{step:03d}.json')


def _terminal(root, step, chain, outcome):
    """A terminal continuation cannot rebind its accepted intent before seal."""
    current = chain[-1]
    binding = c.digest(c.regular(current / 'native-intent.json'))
    intent = c.read(current / 'native-intent.json')
    for name in ('runner-process.json', 'native-process.json'):
        path = c.regular(current / name)
        receipt = c.read(path)
        if (c.digest(path) != outcome.get('execution_processes', {}).get(name)
                or receipt.get('task_sha256') != binding
                or receipt.get('boot_id') != intent['budget_slice']['boot_id']
                or any(type(receipt.get(key)) is not int or receipt[key] <= 0
                       for key in ('pid', 'start_ticks', 'pgid', 'sid', 'ppid'))):
            raise ValueError('Terminal continuation differs from its accepted process identity')
    from . import budget
    budget._attempt_consumption(root, c.read(root / 'jobs' / f'{step:03d}.json'), chain)
    from . import continuation
    continuation.validate_repair_chain(root, step, chain)
