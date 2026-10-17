"""One admission rule from public contract through exact reviewer attachment."""
import json
import pytest


def test_review_policy_and_transform_authorship_are_compiled():
    from tests.operations.test_agent_contract_alignment import _catalog
    from scidiscovery.operations.catalog import CatalogCompileError, compile_catalog
    from scidiscovery.general_science_plugin import PLUGIN
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    catalog = _catalog()
    projected = next(v for v in catalog.scheduler_projection() if v.operation_id=='science.object.review.v1')
    assert projected.review_subject_policy['ports']==['subject']
    assert 'Original user text' in projected.review_subject_policy['requirement']
    split = next(v for v in PLUGIN.operations if v.operation_id=='science.intake.split.v1')
    for ports in (('missing',), ('scientific_intake','scientific_intake')):
        plugin = PLUGIN.model_copy(update={'operations':tuple(
            v.model_copy(update={'authorship_source_ports':ports}) if v==split else v for v in PLUGIN.operations)})
        with pytest.raises(CatalogCompileError) as caught:
            compile_catalog((CORE_PLUGIN,plugin))
        assert caught.value.reason_code=='authorship_source_invalid'


def test_review_policy_hides_private_and_derived_ports():
    from scidiscovery.general_science_experiment_review import OPERATION
    from scidiscovery.operations.spec import InputDerivationSpec, scheduler_operation_view
    subject = OPERATION.inputs[0]
    hidden = subject.model_copy(update={'name':'private_subject', 'agent_visible':False})
    derived = subject.model_copy(update={'name':'derived_subject',
        'derivation':InputDerivationSpec(anchor_port='subject')})
    spec = OPERATION.model_copy(update={'inputs':(*OPERATION.inputs, hidden, derived),
        'independent_review_ports':('subject', 'private_subject', 'derived_subject')})
    view = scheduler_operation_view(spec).model_dump(mode='json')
    assert view['review_subject_policy']['ports'] == ['subject']
    assert 'private_subject' not in json.dumps(view)
    assert 'derived_subject' not in json.dumps(view)
