# EXP-SD0 — SD=0 Diagnostic Investigation

**Date**: 2026-07-30 21:59
**Commit**: c2cc5af

---

## 1. The Question

EXP-0001 found SD=0 for all substantive metrics. This is a DATA point,
not a conclusion. The question is: **Why is SD=0?**

Four possible explanations:
1. The experiment is truly completely deterministic
2. The metric (OU) is quantized and doesn't capture small differences
3. The dataset is too simple
4. No real source of variability exists yet

## 2. Method

Two conditions tested:
- **Standard**: Same as EXP-0001 (no noise)
- **With noise**: Random delays added (0-1ms) to simulate scheduling

Metrics recorded at HIGHER precision:
- Nanosecond-precision runtime
- Per-file RVS values
- Per-file functional scores
- Raw byte counts
- Per-file SHA-256 hashes

## 3. Results

### Standard Condition

| Metric | SD=0? | Unique Values |
|--------|-------|---------------|
| overall_utility | YES | 1 |
| rvs | YES | 1 |
| fqs | YES | 1 |
| recovery_rate | YES | 1 |
| read_count | YES | 1 |
| runtime_ms | NO | 30 |
| runtime_ns | NO | 30 |
| files_recovered | YES | 1 |
| files_correct_checksum | YES | 1 |
| files_missing | YES | 1 |
| bytes_recovered | YES | 1 |
| bytes_correct | YES | 1 |
| integrity_score | YES | 1 |
| read_efficiency | YES | 1 |
| sectors_wasted | YES | 1 |
| mft_entries_parsed | YES | 1 |
| rvs_total_value_recovered | YES | 1 |
| rvs_total_value_ground_truth | YES | 1 |

Per-file consistency: ALL IDENTICAL

### With Noise Condition

| Metric | SD=0? | Unique Values |
|--------|-------|---------------|
| overall_utility | YES | 1 |
| rvs | YES | 1 |
| fqs | YES | 1 |
| recovery_rate | YES | 1 |
| read_count | YES | 1 |
| runtime_ms | NO | 30 |
| runtime_ns | NO | 30 |
| files_recovered | YES | 1 |
| files_correct_checksum | YES | 1 |
| files_missing | YES | 1 |
| bytes_recovered | YES | 1 |
| bytes_correct | YES | 1 |
| integrity_score | YES | 1 |
| read_efficiency | YES | 1 |
| sectors_wasted | YES | 1 |
| mft_entries_parsed | YES | 1 |
| rvs_total_value_recovered | YES | 1 |
| rvs_total_value_ground_truth | YES | 1 |

## 4. Conclusion

**EXPLANATION_2: Overall Utility is quantized (discrete file counts). Runtime shows variability but OU does not because it's computed from integer file counts and fixed RVS profiles.**

**EXPLANATION_2: Overall Utility is quantized (discrete file counts). Runtime shows variability but OU does not because it's computed from integer file counts and fixed RVS profiles.**

## 5. Implication for Future Experiments

SD=0 is an artifact of the metrics used. Some raw metrics DO show variability.
This means:
- Overall Utility is quantized (discrete file counts)
- Future experiments should use more granular metrics
- The empirical threshold should be computed from raw metrics

---

*Experiment ID: EXP-SD0 | Protocol: v1.5 | Judge: v1.0*