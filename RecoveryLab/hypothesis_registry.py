"""
RecoveryLab — Hypothesis Registry
====================================
Formal tracking of hypotheses, evidence, and status.

The goal is NOT "add features" — it's "close hypotheses with evidence."

Each hypothesis has:
  - ID: Unique identifier (H1.1, H1.2, H1.3, ...)
  - Statement: What we're testing
  - Status: pending | in_evaluation | supported | refuted | refined
  - Evidence: What experiments support or refute this
  - Confidence: How confident we are (0.0-1.0)
  - Dependencies: What hypotheses must be resolved first
  - Open questions: What we still don't know

The registry is append-only. Once a hypothesis is supported or refuted,
it stays that way. If it's refined, the refinement becomes a new hypothesis.

This is the single source of truth for the project's scientific direction.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum


class HypothesisStatus(Enum):
    PENDING = "pending"
    IN_EVALUATION = "in_evaluation"
    SUPPORTED = "supported"
    REFUTED = "refuted"
    REFINED = "refined"       # Original was too broad; split into sub-hypotheses
    INCONCLUSIVE = "inconclusive"


class EvidenceType(Enum):
    SIMULATION = "simulation"       # From RecoveryLab experiments
    EXTERNAL_TOOL = "external_tool" # From TestDisk, PhotoRec, etc.
    REAL_DISK = "real_disk"         # From actual hardware
    LITERATURE = "literature"       # From published research
    FORMAL = "formal"               # From mathematical proof


@dataclass
class Evidence:
    """A piece of evidence supporting or refuting a hypothesis."""
    timestamp: str
    type: EvidenceType
    supports: bool                  # True = supports, False = refutes
    description: str
    experiment_id: str = ""         # Link to experiment results
    strength: str = "moderate"      # weak | moderate | strong
    details: Dict = field(default_factory=dict)


@dataclass
class Hypothesis:
    """A single hypothesis with full tracking."""
    id: str
    statement: str
    status: HypothesisStatus = HypothesisStatus.PENDING
    confidence: float = 0.0
    evidence: List[Evidence] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    refinement_of: Optional[str] = None   # If this refines a previous hypothesis
    created_at: str = ""
    updated_at: str = ""

    def add_evidence(self, evidence: Evidence):
        """Add evidence and update status/confidence."""
        self.evidence.append(evidence)
        self.updated_at = datetime.now(timezone.utc).isoformat()
        self._recompute_status()

    def _recompute_status(self):
        """Recompute status based on accumulated evidence."""
        if not self.evidence:
            self.status = HypothesisStatus.PENDING
            return

        supports = [e for e in self.evidence if e.supports]
        refutes = [e for e in self.evidence if not e.supports]

        support_strength = sum(
            {"weak": 1, "moderate": 2, "strong": 3}[e.strength]
            for e in supports
        )
        refute_strength = sum(
            {"weak": 1, "moderate": 2, "strong": 3}[e.strength]
            for e in refutes
        )

        total = support_strength + refute_strength
        if total == 0:
            self.confidence = 0.5
            self.status = HypothesisStatus.INCONCLUSIVE
            return

        self.confidence = support_strength / total

        if self.confidence >= 0.8:
            self.status = HypothesisStatus.SUPPORTED
        elif self.confidence <= 0.2:
            self.status = HypothesisStatus.REFUTED
        elif len(self.evidence) < 3:
            self.status = HypothesisStatus.IN_EVALUATION
        else:
            self.status = HypothesisStatus.INCONCLUSIVE

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "statement": self.statement,
            "status": self.status.value,
            "confidence": round(self.confidence, 3),
            "evidence": [
                {
                    "timestamp": e.timestamp,
                    "type": e.type.value,
                    "supports": e.supports,
                    "description": e.description,
                    "experiment_id": e.experiment_id,
                    "strength": e.strength,
                }
                for e in self.evidence
            ],
            "dependencies": self.dependencies,
            "open_questions": self.open_questions,
            "refinement_of": self.refinement_of,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class HypothesisRegistry:
    """
    The single source of truth for project hypotheses.

    Append-only: once a hypothesis is registered, it stays.
    Evidence accumulates over time. Status updates automatically.
    """

    def __init__(self):
        self.hypotheses: Dict[str, Hypothesis] = {}
        self._init_core_hypotheses()

    def _init_core_hypotheses(self):
        """Initialize the core hypotheses from the project's evolution."""

        now = datetime.now(timezone.utc).isoformat()

        # H1.1: Metadata prioritization reduces acquisition cost (REFINED)
        # Original: "Priorizar metadatos reduce lecturas"
        # Refined: Precise statement about acquisition cost, not just "lecturas"
        self.register(
            "H1.1",
            "Cuando los metadatos son confiables, una estrategia guiada por metadatos "
            "reduce el costo de adquisición sin disminuir la recuperación, "
            "comparada con una estrategia de carving puro.",
            open_questions=[
                "¿Cuál es el umbral de 'confiables'? (¿85%? ¿73%? ¿50%?)",
                "¿Cómo cambia el resultado con archivos fragmentados?",
                "¿La ventaja se mantiene con discos reales?",
                "BLOCKER-001: Las comparaciones previas A vs B NO son válidas — "
                "ambos usan MFT como fuente primaria. Necesitamos comparar "
            "contra Carving real (sin MFT).",
            ],
        )
        # Add existing evidence from first experiment
        self.add_evidence("H1.1", Evidence(
            timestamp=now,
            type=EvidenceType.SIMULATION,
            supports=True,
            description="Experimento 75 escenarios: Motor B usa 50-60% menos lecturas "
                        "en 93.3% de escenarios con MFT intacto",
            experiment_id="experiment_20260730_091046",
            strength="moderate",
            details={"avg_reads_saved": 9354, "support_pct": 0.933},
        ))
        self.add_evidence("H1.1", Evidence(
            timestamp=now,
            type=EvidenceType.SIMULATION,
            supports=False,
            description="A09 (sectores intermitentes): Motor B recupera 0% vs Motor A 26-40%. "
                        "Sin fallback, MFT-first colapsa cuando sectores MFT están dañados.",
            experiment_id="experiment_20260730_091046",
            strength="strong",
            details={"attack": "A09", "motor_a_recovery": 0.33, "motor_b_recovery": 0.0},
        ))

        # H1.2: There exists a threshold for switching strategy
        self.register(
            "H1.2",
            "Cuando la confianza en los metadatos cae por debajo de un umbral, "
            "la estrategia óptima deja de ser la priorización y pasa a ser "
            "una estrategia híbrida.",
            open_questions=[
                "¿Cuál es el valor exacto del umbral? (¿85%? ¿73%? ¿50%?)",
                "¿El umbral es gradual o abrupto?",
                "¿El umbral depende del tipo de daño?",
                "¿Existe un umbral en discos reales?",
            ],
            dependencies=["H1.1"],
        )
        self.add_evidence("H1.2", Evidence(
            timestamp=now,
            type=EvidenceType.SIMULATION,
            supports=True,
            description="A09 demuestra que MFT-first colapsa sin fallback. "
                        "Existe un punto donde la estrategia debe cambiar.",
            experiment_id="experiment_20260730_091046",
            strength="weak",
            details={"note": "Demuestra necesidad, no valor del umbral"},
        ))
        self.add_evidence("H1.2", Evidence(
            timestamp=now,
            type=EvidenceType.SIMULATION,
            supports=False,
            description="Confidence Sweep no encontró umbral abrupto: "
                        "Motor B nunca recupera MENOS que Motor A (ambos usan MFT como fuente). "
                        "El umbral solo existe si los fallbacks funcionan.",
            experiment_id="confidence_sweep_20260730",
            strength="moderate",
        ))

        # H1.3: Journal outperforms carving when MFT is partial
        self.register(
            "H1.3",
            "Cuando el MFT está parcialmente dañado, la estrategia Journal-guided "
            "recupera más archivos que el carving puro.",
            open_questions=[
                "¿El journal de NTFS contiene suficiente información de archivo?",
                "¿Cómo se compara con INDX recovery?",
                "¿Qué pasa si el journal también está corrupto?",
            ],
            dependencies=["H1.2"],
        )

        # H1.4: Bitmap improves recovery when MFT is damaged
        self.register(
            "H1.4",
            "El bitmap de asignación mejora la recuperación en discos con MFT dañada, "
            "al reducir el espacio de búsqueda para carving.",
            open_questions=[
                "¿Cuánto reduce el espacio de búsqueda?",
                "¿Qué pasa si el bitmap está parcialmente corrupto?",
                "¿Un bitmap vacío (todo zeros) es peor que no tener bitmap?",
            ],
            dependencies=["H1.2"],
        )

        # H1.5: The lab represents NTFS well enough
        self.register(
            "H1.5",
            "El RecoveryLab captura suficientes características de NTFS real "
            "como para que los resultados del laboratorio sean predictivos "
            "de comportamiento en discos reales.",
            open_questions=[
                "¿Los resultados cambian con archivos fragmentados?",
                "¿Los resultados cambian con jerarquía de directorios?",
                "¿Los resultados cambian con atributos extendidos?",
                "¿Qué pasa con discos creados por Windows real?",
            ],
        )
        self.add_evidence("H1.5", Evidence(
            timestamp=now,
            type=EvidenceType.SIMULATION,
            supports=False,
            description="El laboratorio NO tiene fragmentación (hardcoded 0.0), "
                        "NO tiene jerarquía de directorios, NO tiene INDX records. "
                        "Motor A y Motor B recuperan archivos idénticos porque ambos "
                        "son parseadores de MFT con diferente orden de lectura.",
            experiment_id="code_review",
            strength="strong",
        ))

        # H1.6: Determinism — same scenario produces same result
        self.register(
            "H1.6",
            "El RecoveryLab produce resultados deterministas: "
            "ejecutar el mismo escenario 100 veces produce exactamente el mismo resultado.",
            open_questions=[
                "¿Hay alguna fuente de no-determinismo en el código?",
                "¿Los RNG con seed producen exactamente las mismas secuencias?",
            ],
        )

        # H1.7: Motor C's confidence calculation correlates with real recovery
        self.register(
            "H1.7",
            "La confianza calculada por Motor C (user_readable / user_total) "
            "está correlacionada con la tasa de recuperación real.",
            open_questions=[
                "¿La correlación es lineal o no lineal?",
                "¿Qué señales adicionales mejorarían la confianza calculada?",
                "¿MFT Mirror consistencia es una señal útil?",
            ],
            dependencies=["H1.2"],
        )

        # H2: An adaptive strategy consistently outperforms any fixed strategy
        # This is the NEW hypothesis — the one about the value of the ORCHESTRATOR,
        # not the value of any single data source.
        # H1 asks: "Is MFT useful?"
        # H2 asks: "Is the strategy selector useful?"
        # These are DIFFERENT questions.
        self.register(
            "H2",
            "Una estrategia adaptativa (que selecciona entre carving, MFT-first, "
            "journal-guided, bitmap-guided según el estado del disco) "
            "supera consistentemente a cualquier estrategia fija individual, "
            "medida por la relación entre recuperación, tiempo y riesgo.",
            open_questions=[
                "¿Qué métrica combina recuperación, tiempo y riesgo de forma justa?",
                "¿'Consistentemente' significa en todos los escenarios o en la mayoría?",
                "¿Hay escenarios donde una estrategia fija es suficiente?",
                "¿Motor C puede ser peor que una estrategia fija en algún caso?",
                "¿Cómo se compara contra un técnico humano experimentado?",
            ],
            dependencies=["H1.1", "H1.2"],
        )

        # BLOCKER-001: All previous A vs B comparisons are invalid
        self.register(
            "BLOCKER-001",
            "Las comparaciones previas Motor A vs Motor B NO son científicamente válidas "
            "porque ambas estrategias comparten la misma fuente de datos primaria (MFT). "
            "Motor A no es carving — es 'MFT-last'. Necesitamos un Motor Carving "
            "real (solo firmas, nunca MFT) para validar H1.1.",
            open_questions=[
                "¿Motor Carving recupera menos archivos que MFT-first cuando MFT está intacto?",
                "¿Motor Carving recupera MÁS archivos que MFT-first cuando MFT está destruido?",
                "¿Cuál es el punto de crossover?",
            ],
        )
        now_blocker = datetime.now(timezone.utc).isoformat()
        self.add_evidence("BLOCKER-001", Evidence(
            timestamp=now_blocker,
            type=EvidenceType.SIMULATION,
            supports=True,
            description="Análisis de código: Motor A tiene FILE_SIGNATURES pero nunca lo usa. "
                        "Ambos motores llaman a _parse_mft_record(). Motor A lee todo "
                        "secuencialmente y DESPUÉS parsea MFT. Motor B lee MFT primero. "
                        "Ambos dependen del MFT como fuente de verdad.",
            experiment_id="code_review_20260730",
            strength="strong",
        ))
        self.add_evidence("BLOCKER-001", Evidence(
            timestamp=now_blocker,
            type=EvidenceType.SIMULATION,
            supports=True,
            description="RESUELTO: Motor Carving implementado. Recupera 3-4/15 archivos "
                        "con firmas (JPEG, PNG, PDF) vs MFT-First 14/15. "
                        "MFT entries parsed = 0 (verificado: NUNCA lee MFT). "
                        "Comparación Carving vs MFT-First VALIDADA por strategy_profiles.py.",
            experiment_id="experiment_v2_20260730_142442",
            strength="strong",
        ))

        # ─── H1.1: New evidence from 3-strategy experiment ─────────────
        self.add_evidence("H1.1", Evidence(
            timestamp=now_blocker,
            type=EvidenceType.SIMULATION,
            supports=True,
            description="Experimento v2 (100 escenarios, 3 estrategias): "
                        "MFT-First supera a Carving en 100/100 escenarios. "
                        "Avg Δ recovery rate: +43.87%. MFT-First recupera "
                        "significativamente más archivos que Carving puro. "
                        "STRONG_SUPPORT en 90/100 escenarios.",
            experiment_id="experiment_v2_20260730_142442",
            strength="strong",
            details={
                "support_pct": 1.0,
                "avg_delta_recovery": 0.4387,
                "strong_support_count": 90,
                "strong_refutation_count": 9,
            },
        ))
        self.add_evidence("H1.1", Evidence(
            timestamp=now_blocker,
            type=EvidenceType.SIMULATION,
            supports=False,
            description="A09 (sectores intermitentes): Carving recupera 2/15 archivos, "
                        "MFT-First recupera 0/15. Cuando el MFT es inaccesible, "
                        "Carving supera a MFT-First. 9 escenarios de STRONG_REFUTATION.",
            experiment_id="experiment_v2_20260730_142442",
            strength="strong",
            details={"attack": "A09", "carving_recovery": 0.133, "mft_recovery": 0.0},
        ))

        # ─── H2: First evidence — Motor C recovers when both fail ──────
        self.add_evidence("H2", Evidence(
            timestamp=now_blocker,
            type=EvidenceType.SIMULATION,
            supports=True,
            description="A09 (sectores intermitentes): Carving=2/15, MFT-First=0/15, "
                        "Motor C=4/15. Motor C es el ÚNICO que recupera archivos "
                        "cuando MFT es inaccesible y Carving tiene baja cobertura. "
                        "Motor C usa diagnóstico (DecisionTrace) para decidir estrategia híbrida.",
            experiment_id="experiment_v2_20260730_142442",
            strength="moderate",
            details={"attack": "A09", "carving": 0.133, "mft": 0.0, "motor_c": 0.267},
        ))
        self.add_evidence("H2", Evidence(
            timestamp=now_blocker,
            type=EvidenceType.SIMULATION,
            supports=False,
            description="MFT-First vs Motor C: Motor C apenas supera a MFT-First "
                        "(5% supported, avg Δ recovery +1.40%). Motor C gasta más "
                        "lecturas (-1737 avg). En la mayoría de escenarios, Motor C "
                        "no mejora sobre MFT-First porque el diagnóstico tiene costo "
                        "y el fallback no está implementado (Journal/Bitmap/INDX = stubs).",
            experiment_id="experiment_v2_20260730_142442",
            strength="moderate",
            details={"support_pct": 0.05, "avg_delta_recovery": 0.014},
        ))

    def register(self, hypothesis_id: str, statement: str,
                 status: HypothesisStatus = HypothesisStatus.PENDING,
                 dependencies: List[str] = None,
                 open_questions: List[str] = None,
                 refinement_of: str = None) -> Hypothesis:
        """Register a new hypothesis."""
        if hypothesis_id in self.hypotheses:
            return self.hypotheses[hypothesis_id]

        now = datetime.now(timezone.utc).isoformat()
        h = Hypothesis(
            id=hypothesis_id,
            statement=statement,
            status=status,
            dependencies=dependencies or [],
            open_questions=open_questions or [],
            refinement_of=refinement_of,
            created_at=now,
            updated_at=now,
        )
        self.hypotheses[hypothesis_id] = h
        return h

    def add_evidence(self, hypothesis_id: str, evidence: Evidence):
        """Add evidence to a hypothesis."""
        if hypothesis_id not in self.hypotheses:
            raise ValueError(f"Unknown hypothesis: {hypothesis_id}")
        self.hypotheses[hypothesis_id].add_evidence(evidence)

    def get(self, hypothesis_id: str) -> Optional[Hypothesis]:
        """Get a hypothesis by ID."""
        return self.hypotheses.get(hypothesis_id)

    def all_hypotheses(self) -> List[Hypothesis]:
        """Get all hypotheses sorted by ID."""
        return sorted(self.hypotheses.values(), key=lambda h: h.id)

    def summary_table(self) -> str:
        """Generate a markdown summary table of all hypotheses."""
        lines = [
            "# RecoveryLab — Hypothesis Registry",
            "",
            "| ID | Hypothesis | Status | Confidence | Evidence | Open Questions |",
            "|----|-----------|--------|------------|----------|----------------|",
        ]
        for h in self.all_hypotheses():
            supports = sum(1 for e in h.evidence if e.supports)
            refutes = sum(1 for e in h.evidence if not e.supports)
            evidence_str = f"{supports}S / {refutes}R"
            questions = len(h.open_questions)
            lines.append(
                f"| {h.id} | {h.statement[:60]}... | {h.status.value} | "
                f"{h.confidence:.0%} | {evidence_str} | {questions} |"
            )
        return "\n".join(lines)

    def detailed_report(self) -> str:
        """Generate a detailed report of all hypotheses."""
        lines = ["# RecoveryLab — Detailed Hypothesis Report", ""]

        for h in self.all_hypotheses():
            lines.append(f"## {h.id}: {h.statement}")
            lines.append(f"**Status:** {h.status.value}")
            lines.append(f"**Confidence:** {h.confidence:.0%}")
            if h.refinement_of:
                lines.append(f"**Refinement of:** {h.refinement_of}")
            if h.dependencies:
                lines.append(f"**Dependencies:** {', '.join(h.dependencies)}")
            lines.append("")

            if h.evidence:
                lines.append("### Evidence")
                for i, e in enumerate(h.evidence, 1):
                    symbol = "✓" if e.supports else "✗"
                    lines.append(
                        f"{i}. {symbol} [{e.type.value}] {e.description} "
                        f"(strength: {e.strength})"
                    )
                lines.append("")

            if h.open_questions:
                lines.append("### Open Questions")
                for q in h.open_questions:
                    lines.append(f"- {q}")
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def save(self, path: Path):
        """Save the registry to a JSON file."""
        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "hypotheses": {h_id: h.to_dict() for h_id, h in self.hypotheses.items()},
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self, path: Path):
        """Load the registry from a JSON file."""
        with open(path, 'r') as f:
            data = json.load(f)

        for h_id, h_data in data.get("hypotheses", {}).items():
            if h_id in self.hypotheses:
                # Update existing hypothesis with loaded evidence
                h = self.hypotheses[h_id]
                for e_data in h_data.get("evidence", []):
                    # Check if we already have this evidence
                    already_exists = any(
                        e.description == e_data["description"]
                        for e in h.evidence
                    )
                    if not already_exists:
                        h.add_evidence(Evidence(
                            timestamp=e_data["timestamp"],
                            type=EvidenceType(e_data["type"]),
                            supports=e_data["supports"],
                            description=e_data["description"],
                            experiment_id=e_data.get("experiment_id", ""),
                            strength=e_data.get("strength", "moderate"),
                        ))

    def next_steps(self) -> List[str]:
        """What experiments should we run next to close open hypotheses?"""
        steps = []

        # Check what's most needed
        for h in self.all_hypotheses():
            if h.status == HypothesisStatus.PENDING:
                steps.append(
                    f"[{h.id}] PENDING — needs first experiment: {h.open_questions[0] if h.open_questions else 'design experiment'}"
                )
            elif h.status == HypothesisStatus.IN_EVALUATION:
                steps.append(
                    f"[{h.id}] IN EVALUATION — needs more evidence: {h.open_questions[0] if h.open_questions else 'gather more data'}"
                )
            elif h.status == HypothesisStatus.INCONCLUSIVE:
                steps.append(
                    f"[{h.id}] INCONCLUSIVE — conflicting evidence, need decisive experiment"
                )

        return steps


# ─── Singleton for convenience ────────────────────────────────────────────────

_registry = None

def get_registry() -> HypothesisRegistry:
    """Get the global hypothesis registry."""
    global _registry
    if _registry is None:
        _registry = HypothesisRegistry()
    return _registry


if __name__ == "__main__":
    registry = get_registry()
    print(registry.summary_table())
    print()
    print("Next steps:")
    for step in registry.next_steps():
        print(f"  {step}")
