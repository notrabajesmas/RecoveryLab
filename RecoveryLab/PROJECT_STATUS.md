# RecoveryLab — Project Status

> **Version**: v0.6.0
> **Last CI run**: 2026-08-05 — ALL CHECKS PASS
> **Repo**: https://github.com/notrabajesmas/RecoveryLab (privado)

---

## Roadmap

Cada version agrega **una capacidad nueva de recuperacion**, medida por un benchmark.

Antes de abrir una version, preguntar: **Que benchmark va a cambiar?**

Si no se puede responder en una linea, la version todavia no deberia empezar.

| Version | Benchmark objetivo | Estado |
|---------|-------------------|--------|
| v0.5.2 | NTFS normales 100% | Done |
| **v0.6.0** | **Sparse files 100%** | **Current** |
| v0.6.1 | Compressed files >=95% | Pending |
| v0.7.0 | GUI funcional | Pending |
| v0.8.0 | FAT32 100% | Pending |
| v0.9.0 | exFAT 100% | Pending |
| v1.0.0 | Public release | Pending |

---

## Product Metrics — v0.6.0

> These numbers come from `python scripts/ci_full.py` executed on 2026-08-05.
> No number appears here unless it was produced by a real, reproducible benchmark.

| Category | Files | RR | RFS | RC | Time | RAM |
|----------|------:|---:|----:|---:|-----:|----:|
| Normal | 20/20 | 100.0% | 0.815 | 0.500 | 0.53s | 117 MB |
| Fragmented | 20/20 | 100.0% | 0.815 | 0.500 | 0.50s | 159 MB |
| Deleted | 20/20 | 100.0% | 0.815 | 0.500 | 0.48s | 159 MB |
| **Sparse** | **20/20** | **100.0%** | **0.850** | **0.500** | **0.19s** | **159 MB** |

**Before v0.6.0**: Sparse files 0% (parser discarded sparse runs)
**After v0.6.0**: Sparse files 100% (20/20 verified, SHA-256 100%)

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

| Componente | Estado | Detalle |
|-----------|--------|---------|
| Strategy A (MFT) | Working | Metadata-based recovery |
| Strategy B (Journal) | Working | USN V2/V3/V4, delete detection |
| Strategy C (Carving) | Working | 19 formats, signature-based |
| Strategy D (Fragment) | Working | Multi-run reconstruction |
| Strategy E (Hybrid) | Working | Adaptive delegation |
| **Sparse runs** | **Working (v0.6.0)** | **Parser + recovery + corpus + CI** |
| Compressed runs | Not implemented | |
| GUI | Not implemented | |
| FAT32 / exFAT | Not implemented | |

---

## Infrastructure

| Componente | Estado |
|-----------|--------|
| RecoveryEngine API | Frozen, 25 contract tests |
| CLI | scan/recover/info, 7 profiles |
| Corpus | 4 categories (normal/fragmented/deleted/sparse), 80/80 CI-verified |
| CI regression | Baseline saved, sparse now included |
| Recovery Cost (RC) | CPU + RAM + I/O + efficiency |
| Pipeline | 8 stages, extensible |
| Stability policy | 3 tiers (public/extension/internal) |
| Versioning | Semantic |
| pyproject.toml | pip install recoverylab |
| User docs | Installation, QuickStart, CLI, API, Profiles, Plugins |

---

## Reglas del Proyecto

1. **Cada version agrega una capacidad nueva de recuperacion** — no una metrica, no un documento, no una abstraccion
2. **Antes de abrir una version**: Que benchmark va a cambiar? Si no hay respuesta, no empezar
3. **Ningun porcentaje entra a la documentacion hasta que exista un benchmark reproducible que lo genere**
4. **Medir avance = que puede recuperar hoy que ayer no podia**
5. **API congelada** — breaking = MAJOR bump
6. **Corpus permanente** — cada release se verifica contra corpus
7. **CI regresion** — version nueva >= version anterior en RR

---

## Como retomar

1. La version actual es **v0.6.0** — Sparse files 100% (CI-verified)
2. Before v0.6.1: make `pip install recoverylab` work for a stranger
3. Proximo paso: **v0.6.1** — Compressed files >=95%
4. Verificar: `python tests/test_api_contract.py` y `python scripts/ci_full.py`
5. User docs: `docs/QuickStart.md`
