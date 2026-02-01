from pathlib import Path
from signal_company_os.adapters.rhythm_ingest.ingest_envelope import load_envelope_json
from signal_company_os.adapters.rhythm_ingest.receipt_log import append_receipt

HERE = Path(__file__).parent

envelope_path = (
    HERE
    / "storage"
    / "rhythm_envelopes"
    / "_samples"
    / "sample_envelope.json"
)

env = load_envelope_json(envelope_path)

append_receipt(
    envelope_id=env.envelope_id,
    shepherd_posture=env.shepherd_posture,
    source_path=envelope_path,
    log_dir=HERE / "storage" / "receipts",
)

print("receipt appended for:", env.envelope_id)
