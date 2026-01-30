from typing import List, TypedDict


class StaffSurvey(TypedDict):
    situation_snapshot: str
    structural_patterns: List[str]
    anomalies: List[str]
    risk_surfaces: List[str]
    uncertainties: List[str]

