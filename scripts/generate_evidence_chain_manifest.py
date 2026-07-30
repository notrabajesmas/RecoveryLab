#!/usr/bin/env python3
"""
Evidence Chain Manifest — Phase A
===================================
Generates a comprehensive summary of the entire evidence chain
from EXP-0001 through EXP-0005, including EXP-SD0 diagnostic.

This document answers: "What do we know, and how do we know it?"
"""

import json
from pathlib import Path
from datetime import datetime

OUTPUT_BASE = Path("/home/z/my-project/output")

# ─── Load all experiment results ──────────────────────────────────────────

def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None

# EXP-0001
exp_0001_summary = load_json(OUTPUT_BASE / "exp_0001" / "baseline_summary.json")
exp_0001_claims = load_json(OUTPUT_BASE / "exp_0001" / "claim_updates.json")

# EXP-0002
exp_0002_summary = load_json(OUTPUT_BASE / "exp_0002" / "seed_variation_summary.json")
exp_0002_claims = load_json(OUTPUT_BASE / "exp_0002" / "claim_updates.json")

# EXP-0003
exp_0003_summary = load_json(OUTPUT_BASE / "exp_0003" / "cross_machine_summary.json")
exp_0003_claims = load_json(OUTPUT_BASE / "exp_0003" / "claim_updates.json")

# EXP-0005
exp_0005_summary = load_json(OUTPUT_BASE / "exp_0005" / "external_validation_summary.json")
exp_0005_claims = load_json(OUTPUT_BASE / "exp_0005" / "claim_updates.json")

# EXP-SD0
exp_sd0_summary = load_json(OUTPUT_BASE / "exp_sd0" / "sd0_diagnostic_summary.json")
exp_sd0_ledger = load_json(OUTPUT_BASE / "exp_sd0" / "ledger_entry.json")

# ─── Build the evidence chain ─────────────────────────────────────────────

evidence_chain = {
    "manifest_version": "1.0",
    "generated": datetime.now().isoformat(),
    "phase": "A",
    "total_experiments": 5,
    "experiments_executed": 4,
    "experiments_pending": ["EXP-0004 (dataset scaling — requires longer runtime)"],

    "experiments": {
        "EXP-0001": {
            "name": "Baseline Stability Characterization",
            "status": "COMPLETED",
            "question": "Is the laboratory deterministic under identical conditions?",
            "answer": "YES — SD=0 for all result metrics. Runtime is the only varying metric.",
            "key_findings": {
                "mft_first_ou": 0.9589,
                "carving_ou": 0.0,
                "deterministic": True,
                "sd_zero": True,
                "empirical_threshold": 0.01,
            },
            "evidence_debt_addressed": ["ED-008"],
            "claims_advanced": [],
        },
        "EXP-0002": {
            "name": "Seed Variation Reproducibility",
            "status": "COMPLETED",
            "question": "Does CLAIM-001 depend on a lucky seed?",
            "answer": "NO — MFT-First > Carving across all 4 seeds (42, 1337, 2026, 9999).",
            "key_findings": {
                "seeds_tested": [42, 1337, 2026, 9999],
                "mft_first_ou_range": [0.9589, 0.9983],
                "carving_ou_range": [0.0, 0.0080],
                "claim_001_robust": True,
                "new_finding": "Carving is NOT always OU=0 on healthy images (0.0028-0.0080)",
                "deterministic_per_seed": True,
                "cross_seed_cv": 2.30,
            },
            "evidence_debt_addressed": ["ED-001 (partial)"],
            "claims_advanced": ["CLAIM-001 → REPEATED", "CLAIM-005 → REPEATED"],
        },
        "EXP-0003": {
            "name": "Cross-Machine Reproduction",
            "status": "SAME_MACHINE_VERIFIED",
            "question": "Does the laboratory produce the same results on another machine?",
            "answer": "Same-machine verification PASSED. Cross-machine execution PENDING.",
            "key_findings": {
                "same_machine_match": True,
                "reproduction_package_generated": True,
                "codebase_hash": exp_0003_summary.get("codebase_hash", "unknown") if exp_0003_summary else "unknown",
                "cross_machine_executed": False,
            },
            "evidence_debt_addressed": ["ED-001 (partial)"],
            "claims_advanced": [],
        },
        "EXP-0004": {
            "name": "Dataset Scaling Robustness",
            "status": "SCRIPT_READY",
            "question": "Does the laboratory work beyond toy 10 MB datasets?",
            "answer": "NOT YET EXECUTED (requires longer runtime for 1 GB datasets).",
            "key_findings": {},
            "evidence_debt_addressed": ["ED-004"],
            "claims_advanced": [],
        },
        "EXP-0005": {
            "name": "External Strategy Validation",
            "status": "PARTIAL",
            "question": "Where does RecoveryLab sit in the strategy space?",
            "answer": "MFT-First degrades gracefully with corruption (0.9589 → 0.5508 → 0.1794). "
                     "Carving shows OU=0.0 on ALL corruption variants. "
                     "No crossover detected. External tool comparison pending.",
            "key_findings": {
                "healthy_mft_first_ou": 0.9589,
                "mft20_mft_first_ou": 0.5508,
                "mft60_mft_first_ou": 0.1794,
                "healthy_carving_ou": 0.0,
                "mft20_carving_ou": 0.0,
                "mft60_carving_ou": 0.0,
                "crossover_detected": False,
                "carving_motor_weakness": "Carving motor does not recover files even on corrupted images",
                "test_dataset_package_generated": True,
            },
            "evidence_debt_addressed": ["ED-001 (partial)", "ED-004 (partial)"],
            "claims_advanced": [],
        },
        "EXP-SD0": {
            "name": "SD=0 Diagnostic Investigation",
            "status": "COMPLETED",
            "question": "Why is SD=0 in EXP-0001?",
            "answer": "EXPLANATION_2: OU is quantized (discrete file counts, fixed RVS profiles). "
                     "Runtime IS the only varying metric (SD=3.2ms). "
                     "All result metrics are deterministic because they are computed from "
                     "integer file counts and fixed value profiles.",
            "key_findings": {
                "sd0_is_genuine": True,  # For result metrics
                "sd0_is_artifact": True,  # For OU specifically — quantization
                "runtime_varies": True,
                "runtime_sd_ms": 3.2,
                "per_file_identical": True,
                "explanation": "OU quantization: discrete file counts × fixed RVS profiles = deterministic composites",
            },
            "evidence_debt_addressed": [],
            "claims_advanced": [],
        },
    },

    "claims_status": {
        "CLAIM-001": {
            "statement": "MFT-First > Carving (when MFT is intact)",
            "evidence_level": "REPEATED",
            "evidence_gate_progress": "OBSERVED → REPEATED",
            "supporting_experiments": ["EXP-0001", "EXP-0002"],
            "next_step": "EXP-0003 cross-machine to reach REPRODUCIBLE",
        },
        "CLAIM-002": {
            "statement": "Functional recovery is not binary",
            "evidence_level": "OBSERVED",
            "supporting_experiments": ["EXP-0001"],
            "next_step": "Corruption experiments showing partial recovery",
        },
        "CLAIM-003": {
            "statement": "RVS value model",
            "evidence_level": "OBSERVED",
            "supporting_experiments": [],
            "next_step": "RVS calibration experiment (EXP-RVS-CAL)",
        },
        "CLAIM-004": {
            "statement": "Crossover at 95% is artifact",
            "evidence_level": "OBSERVED",
            "supporting_experiments": ["EXP-0005"],
            "next_step": "More fine-grained corruption + Carving motor improvement",
        },
        "CLAIM-005": {
            "statement": "Parsers golden reference",
            "evidence_level": "REPEATED",
            "evidence_gate_progress": "OBSERVED → REPEATED",
            "supporting_experiments": ["EXP-0001", "EXP-0002"],
            "next_step": "EXP-0003 cross-machine to reach REPRODUCIBLE",
        },
    },

    "evidence_debt_status": {
        "ED-001_umbral_empirico": "EN PROGRESO — threshold calibrated, cross-seed validated, cross-machine PENDING",
        "ED-002_claim_sin_evidencia": "ABIERTA — no experiment has directly tested CLAIM-002/003",
        "ED-004_self_complacent_benchmark": "EN PROGRESO — EXP-0005 tested corruption, external comparison PENDING",
        "ED-008_variabilidad_desconocida": "PAGADA — laboratory is deterministic (EXP-0001, EXP-0002)",
    },

    "rcr": {
        "metric": "Reproducible Claims Ratio",
        "definition": "Claims at REPEATED or above / Total claims",
        "current": "2/5 = 40%",
        "target_phase_a": "60%",
        "target_graduation": "80%",
        "path_to_60": "EXP-0003 cross-machine → CLAIM-001 and CLAIM-005 to REPRODUCIBLE → 2/5 = 40% (need 3/5)",
        "note": "RCR increases when claims advance. Need 3/5 claims at REPEATED+ for Phase A target.",
    },

    "key_insights": [
        "1. The laboratory is deterministic under identical conditions (EXP-0001, EXP-0002, EXP-SD0)",
        "2. SD=0 is genuine for result metrics — OU is quantized from integer file counts (EXP-SD0)",
        "3. CLAIM-001 does NOT depend on seed=42 — it's robust across 4 seeds (EXP-0002)",
        "4. Carving motor is NOT always OU=0 on healthy images — sometimes recovers tiny amounts (EXP-0002)",
        "5. Carving motor does NOT recover files even on corrupted images — implementation weakness (EXP-0005)",
        "6. MFT-First degrades gracefully with corruption: 0.9589 → 0.5508 → 0.1794 (EXP-0005)",
        "7. No crossover detected between MFT-First and Carving under current conditions (EXP-0005)",
        "8. The bottleneck is NOT engineering — it's converting observations into independent evidence (auditor)",
    ],

    "next_actions": [
        "1. Execute EXP-0003 reproduction package on another machine (CRITICAL for RCR)",
        "2. Execute EXP-0004 (dataset scaling) — requires longer runtime",
        "3. Improve Carving motor to actually recover files on corrupted images",
        "4. Run external tools (PhotoRec, TestDisk) on test_dataset_package/",
        "5. Run RVS calibration experiment (EXP-RVS-CAL)",
        "6. Do NOT implement new features (Journal, Bitmap, INDX, Motor C) until evidence chain is stronger",
    ],
}

# Save the manifest
manifest_path = OUTPUT_BASE / "evidence_chain_manifest.json"
with open(manifest_path, 'w') as f:
    json.dump(evidence_chain, f, indent=2, default=str, ensure_ascii=False)

print(f"Evidence Chain Manifest saved to: {manifest_path}")
print(f"")
print(f"Phase A Progress:")
print(f"  Experiments executed: 4/5 (+1 diagnostic)")
print(f"  Claims at REPEATED+: 2/5 (40% RCR)")
print(f"  Evidence debts paid: 1/4 (ED-008)")
print(f"  Evidence debts in progress: 2/4 (ED-001, ED-004)")
print(f"")
print(f"Key findings:")
print(f"  1. Lab is deterministic (SD=0 for results, runtime varies)")
print(f"  2. CLAIM-001 robust across 4 seeds")
print(f"  3. Carving motor weakness identified (doesn't recover on corrupted images)")
print(f"  4. MFT-First degrades gracefully with corruption")
print(f"  5. No crossover detected yet")
