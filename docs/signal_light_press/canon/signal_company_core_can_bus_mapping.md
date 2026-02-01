Authority: Signal Light Press
Classification: WORKING
Status: DRAFT
Domain: Document
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
Authority: Signal Light Press
Classification: WORKING
Status: DRAFT
Domain: Document
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
Authority: Signal Light Press
Classification: WORKING
Status: DRAFT
Domain: Document
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
Authority: Signal Light Press
Classification: WORKING
Status: DRAFT
Domain: Document
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
Authority: Signal Light Press
Classification: WORKING
Status: DRAFT
Domain: Document
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
Authority: Signal Light Press
Classification: WORKING
Status: DRAFT
Domain: Document
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
Authority: Signal Light Press
Classification: WORKING
Status: DRAFT
Domain: Document
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
Authority: Signal Light Press
Classification: WORKING
Status: DRAFT
Domain: Document
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
Authority: Signal Light Press
Classification: WORKING
Status: DRAFT
Domain: Document
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
Authority: Signal Light Press
Classification: WORKING
Status: DRAFT
Domain: Document
Applies To: Signal Light Press
Amendment Rule: Signal Light Press only
Executable: No
# Signal Company Core — CAN Bus Model Mapping
All former scripts and files you sent are mapped into the new CAN bus structure below. Each component is placed where it fits logically, with a short description of why it's there, what it does, and how it flows in the CAN style (distributed nodes, message-passing, coherence arbitration).

## The Bus = Helix Sync + Dark Field
Shared append-only message backbone (JSONL files or in-memory queue). Nodes broadcast sealed packets when locally coherent. Helix Sync scores global coherence. High sync → high priority → proposal eligibility.

- dark_field/store.py  
  Why: Append-only writer for general Waves to daily JSONL.  
  What: Seals and appends messages (packets) to the bus.  
  Flow: Nodes call this to broadcast sealed DomainWaves or envelopes. Flows to loader for read-back.

- dark_field/loader.py  
  Why: Verbatim loader of raw wave records from JSONL.  
  What: Loads sealed packets from the bus for other nodes to listen.  
  Flow: Nodes read bus traffic to aggregate or compute (e.g., oracle listens for DomainWaves).

- write.py  
  Why: Specialized append-only writer for DomainWave to JSONL.  
  What: Broadcasts phase relationship packets to the bus.  
  Flow: Domain helmsmen call this to send guest signals as packets. Flows to loader for oracle/antifragile.

## Nodes (Distributed Helmsmen)
Distributed observers that observe, phase-align, and broadcast packets when local sync high. No central scheduler — nodes talk when coherent.

- prepare_daily_signals.py  
  Why: Embryonic signal ingestion node (natural/market loaders).  
  What: Orchestrates daily signal sampling → merged_signal.csv as time-series packets.  
  Flow: Feeds domain helmsmen nodes for phase extraction. Flows to oracle node for convergence.

- run_staff_survey.py  
  Why: Core self helmsman node (embryonic self-observation).  
  What: Surveys self-state → outputs descriptive envelopes as packets.  
  Flow: Broadcasts self-metrics packets to bus. Flows to antifragile/oracle nodes.

- run_proposals.py  
  Why: Readiness/proposal node.  
  What: Aggregates bus traffic → generates proposal packets if sync high.  
  Flow: Listens to oracle/antifragile packets → broadcasts proposal if criteria met. Flows to human gate.

- coupling.py  
  Why: Coherence computation in oracle/antifragile node.  
  What: Computes lagged correlations (CouplingStat) for entrainment_fraction.  
  Flow: Listens to time-series packets → broadcasts coherence packets. Flows to readiness node.

- ghost.py  
  Why: Memory damping in memory node.  
  What: Injects ghost layer, computes stability metrics as decay envelopes.  
  Flow: Listens to bus residue → broadcasts stability packets. Flows to antifragile node.

- afterglow.py  
  Why: Memory decay in memory node.  
  What: Computes memory fields (intensity, charge, afterglow) for temporal inertia.  
  Flow: Listens to bus residue → broadcasts decay packets. Flows to antifragile node.

- drift.py  
  Why: Drift computation in antifragile node.  
  What: Computes drift index as temporal deviation envelope.  
  Flow: Listens to bus envelopes → broadcasts drift packets. Flows to readiness node.

- brittleness.py  
  Why: Brittleness computation in antifragile node.  
  What: Computes brittleness index as structural exposure envelope.  
  Flow: Listens to bus envelopes → broadcasts brittleness packets. Flows to readiness node.

- strain.py  
  Why: Strain computation in antifragile node.  
  What: Computes strain index as load dominance envelope.  
  Flow: Listens to bus envelopes → broadcasts strain packets. Flows to readiness node.

- state.py  
  Why: Antifragile aggregation in antifragile node.  
  What: Aggregates drift/brittleness/strain into state packet.  
  Flow: Broadcasts full antifragile state. Flows to readiness node.

- convergence.py  
  Why: Convergence aggregation in oracle node.  
  What: Aggregates descriptors → cycle density summaries.  
  Flow: Listens to alignment packets → broadcasts convergence packets. Flows to phase node.

- phase.py  
  Why: Symbolic phase emission in oracle node.  
  What: Emits symbolic phase from convergence.  
  Flow: Broadcasts phase label packets. Flows to readiness node.

- oracle.py  
  Why: Stateless oracle wrapper in oracle node.  
  What: Describes alignment and summarizes convergence.  
  Flow: Coordinates oracle broadcasts. Flows to readiness node.

- contract_v1.py  
  Why: Schema contract for oracle packets.  
  What: Defines required columns/ranges for oracle messages.  
  Flow: Used by oracle node for packet validation before broadcast.

- validate.py  
  Why: Runtime packet validator.  
  What: Enforces contract invariants on messages.  
  Flow: Nodes call before broadcast — bad packet → scar.

- oracle_layer1.py  
  Why: First harmonic convergence in oracle node.  
  What: Computes OCI/RiskIndex/Band/Bias.  
  Flow: Broadcasts L1 packets. Flows to L2 node.

- oracle_layer2.py  
  Why: Multi-source synthesis in oracle node.  
  What: Computes HCFIndex + components + Band/Bias.  
  Flow: Broadcasts L2 packets. Flows to L3 node.

- oracle_layer3.py  
  Why: Forward-looking horizon in oracle node.  
  What: Computes OHI + HorizonBand/Bias/Windows.  
  Flow: Broadcasts L3 packets. Flows to L4 node.

- oracle_layer4.py  
  Why: Latent dark field inference in oracle node.  
  What: Computes D_t + DarkFieldBand + D_* components.  
  Flow: Broadcasts L4 packets. Flows to readiness node.

- features.py  
  Why: Residue quantifier in lighthouse node.  
  What: Builds feature matrices from journal.  
  Flow: Broadcasts feature packets. Flows to predict nodes.

- predict_resonance.py  
  Why: Resonance prediction in lighthouse node.  
  What: Predicts next-day ResonanceValue.  
  Flow: Broadcasts resonance outlook. Flows to readiness node.

- predict_state.py  
  Why: State prediction in lighthouse node.  
  What: Predicts next-day SignalState.  
  Flow: Broadcasts state outlook. Flows to readiness node.

- mock_cycle.py  
  Why: End-to-end simulation for readiness/proposal/execution.  
  What: Mocks PSR, readiness, proposal, human gate, execution.  
  Flow: Diagnostic harness — non-canonical. Flows to full cycle implementation.

## Arbitration (Readiness)
- No central scheduler.
- Nodes broadcast only when local sync high.
- Helix Sync global coherence determines readiness: high → proposal packet broadcast.
- Low → no broadcast → silence.

## Human Sovereignty Gate
- Human reads proposal packets from bus.
- Grants/denies mandate → mandate broadcast as high-priority packet.
- Execution node listens → runs → broadcasts outcome.

## Nightly Reconciliation
- Bus maintenance: prune low-coherence packets, seal scars, reset volatile traffic.

## Benefits of CAN Bus Model

- Simpler: 5–7 small nodes instead of 20+ layered scripts.
- Distributed: Nodes can run on separate Pis, bus as shared file or MQTT broker.
- Emergent Silence: No traffic = no proposal (natural, not enforced).
- Fault-Tolerant: Node fails → bus continues; bad message → scar.
- Scalable: Add new domains as new nodes — no central rewrite.

END OF SIGNAL COMPANY CORE DOCUMENT

— END OF DOCUMENT —
SEAL: ae78e6cb8078dc5b69ee19cd5150595867c79836c67733b4425700b4dc64b4aa
