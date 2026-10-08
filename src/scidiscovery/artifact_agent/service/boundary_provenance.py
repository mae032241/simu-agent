"""Seal attributed boundary declarations; location checks grant no authority."""
from __future__ import annotations

import json

from ..schema.common import canonical_json
from .input_reader import select, public_boundary_signal
from ..schema.research_objective import is_original_text_objective


def seal_boundaries(declarations, references, *, input_bytes, descriptors, producer, resolve):
    records = []
    for declaration in declarations:
        authored = declaration.model_dump(mode='json')
        checks = []
        for citation in declaration.evidence:
            source = citation.source
            descriptor = descriptors.get(source.source_key)
            check = dict(source_key=source.source_key, locator=source.locator,
                verification='unverified', source_location_verification='unverified',
                quote_verification='absent' if citation.quote is None else 'unverified',
                verification_scope='quoted_bytes_only', origin='unknown', authority='owner_interpretation')
            if descriptor is not None:
                check['artifact_ref'] = descriptor.artifact_ref.model_dump(mode='json')
                check['producer_run_id'] = descriptor.producer_run_id
                # A payload's schema or author's source_type cannot promote it to user text.
                check['origin'] = ('original_user_text' if is_original_text_objective(descriptor.artifact_ref, descriptor.media_type, descriptor.labels) else
                    'produced_material' if descriptor.producer_run_id else 'frozen_material')
                try:
                    raw = input_bytes[source.source_key].decode('utf-8')
                    plain_text = descriptor.media_type.split(';', 1)[0] in ('text/plain', 'text/markdown')
                    if source.locator == 'text':
                        located, scope = raw, 'source_text'
                        check['source_location_verification'] = 'matched'
                    elif plain_text and not source.locator.startswith('/'):
                        # A heading/section is a hint, not a JSON Pointer or a
                        # verified location. Match the quote in the frozen text
                        # independently; never fall back from an explicit pointer.
                        located, scope = raw, 'source_text'
                    else:
                        located, scope = select(json.loads(raw), source.locator), 'selected_value'
                        check['source_location_verification'] = 'matched'
                    if citation.quote and isinstance(located, str):
                        check['quote_match_scope'] = scope
                        first = located.find(citation.quote)
                        if first >= 0:
                            check['verification'] = check['quote_verification'] = 'matched'
                            check['quote_match_multiplicity'] = ('multiple' if
                                located.find(citation.quote, first + 1) >= 0 else 'unique')
                except (KeyError, ValueError, UnicodeError, TypeError):
                    pass
            checks.append(check)
        revisions = [resolve_reference(reference, resolve=resolve) for reference in declaration.revises]
        for revision in revisions:
            original = revision.pop('declaration', None)
            if original is not None:
                revision['resolved_source'] = dict(artifact_ref=original.get('artifact_ref'),
                    producer=original['producer'], boundary_key=original['declaration']['boundary_key'])
                revision['history'] = 'retained_in_exact_original_declaration'
        records.append(dict(declaration=authored, producer=producer, source_checks=checks,
            revision_checks=revisions, verification='unverified', interpretation_verification='unverified',
            authority='owner_interpretation', effect='owner_statement'))
    by_key = {record['declaration']['boundary_key']: record for record in records}
    resolved = [resolve_reference(reference, resolve=resolve, local=by_key) for reference in references]
    return records, resolved


def resolve_reference(reference, *, resolve, local=None):
    authored = reference.model_dump(mode='json')
    found = ((local or {}).get(reference.boundary_key) if reference.source_key is None
        else resolve(reference.source_key, reference.boundary_key))
    if found is None:
        return dict(reference=authored, verification='unverified', effect='unresolved',
            authority='owner_interpretation', instruction='The declaration is unresolved. Preserve current H boundaries; this cannot authorize relaxation.')
    # The exact upstream declaration remains unchanged. Its citation status and
    # its applicability are independent; neither invalid citations nor A advice
    # silently revises an assigned H boundary.
    return dict(reference=authored, verification='matched', effect=found.get('application', 'referenced_owner_statement'),
        authority='owner_interpretation', **({'declaration': found} if reference.source_key is not None else {}))


def boundary_original(runs, artifact_ref, key):
    """Resolve only an exact completed primary, never a current name/revision."""
    producer = runs.completed_for_output(artifact_ref)
    if producer is None or producer.output_ref != artifact_ref or producer.signal is None:
        return None
    matches = [item for item in producer.signal.boundary_declarations
        if item['declaration']['boundary_key'] == key]
    if len(matches) == 1:
        return json.loads(canonical_json(matches[0]))
    references = [item for item in producer.signal.boundary_references
        if item.get('reference', {}).get('boundary_key') == key and item.get('verification') == 'matched'
        and item.get('declaration') is not None]
    if len(references) == 1:
        return json.loads(canonical_json(references[0]['declaration']))
    return None
