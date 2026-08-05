# RecoveryLab — Project Status

> **Versión actual**: v0.6.0
> **Repo**: https://github.com/notrabajesmas/RecoveryLab (privado)

---

## Roadmap

Cada versión agrega **una capacidad nueva de recuperación**, medida por un benchmark.

Antes de abrir una versión, preguntar: **¿Qué benchmark va a cambiar?**

Si no se puede responder en una línea, la versión todavía no debería empezar.

| Versión | Benchmark objetivo | Estado |
|---------|-------------------|--------|
| v0.5.2 | NTFS normales 100% | ✅ |
| **v0.6.0** | **Sparse files 100%** | ✅ Actual |
| v0.6.1 | Compressed files ≥95% | Pendiente |
| v0.7.0 | GUI funcional | Pendiente |
| v0.8.0 | FAT32 100% | Pendiente |
| v0.9.0 | exFAT 100% | Pendiente |
| v1.0.0 | Public release | Pendiente |

---

## Product Metrics — v0.6.0

| Category | Files | RR | RFS | Time | RAM |
|----------|------:|---:|----:|-----:|----:|
| Normal | 20 | 100% | 0.850 | 0.53s | 116 MB |
| Fragmented | 20 | 100% | 0.850 | 0.49s | 159 MB |
| Deleted | 20 | 100% | 0.850 | 0.48s | 159 MB |
| **Sparse** | **20** | **100%** | **0.850** | **0.21s** | — |

**Antes de v0.6.0**: Sparse files 0% (parser descartaba sparse runs)
**Después de v0.6.0**: Sparse files 100% (20/20 verificados, SHA-256 100%)

---

## Capabilities

| Componente | Estado | Detalle |
|-----------|--------|---------|
| Strategy A (MFT) | ✅ | 100% metadata, targeted reads |
| Strategy B (Journal) | ✅ | USN V2/V3/V4, delete detection |
| Strategy C (Carving) | ✅ | 19 formatos, JPEG 100% real |
| Strategy D (Fragment) | ✅ | Multi-run 41/41, SHA-256 100% |
| Strategy E (Hybrid) | ✅ | Delegación adaptativa |
| **Sparse runs** | ✅ **v0.6.0** | **Parser + recovery + corpus + benchmark** |
| Compressed runs | ❌ | Sin implementar |
| GUI | ❌ | Sin implementar |
| FAT32 / exFAT | ❌ | Sin implementar |

---

## Infrastructure

| Componente | Estado |
|-----------|--------|
| RecoveryEngine API | ✅ Congelada, 25 contract tests |
| CLI | ✅ scan/recover/info, 7 profiles |
| Corpus permanente | ✅ 4 categorías (normal/fragmented/deleted/sparse), 80/80 |
| CI regresión | ✅ Baseline guardada |
| Recovery Cost (RC) | ✅ CPU + RAM + I/O + efficiency |
| Pipeline | ✅ 8 stages, extensible |
| Stability policy | ✅ 3 tiers (public/extension/internal) |
| Versionado | ✅ Semántico |
| pyproject.toml | ✅ pip install recoverylab |
| **User docs** | ✅ **Installation, QuickStart, CLI, API, Profiles, Plugins** |

---

## Arquitectura

```
RecoveryLab/
├── core/                    # PUBLIC API (FROZEN)
│   ├── engine.py            #   RecoveryEngine
│   ├── result.py            #   ScanResult, RecoveredItem, RecoveryStatistics
│   ├── pipeline.py          #   Pipeline, PipelineStage
│   └── stages.py            #   8 concrete stages (FragmentStage: sparse-aware)
│
├── strategies/              # STABLE EXTENSION API
├── motors/                  # Internal
├── ntfs_parser/             # Internal (sparse runs now handled)
├── recovery_judge/          # Internal
├── dataset_builder/         # Internal (add_sparse_file() added)
├── corruptor/               # Internal
│
├── recoverylab.py           # CLI v0.6.0
├── docs/                    # User documentation
├── datasets/ntfs/           # Corpus
│   ├── normal/
│   ├── fragmented/
│   ├── sparse/              # ✅ v0.6.0 — 20 sparse files
│   ├── compressed/          # (v0.6.1)
│   └── deleted/
│
├── tests/                   # API contract tests
├── scripts/                 # CI + benchmarks
└── results/ci_baselines/    # Regression baselines
```

---

## Reglas del Proyecto

1. **Cada versión agrega una capacidad nueva de recuperación** — no una métrica, no un documento, no una abstracción
2. **Antes de abrir una versión**: ¿Qué benchmark va a cambiar? Si no hay respuesta, no empezar
3. **Medir avance = qué puede recuperar hoy que ayer no podía**
4. **API congelada** — breaking = MAJOR bump
5. **Corpus permanente** — cada release se verifica contra corpus
6. **CI regresión** — versión nueva ≥ versión anterior en RR
7. **Regla de Oro**: ningún resultado positivo es válido hasta sobrevivir un intento de refutación
8. **Escribir docs para usuarios, no para nosotros** — ¿alguien puede usar RecoveryLab en 10 minutos?

---

## Cómo retomar

1. La versión actual es **v0.6.0** — Sparse files 100%
2. Próximo paso: **v0.6.1** — Compressed files ≥95%
3. Archivos clave: `ntfs_parser/parser.py` (sparse run parsing), `core/stages.py` (FragmentStage), `dataset_builder/ntfs_image.py` (add_sparse_file)
4. Verificar: `python tests/test_api_contract.py` y `python scripts/ci_regression.py`
5. User docs: `docs/QuickStart.md`
