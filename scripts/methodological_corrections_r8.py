#!/usr/bin/env python3
"""
Methodological Corrections — Round 8 Audit
============================================
Applies the auditor's methodological corrections:

1. CLAIM-001 REFINEMENT: Restrict to observed conditions, not general claim.
   OLD: "MFT-First > Carving"
   NEW: "En los datasets sintéticos evaluados durante EXP-0001 y EXP-0002,
         MFT-First obtuvo un Overall Utility superior al Motor Carving."

2. RCR CORRECTION: Do NOT count Repeated claims toward RCR.
   RCR = Reproducible Claims Ratio, not Repeated Claims Ratio.
   Until EXP-0003 runs on another machine, claims remain at REPEATED (level 2),
   not REPRODUCIBLE (level 3). RCR stays at 0%.

3. EVIDENCE LEDGER SEPARATION: Observation vs. Explanation.
   OBSERVATION: "Motor Carving obtuvo Overall Utility = 0.0 en EXP-0001,
                 EXP-0002, y EXP-0005 bajo condiciones X, Y, Z."
   EXPLANATION: "El Motor Carving no aprovecha la corrupción" — THIS IS A
                HYPOTHESIS, not a claim. At least 7 hypotheses are compatible
                with the observation.

4. ELEVATE LAB DETERMINISM: The claim "The lab produces identical results
   under identical conditions" is the most important result of Phase A.
   It doesn't depend on any motor or dataset — it depends on the lab itself.
   If this survives across seeds, machines, and OSes, RecoveryLab becomes
   a reliable experimental platform.

This script generates the corrected artifacts.
"""

import json
import datetime
from pathlib import Path

OUTPUT_DIR = Path("/home/z/my-project/output/methodological_corrections_r8")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_refined_claims():
    """Generate the corrected claim registry with refined language."""
    claims = {
        "CLAIM-001": {
            "id": "CLAIM-001",
            "title": "MFT-First obtuvo OU superior a Carving en datasets sintéticos evaluados",
            "statement": (
                "En los datasets sintéticos evaluados durante EXP-0001 y EXP-0002, "
                "con semillas 42, 1337, 2026 y 9999, imágenes NTFS de 10 MB sin corrupción, "
                "y utilizando Judge API v1.0 y Protocol v1.5, el Motor MFT-First obtuvo "
                "un Overall Utility superior al Motor Carving."
            ),
            "evidence_level": "REPEATED",
            "evidence_level_number": 2,
            "evidence_level_note": (
                "REPEATED, no REPRODUCIBLE. EXP-0003 ejecutó en la misma máquina, "
                "no en otra máquina ni por otro investigador. Hasta que no se "
                "reproduzca externamente, el RCR no cuenta este claim."
            ),
            "supporting_experiments": ["EXP-0001", "EXP-0002"],
            "conditions": {
                "datasets": "sintéticos, 10 MB, sin corrupción",
                "seeds": [42, 1337, 2026, 9999],
                "motors": ["MFT-First v1.0", "Carving v1.0"],
                "judge": "v1.0",
                "protocol": "v1.5",
            },
            "what_this_claim_does_NOT_say": [
                "No dice que MFT-First sea 'mejor' en general",
                "No dice que MFT-First sea superior en imágenes corruptas",
                "No dice que MFT-First sea superior en datasets reales",
                "No dice que MFT-First sea superior en otros tamaños de dataset",
                "No dice que la diferencia sea estadísticamente significativa (SD=0 impide test tradicional)",
            ],
            "threats": [
                "T02 (ALTO): datasets pueden favorecer MFT-First por diseño",
                "T03 (MITIGADO): sesgo del parser controlado",
                "T_NEW (ALTO): SD=0 impide evaluación estadística tradicional",
            ],
            "next_step": "EXP-0004 (dataset scaling) y DIAG-0001 (origen del cero en carving)",
        },

        "CLAIM-001_OLD": {
            "id": "CLAIM-001_OLD",
            "title": "DEPRECATED — MFT-First beats Carving in OU when metadata is reliable",
            "statement": "MFT-First beats Carving in OU when metadata is reliable",
            "deprecation_reason": (
                "El lenguaje 'beats' excede la evidencia. El claim original no acotaba "
                "las condiciones ni las consecuencias. Reemplazado por CLAIM-001 refinado."
            ),
            "deprecated_by": "CLAIM-001",
            "deprecated_date": datetime.datetime.now().strftime("%Y-%m-%d"),
        },

        "CLAIM-DETERMINISM": {
            "id": "CLAIM-DETERMINISM",
            "title": "El laboratorio produce resultados idénticos bajo condiciones idénticas",
            "statement": (
                "En las condiciones evaluadas por EXP-0001, EXP-0002, EXP-SD0 y EXP-0003 "
                "(misma máquina), RecoveryLab produce resultados bit-identical (hash-identical) "
                "cuando se ejecuta con las mismas condiciones de entrada: misma semilla, "
                "mismo dataset, mismo motor, misma configuración."
            ),
            "evidence_level": "REPEATED",
            "evidence_level_number": 2,
            "evidence_level_note": (
                "REPEATED dentro de la misma máquina. No es REPRODUCIBLE hasta que "
                "se verifique en otra máquina/investigador."
            ),
            "supporting_experiments": ["EXP-0001", "EXP-0002", "EXP-SD0", "EXP-0003"],
            "importance": "PRIMARY_PHASE_A_OBJECTIVE",
            "importance_rationale": (
                "Este claim NO depende de ningún motor ni dataset específico. "
                "Depende del propio laboratorio. Si este claim sobrevive a: "
                "varias semillas (verificado EXP-0002), otra máquina (pendiente EXP-0003 real), "
                "otro sistema operativo (pendiente), entonces RecoveryLab deja de ser "
                "simplemente un proyecto de recuperación de datos y pasa a ser una "
                "plataforma experimental confiable. Ese debería ser el objetivo principal "
                "de la Fase A: que cualquier resultado futuro tenga un entorno experimental "
                "cuya reproducibilidad ya esté demostrada."
            ),
            "what_this_claim_does_NOT_say": [
                "No dice que los resultados sean correctos (sino que son consistentes)",
                "No dice que la reproducibilidad se mantenga en otra máquina",
                "No dice que la reproducibilidad se mantenga con otro OS",
                "No dice que SD=0 sea 'bueno' o 'malo' (es un dato)",
            ],
            "next_step": "EXP-0003 real en otra máquina / otro investigador",
        },
    }

    return claims


def generate_rcr_correction():
    """Correct the RCR calculation: only Reproducible counts, not Repeated."""
    rcr = {
        "metric": "RCR (Reproducible Claims Ratio)",
        "definition": "Fracción de claims que han alcanzado nivel REPRODUCIBLE (3/5) o superior",
        "current_value": 0.0,
        "previous_incorrect_value": 0.4,
        "correction_reason": (
            "El protocolo distingue entre REPEATED (2/5) y REPRODUCIBLE (3/5). "
            "RCR = Reproducible Claims Ratio. Los claims actualmente están en REPEATED "
            "porque EXP-0001 y EXP-0002 se ejecutaron en la misma máquina por el mismo "
            "investigador. Hasta que EXP-0003 se ejecute en otra máquina (o por otro "
            "investigador), esos claims siguen siendo repetidos, no reproducibles. "
            "Contarlos como reproducibles inflaría prematuramente el RCR y destruiría "
            "su valor como indicador."
        ),
        "claims_status": {
            "CLAIM-001": {
                "current_level": "REPEATED (2/5)",
                "counts_for_rcr": False,
                "reason": "Misma máquina, mismo investigador. Requiere reproducción externa.",
                "needs": "EXP-0003 en otra máquina o por otro investigador",
            },
            "CLAIM-005": {
                "current_level": "OBSERVED (1/5)",
                "counts_for_rcr": False,
                "reason": "No ha sido repetido formalmente.",
                "needs": "Repetición + reproducción externa",
            },
            "CLAIM-DETERMINISM": {
                "current_level": "REPEATED (2/5)",
                "counts_for_rcr": False,
                "reason": "Misma máquina. Requiere reproducción externa.",
                "needs": "EXP-0003 en otra máquina",
            },
            "CLAIM-002": {
                "current_level": "OBSERVED (1/5)",
                "counts_for_rcr": False,
                "reason": "No repetido.",
            },
            "CLAIM-003": {
                "current_level": "OBSERVED (1/5)",
                "counts_for_rcr": False,
                "reason": "No repetido.",
            },
            "CLAIM-004": {
                "current_level": "OBSERVED (1/5)",
                "counts_for_rcr": False,
                "reason": "No repetido.",
            },
        },
        "total_claims": 6,
        "reproducible_claims": 0,
        "rcr_percent": 0.0,
        "phase_a_target": ">= 60%",
        "graduation_target": ">= 80%",
        "path_to_improvement": (
            "El camino para aumentar el RCR es: "
            "1) Ejecutar EXP-0003 en otra máquina → CLAIM-001 y CLAIM-DETERMINISM avanzan a REPRODUCIBLE "
            "2) Repetir CLAIM-002/003/004 en nuevos experimentos → avanzan a REPEATED "
            "3) Reproducir CLAIM-002/003/004 externamente → avanzan a REPRODUCIBLE"
        ),
    }
    return rcr


def generate_observation_explanation_separation():
    """Separate observation from explanation in the Evidence Ledger for carving OU=0.0."""
    separation = {
        "id": "OBS-EXPL-SEPARATION-001",
        "topic": "Motor Carving Overall Utility = 0.0",
        "observation": {
            "statement": (
                "En EXP-0001, EXP-0002 y EXP-0005, bajo las condiciones evaluadas "
                "(datasets sintéticos NTFS de 10 MB, sin corrupción o con corrupción "
                "de MFT, Judge API v1.0, Protocol v1.5), el Motor Carving obtuvo "
                "Overall Utility = 0.0 en todos los datasets evaluados."
            ),
            "belongs_in": "Evidence Ledger (nivel OBSERVACIÓN)",
            "is_factual": True,
            "is_refutable": True,
            "refutation_method": "Encontrar un dataset donde carving OU > 0.0",
        },
        "NOT_a_claim": {
            "statement": "El Motor Carving no aprovecha la corrupción",
            "reason": (
                "Esto es una EXPLICACIÓN, no una observación. Excede la evidencia. "
                "Hay al menos 7 hipótesis compatibles con la observación OU=0.0."
            ),
        },
        "compatible_hypotheses": [
            {
                "id": "H-CARVING-001",
                "statement": "El parser de carving tiene un bug",
                "testable": True,
                "test_method": "DIAG-0001: probar con datasets de formato único",
                "implication_if_true": "El cero es un artifact del código, no del enfoque",
            },
            {
                "id": "H-CARVING-002",
                "statement": "El dataset no contiene suficientes formatos carveables",
                "testable": True,
                "test_method": "DIAG-0001: probar con datasets de formato único",
                "implication_if_true": "El cero es un artifact del dataset, no del motor",
            },
            {
                "id": "H-CARVING-003",
                "statement": "El generador produce archivos poco realistas",
                "testable": True,
                "test_method": "DIAG-0001: comparar archivos generados vs. archivos reales",
                "implication_if_true": "El cero es un artifact del generador",
            },
            {
                "id": "H-CARVING-004",
                "statement": "El Judge penaliza excesivamente el carving",
                "testable": True,
                "test_method": "Analizar cómo el Judge puntúa archivos carved vs. MFT-recovered",
                "implication_if_true": "El cero es un artifact del scoring",
            },
            {
                "id": "H-CARVING-005",
                "statement": "Los footers siguen siendo insuficientes",
                "testable": True,
                "test_method": "DIAG-0001: verificar si los archivos generados tienen footers detectables",
                "implication_if_true": "El cero es un artifact de la generación de footers",
            },
            {
                "id": "H-CARVING-006",
                "statement": "El RVS/FQS favorecen tipos de archivo que carving no puede recuperar",
                "testable": True,
                "test_method": "DIAG-0001: descomponer RVS/FQS por formato",
                "implication_if_true": "El cero es un artifact del scoring pero no del motor",
            },
            {
                "id": "H-CARVING-007",
                "statement": "La implementación del carving todavía está incompleta",
                "testable": True,
                "test_method": "DIAG-0001: verificar si los archivos generados son detectables por el scanner",
                "implication_if_true": "El cero es un artifact de la implementación",
            },
        ],
        "diagnostic_experiment": "DIAG-0001",
        "diagnostic_question": "¿El cero proviene del algoritmo o del banco de pruebas?",
    }
    return separation


def generate_phase_a_objective():
    """Elevate lab determinism as the primary Phase A objective."""
    objective = {
        "id": "PHASE-A-PRIMARY-OBJECTIVE",
        "statement": (
            "El objetivo principal de la Fase A es demostrar que RecoveryLab "
            "es una plataforma experimental confiable, no demostrar que un motor "
            "es mejor que otro."
        ),
        "rationale": (
            "Si el laboratorio produce resultados reproducibles (no solo repetidos), "
            "entonces cualquier resultado futuro — comparación de motores, evaluación "
            "de estrategias, calibración de RVS — tiene un fundamento sólido. "
            "Sin reproducibilidad del entorno, ningún resultado comparativo es confiable."
        ),
        "success_criteria": {
            "CLAIM-DETERMINISM reaches REPRODUCIBLE": {
                "current": "REPEATED (2/5)",
                "required": "REPRODUCIBLE (3/5)",
                "action": "EXP-0003 en otra máquina o por otro investigador",
                "status": "PENDIENTE",
            },
            "CLAIM-DETERMINISM survives across seeds": {
                "current": "VERIFICADO (EXP-0002, 4 semillas)",
                "status": "CUMPLIDO",
            },
            "CLAIM-DETERMINISM survives across machines": {
                "current": "NO VERIFICADO",
                "action": "EXP-0003 real en otra máquina",
                "status": "PENDIENTE",
            },
            "CLAIM-DETERMINISM survives across OS": {
                "current": "NO VERIFICADO",
                "action": "Futuro experimento",
                "status": "PENDIENTE",
            },
        },
        "implication": (
            "Si CLAIM-DETERMINISM alcanza REPRODUCIBLE, RecoveryLab pasa de ser "
            "un proyecto de recuperación de datos a ser una plataforma experimental "
            "confiable. Ese es el verdadero valor de la Fase A."
        ),
        "secondary_objectives": [
            "DIAG-0001: localizar origen del cero en carving",
            "EXP-0004: validar que resultados escalan a datasets más grandes",
            "EXP-0005: posicionar RecoveryLab en el espacio de herramientas",
        ],
    }
    return objective


def main():
    print("=" * 70)
    print("Methodological Corrections — Round 8 Audit")
    print("=" * 70)
    print()

    # 1. Refined claims
    print("[1/4] Generating refined claims...")
    claims = generate_refined_claims()
    claims_path = OUTPUT_DIR / "refined_claims.json"
    with open(claims_path, "w", encoding="utf-8") as f:
        json.dump(claims, f, indent=2, ensure_ascii=False)
    print(f"  → {claims_path}")
    print(f"  CLAIM-001 refinado: lenguaje acotado a condiciones observadas")
    print(f"  CLAIM-001_OLD: deprecado con razón documentada")
    print(f"  CLAIM-DETERMINISM: elevado como objetivo principal de Fase A")
    print()

    # 2. RCR correction
    print("[2/4] Correcting RCR calculation...")
    rcr = generate_rcr_correction()
    rcr_path = OUTPUT_DIR / "rcr_correction.json"
    with open(rcr_path, "w", encoding="utf-8") as f:
        json.dump(rcr, f, indent=2, ensure_ascii=False)
    print(f"  → {rcr_path}")
    print(f"  RCR corregido: 0.4 → 0.0 (solo REPRODUCIBLE cuenta, no REPEATED)")
    print()

    # 3. Observation vs. Explanation separation
    print("[3/4] Separating observation from explanation...")
    separation = generate_observation_explanation_separation()
    sep_path = OUTPUT_DIR / "observation_explanation_separation.json"
    with open(sep_path, "w", encoding="utf-8") as f:
        json.dump(separation, f, indent=2, ensure_ascii=False)
    print(f"  → {sep_path}")
    print(f"  7 hipótesis compatibles con OU=0.0 documentadas")
    print(f"  DIAG-0001 propuesto como mecanismo de discriminación")
    print()

    # 4. Phase A objective
    print("[4/4] Elevating lab determinism as primary Phase A objective...")
    objective = generate_phase_a_objective()
    obj_path = OUTPUT_DIR / "phase_a_primary_objective.json"
    with open(obj_path, "w", encoding="utf-8") as f:
        json.dump(objective, f, indent=2, ensure_ascii=False)
    print(f"  → {obj_path}")
    print()

    # Summary
    print("=" * 70)
    print("SUMMARY OF CORRECTIONS")
    print("=" * 70)
    print()
    print("1. CLAIM-001: 'MFT-First > Carving' → 'En los datasets sintéticos")
    print("   evaluados durante EXP-0001 y EXP-0002, MFT-First obtuvo OU")
    print("   superior al Motor Carving.'")
    print()
    print("2. RCR: 0.4 → 0.0. REPEATED no cuenta. Solo REPRODUCIBLE.")
    print("   Proteger el valor del RCR es más importante que inflarlo.")
    print()
    print("3. Carving OU=0.0: OBSERVACIÓN pura. 7 hipótesis compatibles.")
    print("   No se asume cuál es correcta. DIAG-0001 discriminará.")
    print()
    print("4. CLAIM-DETERMINISM: objetivo principal de Fase A.")
    print("   Si el lab es reproducible, cualquier resultado futuro es confiable.")
    print()
    print("Artifacts generated in:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
