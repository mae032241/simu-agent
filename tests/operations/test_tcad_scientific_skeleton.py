"""Small scientific skeleton fixture used by current gateway contracts."""

def skeleton():
    return {"selected_hypothesis_keys": ["hypothesis_a"], **{name: ["Bounded scientific fixture with stated evidence basis."] for name in (
        "current_objectives", "competing_explanations_and_controls", "changed_conditions",
        "held_conditions", "observables", "discrimination_criteria_and_basis",
        "immutable_conditions", "stop_conditions")}}
