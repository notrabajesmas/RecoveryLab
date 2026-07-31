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

        # ─── H4: The Damage × Strategy Matrix ────────────────────────────
        # The most useful artifact is not a single curve, but a MATRIX:
        # damage_type × strategy → expected outcome. This maps the problem
        # space and tells us which strategy to use for each damage pattern.
        # The matrix is the LAB's real product — not a single motor.
        self.register(
            "H4",
            "Para cada tipo de daño, existe una estrategia que produce "
            "los mejores resultados. La combinación de estas relaciones "
            "forma una matriz daño×estrategia que predice la estrategia "
            "óptima para cada estado del medio.",
            open_questions=[
                "¿Cuántos tipos de daño distintos existen en la práctica?",
                "¿La matriz tiene dimensiones finitas o es un espacio continuo?",
                "¿Se puede construir la matriz empíricamente con el laboratorio?",
                "¿La matriz es universal (independiente del disco) o específica?",
                "¿Cómo se generaliza la matriz a filesystems no-NTFS?",
            ],
            dependencies=["H2"],
        )
        self.add_evidence("H4", Evidence(
            timestamp=datetime.now(timezone.utc).isoformat(),
            type=EvidenceType.SIMULATION,
            supports=True,
            description="Evidencia preliminar de la matriz: "
                        "MFT parcial → MFT-First gana (90/100). "
                        "Head crash inicio → Carving gana (MFT en primeros sectores). "
                        "Sectores intermitentes → Carving parcialmente gana (2/15 vs 0/15). "
                        "Runlists corruptos → sin datos aún. "
                        "Bitmap roto → sin datos aún. "
                        "La matriz es más útil que una sola curva porque mapea "
                        "el espacio de problemas completo.",
            experiment_id="experiment_v2_20260730_142442",
            strength="weak",
            details={
                "matrix_rows": ["MFT parcial", "Head crash inicio", "Sectores intermitentes"],
                "matrix_cols": ["MFT-First", "Carving", "Motor C"],
                "filled_cells": 3,
                "total_cells": 9,
            },
        ))

        # ─── H5: Per-format recovery differs ─────────────────────────────
        # The user loses FILES, not sectors. Each format has different
        # properties that affect recovery strategy effectiveness.
        # JPEG (footer FF D9) is easier to carve than TXT (no signature).
        # The experiment axis should be per-format, not per-MFT-degradation.
        self.register(
            "H5",
            "La efectividad de cada estrategia de recuperación depende "
            "del formato de archivo. Archivos con firmas fuertes y footers "
            "confiables (JPEG, PNG) son más recuperables por carving que "
            "archivos sin firmas (TXT, LOG) o con firmas ambiguas (ZIP/DOCX).",
            open_questions=[
                "¿Cuál es la tasa de recuperación por formato para cada estrategia?",
                "¿Existe un formato donde carving siempre supera a MFT-First?",
                "¿La fragmentación afecta más a unos formatos que a otros?",
                "¿Cómo se compara la recuperación de RAW (CR2, NEF) vs JPEG?",
            ],
            dependencies=["H1.1"],
        )

        # ─── H6: Functional recovery is not binary ────────────────────────
        # "What does 'recovered' mean?" A JPEG with 2 bad pixels is NOT "failed".
        # An MP4 that plays is NOT "lost". A DOCX that opens but lost an image
        # is NOT "worth zero". Recovery is functional, not binary.
        self.register(
            "H6",
            "La recuperación de archivos no es binaria (SHA-256 coincide/no). "
            "Existe un espectro de recuperación funcional: un archivo puede "
            "ser FULL (bit-perfect), FUNCTIONAL (funciona con daño menor), "
            "PARTIAL (funciona parcialmente), DEGRADED (contenido accesible "
            "pero dañado), o FAILED (inutilizable). La métrica de recuperación "
            "funcional es más representativa del mundo real que el checksum binario.",
            open_questions=[
                "¿Cómo se correlaciona la recuperación funcional con la satisfacción del usuario?",
                "¿Un JPEG con 2 píxeles corruptos tiene el mismo valor que uno perfecto?",
                "¿Un MP4 que se reproduce pero tiene checksum distinto está 'recuperado'?",
                "¿Un DOCX que abre pero perdió una imagen vale cero?",
                "¿Cómo se integra la recuperación funcional con el RVS?",
            ],
            dependencies=["H5"],
        )

        # ─── H7: Recovery Value Score predicts user satisfaction ───────────
        # Not all files have the same value. A motor that recovers 200 thumbnails
        # but loses the thesis has objectively done a worse job. RVS captures
        # this by weighting: Value × Replacement Probability × Recreation Time ×
        # Emotional Impact.
        self.register(
            "H7",
            "El Recovery Value Score (RVS) es un mejor predictor de la utilidad "
            "de una recuperación que el conteo bruto de archivos. El RVS incorpora "
            "cuatro dimensiones: valor intrínseco del archivo, probabilidad de "
            "reemplazo, tiempo de recreación, e impacto emocional de la pérdida. "
            "Un motor que recupera la tesis pero pierde 200 thumbnails tiene mayor "
            "RVS que uno que recupera 200 thumbnails pero pierde la tesis.",
            open_questions=[
                "¿El RVS se correlaciona con la satisfacción del usuario?",
                "¿Son los pesos del RVS correctos? ¿Cómo se calibran?",
                "¿El RVS debería incluir el formato del archivo como factor?",
                "¿Cómo se integra el RVS con la recuperación funcional (H6)?",
                "¿El WFS (Weighted Functional Score = RVS × funcionalidad) "
                "es la métrica definitiva?",
            ],
            dependencies=["H5", "H6"],
        )

        # ─── H8: The 95% crossover is an artifact ─────────────────────────
        # The crossover point at 95% MFT degradation is NOT a discovery.
        # It's a property of the current carving motor's low ceiling.
        # If carving supported more formats, the curve would change completely.
        self.register(
            "H8",
            "El punto de crossover observado en los experimentos es una propiedad "
            "del motor de carving actual, no una propiedad del espacio de "
            "estrategias. El carving básico tiene un techo bajo porque solo "
            "soporta firmas de header+footer y no distingue formatos ambiguos. "
            "Un motor de carving con soporte completo de formatos y parsers "
            "funcionales cambiaría la curva de crossover significativamente.",
            open_questions=[
                "¿Dónde está el crossover real con un carving completo?",
                "¿El crossover depende del dataset (tipos de archivos)?",
                "¿Existe un crossover para cada formato individual?",
                "¿Se puede eliminar el crossover con un motor adaptativo?",
            ],
            dependencies=["H3", "H5"],
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

        # H2: Strategy Crossover — the most important hypothesis
        # Original: "Motor C supera estrategias fijas"
        # Refined: The observable frontier where optimal strategy changes
        # This is FALSIFIABLE — we can find the exact crossover point
        # H1 asks: "Is MFT useful?"
        # H2 asks: "When does the optimal strategy change?"
        # These are DIFFERENT questions. H2 is the more valuable one.
        self.register(
            "H2",
            "Existe una frontera observable donde la estrategia óptima cambia "
            "según el estado del medio. Específicamente, existe un punto de "
            "degradación del MFT a partir del cual una estrategia de carving "
            "supera a una estrategia basada en metadatos.",
            open_questions=[
                "¿Cuál es el porcentaje exacto de degradación del MFT donde ocurre el crossover?",
                "¿El crossover es gradual o abrupto?",
                "¿El crossover depende del tipo de daño (intermitente vs destrucción total)?",
                "¿El crossover cambia con el tipo de archivo (JPEG vs PDF vs TXT)?",
                "¿El crossover se mantiene con discos reales?",
            ],
            dependencies=["H1.1"],
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

        # ─── H2: Crossover Curve evidence ──────────────────────────────
        # IMPORTANT CAVEAT: The crossover at 95% is NOT a discovery.
        # It is an artifact of the current carving motor's limited format support.
        # Carving only recovers 1/15 files (6.7%) because it only supports
        # JPEG, PNG, PDF, ZIP, MP4, DOCX signatures. If carving supported
        # TIFF, CR2, NEF, MOV, SQLite, XLSX, etc., the curve would shift.
        # The 95% crossover point is a property of the current carving motor,
        # not a property of the strategy space.
        now_crossover = datetime.now(timezone.utc).isoformat()
        self.add_evidence("H2", Evidence(
            timestamp=now_crossover,
            type=EvidenceType.SIMULATION,
            supports=True,
            description="Crossover Curve (21 puntos, 5 repeticiones): "
                        "MFT-First supera a Carving desde 0% hasta 95% de daño del MFT. "
                        "CAVEAT: El crossover al 95% NO es un descubrimiento — es una "
                        "propiedad del carving actual (solo 6.7% recovery, 1/15 archivos). "
                        "Si el carving soportara más formatos, la curva cambiaría. "
                        "Lo que SÍ es sólido: las curvas se cruzan, confirmando que "
                        "los modos de falla son distintos.",
            experiment_id="crossover_curve_20260730",
            strength="moderate",  # Downgraded from "strong" — ceiling artifact
            details={
                "crossover_point": 0.95,
                "crossover_type": "gradual",
                "carving_constant_recovery": 0.067,
                "mft_at_0_pct": 0.933,
                "mft_at_100_pct": 0.0,
                "caveat": "Crossover point is artifact of limited carving format support. "
                          "Not a discovery. Need expanded carving + per-format experiments.",
            },
        ))

        # ─── H2: The REAL insight — different failure modes ─────────────
        # The one conclusion that IS solid even with current limitations:
        # metadata-based and signature-based strategies fail differently.
        self.add_evidence("H2", Evidence(
            timestamp=now_crossover,
            type=EvidenceType.SIMULATION,
            supports=True,
            description="CONCLUSIÓN SÓLIDA: Una estrategia basada en metadatos y una "
                        "estrategia basada en firmas no fallan de la misma manera. "
                        "MFT-First falla cuando el MFT es inaccesible (A09: 0/15). "
                        "Carving falla cuando los archivos no tienen firmas conocidas "
                        "o están fragmentados. Sus modos de falla son DISTINTOS. "
                        "Eso es exactamente el tipo de evidencia que justifica un orquestador.",
            experiment_id="crossover_curve_20260730",
            strength="strong",
            details={
                "insight": "different_failure_modes",
                "mft_fails_when": "MFT inaccessible (sectores intermitentes, head crash inicio)",
                "carving_fails_when": "No signatures, fragmented files, no footers",
            },
        ))

        # ─── H3: No universally optimal strategy ─────────────────────────
        # If H2 is true (there's a crossover frontier), then H3 follows:
        # No single strategy wins everywhere. The value is in the SELECTOR.
        # This is the real product: not "the best algorithm" but
        # "the best system for choosing algorithms."
        #
        # CAVEAT: H3 is NOT yet demonstrated. The current evidence is consistent
        # with H3, but the strategy space evaluated is still too small:
        #   - Only basic MFT parser vs basic carving (6 signatures)
        #   - Missing: advanced carving, journal-first, bitmap-guided,
        #     USN-guided, MFT Mirror recovery, tolerant parser,
        #     probabilistic carving
        # We should write: "La evidencia preliminar es consistente con H3,
        # pero el espacio de estrategias evaluadas aún es reducido
        # para considerarla demostrada."
        self.register(
            "H3",
            "No existe una estrategia de recuperación universalmente óptima. "
            "Para cualquier estrategia fija, existe al menos un estado del medio "
            "donde otra estrategia fija produce mejores resultados.",
            open_questions=[
                "¿Es H3 una consecuencia de H2, o una hipótesis independiente?",
                "¿Se puede demostrar H3 con un contraejemplo para cada estrategia?",
                "¿H3 implica que Motor C siempre es mejor que cualquier estrategia fija?",
                "¿Existen estrategias que son 'casi universalmente óptimas'?",
                "¿El espacio de estrategias evaluadas es suficiente para demostrar H3? "
                "Actualmente solo tenemos MFT parser básico + carving básico (6 firmas).",
                "¿Qué pasa con journal-first, bitmap-guided, USN-guided, MFT Mirror, "
                "parser tolerante, carving probabilístico?",
            ],
            dependencies=["H2"],
        )
        self.add_evidence("H3", Evidence(
            timestamp=now_blocker,
            type=EvidenceType.SIMULATION,
            supports=True,
            description="La evidencia preliminar es CONSISTENTE con H3, pero el espacio "
                        "de estrategias evaluadas aún es reducido para considerarla "
                        "demostrada. MFT-First supera a Carving en 90/100 escenarios, "
                        "pero Carving supera a MFT-First en A09 (intermitente). "
                        "Ninguna estrategia gana en todos los escenarios. "
                        "Sin embargo, solo comparamos un parser MFT básico contra un "
                        "carving muy básico (6 firmas). Faltan: carving avanzado, "
                        "journal-first, bitmap-guided, USN-guided, MFT Mirror, "
                        "parser tolerante a corrupción, carving probabilístico.",
            experiment_id="experiment_v2_20260730_142442",
            strength="weak",  # Downgraded from "moderate" — strategy space too small
            details={
                "mft_wins": 90, "carving_wins": 9, "neutral": 1,
                "note": "A09 es el contraejemplo para MFT-First, pero "
                        "el espacio de estrategias es demasiado reducido",
                "strategies_evaluated": ["MFT parser básico", "carving básico (6 firmas)"],
                "strategies_missing": ["journal-first", "bitmap-guided", "USN-guided",
                                       "MFT Mirror recovery", "tolerant parser",
                                       "probabilistic carving", "advanced carving"],
            },
        ))

        # ─── Critical review: 95% crossover is NOT a discovery ─────────
        # The user's key insight: the 95% crossover point is an artifact of the
        # current carving motor's low ceiling, not a scientific finding.
        # If carving supported more formats, the curve would change completely.
        self.add_evidence("H3", Evidence(
            timestamp=datetime.now(timezone.utc).isoformat(),
            type=EvidenceType.SIMULATION,
            supports=True,
            description="REVISIÓN CRÍTICA: El punto de crossover al 95% NO es un "
                        "descubrimiento. Es una propiedad del carving actual, que solo "
                        "recupera 1/15 archivos. El carving básico tiene un techo bajo "
                        "porque: (1) solo soporta firmas de header+footer, (2) no puede "
                        "distinguir ZIP/DOCX/XLSX, (3) no tiene parsers funcionales. "
                        "Si el carving soportara más formatos (JPEG, PNG, TIFF, CR2, NEF, "
                        "MP4, MOV, ZIP, DOCX, XLSX, SQLite, PDF), la curva cambiaría "
                        "completamente. El 95% no es una propiedad del espacio de "
                        "estrategias — es una propiedad del motor de carving actual. "
                        "H3 sigue siendo consistente con la evidencia (las estrategias "
                        "fallan de maneras distintas), pero el espacio evaluado es "
                        "demasiado reducido para considerarla demostrada.",
            experiment_id="critical_review_20260730",
            strength="moderate",
            details={
                "crossover_artifact": True,
                "crossover_pct": 0.95,
                "carving_ceiling": "1/15 archivos",
                "reason": "Carving básico con soporte limitado de formatos",
                "missing_strategies": 7,
                "h3_status": "consistente pero no demostrada",
            },
        ))

        # ─── H9: JPEG Exposure — cascade effect reveals hidden delimitation defect ───
        # Derived from PRED-007 (INCONCLUSIVE): when BMP false positives were removed,
        # JPEG files that were previously eliminated at Dedup now reached the Judge,
        # where they were classified as SHA-256 mismatches due to truncation.
        # This is NOT a Judge defect — it's a delimitation defect that was HIDDEN
        # by the upstream BMP cascade. The Judge acts as a diagnostic instrument.
        self.register(
            "H9",
            "Al eliminar las pérdidas en Dedup (RP-002), aumenta el flujo de "
            "candidatos JPEG hacia el Judge, exponiendo defectos de delimitación "
            "JPEG que antes permanecían ocultos. Específicamente: el carving motor "
            "usa el primer FFD9 como footer, pero los JPEG pueden contener "
            "múltiples marcadores FFD9 dentro de su payload, causando que el "
            "archivo se trunque prematuramente. El Judge no cambió — cambió el "
            "flujo de entrada que antes era filtrado por el BMP cascade.",
            open_questions=[
                "¿El primer FFD9 aparece dentro del payload JPEG o es el verdadero EOI?",
                "¿El parser usa el primer footer en lugar del último?",
                "¿La delimitación ignora la estructura interna del JPEG?",
                "¿El Dataset Builder genera JPEG válidos con FFD9 internos?",
                "¿PhotoRec presenta el mismo comportamiento sobre exactamente esos archivos?",
                "¿Cuántos FFD9 contiene un JPEG típico dentro de sus datos?",
                "¿La solución es buscar el ÚLTIMO FFD9 o validar la estructura JPEG?",
            ],
            dependencies=["H5"],
        )
        now_h9 = datetime.now(timezone.utc).isoformat()
        self.add_evidence("H9", Evidence(
            timestamp=now_h9,
            type=EvidenceType.SIMULATION,
            supports=True,
            description="PRED-007 (INCONCLUSIVE): losses_at_judge pasó de 0.8% (4/525) a 8.6% "
                        "(45/525) después de RP-002. Los 45 archivos son JPEG truncados que "
                        "antes eran eliminados por dedup (BMP cascade) y ahora llegan al Judge. "
                        "Los JPEG truncados muestran carved_size << gt_size (ej: 63101 vs 928182, "
                        "1467 vs 2615725). El patrón de truncamiento es consistente con "
                        "delimitación prematura por FFD9 dentro del payload.",
            experiment_id="INST-0002",
            strength="moderate",
            details={
                "pred_007_status": "INCONCLUSIVE",
                "judge_loss_pre_rp002": "0.8% (4/525)",
                "judge_loss_post_rp002": "8.6% (45/525)",
                "all_45_are_jpeg": True,
                "truncation_pattern": "carved_size << gt_size",
                "example_truncation": "jpg_0001: carved=63101 gt=928182 (865081 bytes short)",
            },
        ))
        self.add_evidence("H9", Evidence(
            timestamp=now_h9,
            type=EvidenceType.SIMULATION,
            supports=True,
            description="Análisis del código fuente: motor_carving.py._find_footer() busca "
                        "la PRIMERA ocurrencia del footer bytes. Para JPEG, el footer es "
                        "b'\\xFF\\xD9' (FFD9 = EOI marker). Si el payload JPEG contiene "
                        "FFD9 dentro de sus datos de imagen (ej: thumbnails EXIF, datos "
                        "de imagen comprimidos), el parser se detiene en el primer FFD9 "
                        "en lugar del último. Esto es consistente con la observación de "
                        "truncamiento severo (archivos de ~1MB truncados a ~60KB).",
            experiment_id="code_review_motor_carving",
            strength="moderate",
            details={
                "function": "_find_footer",
                "behavior": "returns first occurrence of footer bytes",
                "jpeg_footer": "b'\\xFF\\xD9'",
                "line_range": "593-619",
            },
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
