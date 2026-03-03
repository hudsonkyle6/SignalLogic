"""
ConvergenceMemoryStore — Cross-day persistent store for domain-pair convergence history.

Records every turbine convergence observation keyed by:
  - domain_pair   Two domain names, sorted and joined: "natural+system"
  - phase_bucket  Which 1/12 slice of the diurnal cycle [0-11]
  - leading_domain Which domain's packet was current when convergence was detected

This cross-day accumulation is what allows the classifier to distinguish:
  NOISE     — same pair locks to the same phase bucket day after day
  COUPLING  — pair meets irregularly across buckets, no consistent leader
  LAG       — one domain consistently leads the other into convergence

Architecture:
  - Single append-only JSONL file (not daily-rotated — cross-day is the point)
  - Each line is one ConvergenceObservation
  - No in-memory mutation. Load → classify → record is the only flow.
  - Pure read/write. No derived state is stored.

Phase bucketing:
  N_BUCKETS = 12 divides the diurnal cycle into 2-hour slices, matching
  CONVERGENCE_WINDOW = 1/12 used by the turbine.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from rhythm_os.runtime.paths import CONVERGENCE_MEMORY_PATH

# Number of phase buckets across the diurnal cycle.
# 12 buckets → each bucket spans 1/12 of cycle ≈ 2 h, matching CONVERGENCE_WINDOW.
N_BUCKETS = 12


# ---------------------------------------------------------------------------
# Phase geometry helpers
# ---------------------------------------------------------------------------


def phase_to_bucket(diurnal_phase: float, n_buckets: int = N_BUCKETS) -> int:
    """Map a diurnal phase [0, 1) to a bucket index [0, n_buckets)."""
    return int(diurnal_phase * n_buckets) % n_buckets


def pair_key(domain_a: str, domain_b: str) -> str:
    """Canonical sorted key for a domain pair: 'natural+system'."""
    return "+".join(sorted([domain_a.strip(), domain_b.strip()]))


# ---------------------------------------------------------------------------
# ConvergenceObservation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConvergenceObservation:
    """
    A single cross-domain convergence event recorded by the turbine.

    obs_id          Unique UUID for this record
    t               Unix seconds when observed
    domain_pair     Canonical pair key: "natural+system"
    phase_bucket    Diurnal bucket index [0, N_BUCKETS)
    diurnal_phase   Exact diurnal phase for precision reference
    leading_domain  The domain whose packet triggered the observation
                    (i.e., the domain currently entering the turbine)
    convergence_note The raw convergence_note from the turbine observation
    """

    obs_id: str
    t: float
    domain_pair: str
    phase_bucket: int
    diurnal_phase: float
    leading_domain: str
    convergence_note: str

    def to_dict(self) -> Dict:
        return {
            "obs_id": self.obs_id,
            "t": self.t,
            "domain_pair": self.domain_pair,
            "phase_bucket": self.phase_bucket,
            "diurnal_phase": self.diurnal_phase,
            "leading_domain": self.leading_domain,
            "convergence_note": self.convergence_note,
        }

    @staticmethod
    def from_dict(d: Dict) -> "ConvergenceObservation":
        return ConvergenceObservation(
            obs_id=str(d["obs_id"]),
            t=float(d["t"]),
            domain_pair=str(d["domain_pair"]),
            phase_bucket=int(d["phase_bucket"]),
            diurnal_phase=float(d["diurnal_phase"]),
            leading_domain=str(d["leading_domain"]),
            convergence_note=str(d["convergence_note"]),
        )


# ---------------------------------------------------------------------------
# ConvergenceMemoryStore
# ---------------------------------------------------------------------------


class ConvergenceMemoryStore:
    """
    Append-only JSONL store for turbine convergence observations.

    Records persist across days so the classifier can detect patterns
    that only emerge over time (e.g., NOISE requires many daily samples).

    Thread safety: Not guaranteed. Single-process use only.
    """

    def __init__(self, store_path: Optional[Path] = None) -> None:
        self._path = store_path or CONVERGENCE_MEMORY_PATH

    # ------------------------------------------------------------------
    # Internal I/O
    # ------------------------------------------------------------------

    def _append(self, record: Dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        with self._path.open("a", encoding="utf-8") as f:
            f.write(line)

    def _load_all(self) -> List[ConvergenceObservation]:
        if not self._path.exists():
            return []
        obs: List[ConvergenceObservation] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obs.append(ConvergenceObservation.from_dict(json.loads(line)))
            except Exception:
                continue
        return obs

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        *,
        domain_a: str,
        domain_b: str,
        diurnal_phase: float,
        leading_domain: str,
        convergence_note: str,
        t: Optional[float] = None,
    ) -> ConvergenceObservation:
        """
        Record a new convergence observation.

        domain_a / domain_b — the two converging domains (order doesn't matter)
        diurnal_phase       — current diurnal phase [0, 1)
        leading_domain      — which domain triggered the observation
        convergence_note    — raw note from the turbine
        """
        obs = ConvergenceObservation(
            obs_id=str(uuid.uuid4()),
            t=t if t is not None else time.time(),
            domain_pair=pair_key(domain_a, domain_b),
            phase_bucket=phase_to_bucket(diurnal_phase),
            diurnal_phase=diurnal_phase,
            leading_domain=leading_domain,
            convergence_note=convergence_note,
        )
        self._append(obs.to_dict())
        return obs

    def get_history(
        self,
        domain_a: str,
        domain_b: str,
        *,
        phase_bucket: Optional[int] = None,
        max_records: int = 1000,
    ) -> List[ConvergenceObservation]:
        """
        Return historical observations for a domain pair.

        Optionally filter to a specific phase bucket.
        Returns at most max_records, most-recent first.
        """
        key = pair_key(domain_a, domain_b)
        all_obs = self._load_all()
        filtered = [o for o in all_obs if o.domain_pair == key]
        if phase_bucket is not None:
            filtered = [o for o in filtered if o.phase_bucket == phase_bucket]
        # most-recent first
        filtered.sort(key=lambda o: o.t, reverse=True)
        return filtered[:max_records]

    def pair_summary(self, domain_a: str, domain_b: str) -> Dict:
        """
        High-level summary of a domain pair's convergence history.

        Returns:
          total_count       Total observations for this pair
          bucket_counts     Dict[int, int] — count per phase bucket
          leading_counts    Dict[str, int] — count per leading domain
          first_seen        Unix seconds of earliest observation (or None)
          last_seen         Unix seconds of most-recent observation (or None)
          dominant_bucket   Phase bucket with most observations (or None)
        """
        history = self.get_history(domain_a, domain_b)

        if not history:
            return {
                "total_count": 0,
                "bucket_counts": {},
                "leading_counts": {},
                "first_seen": None,
                "last_seen": None,
                "dominant_bucket": None,
            }

        bucket_counts: Dict[int, int] = {}
        leading_counts: Dict[str, int] = {}
        for o in history:
            bucket_counts[o.phase_bucket] = bucket_counts.get(o.phase_bucket, 0) + 1
            leading_counts[o.leading_domain] = (
                leading_counts.get(o.leading_domain, 0) + 1
            )

        dominant_bucket = max(bucket_counts, key=lambda b: bucket_counts[b])
        times = [o.t for o in history]

        return {
            "total_count": len(history),
            "bucket_counts": bucket_counts,
            "leading_counts": leading_counts,
            "first_seen": min(times),
            "last_seen": max(times),
            "dominant_bucket": dominant_bucket,
        }

    def all_pairs(self) -> List[str]:
        """Return sorted list of all domain pair keys seen in memory."""
        all_obs = self._load_all()
        return sorted({o.domain_pair for o in all_obs})
