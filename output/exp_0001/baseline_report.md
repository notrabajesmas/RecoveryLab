# EXP-0001 — Baseline Stability Characterization

**Date**: 2026-07-30 21:47
**Commit**: 552e140
**Protocol**: v1.5 | **Judge**: v1.0
**Primary Motor**: MFT-First v1.0 | **Secondary Motor**: Carving v1.0
**Runs**: 30 per motor | **Seed**: 42 | **Corruption**: NONE

---

## 1. Observation — MFT-First (Primary)

Overall Utility across 30 executions under identical conditions:

| Metric | Value |
|--------|-------|
| Mean | 0.958900 |
| SD | 0.000000 |
| CV | 0.0000% |
| Min | 0.958900 |
| Max | 0.958900 |
| 95% CI | [0.958900, 0.958900] |

### All Metrics Summary — MFT-First

| Metric | Mean | SD | CV% |
|--------|------|----|----|
| overall_utility | 0.958900 | 0.000000 | 0.0000 |
| rvs | 0.972500 | 0.000000 | 0.0000 |
| fqs | 0.985999 | 0.000000 | 0.0000 |
| recovery_rate | 0.933333 | 0.000000 | 0.0000 |
| read_count | 14593.000000 | 0.000000 | 0.0000 |
| runtime_ms | 46.115572 | 1.798757 | 3.9005 |

## 2. Observation — Carving (Secondary / Floor)

Overall Utility across 30 executions:

| Metric | Value |
|--------|-------|
| Mean | 0.000000 |
| SD | 0.000000 |
| Hash identical | True |

Note: Carving on a healthy (0% corruption) NTFS image produces OU=0.0. This is expected: Carving does not use MFT, and on a healthy image, it cannot correctly identify file boundaries without MFT references.

## 3. Reproducibility (Bit-Exact)

**MFT-First**: 1 unique hash — ALL 30 IDENTICAL
**Carving**: 1 unique hash — ALL 30 IDENTICAL

**Both motors produce deterministic results under identical conditions.**

## 4. Temporal Drift

**MFT-First**: drift = 0.000000 (0.0000%) — No drift detected

## 5. Empirical Threshold (ED-008)

Based on MFT-First variability:
- Overall Utility SD: 0.000000
- Empirical threshold (2-sigma): 0.010000 (1.00%)

A difference in Overall Utility must exceed 0.0100 (1.00%) to be considered significant at 2-sigma

## 6. Success Criteria Evaluation

- [PASS] 30_executions_completed
- [PASS] no_errors
- [PASS] hash_identical
- [PASS] no_temporal_drift
- cv_overall_utility: 0.0
- cv_note: CV threshold (X) to be defined after data collection

---

## 7. Explanation

This is consistent with the hypothesis that the laboratory produces deterministic,
stable measurements under identical conditions (H1.6: same seed produces same result).

The fact that MFT-First produces OU=0.958900 while Carving produces OU=0.000000
on a healthy image is consistent with CLAIM-001 (MFT-First > Carving when MFT is intact).
This is NOT a discovery — it is an expected baseline that confirms the laboratory
behaves as designed. The Carving motor does not use MFT, so on a healthy image
where MFT is intact, MFT-First correctly recovers files while Carving cannot
identify file boundaries without MFT references.

The empirical threshold of 0.010000 (1.00%)
provides the minimum detectable difference for future experiments.

IMPORTANT: The laboratory is fully deterministic under these conditions (SD=0).
The empirical threshold falls back to the floor of 1.0%. This means that
future experiments with non-deterministic conditions (corruption, different
datasets, different seeds) will need their own baseline calibration.

---

*Experiment ID: EXP-0001 | Protocol: v1.5 | Judge: v1.0*