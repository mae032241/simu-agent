"""Production Root read authority and native Worker/UI compatibility."""


def structured_catalog():
    from blind_csv_plugin.plugin import PLUGIN
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as GENERAL
    from scidiscovery.operations.catalog import compile_catalog
    author = PLUGIN.operations[0].model_copy(update={'decision_fields': ('structure', 'interpretation', 'limitations')})
    return compile_catalog((CORE_PLUGIN, GENERAL,
        PLUGIN.model_copy(update={'operations': (author, *PLUGIN.operations[1:])})))


def compiled_role(operation_id):
    from scidiscovery.operations.tooling import operation_role_instructions
    return operation_role_instructions(structured_catalog().operation(operation_id))


def test_compiled_worker_method_freedom_does_not_authorize_changed_hypotheses_or_data():
    prompt = compiled_role('science.experiment.v1')
    assert 'continuously try related parameters, implementations, numerical' in prompt
    assert "H's declared mechanisms, key assumptions, allowed data and validation" in prompt
    assert 'then H revision before executing the new' in prompt
    assert 'must not execute a new direction on that basis' in prompt
    assert 'Genuine original user constraints and control permissions remain' in prompt
    assert 'until H explicitly revises them' in prompt
    assert 'train-only' not in prompt and 'training data only' not in prompt
    assert 'this adds no schema, gate or permission' in prompt


def test_compiled_hypothesis_improvement_and_diagnosis_have_distinct_scientific_scope():
    prompt = ' '.join(compiled_role('science.hypothesis.propose.v1').split())
    assert 'optimization or improvement goal' in prompt
    assert 'one testable solution mechanism directly addressing the target conditions' in prompt
    assert 'A pure diagnosis goal need not propose solution mechanisms' in prompt
    assert 'Do not invent candidates to satisfy a count' in prompt
    assert 'Preserve genuine original user constraints' in prompt
    assert 'train-only' not in prompt
    assert 'no exploratory execution outside its declared native permissions' in prompt
