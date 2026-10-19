"""Read-only step ceilings use immutable amendments, never current metering."""
import pytest

from scidiscovery.research_loop import budget, contracts as c, controller, native


@pytest.fixture
def amended(tmp_path):
    public = tmp_path / 'public';public.mkdir()
    objective = public / 'objective.md';objective.write_text('Retain exact originals under finite amended limits.')
    root = tmp_path / 'instance'
    controller.prepare(root, objective, public, ['fixture-never-launch'], max_tokens=1000,
        max_seconds=200, max_steps=5, model='fixture', reasoning_effort='high')
    return root


def revise(root):
    budget.amend(root, max_tokens=1200, max_steps=24, authorization_note='Finite review allowance.',
        authorization_statement='Finish the retained work.')
    budget.amend(root, max_tokens=1300, authorization_note='Revise only the cumulative token ceiling.')
    budget.amend(root, max_steps=12, authorization_note='Reduce the remaining control ceiling.',
        authorization_statement='Keep the review bounded.')


@pytest.mark.parametrize('has_amendments', [False, True])
def test_step_ceiling_is_readonly_without_current_clock_usage_or_snapshot(amended, monkeypatch, has_amendments):
    root = amended
    if has_amendments:
        revise(root)
    expected = 12 if has_amendments else 5
    assert budget.snapshot(root)['max_steps'] == expected
    originals = {path: path.read_bytes() for path in root.rglob('*') if path.is_file()}
    def forbidden(*args, **kwargs):
        pytest.fail('A read-only step ceiling must not sample current time or consumption')
    monkeypatch.setattr(budget, 'snapshot', forbidden)
    monkeypatch.setattr(budget, 'clock_stamp', forbidden)
    monkeypatch.setattr(native, 'usage', forbidden)
    assert budget.effective_max_steps(root) == expected
    assert budget.step_limit(root) == expected
    assert {path: path.read_bytes() for path in root.rglob('*') if path.is_file()} == originals
    assert c.settings(root)['max_steps'] == 5


@pytest.mark.parametrize('changed,reason', [
    ('tokens_predecessor', 'Budget amendment predecessor changed'),
    ('steps_predecessor', 'Budget step amendment predecessor changed'),
    ('step_delta', 'Audited step amendment delta changed'),
    ('settings', 'Frozen instance settings changed'),
])
def test_readonly_step_ceiling_and_snapshot_reject_the_same_amendment_tamper(amended, monkeypatch, changed, reason):
    root = amended
    revise(root)
    if changed == 'settings':
        path = root / 'settings.json'
        value = c.read(path);value['max_steps'] = 24
    else:
        path = root / 'control-ledger/000003.json'
        value = c.read(path)
        if changed == 'tokens_predecessor':
            value['before']['max_tokens'] += 1
        elif changed == 'steps_predecessor':
            value['before_max_steps'] = 23
            value['max_steps_delta'] = value['after_max_steps'] - 23
        else:
            value['max_steps_delta'] += 1
    c.write(path, value)
    originals = {item: item.read_bytes() for item in root.rglob('*') if item.is_file()}
    def forbidden(*args, **kwargs):
        pytest.fail('Invalid immutable ceilings must be rejected before sampling current time')
    monkeypatch.setattr(budget, 'clock_stamp', forbidden)
    monkeypatch.setattr(native, 'usage', forbidden)
    for read in (budget.effective_max_steps, budget.snapshot):
        with pytest.raises(ValueError, match=reason):
            read(root)
    assert {item: item.read_bytes() for item in root.rglob('*') if item.is_file()} == originals
