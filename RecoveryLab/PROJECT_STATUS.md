# RecoveryLab — Project Status & Resume Guide

> **Ultima actualización**: 2026-08-05
> **Version actual**: v0.5.1
> **Repo GitHub**: https://github.com/notrabajesmas/RecoveryLab (privado)
> **Pregunta central**: ¿Qué puede hacer RecoveryLab hoy que no podía ayer?

---

## Estado Actual — Resumen Ejecutivo

RecoveryLab es una herramienta de recuperación de archivos sobre imágenes NTFS. Implementa 5 estrategias de recuperación (A-E), un sistema de métricas duales (RR + RFS), y una API pública congelada.

| Componente | Estado | Cobertura |
|-----------|--------|-----------|
| Strategy A (MFT) | ✅ Funcional | 100% metadata (75/75 archivos) |
| Strategy B (Journal) | ✅ Funcional | USN V2/V3, MFT xref, delete detection |
| Strategy C (Carving, 19 formatos) | ✅ Funcional | JPEG 100% real, PNG/PDF/ZIP/DOCX 99.8% sintético |
| Strategy D (Fragment) | ✅ Funcional | 41/41 multi-run files recovered, SHA-256 100% |
| Strategy E (Hybrid) | ✅ Funcional | Delegación adaptativa |
| NTFS MFT Parser | ✅ Funcional + SCALED | 100% SHA-256 at 10,000 files |
| NTFS Journal Parser | ✅ Funcional + SCALED + INTEGRATED | 100% entries at 5K files |
| **Métrica: RR (Recovery Rate)** | ✅ Funcional | Recuperados / Total |
| **Métrica: RFS (Recovery Fidelity Score)** | ✅ Funcional | 9-component weighted |
| **RecoveryEngine API** | ✅ Congelada v0.5.1 | scan(), recover(), statistics — 22 contract tests pass |
| **CLI** | ✅ Funcional v0.5.1 | recoverylab scan/recover/info + progreso + errores amigables |
| **Pipeline** | ✅ Funcional | 8 stages, extensible (FAT32/exFAT/EXT4) |
| **Corpus permanente** | ✅ Construido | 3 categorías, 60/60 verificados, RR=100% |
| **CI regresión** | ✅ Funcional | Baseline v0.5.1 guardada, 3 categorías PASS |
| GUI | ❌ No implementado | Solo CLI |

---

## Roadmap por Versiones — Lo que el usuario gana

| Versión | Lo que el usuario gana | Estado |
|---------|----------------------|--------|
| **v0.5.1** | **API pública congelada + CLI usable + corpus + CI** | ✅ Actual |
| v0.6.0 | Soporte para sparse runs (archivos con gaps) | Pendiente |
| v0.6.1 | Soporte para compressed runs (NTFS compression) | Pendiente |
| v0.7.0 | Primera GUI usable | Pendiente |
| v0.8.0 | Plugins (FAT32, exFAT, EXT4 auto-detectados) | Pendiente |
| v0.9.0 | Benchmark público vs PhotoRec/Foremost | Pendiente |
| v1.0.0 | Release pública (API estable + docs + installer) | Pendiente |

### v0.5.1 (actual)
**Objetivo:** API congelada + CLI usable + corpus permanente + CI de regresión

Checklist:
- ✅ RecoveryEngine API congelada (scan, recover, statistics)
- ✅ ScanResult.recover(id) — consumer-facing API
- ✅ ScanResult.recover_all(), get_file(), by_source(), by_status()
- ✅ core.__version__ = "0.5.1"
- ✅ 22 API contract tests pass
- ✅ CLI: recoverylab scan/recover/info
- ✅ CLI: barra de progreso (spinner)
- ✅ CLI: barras de confianza (█████)
- ✅ CLI: errores amigables (imagen inexistente, permisos, formato no soportado)
- ✅ CLI: --help con ejemplos y perfiles documentados
- ✅ CLI: estadísticas completas al finalizar (RR, RFS, tiempo, RAM)
- ✅ pyproject.toml para pip install
- ✅ Corpus permanente (normal, fragmented, deleted) — 60/60 verificados
- ✅ CI regresión contra corpus — baseline v0.5.1 guardada
- ✅ Pipeline architecture (8 stages, extensible)
- ⬜ Sparse runs (v0.6.0)
- ⬜ Compressed runs (v0.6.1)

### v0.6.0
**Objetivo:** Sparse runs — archivos con gaps (NTFS sparse files)

Checklist:
- Strategy D: handle sparse data runs (zero-fill gaps)
- Confidence scoring para sparse files
- Corpus: popular categoría sparse/
- CI: verificar que sparse no rompe normal/fragmented

### v0.6.1
**Objetivo:** Compressed runs — NTFS compression

Checklist:
- Strategy D: decompress NTFS-compressed data runs
- Confidence scoring para compressed files
- Corpus: popular categoría compressed/
- CI: verificar que compressed no rompe lo anterior

### v0.7.0
**Objetivo:** Primera GUI usable

Checklist:
- Seleccionar disco
- Preview de archivos
- Filtros por tipo/fecha/estado
- Exportar resultados
- Barra de progreso
- Consumir SOLO la API congelada de RecoveryEngine

### v0.8.0
**Objetivo:** Plugins — otros filesystems

Checklist:
- `class FAT32Strategy(RecoveryStrategy)` auto-detectado
- `class ExFATStrategy(RecoveryStrategy)` auto-detectado
- `class EXT4Strategy(RecoveryStrategy)` auto-detectado
- Pipeline: insertar stage para filesystem detectado
- Sin tocar el código existente

### v0.9.0
**Objetivo:** Benchmark público

Checklist:
- Comparación con PhotoRec
- Comparación con Foremost
- Comparación con Scalpel
- Datasets reproducibles
- Tabla pública de resultados

### v1.0.0
**Objetivo:** Release pública

Checklist:
- API estable sin breaking changes
- Documentación completa
- Installer (pip, binary)
- Corpus permanente + CI verde
- Benchmark público

---

## Product Metrics — v0.5.1

| Metric | Normal | Fragmented | Deleted |
|--------|--------|------------|---------|
| Files found | 20 | 20 | 20 |
| RR | 100% | 100% | 100% |
| RFS | 0.815 | 0.815 | 0.815 |
| Scan time | 0.53s | 0.52s | 0.50s |
| Peak RAM | 116 MB | 158 MB | 159 MB |

---

## Arquitectura del Proyecto

```
RecoveryLab/
├── core/                          # ★ PUBLIC API (FROZEN v0.5.1)
│   ├── engine.py                  #   RecoveryEngine — single entry point
│   ├── result.py                  #   ScanResult, RecoveredItem, RecoveryStatistics
│   ├── pipeline.py                #   Pipeline, PipelineStage, PipelineContext
│   └── stages.py                  #   8 concrete stages
│
├── strategies/                    # Strategy wrappers (thin over motors)
│   ├── strategy_a_mft.py          # Strategy A: MFT → targeted reads
│   ├── strategy_b_journal.py      # Strategy B: Journal → deleted/renamed files
│   ├── strategy_c_carving.py      # Strategy C: Signature carving (19 formatos)
│   ├── strategy_d_fragment.py     # Strategy D: Fragment → multi-run reconstruction
│   └── strategy_e_hybrid.py       # Strategy E: Hybrid → adaptive delegation
│
├── motors/                        # Motores (internal, strategy-level)
├── ntfs_parser/                   # NTFS parsing (MFT + Journal)
├── recovery_judge/                # Métricas + Scoring
├── dataset_builder/               # Generación de imágenes NTFS sintéticas
├── corruptor/                     # Modelos de corrupción
│
├── recoverylab.py                 # ★ CLI entry point
├── pyproject.toml                 # Packaging (pip install recoverylab)
│
├── datasets/ntfs/                 # ★ Corpus permanente de pruebas
│   ├── normal/                    #   Contiguous files
│   ├── fragmented/                #   Multi-run files
│   ├── sparse/                    #   (placeholder para v0.6.0)
│   ├── compressed/                #   (placeholder para v0.6.1)
│   └── deleted/                   #   Journal-recoverable
│
├── tests/                         # API contract tests
│   └── test_api_contract.py       #   22 tests — API frozen
│
├── scripts/                       # CI + corpus
│   ├── build_corpus.py            #   Build permanent test corpus
│   ├── ci_regression.py           #   Regression CI against corpus
│   └── benchmark_*.py             #   Performance benchmarks
│
└── results/ci_baselines/          # CI baseline results per version
```

---

## Reglas del Proyecto

1. **Cada versión entrega algo que un usuario puede descargar y usar**
2. **Medir avance = qué puede hacer hoy que no podía ayer**
3. **Core ≠ App** — el motor es una librería, la GUI es un consumidor
4. **Filtro**: ¿Esto acerca al usuario a recuperar sus archivos, o solo mejora el laboratorio?
5. **API congelada** — cambiar firmas públicas requiere MAJOR bump
6. **No perseguir 100% en sintéticos sin medir reales primero**
7. **No afirmar que X resolverá Y antes de medir**
8. **Cada versión tiene métricas visibles** (Product Metrics table)
9. **Pregunta central**: "¿Qué puede recuperar RecoveryLab hoy que ayer no podía?"
10. **Versiones semánticas** — no "Sprint X", sino "v0.X.Y"
11. **Corpus permanente** — cada release se verifica contra el corpus
12. **CI regresión** — "¿La versión nueva recupera al menos lo mismo que la anterior?"
13. **Regla de Oro (falsificación)**: "Ningún resultado positivo será considerado válido hasta que haya sobrevivido a al menos un intento serio de refutación"

---

## Cómo retomar el proyecto

1. Leer este archivo (`PROJECT_STATUS.md`) para estado completo
2. Leer `CHANGELOG.md` para historial de versiones
3. Leer `worklog.md` para historial detallado de tareas
4. La versión actual es **v0.5.1** — API congelada + CLI + corpus + CI
5. Próximo paso: **v0.6.0** — Sparse runs
6. Los archivos clave son `core/` (API pública), `strategies/`, `ntfs_parser/parser.py`
7. Las métricas son **RR** + **RFS** + **Quality = RR × RFS**
8. Las estrategias son A: MFT, B: Journal, C: Carving, D: Fragment, E: Hybrid
9. **Objetivo 6 meses**: RecoveryLab descargable → apuntar a disco → recuperar archivos → interfaz sencilla
10. Para verificar: `python tests/test_api_contract.py` y `python scripts/ci_regression.py`

---

## GitHub

- **Repo**: https://github.com/notrabajesmas/RecoveryLab
- **Visibilidad**: Privado
- **Token**: Configurado en remote (push access)
