from staff_schema import StaffSurvey


class GuardViolation(Exception):
    pass


def enforce_staff_survey(obj: dict) -> StaffSurvey:
    required_keys = {
        "situation_snapshot",
        "structural_patterns",
        "anomalies",
        "risk_surfaces",
        "uncertainties",
    }

    if set(obj.keys()) != required_keys:
        raise GuardViolation(f"Schema keys invalid: {obj.keys()}")

    if not isinstance(obj["situation_snapshot"], str):
        raise GuardViolation("situation_snapshot must be string")

    for key in [
        "structural_patterns",
        "anomalies",
        "risk_surfaces",
        "uncertainties",
    ]:
        if not isinstance(obj[key], list):
            raise GuardViolation(f"{key} must be list")
        if not all(isinstance(x, str) for x in obj[key]):
            raise GuardViolation(f"{key} must contain strings only")

    return obj  # now trusted

