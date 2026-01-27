from typing import List, TypedDict


class Proposal(TypedDict):
    title: str
    description: str
    rationale: str
    risks: List[str]
    tradeoffs: List[str]


class ProposalReport(TypedDict):
    situation_snapshot: str
    proposals: List[Proposal]
    uncertainties: List[str]

