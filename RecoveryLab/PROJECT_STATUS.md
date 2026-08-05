# RecoveryLab — Project Status

> **Version**: v0.6.0
> **Last CI run**: 2026-08-05 — ALL CHECKS PASS
> **Repo**: https://github.com/notrabajesmas/RecoveryLab

> **Each version changes a benchmark.**
> Before starting any version: *"What benchmark number will move?"*
> If you can't answer in one line, the version doesn't start.

---

## Roadmap

| Version | Benchmark target | Status |
|---------|-----------------|--------|
| v0.5.2 | NTFS normal files: 0% → 100% | Done |
| **v0.6.0** | **NTFS sparse files: 0% → 100%** | **Current** |
| v0.6.1 | NTFS compressed files: 0% → ≥95% | Pending |
| v0.7.0 | GUI: 0 → functional | Pending |
| v0.8.0 | FAT32: 0% → 100% | Pending |
| v0.9.0 | exFAT: 0% → 100% | Pending |
| v1.0.0 | Public release | Pending |

---

## Product Metrics — v0.6.0

> These numbers come from `python scripts/ci_full.py` executed on 2026-08-05.
> No number appears here unless it was produced by a real, reproducible benchmark.

### Technical metrics (measure the motor)

| Category | Files | RR | RFS | RC | Time | RAM |
|----------|------:|---:|----:|---:|-----:|----:|
| Normal | 20/20 | 100.0% | 0.815 | 0.500 | 0.53s | 117 MB |
| Fragmented | 20/20 | 100.0% | 0.815 | 0.500 | 0.50s | 159 MB |
| Deleted | 20/20 | 100.0% | 0.815 | 0.500 | 0.48s | 159 MB |
| **Sparse** | **20/20** | **100.0%** | **0.850** | **0.500** | **0.19s** | **159 MB** |

### User metrics (measure the experience)

**UXR — User Recovery Rate**: Of N people who download RecoveryLab,
how many recover a file without reading source code and without asking for help?

- RR = 100% means nothing if UXR = 2/10.
- The problem is no longer the motor. It's the experience.
- Target for v1.0.0: UXR ≥ 8/10

**Stranger test**: Can someone who never spoke to us do this in 10 minutes?

```
git clone ...
pip install .
recoverylab scan examples/demo.img
recoverylab recover examples/demo.img recovered/
```

If they get stuck at any step, that's a product bug.

---

## CI Status

```
python scripts/ci_full.py

  API contract tests:  25/25
  Corpus normal:       20/20  RR=100.0%  RFS=0.815
  Corpus fragmented:   20/20  RR=100.0%  RFS=0.815
  Corpus deleted:      20/20  RR=100.0%  RFS=0.815
  Corpus sparse:       20/20  RR=100.0%  RFS=0.850
  Regression:          No regressions vs v0.5.2 baseline
  Carving tests:       19/19
```

---

## Capabilities

| Capability | Status | Detail |
|-----------|--------|--------|
| Strategy A (MFT) | Working | Metadata-based recovery |
| Strategy B (Journal) | Working | USN V2/V3/V4, delete detection |
| Strategy C (Carving) | Working | 19 formats, signature-based |
| Strategy D (Fragment) | Working | Multi-run reconstruction |
| Strategy E (Hybrid) | Working | Adaptive delegation |
| **Sparse runs** | **Working (v0.6.0)** | **Parser + recovery + corpus + CI** |
| Compressed runs | Not yet | |
| GUI | Not yet | |
| FAT32 / exFAT | Not yet | |

---

## Infrastructure

| Component | Status |
|-----------|--------|
| RecoveryEngine API | Frozen, 25 contract tests |
| CLI | scan/recover/info, 7 profiles |
| Corpus | 4 categories, 80/80 CI-verified |
| CI regression | Baseline saved, sparse included |
| Example image | examples/demo.img (5 files, 1MB) |
| Recovery Cost (RC) | CPU + RAM + I/O + efficiency |
| Pipeline | 8 stages, extensible |
| Stability policy | 3 tiers (public/extension/internal) |
| Versioning | Semantic |
| pip package | recoverylab-0.6.0-py3-none-any.whl |
| User docs | Installation, QuickStart, CLI, API, Profiles, Plugins |

---

## Project Rules

1. **Each version changes a benchmark** — not a metric, not a document, not an abstraction
2. **Before starting a version**: What benchmark will move? No answer = don't start
3. **No percentage enters documentation until a reproducible benchmark produces it**
4. **Measure progress = what can you recover today that you couldn't yesterday?**
5. **API frozen** — breaking = MAJOR bump
6. **Corpus permanent** — every release verified against corpus
7. **CI regression** — new version ≥ previous version on RR
8. **UXR matters** — RR=100% means nothing if strangers can't use the tool

---

## Definition of Done

A version is **not done** until ALL of these are true.
If even one is missing, the version stays open.

| # | Criterion | v0.6.0 |
|---|-----------|--------|
| 1 | Target benchmark improves | ✅ Sparse 0% → 100% |
| 2 | Full CI is green | ✅ 25/25 API, 19/19 carving, 80/80 corpus |
| 3 | Wheel builds cleanly | ✅ recoverylab-0.6.0-py3-none-any.whl |
| 4 | `pip install` works in a clean environment | ✅ Tested |
| 5 | `recoverylab demo` works | ✅ 4/4 recovered |
| 6 | README updated | ✅ |
| 7 | CHANGELOG updated | ✅ |
| 8 | GitHub Release published | ❌ Pending |
| 9 | At least one person outside the project tested it | ❌ Pending |

---

## Next steps

1. **Publish GitHub Release v0.6.0** with wheel + sdist as assets
2. **UXR experiment**: get 10 people who never saw RecoveryLab to try it
   - `pip install recoverylab`
   - `recoverylab demo`
   - If ≥8/10 recover a file without help → UXR is good
   - If <5/10 → fix the experience before adding any new capability
3. Only after UXR data: decide between improving UX or opening v0.6.1 (compressed files)
