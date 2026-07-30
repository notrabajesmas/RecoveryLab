"""
RecoveryLab — Hypothesis Audit Module
=======================================
Enforces the Research Protocol by auditing each hypothesis.

For each hypothesis, this module answers:
  1. What is the independent variable?
  2. What is the dependent variable?
  3. What is the success criterion?
  4. Is the hypothesis testable in its current form?

If a hypothesis doesn't have these three things defined,
it's not testable and should be reformulated.

Usage:
    from hypothesis_audit import audit_all_hypotheses, print_audit_report
    report = audit_all_hypotheses()
    print_audit_report(report)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class AuditStatus(Enum):
    """Status of a hypothesis audit."""
    TESTABLE = "testable"           # All 3 variables defined, ready to test
    NEEDS_REFORMULATION = "needs"   # Missing variables, needs work
    CONTESTED = "contested"         # Has contradictory evidence
    FROZEN = "frozen"               # No more experiments until Phase A complete


@dataclass
class HypothesisAudit:
    """The audit result for a single hypothesis."""
    hypothesis_id: str
    statement: str

    # The three required elements
    independent_variable: str = ""
    dependent_variable: str = ""
    success_criterion: str = ""

    # Audit status
    status: AuditStatus = AuditStatus.NEEDS_REFORMULATION
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    @property
    def is_testable(self) -> bool:
        """A hypothesis is testable if all three elements are defined."""
        return bool(self.independent_variable and
                   self.dependent_variable and
                   self.success_criterion)

    def to_dict(self) -> Dict:
        return {
            "hypothesis_id": self.hypothesis_id,
            "statement": self.statement[:100] + "..." if len(self.statement) > 100 else self.statement,
            "independent_variable": self.independent_variable,
            "dependent_variable": self.dependent_variable,
            "success_criterion": self.success_criterion,
            "status": self.status.value,
            "is_testable": self.is_testable,
            "issues": self.issues,
            "recommendations": self.recommendations,
        }


def audit_all_hypotheses() -> Dict[str, HypothesisAudit]:
    """
    Audit all hypotheses in the project against the Research Protocol.

    Returns a dict mapping hypothesis_id → HypothesisAudit.
    """
    audits = {}

    # ─── H1.1: Metadata prioritization reduces acquisition cost ────────────
    audits["H1.1"] = HypothesisAudit(
        hypothesis_id="H1.1",
        statement=(
            "Cuando los metadatos son confiables, una estrategia guiada por metadatos "
            "reduce el costo de adquisicion sin disminuir la recuperacion, "
            "comparada con una estrategia de carving puro."
        ),
        independent_variable="Estrategia (Carving vs MFT-First)",
        dependent_variable="Overall Utility (RVS × FQS)",
        success_criterion=(
            "MFT-First supera a Carving por al menos 5% en Overall Utility, "
            "consistente en 3+ datasets, con al menos 10 repeticiones por dataset"
        ),
        status=AuditStatus.TESTABLE,
        issues=[],
        recommendations=[
            "El experimento actual usa solo Recovery Rate como metrica. "
            "Migrar a Overall Utility (RVS × FQS) como metrica principal.",
            "Verificar que solo cambia la estrategia (variable independiente) "
            "y no el dataset o el nivel de dano simultaneamente.",
        ],
    )

    # ─── H1.2: Strategy switching threshold exists ────────────────────────
    audits["H1.2"] = HypothesisAudit(
        hypothesis_id="H1.2",
        statement=(
            "Cuando la confianza en los metadatos cae por debajo de un umbral, "
            "la estrategia optima deja de ser la priorizacion y pasa a ser "
            "una estrategia hibrida."
        ),
        independent_variable="Nivel de confianza en metadatos (0-100%)",
        dependent_variable="Estrategia optima (categorica)",
        success_criterion=(
            "Existe un umbral de confianza donde la estrategia optima cambia "
            "de MFT-First a hibrida, con la diferencia siendo consistente "
            "en 3+ datasets"
        ),
        status=AuditStatus.NEEDS_REFORMULATION,
        issues=[
            "El umbral exacto no esta definido. 'Confianza en metadatos' es ambiguo.",
            "Confidence Sweep no encontro umbral abrupto.",
            "La variable dependiente es categorica (estrategia optima) pero "
            "no esta claro como se determina cual es optima.",
        ],
        recommendations=[
            "Operacionalizar 'confianza en metadatos': % de entradas MFT legibles, "
            "o % de MFT con checksum valido.",
            "Definir metrica cuantitativa para 'estrategia optima': "
            "la que maximiza Overall Utility.",
            "Reformular como: 'Existe un umbral X de MFT legible donde "
            "Carving supera a MFT-First en Overall Utility.'",
        ],
    )

    # ─── H2: Strategy crossover exists ─────────────────────────────────────
    audits["H2"] = HypothesisAudit(
        hypothesis_id="H2",
        statement=(
            "Existe una frontera observable donde la estrategia optima cambia "
            "segun el estado del medio."
        ),
        independent_variable="Nivel de dano MFT (0-100%)",
        dependent_variable="Recovery Rate (y Overall Utility)",
        success_criterion=(
            "Crossover observable con un motor de carving completo (no limitado). "
            "La diferencia debe ser consistente en 3+ datasets."
        ),
        status=AuditStatus.CONTESTED,
        issues=[
            "El crossover al 95% es un artefacto del carving limitado.",
            "Solo 3 formatos soportados (JPEG, PNG, PDF) — el techo es 6.7%.",
            "No se puede confirmar ni refutar hasta que el carving sea mas completo.",
        ],
        recommendations=[
            "NO publicar el crossover al 95% como descubrimiento.",
            "La conclusion SOLIDA es: modos de falla distintos entre estrategias.",
            "Congelar: no expandir carving hasta Fase C.",
            "Reformular la hipotesis para enfocarse en los modos de falla, "
            "no en el punto de crossover.",
        ],
    )

    # ─── H4: Damage × Strategy Matrix ──────────────────────────────────────
    audits["H4"] = HypothesisAudit(
        hypothesis_id="H4",
        statement=(
            "Para cada tipo de dano, existe una estrategia que produce "
            "los mejores resultados."
        ),
        independent_variable="Tipo de dano (MFT parcial, head crash, intermitente, etc.)",
        dependent_variable="Mejor estrategia (por Overall Utility)",
        success_criterion=(
            "Matriz completa con >80% de celdas llenas, cada celda con "
            "al menos 3 repeticiones y 2+ datasets"
        ),
        status=AuditStatus.NEEDS_REFORMULATION,
        issues=[
            "La matriz actual tiene 3 celdas llenas de muchas posibles.",
            "No hay suficientes experimentos por tipo de dano.",
            "La variable dependiente es categorica (mejor estrategia) pero "
            "no se ha definido como se determina cual es la mejor.",
        ],
        recommendations=[
            "Reducir el ambito: en Fase A, solo probar 3 tipos de dano "
            "con 3 estrategias (9 celdas).",
            "Definir 'mejor' como: la que maximiza Overall Utility.",
            "Llenar una celda a la vez, con 3+ repeticiones.",
        ],
    )

    # ─── H5: Per-format recovery differs ───────────────────────────────────
    audits["H5"] = HypothesisAudit(
        hypothesis_id="H5",
        statement=(
            "La efectividad de cada estrategia depende del formato de archivo."
        ),
        independent_variable="Formato de archivo (JPEG, PNG, PDF, TXT, etc.)",
        dependent_variable="Recovery Rate por formato (y FQS por formato)",
        success_criterion=(
            "Diferencia >10% en Recovery Rate entre formatos con firmas fuertes "
            "(JPEG, PNG) y formatos sin firmas (TXT), consistente en 3+ datasets"
        ),
        status=AuditStatus.FROZEN,
        issues=[
            "No se ha ejecutado un experimento sistematico por formato.",
            "Carving solo soporta 3 formatos — no se puede comparar con TXT.",
            "El experimento per_format_experiment.py existe pero no se ha corrido "
            "con la metrica Overall Utility.",
        ],
        recommendations=[
            "Congelar: no expandir carving hasta Fase C.",
            "En Fase A: ejecutar experimentos por formato SOLO para JPEG, PNG, PDF.",
            "Medir FQS por formato para cada parser.",
            "No comparar con TXT hasta que se tenga un motor que pueda recuperar TXT "
            "(lo cual requiere MFT, no carving).",
        ],
    )

    # ─── H6: Functional recovery is not binary ─────────────────────────────
    audits["H6"] = HypothesisAudit(
        hypothesis_id="H6",
        statement=(
            "La recuperacion de archivos no es binaria (SHA-256 coincide/no). "
            "Existe un espectro de recuperacion funcional."
        ),
        independent_variable="Nivel de dano en archivo (0%, 25%, 50%, 75%, 100%)",
        dependent_variable="FQS (Functional Quality Score)",
        success_criterion=(
            "FQS varia continuamente (no binario) con el nivel de dano, "
            "con al menos 3 niveles funcionales distintos observados"
        ),
        status=AuditStatus.TESTABLE,
        issues=[],
        recommendations=[
            "Ejecutar experimento: tomar un JPEG sano, daniarlo gradualmente, "
            "medir FQS en cada nivel.",
            "Verificar que FQS produce un espectro, no un binario.",
            "Repetir con PNG y PDF.",
        ],
    )

    # ─── H7: RVS predicts user satisfaction ────────────────────────────────
    audits["H7"] = HypothesisAudit(
        hypothesis_id="H7",
        statement=(
            "El RVS es un mejor predictor de la utilidad de una recuperacion "
            "que el conteo bruto de archivos."
        ),
        independent_variable="Metrica de evaluacion (RVS vs Recovery Rate)",
        dependent_variable="Correlacion con utilidad percibida",
        success_criterion=(
            "RVS correlaciona mejor con la utilidad percibida que Recovery Rate, "
            "en al menos 3 escenarios con diferentes perfiles de valor"
        ),
        status=AuditStatus.NEEDS_REFORMULATION,
        issues=[
            "No hay validacion con usuarios reales.",
            "'Utilidad percibida' es subjetiva y no esta operacionalizada.",
            "No se puede testar sin un estudio de usuarios.",
        ],
        recommendations=[
            "Reformular como hipotesis no-testable por ahora: "
            "'RVS captura la importancia de los archivos mejor que el conteo bruto.'",
            "Probar con escenarios sinteticos: tesis vs thumbnails, "
            "donde el resultado correcto es obvio.",
            "Dejar la validacion con usuarios para la Fase B.",
        ],
    )

    # ─── H8: 95% crossover is an artifact ──────────────────────────────────
    audits["H8"] = HypothesisAudit(
        hypothesis_id="H8",
        statement=(
            "El punto de crossover observado es una propiedad del motor de "
            "carving actual, no una propiedad del espacio de estrategias."
        ),
        independent_variable="Motor de carving (limitado vs completo)",
        dependent_variable="Crossover point (% MFT dano donde Carving > MFT-First)",
        success_criterion=(
            "El crossover cambia significativamente cuando se expande el carving "
            "a mas formatos (de 95% a un valor diferente)"
        ),
        status=AuditStatus.FROZEN,
        issues=[
            "No se puede testar hasta que el carving soporte mas formatos.",
            "Congelado hasta Fase C.",
        ],
        recommendations=[
            "NO publicar el crossover al 95% como descubrimiento.",
            "Marcar como hipotesis congelada.",
            "Revisar en Fase C cuando se agregue un nuevo formato.",
        ],
    )

    # ─── H1.5: Lab represents NTFS well enough ────────────────────────────
    audits["H1.5"] = HypothesisAudit(
        hypothesis_id="H1.5",
        statement=(
            "El RecoveryLab captura suficientes caracteristicas de NTFS real "
            "como para que los resultados sean predictivos de comportamiento en discos reales."
        ),
        independent_variable="Representacion del NTFS (simplificado vs real)",
        dependent_variable="Correlacion con resultados de discos reales",
        success_criterion=(
            "Resultados del laboratorio predicen correctamente el ranking de "
            "estrategias en al menos 3 discos reales"
        ),
        status=AuditStatus.NEEDS_REFORMULATION,
        issues=[
            "Sin fragmentacion, sin jerarquia, sin INDX.",
            "No hay forma de testar sin discos reales.",
            "La variable independiente no es manipulable.",
        ],
        recommendations=[
            "Reformular como: 'Las limitaciones del laboratorio (sin fragmentacion, "
            "sin INDX) afectan los resultados de que manera?'",
            "En Fase B: comparar con resultados de PhotoRec/TestDisk.",
            "En Fase C: agregar fragmentacion y medir el impacto.",
        ],
    )

    # ─── H1.6: Determinism ────────────────────────────────────────────────
    audits["H1.6"] = HypothesisAudit(
        hypothesis_id="H1.6",
        statement=(
            "El RecoveryLab produce resultados deterministas."
        ),
        independent_variable="Ejecucion (run 1 vs run 2 vs ... vs run N)",
        dependent_variable="Resultado (hash del resultado)",
        success_criterion=(
            "100 ejecuciones del mismo escenario producen resultados identicos "
            "(mismo hash de resultado)"
        ),
        status=AuditStatus.TESTABLE,
        issues=[],
        recommendations=[
            "Ya verificado: 100 ejecuciones, determinista.",
            "Re-ejecutar periodicamente cuando se agregue codigo nuevo.",
        ],
    )

    # ─── H1.7: Motor C confidence correlates with recovery ─────────────────
    audits["H1.7"] = HypothesisAudit(
        hypothesis_id="H1.7",
        statement=(
            "La confianza calculada por Motor C esta correlacionada con "
            "la tasa de recuperacion real."
        ),
        independent_variable="Nivel de confianza calculado por Motor C",
        dependent_variable="Recovery Rate real",
        success_criterion=(
            "Correlacion positiva (r > 0.7) entre confianza calculada y "
            "recovery rate, en al menos 3 tipos de dano"
        ),
        status=AuditStatus.NEEDS_REFORMULATION,
        issues=[
            "Motor C apenas supera a MFT-First (5% support).",
            "Fallbacks no implementados (Journal, Bitmap, INDX = stubs).",
            "La confianza de Motor C no es una metrica independiente — "
            "es derivada del MFT.",
        ],
        recommendations=[
            "Congelar Motor C hasta que los fallbacks esten implementados.",
            "Reformular como: 'El diagnostico de estado del disco de Motor C "
            "predice la estrategia optima.'",
        ],
    )

    return audits


def print_audit_report(audits: Dict[str, HypothesisAudit]) -> str:
    """Print a human-readable audit report."""
    lines = [
        "=" * 70,
        "RECOVERYLAB — Hypothesis Audit Report",
        "=" * 70,
        "",
    ]

    testable = [a for a in audits.values() if a.status == AuditStatus.TESTABLE]
    needs = [a for a in audits.values() if a.status == AuditStatus.NEEDS_REFORMULATION]
    contested = [a for a in audits.values() if a.status == AuditStatus.CONTESTED]
    frozen = [a for a in audits.values() if a.status == AuditStatus.FROZEN]

    for group_name, group in [
        ("TESTABLE", testable),
        ("NEEDS REFORMULATION", needs),
        ("CONTESTED", contested),
        ("FROZEN", frozen),
    ]:
        if not group:
            continue
        lines.append(f"--- {group_name} ({len(group)}) ---")
        for audit in group:
            lines.append(f"  {audit.hypothesis_id}")
            lines.append(f"    IV: {audit.independent_variable or 'NOT DEFINED'}")
            lines.append(f"    DV: {audit.dependent_variable or 'NOT DEFINED'}")
            lines.append(f"    SC: {audit.success_criterion or 'NOT DEFINED'}")
            if audit.issues:
                lines.append(f"    Issues: {'; '.join(audit.issues)}")
            lines.append("")

    lines.append("-" * 70)
    lines.append(f"  Testable: {len(testable)}")
    lines.append(f"  Needs reformulation: {len(needs)}")
    lines.append(f"  Contested: {len(contested)}")
    lines.append(f"  Frozen: {len(frozen)}")
    lines.append("=" * 70)

    return "\n".join(lines)


if __name__ == "__main__":
    audits = audit_all_hypotheses()
    print(print_audit_report(audits))
