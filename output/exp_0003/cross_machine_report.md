# EXP-0003 — Cross-Machine Reproduction

**Date**: 2026-07-30 22:00
**Commit**: c2cc5af
**Codebase hash**: 1822d0a07e4d597e
**Protocol**: v1.5 | **Judge**: v1.0
**Runs**: 30 per motor | **Seed**: 42

---

## 1. Execution Environment

| Property | Value |
|----------|-------|
| python_version | 3.12.13 (main, Jul 18 2026, 17:02:19) [Clang 22.1.3 ] |
| python_executable | /home/z/.venv/bin/python3 |
| platform | Linux-5.10.134-013.8.3.kangaroo.al8.x86_64-x86_64-with-glibc... |
| machine | x86_64 |
| processor |  |
| hostname | c-6a6ba435-1416dbb8-9f6f5e659461 |
| os_name | posix |
| os_release | 5.10.134-013.8.3.kangaroo.al8.x86_64 |
| os_version | #1 SMP Fri May 29 08:22:43 UTC 2026 |
| cpu_count | 2 |
| timestamp | 2026-07-30T21:59:59.177307 |
| python_path | ['/home/z/my-project/RecoveryLab', '/home/z/my-project/RecoveryLab', '/home/z/my-project/RecoveryLab', '/home/z/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/lib/python312.zip', '/home/z/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/lib/python3.12'] |
| total_memory_gb | 3.95 |

## 2. Results on This Machine

### MFT-First

| Metric | Value |
|--------|-------|
| OU Mean | 0.958900 |
| OU SD | 0.000000 |
| OU CV% | 0.0000 |
| Hash Identical | YES |

### Carving

| Metric | Value |
|--------|-------|
| OU Mean | 0.000000 |
| OU SD | 0.000000 |
| OU CV% | 0.0000 |
| Hash Identical | YES |

## 3. Comparison with EXP-0001

### MFT-First

| Metric | EXP-0001 | EXP-0003 | Match |
|--------|----------|----------|-------|
| ou_mean | 0.9589 | 0.9589 | YES |
| ou_sd | 0.0 | 0.0 | YES |
| hash_identical | True | True | YES |

### Carving

| Metric | EXP-0001 | EXP-0003 | Match |
|--------|----------|----------|-------|
| ou_mean | 0.0 | 0.0 | YES |
| ou_sd | 0.0 | 0.0 | YES |
| hash_identical | True | True | YES |

## 4. Reproduction Package

A self-contained reproduction package has been generated at:
`/home/z/my-project/output/exp_0003/reproduction_package`

### How to reproduce on another machine:

1. Copy the entire `reproduction_package/` directory to the target machine
2. Ensure Python 3.8+ is installed
3. Run: `python3 run_reproduction.py`
4. Compare the output `reproduction_results.json` with the reference
5. If OU and hash match, CLAIM-001 advances to REPRODUCIBLE

## 5. Success Criteria Evaluation

- [PASS] reproduction_package_generated
- [PASS] results_identical_to_exp_0001
- [PASS] hash_identical_within_this_machine
- [PASS] package_self_contained
- [PASS] evidence_ledger_complete

---

## 6. Explanation

This experiment establishes the procedure for cross-machine reproduction.
Running on the same machine as EXP-0001 serves as a sanity check:
the results should be identical. Any difference on the SAME machine
would indicate a fundamental problem with the laboratory.

The true value of EXP-0003 emerges when the reproduction package is
executed on a DIFFERENT machine. If the results match, the Evidence Gate
level for CLAIM-001 and CLAIM-005 can advance from REPEATED to REPRODUCIBLE.

Codebase hash: 1822d0a07e4d597e
This hash identifies the exact version of the code. Any change in the
codebase will produce a different hash, making it detectable.

---

*Experiment ID: EXP-0003 | Protocol: v1.5 | Judge: v1.0*