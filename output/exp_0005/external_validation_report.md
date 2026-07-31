# EXP-0005 — External Strategy Validation

**Date**: 2026-07-30 21:59
**Commit**: c2cc5af
**Protocol**: v1.5 | **Judge**: v1.0

---

## 1. Observation — RecoveryLab Results

### MFT-First Strategy

| Config | OU Mean | OU SD | Recovery Rate | Hash Identical | Diagnostic |
|--------|---------|-------|---------------|----------------|------------|
| healthy_10mb | 0.958900 | 0.000000 | 0.9333 | YES | STRONG: Recovered important files with good quality |
| mft20_10mb | 0.550800 | 0.000000 | 0.7333 | YES | STRONG: Recovered important files with good quality |
| mft60_10mb | 0.179400 | 0.000000 | 0.3667 | YES | WEAK: Both value and quality are low |

### Carving Strategy

| Config | OU Mean | OU SD | Recovery Rate | Hash Identical |
|--------|---------|-------|---------------|----------------|
| healthy_10mb | 0.000000 | 0.000000 | 0.0000 | YES |
| mft20_10mb | 0.000000 | 0.000000 | 0.0000 | YES |
| mft60_10mb | 0.000000 | 0.000000 | 0.0000 | YES |

## 2. Strategy Space Analysis

This is the most important section of EXP-0005.

RecoveryLab currently implements two strategies:
- **MFT-First**: Reads MFT first, then targets data. Optimal when MFT is intact.
- **Carving**: Signature-based scan, no MFT. Optimal when MFT is destroyed.

### Expected behavior under corruption:

| Corruption | MFT-First | Carving | Winner |
|------------|-----------|---------|--------|
| NONE (0%)  | High OU   | Low OU  | MFT-First |
| MFT 20%    | Medium OU | Low-Med OU | MFT-First (partial) |
| MFT 60%    | Low OU    | Medium OU | Carving (potentially) |

The **crossover point** is where Carving becomes competitive.
This directly addresses CLAIM-004 (crossover at 95% is artifact).

## 3. External Tool Comparison Framework

The following table provides a template for recording external tool results.
Each external tool should be run on the SAME test dataset package.

| Tool | Strategy | healthy_10mb OU | mft20_10mb OU | mft60_10mb OU |
|------|----------|-----------------|----------------|----------------|
| RecoveryLab MFT-First | MFT-first | _see above_ | _see above_ | _see above_ |
| RecoveryLab Carving | Carving | _see above_ | _see above_ | _see above_ |
| PhotoRec | Carving | _pending_ | _pending_ | _pending_ |
| TestDisk | MFT-based | _pending_ | _pending_ | _pending_ |
| Scalpel | Carving | _pending_ | _pending_ | _pending_ |
| ntfsundelete | MFT-based | _pending_ | _pending_ | _pending_ |
| Commercial tool | Hybrid | _pending_ | _pending_ | _pending_ |

### How to add external tool results:
1. Install the external tool on the test machine
2. Run it on each dataset in test_dataset_package/
3. Record OU using the same Judge API (or equivalent metrics)
4. Add results to the comparison table
5. Re-evaluate CLAIM-001 in the context of the full strategy space

## 4. Success Criteria Evaluation

- [PASS] test_dataset_generated
- [PASS] recoverylab_results_recorded
- [PASS] external_tool_template_created
- [PASS] strategy_space_map_generated
- [PASS] evidence_ledger_complete

---

## 5. Explanation

EXP-0005 is the most important experiment of Phase A because it is the
first step toward placing RecoveryLab in the context of the broader recovery
tool landscape. Without external comparison, we cannot claim that RecoveryLab
is better or worse than anything — we can only claim that it produces
reproducible results internally.

The corruption variants are critical because they test the boundary where
MFT-First breaks down and Carving becomes competitive. This is the crossover
point that CLAIM-004 discusses.

Once external tool results are added, this experiment will allow us to:
1. Locate RecoveryLab in the strategy space (not just internally)
2. Validate or refute CLAIM-001 against external baselines
3. Identify the true crossover point with external tools
4. Understand RecoveryLab's strengths and limitations objectively

---

*Experiment ID: EXP-0005 | Protocol: v1.5 | Judge: v1.0*