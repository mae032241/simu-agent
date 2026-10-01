"""Display controlled attachments from an already authorized immutable cohort."""
from collections.abc import Mapping
from ...plugin_runtime.presentation import add_gap, items, pointer, source


def presentation_file_manifest(payload):
    """Keep file identities, captions and original array positions, not calculations.

    Original manifests remain available through their evidence URLs. Retaining all
    aliases also preserves duplicate detection when nonvisual records are omitted.
    """
    if not isinstance(payload, Mapping) or not isinstance(payload.get('records'), list) or not isinstance(payload.get('bindings'), Mapping):
        return None
    records = []
    for record in payload['records']:
        if not isinstance(record, Mapping):
            records.append(None)
            continue
        item = {'alias': record.get('alias')}
        media = str(record.get('media_type', '')).split(';', 1)[0].strip().lower()
        if record.get('output_port') == 'attachments' or media in {'image/png', 'image/jpeg', 'text/csv'}:
            # File metadata is owned by its plugin; keep it intact for registered
            # presentation providers (including figure family and CSV captions).
            item = dict(record)
        records.append(item)
    # Frozen inputs also identify existing images used by a result diagnosis.
    # They need no new output receipt or copied attachment to remain displayable.
    return {'records': records, 'bindings': dict(payload['bindings'])}


def append_attachments(result, cohort):
    for manifest in cohort:
        if (manifest.get('schema_id') != 'scidiscovery.tool-evidence-manifest.v1'
                or manifest.get('family', {}).get('operation_output_port') != 'recovery_manifest_output'):
            continue
        payload = manifest.get('payload')
        if not isinstance(payload, Mapping):
            continue
        records = items(payload.get('records'))
        selected = [(i, r) for i, r in enumerate(records) if isinstance(r, Mapping) and r.get('output_port') == 'attachments']
        if not selected:
            continue
        if manifest.get('payload_state') != 'available' or manifest.get('gaps'):
            add_gap(result, 'attachment_manifest_incomplete', manifest)
            continue
        bindings = payload.get('bindings', {})
        parents = [p.get('ref') for p in manifest.get('provenance', ())]
        for index, record in selected:
            alias, ref = record.get('alias'), record.get('artifact_ref')
            binding = bindings.get(alias) if isinstance(bindings, Mapping) and isinstance(alias, str) else None
            matches = [a for a in cohort if isinstance(ref, Mapping) and a.get('ref') == ref
                and a.get('size_bytes') == record.get('size_bytes') and a.get('media_type') == record.get('media_type')
                and a.get('family', {}).get('operation_output_port') == 'attachments']
            if (len(matches) != 1 or parents.count(ref) != 1 or not isinstance(binding, Mapping)
                    or binding.get('artifact_ref') != ref or binding.get('port_name') != 'attachments'
                    or sum(isinstance(r, Mapping) and r.get('alias') == alias for r in records) != 1):
                add_gap(result, 'attachment_reference_missing_or_ambiguous', manifest, pointer('records', index))
                continue
            metadata = record.get('metadata', {})
            if not isinstance(metadata, Mapping):
                continue
            name = metadata.get('file_name', alias)
            result['sections'].append({'title': '封存科学附件（不代表已审查）', 'kind': 'attachments', 'items': [{
                'label': name, 'value': metadata.get('purpose', ''), 'source': source(matches[0])}]})
            if str(record.get('media_type', '')).split(';', 1)[0].strip().lower() in {'image/png', 'image/jpeg'}:
                result['figures'].append({'artifact_id': matches[0]['artifact_id'],
                    'label': name, 'source': source(manifest, pointer('records', index))})
