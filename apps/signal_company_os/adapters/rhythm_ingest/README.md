RHYTHM\_OS → SIGNAL\_COMPANY\_OS

Envelope Ingestion Adapter (README)



Status: ACTIVE · FROZEN

Scope: Read-only ingestion + receipt logging

Authority: Signal Light Press (Kernel)



PURPOSE



This module provides a read-only ingestion boundary for RHYTHM\_OS envelopes into SIGNAL\_COMPANY\_OS.



It exists to:



Load envelopes without interpretation



Validate structure only



Record receipt, not meaning



Prevent authority or agentive behavior at the boundary



This module is intentionally minimal.



WHAT THIS MODULE DOES

✅ Allowed



Load serialized RHYTHM\_OS envelopes



Validate envelope fields and types



Append a receipt record (NDJSON)



Expose envelope contents for downstream human viewing only



❌ Forbidden



Interpretation or aggregation



Thresholding or scoring



Action gating or execution



Automation or optimization



Writing to RHYTHM\_OS



Feedback loops of any kind



If you think you need any of the above, you are in the wrong layer.



FILES

rhythm\_ingest/

├── ingest\_envelope.py   # Envelope loader (read-only, validation only)

├── receipt\_log.py       # Append-only receipt logger (NDJSON)

├── CANON\_NOTE.md        # Canonical declaration (do not modify)

├── INGESTION\_SEAL.md    # Binding seal (do not modify)

└── README.md            # This file



EXECUTION (CANONICAL)



All ingestion code must be run as a module from the apps/ boundary:



cd SignalLogic/apps

python -m signal\_company\_os.test\_ingest





Direct execution of .py files is forbidden.



PATH HANDLING RULE



All file paths must be resolved relative to the module location:



from pathlib import Path



HERE = Path(\_\_file\_\_).parent





Do not hard-code paths like apps/....



RECEIPT LOGGING



Envelope receipt records are written to:



signal\_company\_os/storage/receipts/envelope\_receipts.ndjson





Format:



NDJSON



One line per receipt



Append-only



No edits or deletes



Logged fields:



received\_at\_utc



envelope\_id



shepherd\_posture



source\_path



DESIGN INTENT



This adapter is deliberately boring.



If this code ever feels like it should:



decide something,



recommend something,



trigger something,



or “help” more —



stop immediately.

That work belongs downstream, under human authority.



STATUS



This ingestion adapter is complete and frozen.



Any modification requires:



explicit architectural amendment



Signal Light Press approval



a new canon note

