import time
from pathlib import Path

from rhythm_os.core.field import compute_field
from rhythm_os.reports.signal_dashboard import render_signal_report

# Example: no domain waves yet (fine)
field = compute_field(time.time())

render_signal_report(
    field_sample=field,
    domain_waves=[],
    engine_state={"posture": "SILENT", "state": "Still"},
    context={"season": "Reflect"},
)

