"""Frozen role model choices; omitted roles and fields inherit global defaults."""
from __future__ import annotations

ROLES = ('H', 'W', 'A', 'E')
FIELDS = ('model', 'reasoning_effort', 'service_tier')


def normalize(value, defaults):
    base = {key: defaults[key] for key in FIELDS}
    if any(not isinstance(item, str) or not item.strip() for item in base.values()):
        raise ValueError('Explicit model, reasoning effort and service tier are required')
    if not isinstance(value, dict) or set(value) - set(ROLES):
        raise ValueError('Role profiles must name only H, W, A or E')
    result = {}
    for role in ROLES:
        override = value.get(role, {})
        if (not isinstance(override, dict) or set(override) - set(FIELDS)
                or any(not isinstance(item, str) or not item.strip() for item in override.values())):
            raise ValueError('Role profile fields must be nonempty model, reasoning_effort or service_tier strings')
        result[role] = {**base, **override}
    return result


def selected(settings, role):
    if role not in ROLES:
        raise ValueError('Unknown scientific role for native profile')
    return normalize(settings.get('role_profiles', {}), settings)[role]


def for_job(settings, job):
    profile = selected(settings, job['role'])
    if (settings.get('role_profiles') is not None or 'native_profile' in job) and job.get('native_profile') != profile:
        raise ValueError('Frozen native job profile changed')
    return profile


def binding(settings, job):
    profile = for_job(settings, job)
    return dict(native_profile=profile) if 'native_profile' in job else {}


def validate_intent(settings, job, intent):
    profile = for_job(settings, job)
    if ('native_profile' in job or 'native_profile' in intent) and intent.get('native_profile') != profile:
        raise ValueError('Frozen native intent profile changed')
    return profile
