# RecoveryLab — Project Status

> **Version**: v0.6.0
> **Status**: Open
> **Last CI run**: 2026-08-05 — ALL CHECKS PASS
> **Repo**: https://github.com/notrabjesmas/RecoveryLab

> **Each version changes a benchmark.**
> Before starting any version: *"What benchmark number will move?"*
> If you can't answer in one line, the version doesn't start.

---

## The evidence rule

Before starting any version, answer one question:

> **¿Qué evidencia nueva existirá cuando esta versión termine?**

Valid answers:
- "20 sparse files recovered with correct SHA-256."
- "10 users installed RecoveryLab without help."
- "95% of compressed files recovered."
- "TTFS average dropped from 6 minutes to 2 minutes."

Invalid answer:
- "There will be more code."

If the only evidence is code, the version's purpose isn't clear enough.

---

## Version states

A version is either **Open** or **Released**. Nothing else.

There is no "78% done". There is no "7/9 checklist".
Internally we track progress against a checklist, but externally
a version is either published or it isn't.

Users don't care about partial progress. They care about:
"Can I install this version and use it?"

---

## Branch strategy

```
main
 │
 ├── release/v0.6.0
 │
 └── develop
```

**`release/v0.6.0`** — Only these are allowed:
- Bug fixes
- Documentation
- Packaging
- CI adjustments

No new features enter a release branch. This prevents scope creep
and ensures the version ships with exactly what was planned.

**`develop`** — Active development. Features, experiments, refactoring.

**`main`** — Only receives merges from release branches.

---

## Two roadmaps

Technical and product roadmaps are separate.
They are both important, but they must not be mixed.

### Technical roadmap (the motor)

| Version | Benchmark target | Evidence | Status |
|---------|-----------------|----------|--------|
| v0.5.2 | NTFS normal: 0% → 100% | 20/20 files, RR=100% | Released |
| **v0.6.0** | **NTFS sparse: 0% → 100%** | **20/20 files, RR=100%** | **Open** |
| v0.6.1 | NTFS compressed: 0% → ≥95% | Compressed corpus CI-verified | **Release blocked** (UXR-001 first; develop open) |
| v0.6.2 | Alternate Data Streams | ADS corpus CI-verified | Pending |
| v0.7.0 | FAT32: 0% → 100% | FAT32 corpus CI-verified | Pending |
| v0.8.0 | exFAT: 0% → 100% | exFAT corpus CI-verified | Pending |
| v0.9.0 | ext4: 0% → 100% | ext4 corpus CI-verified | Pending |

### Product roadmap (the experience)

| Step | Objective | Evidence | Status |
|------|-----------|----------|--------|
| **UXR-001** | **10 external testers** | **UXR score, TTFS, failure points** | **Current** |
| GitHub Release | Publish v0.6.0 with wheel + sdist | Release page exists | Pending |
| Documentation | README, QuickStart, CLI docs work for strangers | UXR data confirms | Pending |
| Installation | pip install works first try | UXR install rate = 10/10 | Pending |
| CLI | scan/recover/demo clear without reading source | UXR demo+scan rate ≥ 8/10 | Pending |
| GUI | Visual interface for non-CLI users | Separate UXR test | Pending |

**Rule**: v0.6.1 cannot be **released** until UXR-001 has data.
However, development on compressed files is allowed in the `develop` branch.
This prevents the project from stalling if the experiment takes weeks,
while still ensuring no version ships without product evidence.

```
release/v0.6.0  → only fixes
release/v0.6.1  → cannot open until UXR-001 has results
develop          → compressed files work welcome here
```

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

These metrics cannot be estimated. They can only be measured with real people.

#### UXR — User Recovery Rate

Binary result. No opinions. No surveys. No "I liked it".

```
UXR Test
  Participants: 10
  Objective:
    1. Install RecoveryLab
    2. Execute: recoverylab demo
    3. Execute: recoverylab scan image.img
    4. Execute: recoverylab recover image.img output/
  Without help.
  
  Record:
    ¿Instaló?            Sí / No
    ¿Ejecutó demo?       Sí / No
    ¿Recuperó archivo?   Sí / No
    TTFS                 minutos
    ¿Dónde falló?        paso exacto
    ¿Necesitó ayuda?     Sí / No
  
  Result: N/10
```

The only question: **¿Pudo hacerlo?**

- Target for v1.0.0: UXR ≥ 8/10
- If UXR < 5/10: stop adding features. Fix the experience.
- RR = 100% means nothing if UXR = 2/10.

#### TTFS — Time To First Success

From the moment the user opens the README to the moment they recover their first file.

```
Example:
  00:00  User opens GitHub
  00:04  pip install recoverylab
  00:06  recoverylab demo
  00:07  Files recovered
  
  TTFS = 7 minutes
```

TTFS measures the experience, not the motor.
If TTFS drops from 7 minutes to 2 minutes over six months,
the product improved — even if the recovery engine didn't change a single line.

This is the metric almost nobody tracks. It's the one that matters most for adoption.

Current target: **TTFS ≤ 7 minutes** for a first-time user.

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
| Compressed runs | Not yet | Release blocked by UXR-001; develop open |
| GUI | Not yet | |
| FAT32 / exFAT | Not yet | |

---

## Infrastructure

| Component | Status |
|-----------|--------|
| RecoveryEngine API | Frozen, 25 contract tests |
| CLI | scan/recover/info/demo, 7 profiles, identity banner |
| Corpus | 4 categories, 80/80 CI-verified |
| CI regression | Baseline saved, sparse included |
| Example image | examples/demo.img (5 files, 1MB) |
| Recovery Cost (RC) | CPU + RAM + I/O + efficiency |
| Pipeline | 8 stages, extensible |
| Stability policy | 3 tiers (public/extension/internal) |
| Versioning | Semantic |
| pip package | recoverylab-0.6.0-py3-none-any.whl |
| User docs | Installation, QuickStart, CLI, API, Profiles, Plugins |
| UXR template | experiments/UXR-001.md |

---

## Project Rules

1. **Each version changes a benchmark** — not a metric, not a document, not an abstraction
2. **Before starting a version**: What benchmark will move? No answer = don't start
3. **The evidence rule**: What new evidence will exist when this version finishes? "More code" is not valid evidence.
4. **No percentage enters documentation until a reproducible benchmark produces it**
5. **Measure progress = what can you recover today that you couldn't yesterday?**
6. **API frozen** — breaking = MAJOR bump
7. **Corpus permanent** — every release verified against corpus
8. **CI regression** — new version ≥ previous version on RR
9. **UXR matters** — RR=100% means nothing if strangers can't use the tool
10. **TTFS matters** — if it takes 30 minutes to recover the first file, the product is broken
11. **Versions are Open or Released** — no partial progress shown to users
12. **Release branches are frozen** — only bugs, docs, packaging, CI. No features.
13. **Two roadmaps, never mixed** — technical and product are separate. No technical version is released without product evidence.
14. **Develop is always open** — contributions and experiments go to `develop`. Only release branches are gated by product evidence.

---

## Definition of Done (internal checklist)

A version is **not Released** until ALL of these are true.
This checklist is for internal tracking only. Externally, the version is Open.

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

## UXR-001 — Current objective

**Not v0.6.1. Not compressed files. This first.**

See `experiments/UXR-001.md` for the full recording sheet.

```
UXR-001 Experiment

  Objective:
    10 testers who never saw RecoveryLab try to use it.
  
  Same instructions for everyone. No help.
  
  Record only facts:
    ¿Instaló?            Sí / No
    ¿Ejecutó demo?       Sí / No
    ¿Recuperó archivo?   Sí / No
    TTFS                 minutos
    ¿Dónde falló?        paso exacto
    ¿Necesitó ayuda?     Sí / No
  
  Decision:
    UXR ≥ 8/10 → Close UXR-001. Open v0.6.1.
    UXR 5-7/10 → Fix top blockers. Run UXR-002.
    UXR < 5/10 → Stop features. Redesign onboarding.
```

If 8 people fail at `scan`, the next work isn't compressed files.
It's the CLI.

If everyone reaches demo in 2 minutes but fails at `recover`,
the problem isn't the motor either.

These 10 users will produce more real evidence than any feature.
The motor works. Now prove that a person can use it.
