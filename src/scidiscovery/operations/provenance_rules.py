"""Source rules over verified facts; no storage, model labels or permissions."""


def dependency_sources(declared, frozen_inputs):
    """Only a trusted explicit derivation may narrow the frozen input set.

    None means no exact derivation was supplied. An explicit empty declaration
    means no dependencies only after the calling adapter has verified it.
    """
    return tuple(frozen_inputs if declared is None else declared)


def inherited_restriction(states):
    """Clear requires a complete verified closure; absence is not clearance."""
    states = tuple(states)
    if any(state not in {'clear', 'restricted', 'unknown'} for state in states):
        raise ValueError('Unknown source restriction fact')
    if 'restricted' in states:
        return 'restricted'
    return 'unknown' if 'unknown' in states else 'clear'
