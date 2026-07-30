"""
RecoveryLab — Confidence Registry
====================================
The most transparent way to communicate scientific confidence.

Instead of arbitrary percentages, this registry uses a star-based system
that maps DIRECTLY to the type of evidence accumulated:

  1 star  (*)  — Observation isolée (single run, single dataset)
  2 stars (**) — Répété 10 fois (same dataset, multiple runs, deterministic)
  3 stars (***)— Répété avec datasets différents (multiple datasets, stable result)
  4 stars (****)— Validé avec outils externes (PhotoRec, TestDisk comparison)
  5 stars (*****)— Validé avec hardware réel (actual disks, not simulated)

This is MUCH more transparent than saying "H8 has 73% confidence."
A reader can immediately see what evidence supports a result.

Usage:
    from recovery_judge.confidence_registry import ConfidenceRegistry, ConfidenceLevel

    registry = ConfidenceRegistry()
    registry.register("H1.1", ConfidenceLevel.STAR_3,
                      "MFT-First beats Carving in 100/100 scenarios, 3 datasets")
    registry.register("H8", ConfidenceLevel.STAR_1,
                      "Crossover at 95% observed once, single dataset, limited carving")

    print(registry.report())
    # H1.1 → *** (3/5) — MFT-First beats Carving in 100/100 scenarios, 3 datasets
    # H8   → *   (1/5) — Crossover at 95% observed once, single dataset, limited carving

Rules:
  - Stars can ONLY go UP, never down (accumulation of evidence)
  - A star can be CONTESTED (if a contradictory result appears)
  - A contested star shows the contradiction: *** → *** [CONTESTED by: ...]
  - The registry is append-only — evidence is never deleted
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json


# ─── Confidence Levels ────────────────────────────────────────────────────────

class ConfidenceLevel(Enum):
    """
    Star-based confidence levels.

    Each level has a clear, unambiguous definition of what evidence
    is required to reach it. This is NOT a subjective scale.
    """
    STAR_1 = 1   # Isolated observation — single run, single dataset
    STAR_2 = 2   # Repeated 10+ times — same dataset, deterministic
    STAR_3 = 3   # Repeated with different datasets — stable across conditions
    STAR_4 = 4   # Validated with external tools — PhotoRec, TestDisk, etc.
    STAR_5 = 5   # Validated with real hardware — actual disks, not simulated

    @property
    def stars(self) -> str:
        """Visual representation of the confidence level."""
        return "*" * self.value

    @property
    def description(self) -> str:
        """Human-readable description of what this level means."""
        descriptions = {
            1: "Observation isolee — single run, single dataset",
            2: "Repete 10+ fois — same dataset, deterministic result",
            3: "Repete avec datasets differents — stable across conditions",
            4: "Valide avec outils externes — PhotoRec, TestDisk comparison",
            5: "Valide avec hardware reel — actual disks, not simulated",
        }
        return descriptions[self.value]

    @classmethod
    def from_count(cls, count: int) -> "ConfidenceLevel":
        """Create a ConfidenceLevel from a star count (1-5)."""
        if count < 1:
            count = 1
        if count > 5:
            count = 5
        return cls(count)


# ─── Evidence Entry ───────────────────────────────────────────────────────────

@dataclass
class ConfidenceEvidence:
    """A single piece of evidence contributing to a confidence assessment."""
    timestamp: str
    result_id: str                    # H1.1, H2, RVS, etc.
    star_level: ConfidenceLevel       # What level this evidence supports
    description: str                  # What was observed
    experiment_id: str = ""           # Link to experiment results
    dataset_id: str = ""              # Which dataset was used
    n_runs: int = 1                   # How many times this was observed
    is_contradictory: bool = False    # Does this contradict the result?
    contradiction_details: str = ""   # If contradictory, what was observed instead

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "result_id": self.result_id,
            "star_level": self.star_level.value,
            "description": self.description,
            "experiment_id": self.experiment_id,
            "dataset_id": self.dataset_id,
            "n_runs": self.n_runs,
            "is_contradictory": self.is_contradictory,
            "contradiction_details": self.contradiction_details,
        }


# ─── Confidence Entry ─────────────────────────────────────────────────────────

@dataclass
class ConfidenceEntry:
    """
    The confidence assessment for a single result.

    Tracks the current star level, all evidence, and any contradictions.
    Stars can only go UP (accumulation of evidence), unless a contradiction
    at the same or higher level is found.
    """
    result_id: str
    current_level: ConfidenceLevel = ConfidenceLevel.STAR_1
    evidence: List[ConfidenceEvidence] = field(default_factory=list)
    contradictions: List[ConfidenceEvidence] = field(default_factory=list)
    last_updated: str = ""

    def add_evidence(self, evidence: ConfidenceEvidence):
        """Add evidence and potentially upgrade the confidence level."""
        self.evidence.append(evidence)
        self.last_updated = datetime.now(timezone.utc).isoformat()

        if evidence.is_contradictory:
            self.contradictions.append(evidence)
            # Contradictions don't lower the star level, but they mark it
            # as contested. The reader must decide.
        else:
            # Stars can only go UP
            if evidence.star_level.value > self.current_level.value:
                self.current_level = evidence.star_level

    @property
    def is_contested(self) -> bool:
        """Whether this result has any contradictory evidence."""
        return len(self.contradictions) > 0

    @property
    def contestation_summary(self) -> str:
        """Summary of all contradictions, if any."""
        if not self.is_contested:
            return ""
        parts = []
        for c in self.contradictions:
            parts.append(f"{c.description} (star {c.star_level.value})")
        return " | ".join(parts)

    def to_dict(self) -> Dict:
        return {
            "result_id": self.result_id,
            "current_level": self.current_level.value,
            "current_stars": self.current_level.stars,
            "is_contested": self.is_contested,
            "contestation_summary": self.contestation_summary,
            "evidence_count": len(self.evidence),
            "contradiction_count": len(self.contradictions),
            "last_updated": self.last_updated,
            "evidence": [e.to_dict() for e in self.evidence],
        }


# ─── Confidence Registry ──────────────────────────────────────────────────────

class ConfidenceRegistry:
    """
    The single source of truth for confidence assessments.

    Every result in RecoveryLab (hypotheses, metrics, observations)
    gets a confidence entry. The registry is append-only.

    Usage:
        registry = ConfidenceRegistry()
        registry.register("H1.1", ConfidenceLevel.STAR_3,
                          "MFT-First beats Carving consistently")
        registry.register("H8", ConfidenceLevel.STAR_1,
                          "Crossover observed once")

        print(registry.report())
        # H1.1 → *** (3/5) — MFT-First beats Carving consistently
        # H8   → *   (1/5) — Crossover observed once

        # Add contradictory evidence
        registry.add_evidence("H8", ConfidenceEvidence(
            timestamp=now,
            result_id="H8",
            star_level=ConfidenceLevel.STAR_2,
            description="Crossover NOT observed with different dataset",
            is_contradictory=True,
        ))
        # H8 → * (1/5) [CONTESTED] — Crossover NOT observed with different dataset
    """

    def __init__(self):
        self.entries: Dict[str, ConfidenceEntry] = {}
        self._init_from_current_state()

    def _init_from_current_state(self):
        """
        Initialize the registry with the current state of knowledge
        based on the project's existing evidence.

        This is the AUDIT — we're being honest about what we actually know.
        """
        now = datetime.now(timezone.utc).isoformat()

        # ─── H1.1: Metadata prioritization reduces acquisition cost ─────────
        # Evidence: 3-strategy experiment, 100 scenarios, Carving vs MFT-First
        # MFT-First wins in 100/100 scenarios when MFT is intact.
        # BUT: A09 (intermittent sectors) shows MFT-First collapses (0/15).
        # Multiple datasets? Yes (experiment_v2 ran on multiple datasets).
        # External tools? No. Real hardware? No.
        # → STAR 3 (repeated with different datasets, stable result)
        self.register("H1.1", ConfidenceLevel.STAR_3,
                      "MFT-First supera a Carving en 100/100 escenarios con MFT intacto. "
                      "Fall back: A09 demuestra que MFT-First colapsa sin fallback.")

        # ─── H1.2: Strategy switching threshold exists ─────────────────────
        # Evidence: A09 shows MFT-first collapses, but the exact threshold
        # is unknown. Confidence sweep found no abrupt threshold.
        # → STAR 1 (observation isolee, threshold not precisely determined)
        self.register("H1.2", ConfidenceLevel.STAR_1,
                      "Evidencia de que MFT-first colapsa, pero el umbral exacto "
                      "no esta determinado. Confidence sweep no encontro umbral abrupto.")

        # ─── H2: Strategy crossover exists ──────────────────────────────────
        # Evidence: Crossover at 95% observed, but it's an artifact of limited
        # carving. The SOLID conclusion: different failure modes exist.
        # → STAR 2 (repeated 10+ times, but ceiling artifact)
        self.register("H2", ConfidenceLevel.STAR_2,
                      "Crossover observado en 95%, pero es artefacto del carving limitado. "
                      "Conclusion SOLIDA: modos de falla distintos entre estrategias.")

        # ─── H3: (not in current registry, merged into H2) ─────────────────

        # ─── H4: Damage × Strategy Matrix ──────────────────────────────────
        # Evidence: Preliminary matrix exists with 3 filled cells out of many.
        # Only weak evidence from single experiment.
        # → STAR 1 (observation isolee, matrix mostly empty)
        self.register("H4", ConfidenceLevel.STAR_1,
                      "Matriz preliminar con 3 celdas llenas. "
                      "Mayormente vacia. Necesita muchos mas experimentos.")

        # ─── H5: Per-format recovery differs ───────────────────────────────
        # Evidence: Carving only recovers JPEG, PNG, PDF (1/15 files).
        # The rest (TXT, CR2, NEF, etc.) have no signature support.
        # → STAR 1 (observation isolee, no systematic per-format experiment yet)
        self.register("H5", ConfidenceLevel.STAR_1,
                      "Carving solo recupera JPEG/PNG/PDF. Sin experimento "
                      "sistematico por formato aun.")

        # ─── H6: Functional recovery is not binary ─────────────────────────
        # Evidence: FunctionalValidator implemented, 19/19 tests pass.
        # But: only tested on synthetic data, no real-world validation.
        # → STAR 2 (implemented and tested, but synthetic only)
        self.register("H6", ConfidenceLevel.STAR_2,
                      "FunctionalValidator implementado, 19/19 tests pasados. "
                      "Solo datos sinteticos. Sin validacion con herramientas externas.")

        # ─── H7: RVS predicts user satisfaction ────────────────────────────
        # Evidence: RVS computed, thesis > 200 thumbnails test passes.
        # But: no user study, no real-world validation.
        # → STAR 1 (observation isolee, no user validation)
        self.register("H7", ConfidenceLevel.STAR_1,
                      "RVS implementado, test tesis > thumbnails pasa. "
                      "Sin validacion con usuarios reales.")

        # ─── H8: 95% crossover is an artifact ──────────────────────────────
        # Evidence: Crossover at 95% observed, but only with limited carving.
        # The carving motor only supports 3 formats (JPEG, PNG, PDF).
        # → STAR 1 (observation isolee, single dataset, limited carving)
        self.register("H8", ConfidenceLevel.STAR_1,
                      "Crossover al 95% observado con carving limitado. "
                      "Un solo dataset. Carving solo soporta 3 formatos.")

        # ─── BLOCKER-001: Previous A vs B comparisons are invalid ──────────
        # Evidence: Code review confirmed both Motor A and Motor B use MFT.
        # Motor Carving implemented and verified (mft_entries_parsed=0).
        # → STAR 3 (code review + experiment + different datasets)
        self.register("BLOCKER-001", ConfidenceLevel.STAR_3,
                      "Resuelto: Motor Carving implementado, verificado. "
                      "Comparaciones previas A vs B eran invalidas.")

        # ─── RVS: Recovery Value Score ─────────────────────────────────────
        # Evidence: Implemented, thesis > thumbnails test passes.
        # Multi-dimensional (value × replaceability × recreation × emotional).
        # → STAR 2 (implemented, tested, but no user validation)
        self.register("RVS", ConfidenceLevel.STAR_2,
                      "RVS implementado con 4 dimensiones. "
                      "Test tesis > thumbnails pasa. Sin validacion de usuarios.")

        # ─── FQS: Functional Quality Score ─────────────────────────────────
        # Evidence: FunctionalValidator implemented, 5 recovery levels.
        # → STAR 2 (implemented, 19/19 tests pass, synthetic only)
        self.register("FQS", ConfidenceLevel.STAR_2,
                      "FunctionalValidator implementado con 5 niveles. "
                      "19/19 tests pasados. Solo datos sinteticos.")

        # ─── WFS: Weighted Functional Score (= RVS × FQS) ─────────────────
        # Evidence: Not yet implemented as a separate metric.
        # Currently implicit in the judge.
        # → STAR 1 (concept defined, not yet implemented as separate metric)
        self.register("WFS", ConfidenceLevel.STAR_1,
                      "Concepto definido (RVS × FQS). Aun no implementado "
                      "como metrica separada en el Judge.")

        # ─── H1.6: Determinism ─────────────────────────────────────────────
        # Evidence: Stability test runs 100 times, deterministic.
        # → STAR 2 (repeated 100 times, deterministic)
        self.register("H1.6", ConfidenceLevel.STAR_2,
                      "Stability test: 100 ejecuciones, resultados deterministas. "
                      "Solo con datasets sinteticos.")

        # ─── H1.5: Lab represents NTFS well enough ─────────────────────────
        # Evidence: Lab has NO fragmentation, NO directory hierarchy, NO INDX.
        # → STAR 1 (significant gaps identified)
        self.register("H1.5", ConfidenceLevel.STAR_1,
                      "Gaps significativos: sin fragmentacion, sin jerarquia, "
                      "sin INDX. Resultados no predictivos de discos reales.")

        # ─── H1.7: Motor C confidence correlates with recovery ─────────────
        # Evidence: Motor C barely improves over MFT-First (5% support).
        # → STAR 1 (weak evidence, Motor C fallbacks not implemented)
        self.register("H1.7", ConfidenceLevel.STAR_1,
                      "Motor C apenas supera a MFT-First (5% support). "
                      "Fallbacks no implementados.")

    def register(self, result_id: str, level: ConfidenceLevel, description: str):
        """Register a new result with its initial confidence level."""
        now = datetime.now(timezone.utc).isoformat()
        entry = ConfidenceEntry(
            result_id=result_id,
            current_level=level,
            last_updated=now,
        )
        # Add the initial evidence
        entry.add_evidence(ConfidenceEvidence(
            timestamp=now,
            result_id=result_id,
            star_level=level,
            description=description,
        ))
        self.entries[result_id] = entry

    def add_evidence(self, result_id: str, evidence: ConfidenceEvidence):
        """Add evidence to an existing result."""
        if result_id not in self.entries:
            self.entries[result_id] = ConfidenceEntry(result_id=result_id)
        self.entries[result_id].add_evidence(evidence)

    def upgrade(self, result_id: str, new_level: ConfidenceLevel,
                description: str, experiment_id: str = ""):
        """
        Upgrade the confidence level of a result.

        Stars can only go UP. If the new level is lower, it's ignored
        (but the evidence is still recorded).
        """
        now = datetime.now(timezone.utc).isoformat()
        evidence = ConfidenceEvidence(
            timestamp=now,
            result_id=result_id,
            star_level=new_level,
            description=description,
            experiment_id=experiment_id,
        )
        self.add_evidence(result_id, evidence)

    def contest(self, result_id: str, description: str,
                star_level: ConfidenceLevel = ConfidenceLevel.STAR_2,
                experiment_id: str = ""):
        """
        Record a contradiction to a result.

        This doesn't lower the star level, but marks it as contested.
        """
        now = datetime.now(timezone.utc).isoformat()
        evidence = ConfidenceEvidence(
            timestamp=now,
            result_id=result_id,
            star_level=star_level,
            description=description,
            experiment_id=experiment_id,
            is_contradictory=True,
        )
        self.add_evidence(result_id, evidence)

    def get_level(self, result_id: str) -> Optional[ConfidenceLevel]:
        """Get the current confidence level for a result."""
        entry = self.entries.get(result_id)
        return entry.current_level if entry else None

    def get_entry(self, result_id: str) -> Optional[ConfidenceEntry]:
        """Get the full entry for a result."""
        return self.entries.get(result_id)

    def report(self) -> str:
        """Generate a human-readable confidence report."""
        lines = [
            "=" * 70,
            "RECOVERYLAB — Confidence Registry",
            "=" * 70,
            "",
            "Star Scale:",
            "  *     — Observation isolee (single run, single dataset)",
            "  **    — Repete 10+ fois (deterministic, same dataset)",
            "  ***   — Repete avec datasets differents (stable across conditions)",
            "  ****  — Valide avec outils externes (PhotoRec, TestDisk, etc.)",
            "  ***** — Valide avec hardware reel (actual disks)",
            "",
            "-" * 70,
        ]

        # Sort by: contested first, then by star level (ascending)
        sorted_entries = sorted(
            self.entries.values(),
            key=lambda e: (not e.is_contested, e.current_level.value)
        )

        for entry in sorted_entries:
            star_str = entry.current_level.stars
            contest_str = " [CONTESTED]" if entry.is_contested else ""
            lines.append(
                f"  {entry.result_id:15s} → {star_str:5s} ({entry.current_level.value}/5)"
                f"{contest_str}"
            )
            # Show the latest evidence description
            if entry.evidence:
                latest = entry.evidence[-1]
                lines.append(f"    {latest.description}")
            if entry.is_contested:
                lines.append(f"    Contested by: {entry.contestation_summary}")
            lines.append("")

        lines.append("-" * 70)
        lines.append("")

        # Summary statistics
        total = len(self.entries)
        contested = sum(1 for e in self.entries.values() if e.is_contested)
        by_level = {}
        for entry in self.entries.values():
            level = entry.current_level.value
            by_level[level] = by_level.get(level, 0) + 1

        lines.append(f"  Total results: {total}")
        lines.append(f"  Contested: {contested}")
        for level in sorted(by_level.keys()):
            lines.append(f"  {level}-star: {by_level[level]}")

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)

    def to_dict(self) -> Dict:
        """Serialize the registry to a dictionary."""
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_results": len(self.entries),
            "contested": sum(1 for e in self.entries.values() if e.is_contested),
            "entries": {
                rid: entry.to_dict()
                for rid, entry in self.entries.items()
            },
            "summary": {
                "star_1": sum(1 for e in self.entries.values() if e.current_level.value == 1),
                "star_2": sum(1 for e in self.entries.values() if e.current_level.value == 2),
                "star_3": sum(1 for e in self.entries.values() if e.current_level.value == 3),
                "star_4": sum(1 for e in self.entries.values() if e.current_level.value == 4),
                "star_5": sum(1 for e in self.entries.values() if e.current_level.value == 5),
            },
        }

    def save(self, path: Path):
        """Save the registry to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: Path) -> "ConfidenceRegistry":
        """Load a registry from a JSON file."""
        with open(path, 'r') as f:
            data = json.load(f)

        registry = cls()
        registry.entries = {}

        for rid, entry_data in data.get("entries", {}).items():
            entry = ConfidenceEntry(
                result_id=rid,
                current_level=ConfidenceLevel(entry_data["current_level"]),
                last_updated=entry_data.get("last_updated", ""),
            )
            for ev_data in entry_data.get("evidence", []):
                evidence = ConfidenceEvidence(
                    timestamp=ev_data["timestamp"],
                    result_id=ev_data["result_id"],
                    star_level=ConfidenceLevel(ev_data["star_level"]),
                    description=ev_data["description"],
                    experiment_id=ev_data.get("experiment_id", ""),
                    dataset_id=ev_data.get("dataset_id", ""),
                    n_runs=ev_data.get("n_runs", 1),
                    is_contradictory=ev_data.get("is_contradictory", False),
                    contradiction_details=ev_data.get("contradiction_details", ""),
                )
                entry.evidence.append(evidence)
            registry.entries[rid] = entry

        return registry


# ─── Singleton accessor ───────────────────────────────────────────────────────

_registry_instance = None

def get_confidence_registry() -> ConfidenceRegistry:
    """Get the global ConfidenceRegistry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ConfidenceRegistry()
    return _registry_instance


if __name__ == "__main__":
    registry = get_confidence_registry()
    print(registry.report())

    # Save to file
    output_path = Path(__file__).parent.parent / "output" / "results" / "confidence_registry.json"
    registry.save(output_path)
    print(f"\nSaved to: {output_path}")
