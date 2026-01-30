# rhythm_os/core/journal_projection.py

JOURNAL_COLUMNS = [
    "Date",
    "Season",
    "SignalState",
    "Phase",
    "ChangeType",
    "StreakLength",
    "ResonanceValue",
    "DarkFieldBand",
    "D_t",
    "CouplingSummary",
]


def project_signal_journal_row(row: dict) -> dict:
    """
    Reduce merged_signal row → signal journal row.
    """
    return {
        "Date": row.get("Date"),
        "Season": row.get("Season"),
        "SignalState": row.get("SignalState"),
        "Phase": row.get("Phase"),
        "ChangeType": row.get("ChangeType"),
        "StreakLength": row.get("StreakLength"),
        "ResonanceValue": row.get("ResonanceValue"),
        "DarkFieldBand": row.get("DarkFieldBand"),
        "D_t": row.get("D_t"),
        "CouplingSummary": _format_coupling(row),
    }


def _format_coupling(row: dict) -> str | None:
    col = row.get("CouplingCol")
    lag = row.get("CouplingLag")
    if not col or lag is None:
        return None
    return f"{col} ({lag}d)"
