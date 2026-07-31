"""
RecoveryLab — Evidence Gate
=============================
The most important module in the project.

This module enforces the rule that NO claim can use language like
"demuestra" (demonstrates) until it has passed through the Evidence Gate.

Evidence levels:
  1. OBSERVED     — seen once, one dataset, one run
  2. REPEATED     — repeated 10+ times, same dataset
  3. REPRODUCIBLE — reproduced with different datasets
  4. EXTERNALLY_VALIDATED — validated with external tools (PhotoRec, R-Studio, DMDE)
  5. HARDWARE_VALIDATED   — validated with real hardware

Language rules:
  Level 1-2: "observamos" (we observed), "es consistente con" (is consistent with)
  Level 3:   "la evidencia sugiere" (evidence suggests), "es reproducible" (is reproducible)
  Level 4:   "demuestra" (demonstrates), "validado externamente" (externally validated)
  Level 5:   "confirmado" (confirmed), "predictivo del mundo real" (predictive of real world)

FORBIDDEN at levels 1-3:
  - "demuestra" / "demonstrates"
  - "prueba" / "proves"
  - "confirma" / "confirms"
  - "establece" / "establishes"

This is not a stylistic preference. It is a scientific discipline.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum, auto
from datetime import datetime
import json
import os


class EvidenceLevel(Enum):
    """Five levels of evidence strength."""
    OBSERVED = 1              # Seen once, one dataset, one run
    REPEATED = 2              # Repeated 10+ times, same dataset
    REPRODUCIBLE = 3          # Reproduced with different datasets
    EXTERNALLY_VALIDATED = 4  # Validated with external tools
    HARDWARE_VALIDATED = 5    # Validated with real hardware


class ClaimStatus(Enum):
    """Status of a claim."""
    DRAFT = "DRAFT"           # Not yet evaluated
    ACTIVE = "ACTIVE"         # Under evaluation
    CONTESTED = "CONTESTED"   # Contradictory evidence exists
    REFUTED = "REFUTED"       # Evidence contradicts the claim
    SUPERSEDED = "SUPERSEDED" # Replaced by a better claim


# ─── Language Rules ──────────────────────────────────────────────────────────

FORBIDDEN_WORDS_LOW_EVIDENCE = {
    "demuestra", "demonstrates", "prueba", "proves", "confirma",
    "confirms", "establece", "establishes", "garantiza", "guarantees",
    "verifica", "verifies", "comprueba", "validates",
}

ALLOWED_WORDS_BY_LEVEL = {
    1: ["observamos", "we observed", "es consistente con", "is consistent with",
        "vimos", "we saw", "aparece", "appears"],
    2: ["es estable", "is stable", "se repite", "repeats",
        "es consistente en repeticiones", "is consistent across repetitions"],
    3: ["la evidencia sugiere", "evidence suggests", "es reproducible",
        "is reproducible", "los datos indican", "data indicates",
        "es generalizable", "is generalizable"],
    4: ["demuestra", "demonstrates", "validado externamente",
        "externally validated", "es robusto", "is robust",
        "comparable con el estado del arte", "comparable with state of the art"],
    5: ["confirmado", "confirmed", "predictivo del mundo real",
        "predictive of real world", "definitivo", "definitive"],
}


@dataclass
class EvidenceEntry:
    """A single piece of evidence supporting or refuting a claim."""
    experiment_id: str         # e.g., "EXP-001"
    date: str                  # ISO format
    dataset: str               # Dataset used
    result: str                # Brief description
    supports: bool             # True = supports, False = refutes
    notes: str = ""


@dataclass
class ThreatLink:
    """A link between a claim and a threat to validity."""
    threat_id: str             # e.g., "T03"
    description: str
    impact: str = "UNKNOWN"    # LOW / MEDIUM / HIGH / CRITICAL


@dataclass
class Claim:
    """
    A single claim in the Evidence Gate system.

    Each claim has its own evidence file, linked threats, and
    a current evidence level that determines what language is
    permitted when describing it.
    """
    claim_id: str                     # e.g., "CLAIM-001"
    title: str                        # Short description
    hypothesis: str = ""              # Linked hypothesis (e.g., "H1.1")
    status: ClaimStatus = ClaimStatus.DRAFT
    evidence_level: EvidenceLevel = EvidenceLevel.OBSERVED
    evidence: List[EvidenceEntry] = field(default_factory=list)
    threats: List[ThreatLink] = field(default_factory=list)
    next_experiment: str = ""         # What experiment is needed next
    created_date: str = ""
    last_updated: str = ""

    def add_evidence(self, experiment_id: str, dataset: str, result: str,
                     supports: bool, notes: str = ""):
        """Add a piece of evidence to this claim."""
        entry = EvidenceEntry(
            experiment_id=experiment_id,
            date=datetime.now().isoformat(),
            dataset=dataset,
            result=result,
            supports=supports,
            notes=notes,
        )
        self.evidence.append(entry)
        self.last_updated = datetime.now().isoformat()
        self._recalculate_level()

    def add_threat(self, threat_id: str, description: str, impact: str = "UNKNOWN"):
        """Link a threat to validity to this claim."""
        link = ThreatLink(
            threat_id=threat_id,
            description=description,
            impact=impact,
        )
        self.threats.append(link)

    def _recalculate_level(self):
        """Recalculate evidence level based on accumulated evidence."""
        supporting = [e for e in self.evidence if e.supports]
        datasets = set(e.dataset for e in supporting)

        if len(supporting) == 0:
            self.evidence_level = EvidenceLevel.OBSERVED
        elif len(supporting) >= 10 and len(datasets) >= 3:
            self.evidence_level = EvidenceLevel.REPRODUCIBLE
        elif len(supporting) >= 10:
            self.evidence_level = EvidenceLevel.REPEATED
        else:
            self.evidence_level = EvidenceLevel.OBSERVED

        # Levels 4 and 5 require explicit promotion (not automatic)
        # They can only be set via promote_to_external / promote_to_hardware

    def promote_to_external(self):
        """Promote to EXTERNALLY_VALIDATED (requires manual decision)."""
        if self.evidence_level.value >= EvidenceLevel.REPRODUCIBLE.value:
            self.evidence_level = EvidenceLevel.EXTERNALLY_VALIDATED
            self.last_updated = datetime.now().isoformat()

    def promote_to_hardware(self):
        """Promote to HARDWARE_VALIDATED (requires manual decision)."""
        if self.evidence_level.value >= EvidenceLevel.EXTERNALLY_VALIDATED.value:
            self.evidence_level = EvidenceLevel.HARDWARE_VALIDATED
            self.last_updated = datetime.now().isoformat()

    def check_language(self, text: str) -> Dict:
        """
        Check if the given text uses language appropriate for this claim's
        evidence level.

        Returns a dict with:
          - approved: bool
          - violations: list of forbidden words found
          - allowed_phrases: list of phrases that ARE allowed at this level
          - suggested_rewrite: suggested alternative for each violation
        """
        text_lower = text.lower()
        violations = []

        for word in FORBIDDEN_WORDS_LOW_EVIDENCE:
            if word in text_lower and self.evidence_level.value < 4:
                violations.append(word)

        level = self.evidence_level.value
        allowed = ALLOWED_WORDS_BY_LEVEL.get(level, [])

        return {
            "approved": len(violations) == 0,
            "violations": violations,
            "allowed_phrases": allowed,
            "evidence_level": self.evidence_level.name,
            "claim_id": self.claim_id,
            "suggestion": (
                f"Use language appropriate for level {level} ({self.evidence_level.name}): "
                f"{', '.join(allowed[:3])}"
                if violations else
                "Language is appropriate for the evidence level."
            ),
        }

    def gate_status(self) -> str:
        """
        Return a visual gate status showing progress through the 5 levels.

        This is the Evidence Gate visualization.
        """
        level = self.evidence_level.value
        checks = []
        for i in range(1, 6):
            if i <= level:
                checks.append("[X]")
            else:
                checks.append("[ ]")

        labels = [
            "observado",
            "repetido",
            "reproducible",
            "validado externamente",
            "validado en hardware real",
        ]

        lines = [f"Claim: {self.claim_id} — {self.title}"]
        for i, (check, label) in enumerate(zip(checks, labels)):
            lines.append(f"  {check} {label}")

        lines.append(f"  Language permitted: {', '.join(ALLOWED_WORDS_BY_LEVEL.get(level, [])[:3])}")

        if level < 4:
            lines.append(f"  FORBIDDEN: demuestra, prueba, confirma, establece")

        return "\n".join(lines)

    def to_dict(self) -> Dict:
        return {
            "claim_id": self.claim_id,
            "title": self.title,
            "hypothesis": self.hypothesis,
            "status": self.status.value,
            "evidence_level": self.evidence_level.name,
            "evidence_count": len(self.evidence),
            "supporting_count": len([e for e in self.evidence if e.supports]),
            "refuting_count": len([e for e in self.evidence if not e.supports]),
            "datasets_count": len(set(e.dataset for e in self.evidence if e.supports)),
            "threats_count": len(self.threats),
            "next_experiment": self.next_experiment,
            "created_date": self.created_date,
            "last_updated": self.last_updated,
            "evidence": [
                {
                    "experiment_id": e.experiment_id,
                    "date": e.date,
                    "dataset": e.dataset,
                    "result": e.result,
                    "supports": e.supports,
                    "notes": e.notes,
                }
                for e in self.evidence
            ],
            "threats": [
                {
                    "threat_id": t.threat_id,
                    "description": t.description,
                    "impact": t.impact,
                }
                for t in self.threats
            ],
        }

    def to_markdown(self) -> str:
        """Generate a CLAIM file in markdown format."""
        level = self.evidence_level.value
        checks = []
        for i in range(1, 6):
            checks.append("[X]" if i <= level else "[ ]")

        labels = [
            "observado",
            "repetido",
            "reproducible",
            "validado externamente",
            "validado en hardware real",
        ]

        lines = [
            f"# {self.claim_id}: {self.title}",
            "",
            f"**Hipotesis vinculada:** {self.hypothesis or 'N/A'}",
            f"**Estado:** {self.status.value}",
            f"**Nivel de evidencia:** {self.evidence_level.name} ({level}/5)",
            "",
            "## Evidence Gate",
            "",
        ]
        for check, label in zip(checks, labels):
            lines.append(f"- {check} {label}")

        lines.extend([
            "",
            "## Evidencia",
            "",
        ])

        if not self.evidence:
            lines.append("Sin evidencia registrada.")
        else:
            for e in self.evidence:
                icon = "+" if e.supports else "-"
                lines.append(
                    f"- [{icon}] {e.experiment_id} ({e.dataset}): {e.result}"
                )

        lines.extend([
            "",
            "## Amenazas a la validez",
            "",
        ])

        if not self.threats:
            lines.append("Sin amenazas vinculadas.")
        else:
            for t in self.threats:
                lines.append(f"- {t.threat_id} ({t.impact}): {t.description}")

        lines.extend([
            "",
            "## Proximo experimento necesario",
            "",
            self.next_experiment or "No definido.",
            "",
            "## Lenguaje permitido",
            "",
        ])

        allowed = ALLOWED_WORDS_BY_LEVEL.get(level, [])
        lines.append(f"**Permitido:** {', '.join(allowed)}")

        if level < 4:
            lines.append(f"**PROHIBIDO:** demuestra, prueba, confirma, establece")
            lines.append("")
            lines.append("> Mientras no llegue al cuarto casillero, queda prohibido escribir 'demuestra'.")
            lines.append("> Solo: 'es consistente con' o 'observamos'.")

        lines.extend([
            "",
            "---",
            f"Creado: {self.created_date}",
            f"Actualizado: {self.last_updated}",
        ])

        return "\n".join(lines)


class EvidenceGate:
    """
    The central gate that controls all claims in the project.

    Usage:
        gate = EvidenceGate()
        gate.register_claim(claim)
        gate.check_language("CLAIM-001", "Motor C demuestra que...")
        # → VIOLATION: "demuestra" is forbidden at level OBSERVED
    """

    def __init__(self, claims_dir: str = ""):
        self.claims: Dict[str, Claim] = {}
        self.claims_dir = claims_dir

    def register_claim(self, claim: Claim):
        """Register a new claim in the gate."""
        self.claims[claim.claim_id] = claim

    def check_language(self, claim_id: str, text: str) -> Dict:
        """Check if text uses language appropriate for the claim's evidence level."""
        if claim_id not in self.claims:
            return {
                "approved": False,
                "error": f"Claim {claim_id} not found in the Evidence Gate.",
            }
        return self.claims[claim_id].check_language(text)

    def get_claim(self, claim_id: str) -> Optional[Claim]:
        """Get a claim by ID."""
        return self.claims.get(claim_id)

    def list_claims(self) -> List[Dict]:
        """List all claims with their current status."""
        return [
            {
                "claim_id": c.claim_id,
                "title": c.title,
                "status": c.status.value,
                "evidence_level": c.evidence_level.name,
                "evidence_count": len(c.evidence),
                "datasets_count": len(set(e.dataset for e in c.evidence if e.supports)),
            }
            for c in self.claims.values()
        ]

    def kpi_dashboard(self) -> str:
        """
        Generate the Research KPI Dashboard.

        This replaces the software development dashboard.
        The project no longer measures lines of code or features.
        It measures the quality of evidence.
        """
        total = len(self.claims)
        if total == 0:
            return "No claims registered yet."

        by_level = {i: 0 for i in range(1, 6)}
        for c in self.claims.values():
            by_level[c.evidence_level.value] += 1

        three_plus = sum(v for k, v in by_level.items() if k >= 3)
        four_plus = sum(v for k, v in by_level.items() if k >= 4)

        total_threats = sum(len(c.threats) for c in self.claims.values())
        open_threats = sum(
            1 for c in self.claims.values()
            for t in c.threats
            if t.impact in ("HIGH", "CRITICAL", "UNKNOWN")
        )

        lines = [
            "=" * 60,
            "RECOVERYLAB — RESEARCH KPI DASHBOARD",
            "=" * 60,
            "",
            "KPI                              | Actual  | Objetivo",
            "-" * 60,
            f"Resultados con 3+ estrellas      | {three_plus:>3}/{total:<3} | 5/15 (Fase A)",
            f"Resultados con 4+ estrellas      | {four_plus:>3}/{total:<3} | 0/15 (Fase A)",
            f"Claims con evidencia suficiente  | {three_plus:>3}/{total:<3} | Aumentar lentamente",
            f"Amenazas registradas             | {total_threats:>3}      | Documentar todas",
            f"Amenazas abiertas (HIGH/CRIT)    | {open_threats:>3}      | Reducir",
            "",
            "Distribucion por nivel de evidencia:",
        ]

        level_names = {
            1: "OBSERVED",
            2: "REPEATED",
            3: "REPRODUCIBLE",
            4: "EXTERNALLY_VALIDATED",
            5: "HARDWARE_VALIDATED",
        }
        for i in range(1, 6):
            bar = "#" * by_level[i]
            lines.append(f"  {level_names[i]:25s} | {by_level[i]:>2} {bar}")

        lines.extend([
            "",
            "META-REGLA: No agregar una sola caracteristica nueva",
            "si no aumenta la calidad de la evidencia.",
            "=" * 60,
        ])

        return "\n".join(lines)

    def save_all_claims(self, directory: str = ""):
        """Save all claims as markdown files in the claims directory."""
        save_dir = directory or self.claims_dir
        if not save_dir:
            return

        os.makedirs(save_dir, exist_ok=True)

        for claim in self.claims.values():
            filepath = os.path.join(save_dir, f"{claim.claim_id}.md")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(claim.to_markdown())

        # Also save the gate index
        index_path = os.path.join(save_dir, "gate_index.json")
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(self.list_claims(), f, indent=2, ensure_ascii=False)

    def to_dict(self) -> Dict:
        return {
            "total_claims": len(self.claims),
            "claims": {k: v.to_dict() for k, v in self.claims.items()},
        }


# ─── Pre-populated Claims ────────────────────────────────────────────────────

def create_initial_claims() -> EvidenceGate:
    """Create the initial set of claims based on existing evidence."""

    gate = EvidenceGate()

    # CLAIM-001: MFT-First > Carving
    claim_001 = Claim(
        claim_id="CLAIM-001",
        title="MFT-First supera a Carving en Overall Utility cuando los metadatos son confiables",
        hypothesis="H1.1",
        status=ClaimStatus.ACTIVE,
        evidence_level=EvidenceLevel.REPRODUCIBLE,
        next_experiment="Ejecutar en 3+ datasets distintos para confirmar estabilidad",
        created_date="2026-07-30",
        last_updated="2026-07-30",
    )
    claim_001.add_evidence(
        "EXP-001", "dataset_000042", "MFT-First > Carving en 100/100 escenarios",
        supports=True, notes="100 ejecuciones, consistente"
    )
    claim_001.add_threat("T01", "Motores podrian conocer ground truth", "MITIGADA")
    claim_001.add_threat("T02", "Datasets podrian favorecer MFT-First", "HIGH")
    gate.register_claim(claim_001)

    # CLAIM-002: FQS is not binary
    claim_002 = Claim(
        claim_id="CLAIM-002",
        title="La recuperacion funcional no es binaria: existe un espectro de calidad funcional",
        hypothesis="H6",
        status=ClaimStatus.ACTIVE,
        evidence_level=EvidenceLevel.REPEATED,
        next_experiment="Ejecutar FQS en 3+ datasets distintos para alcanzar REPRODUCIBLE",
        created_date="2026-07-30",
        last_updated="2026-07-30",
    )
    claim_002.add_evidence(
        "EXP-010", "dataset_000042", "19/19 tests de FunctionalValidator pasan",
        supports=True, notes="5 niveles funcionales observados"
    )
    claim_002.add_threat("T09", "Umbrales FQS (0.8, 0.5, 0.2) son arbitrarios", "HIGH")
    gate.register_claim(claim_002)

    # CLAIM-003: RVS value model
    claim_003 = Claim(
        claim_id="CLAIM-003",
        title="Recuperar la tesis vale mas que recuperar 200 thumbnails (RVS)",
        hypothesis="H7",
        status=ClaimStatus.ACTIVE,
        evidence_level=EvidenceLevel.OBSERVED,
        next_experiment="Encuesta de calibracion RVS con usuarios reales (Seccion 5.4 del protocolo)",
        created_date="2026-07-30",
        last_updated="2026-07-30",
    )
    claim_003.add_evidence(
        "EXP-015", "synthetic", "RVS calculado: tesis=100, thumbnail=1",
        supports=True, notes="Modelo del laboratorio, sin validacion de usuarios"
    )
    claim_003.add_threat("T12", "RVS no representa valor real (sin calibracion con usuarios)", "CRITICAL")
    claim_003.add_threat("T13", "Overall Utility (RVS x FQS) no representa utilidad real", "HIGH")
    gate.register_claim(claim_003)

    # CLAIM-004: Crossover at 95% is artifact
    claim_004 = Claim(
        claim_id="CLAIM-004",
        title="El crossover al 95% MFT damage es un artefacto del carving limitado",
        hypothesis="H8",
        status=ClaimStatus.ACTIVE,
        evidence_level=EvidenceLevel.OBSERVED,
        next_experiment="Repetir con carving completo (mas formatos) para verificar si el crossover cambia",
        created_date="2026-07-30",
        last_updated="2026-07-30",
    )
    claim_004.add_evidence(
        "EXP-005", "dataset_000042", "Carving solo recupera 3 formatos (JPEG/PNG/PDF)",
        supports=True, notes="Archivos sin firma son invisibles al carving"
    )
    claim_004.add_threat("T05", "Carving limitado a 3 formatos", "HIGH")
    gate.register_claim(claim_004)

    # CLAIM-005: Parser quality
    claim_005 = Claim(
        claim_id="CLAIM-005",
        title="JPEG, PNG y PDF son parsers de referencia dorada (19/19 tests)",
        hypothesis="",
        status=ClaimStatus.ACTIVE,
        evidence_level=EvidenceLevel.REPEATED,
        next_experiment="Verificar 19/19 en 30 ejecuciones consecutivas + edge cases",
        created_date="2026-07-30",
        last_updated="2026-07-30",
    )
    claim_005.add_evidence(
        "EXP-020", "test_carving_impeccable.py", "19/19 tests pasan",
        supports=True, notes="Cobertura: JPEG, PNG, PDF, firmas, no false positives, RVS"
    )
    claim_005.add_threat("T03", "Parser sesgado", "MITIGADA")
    gate.register_claim(claim_005)

    return gate


if __name__ == "__main__":
    # Create the initial claims and save them
    gate = create_initial_claims()

    # Print the KPI dashboard
    print(gate.kpi_dashboard())
    print()

    # Print each claim's gate status
    for claim_id, claim in gate.claims.items():
        print(claim.gate_status())
        print()

    # Test the language gate
    print("=" * 60)
    print("EVIDENCE GATE — LANGUAGE TEST")
    print("=" * 60)

    test_texts = [
        ("CLAIM-001", "MFT-First demuestra que la priorizacion de metadatos es superior"),
        ("CLAIM-001", "Observamos que MFT-First es consistente con una mejora en Overall Utility"),
        ("CLAIM-003", "El RVS demuestra que la tesis vale mas que los thumbnails"),
        ("CLAIM-003", "Es consistente con la hipotesis de que la tesis vale mas"),
    ]

    for claim_id, text in test_texts:
        result = gate.check_language(claim_id, text)
        status = "APPROVED" if result["approved"] else "VIOLATION"
        print(f"\n  [{status}] {text}")
        if not result["approved"]:
            print(f"    Violations: {result['violations']}")
            print(f"    Suggestion: {result['suggestion']}")

    # Save claims to files
    claims_dir = "/home/z/my-project/RecoveryLab/claims"
    gate.save_all_claims(claims_dir)
    print(f"\nClaims saved to: {claims_dir}")
