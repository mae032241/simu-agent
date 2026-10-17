"""Real Root/Worker publication, finalization, downstream and UI file delivery."""


def test_current_scientific_agents_all_declare_publication_without_form_ports(tmp_path):
    from scidiscovery.operations.catalog import compile_catalog
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN
    from tcad_artifact.plugin import PLUGIN as tcad
    from curve_score.plugin import PLUGIN as curve
    from curve_figure_evidence.plugin import PLUGIN as figure
    catalog=compile_catalog((CORE_PLUGIN,PLUGIN,tcad,curve,figure))
    for identity in catalog.operation_ids():
        compiled=catalog.operation(identity)
        if compiled.spec.executor.kind!='agent':continue
        assert 'worker_publish_files' in {t.name for t in compiled.worker_tools}, identity
        port=next(p for p in compiled.spec.outputs if p.name=='attachments')
        assert not port.agent_visible
