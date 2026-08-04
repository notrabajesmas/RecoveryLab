# RecoveryLab — Project Status & Resume Guide

> **Ultima actualización**: 2026-08-05
> **Version actual**: v0.3
> **Repo GitHub**: https://github.com/notrabajesmas/RecoveryLab (privado)
> **Pregunta central**: ¿Qué puede recuperar RecoveryLab hoy que ayer no podía?

---

## Estado Actual — Resumen Ejecutivo

RecoveryLab es una herramienta de recuperación de archivos sobre imágenes NTFS. Implementa 3 motores de recuperación y un sistema científico de validación.

| Componente | Estado | Cobertura |
|-----------|--------|-----------|
| Motor Carving (19 formatos) | ✅ Funcional | JPEG 100% real, PNG/PDF/ZIP/DOCX 99.8% sintético |
| Motor B (MFT-First) | ✅ Funcional | 100% metadata (75/75 archivos) |
| Motor C (Orchestrator) | ✅ Funcional | Delegación adaptativa |
| NTFS MFT Parser | ✅ Funcional | Filenames, timestamps, data runs, directorios |
| NTFS Journal Parser | ❌ Stub | `JournalEntry` dataclass existe, sin parsing real |
| Fragmentación | ❌ No implementado | No hay recuperación de archivos fragmentados |
| EXIF metadata | ❌ No implementado | No hay extracción de metadata JPEG |
| GUI | ❌ No implementado | Solo CLI |

---

## Roadmap (Sprints)

| Sprint | Objetivo | Métrica visible | Estado |
|--------|----------|-----------------|--------|
| Sprint 1 | Carving básico | 0% → 54.7% | ✅ Completado |
| Sprint 2 | Cerrar JPEG + benchmark real | 91.4% → 100% real | ✅ Completado |
| **Sprint 3** | **Journal Parser** | **NTFS Journal 0% → 90%** | **⏳ Próximo** |
| Sprint 4 | Fragmentación | 0% → 50% | Pendiente |
| Sprint 5 | EXIF metadata | 0% → 100% | Pendiente |
| Sprint 6 | GUI (CLI → RecoveryLab.exe) | Interacción visual | Pendiente |
| Sprint 7 | Benchmark vs PhotoRec/Foremost/Scalpel | Comparación externa | Pendiente |

---

## Sprint 1 — Completado

**Fecha**: 2026-07-30
**Resultado**: Carving básico funcional, 54.7% recovery rate

### Lo que se hizo:
- Motor Carving con 6 firmas iniciales (JPEG, PNG, PDF, ZIP, MP4, DOCX)
- Motor A (Sequential) y Motor B (MFT-First)
- Motor C (Orchestrator) con delegación adaptativa
- Dataset builder para imágenes NTFS sintéticas
- Recovery Judge con scoring imparcial (RVS + FQS)
- Experiment runner automatizado
- 10 corruption models para simulación de fallas reales

### Problemas encontrados:
- BMP false positive causaba cascade de 44.6% en dedup
- PDF footer mismatch (`%%EOF` vs `%%EOF\n`) causaba SHA-256 failures
- JPEG truncación por delimitación naïve (primer FFD9)

---

## Sprint 2 — Completado

**Fecha**: 2026-08-01
**Resultado**: JPEG 100% real (1000/1000), 99.8% sintético
**Métrica visible**: Recovery rate real JPEGs

### Lo que se hizo:

#### Bug fix crítico en `_carve_file()`:
- **Problema**: `_carve_jpeg()` retorna un dict con keys {"data", "start_offset", "end_offset", "size", "format"}, pero `_carve_file()` usaba `len(file_data)` para verificar min_size → `len(dict) = 5 < 200` → siempre retornaba None
- **Impacto**: El parser JPEG mejorado (Tier 1/2/3) NUNCA se ejecutaba en carving real
- **Fix**: JPEG branch retorna directamente el resultado de `_carve_jpeg()`
- **Archivo**: `motors/motor_carving.py`

#### JPEG 3-tier parser:
- **Tier 1**: Último FFD9 antes del próximo JPEG signature (método principal)
- **Tier 2**: Parsing estructural SOS + byte stuffing (para JPEGs sin signature siguiente)
- **Tier 3**: Último FFD9 dentro de max_size (fallback)

#### Benchmark con 1000 JPEGs reales:
- **Script**: `scripts/benchmark_real_jpegs.py`
- **Método**: Pillow + numpy generan JPEGs reales (6 modos × 5 tamaños)
- **6 modos de imagen**: photo, landscape, noise, text, screenshot, portrait
- **5 categorías de tamaño**: tiny (50-200px), small (200-800), medium (800-1920), large (1920-3840), huge (3840-7680)
- **Procesamiento**: Stream por lotes de 100 para evitar OOM
- **Resultado**: 1000/1000 = 100.00% recovery rate

#### Defectos cerrados:
- **RC-A-001**: PDF footer fix (VERIFIED)
- **RC-A-002**: BMP false positive eliminado (ROOT_CAUSE_CONFIRMED, fix by RP-002)
- **RC-002 (old)**: JPEG truncation → FIXED — VERIFIED_ON_REAL_JPEGS

#### Decisión metodológica:
- No perseguir 100% en sintéticos (1/525 failure es dataset artefact)
- Medir primero sobre casos reales, luego decidir
- Cada sprint debe terminar con mejor software, no mejor documentación

---

## v0.3 — NTFS MFT Parser (adición de Sprint 2)

**Fecha**: 2026-08-05
**Resultado**: 100% metadata extraction (75/75 archivos)

### Lo que se hizo:
- MFT entry parsing: filenames, timestamps, data runs, directory structure
- Real filenames (en vez de "carved_0001.jpg")
- Directory tree reconstruction
- NTFS timestamps (created, modified, accessed)
- Data run following para archivos non-resident
- Resident file recovery (data embebida en MFT entry)
- Deleted file detection (MFT entries not in use)
- Fixup (Update Sequence) application para multi-sector MFT records
- Bug fix: MFT parser leía value_offset del campo erróneo (offset+14 vs offset+20)

---

## Arquitectura del Proyecto

```
RecoveryLab/
├── motors/                        # Motores de recuperación (core)
│   ├── base_motor.py              # Abstract BaseMotor + RecoveredFile + MotorResult
│   ├── motor_a_sequential.py      # Motor A: Sequential scan
│   ├── motor_b_mft_first.py      # Motor B: MFT-first + fallback cascade
│   ├── motor_carving.py           # ★ Motor Carving: 19 formatos, 3-tier JPEG
│   └── motor_c_orchestrator.py    # Motor C: Adaptive orchestrator
│
├── ntfs_parser/                   # NTFS parsing
│   └── parser.py                  # MFT parser + JournalEntry (stub)
│
├── dataset_builder/               # Generación de imágenes NTFS sintéticas
├── corruptor/                     # Modelos de corrupción (12 escenarios)
├── recovery_judge/                # Scoring imparcial (RVS + FQS + 6 componentes)
├── experiment_runner/             # Pipeline automatizado
├── visualizer/                    # Disk layout ASCII + PNG
│
├── defects/                       # Defect tracking (RC taxonomy)
├── claims/                        # Scientific claims
├── results/                       # Benchmark results
└── scripts/                       # Utility scripts (en /home/z/my-project/scripts/)
```

### Motores:

| Motor | Estrategia | Usa MFT | Usa Firmas | Usa Journal |
|-------|-----------|---------|-----------|------------|
| A (Sequential) | Leer todo → MFT | ✅ | ❌ | ❌ |
| B (MFT-First) | MFT → datos referenciados | ✅ | ❌ | Stub |
| Carving | Firmas → carving | ❌ | ✅ (19) | ❌ |
| C (Orchestrator) | Adaptativo | ✅ | ✅ | Stub |

### Formatos soportados por Carving (19):
JPEG, PNG, PDF, ZIP, MP4, DOCX, TIFF, CR2, NEF, MOV, XLSX, SQLite, GIF, BMP, RAR, 7Z, PSD, DNG, HEIC, AVI

---

## Defectos — Estado Actual

| ID | Título | Estado | Severidad |
|----|--------|--------|-----------|
| RC-A-001 | PDF footer excludes trailing newline | FIXED | HIGH |
| RC-A-002 | BMP false positive → dedup cascade | ROOT_CAUSE_CONFIRMED (fix by RP-002) | HIGH |
| RC-A-003 | Scale-dependent recovery collapse | PARTIALLY_RESOLVED | HIGH |

---

## Blockers — Estado Actual

| ID | Título | Severidad | Estado |
|----|--------|-----------|--------|
| BLOCKER-001 | Motor A no es carving real | CRITICAL | ACTIVO (mitigated by MotorCarving) |
| BLOCKER-002 | Benchmark autocomplaciente | HIGH | PENDIENTE (needs external validation) |
| BLOCKER-003 | Crossover 95% es artefacto | HIGH | ACTIVO |
| BLOCKER-004 | Espacio de estrategias reducido | MEDIUM | ACTIVO (Journal Parser lo amplía) |

---

## Benchmarks — Resultados

### Real JPEG Benchmark (Sprint 2)
- **1000/1000 = 100.00%** recovery rate
- 6 modos × 5 tamaños = 30 combinaciones
- 81.8 segundos elapsed
- Veredicto: A

### Sintético (Sprint 2)
- **724/725 = 99.86%** (5 formatos × 3 tamaños × ~48 archivos)
- 1 failure es dataset artefact, no parser bug

### Benchmark v1 (Simulator)
- 10/10 escenarios: Motor B wins
- S10 (dying disk): A=0, B=37.2

### Benchmark v2 (Simulator + read budget)
- 6/10 Motor B wins, 4/10 tie
- S10 (dying): A=0, B=28.0 (+2800%)

### MFT Parser (v0.3)
- 75/75 archivos = 100% metadata
- 5 formatos: JPEG, PNG, PDF, ZIP, DOCX
- SHA-256: 100% match

---

## Journal Parser — Estado Actual (Sprint 3 target)

### Infraestructura existente (stubs):
- `ntfs_parser/parser.py`: `JournalEntry` dataclass (usn, file_reference, parent_reference, reason, file_attributes, timestamp, filename, is_delete)
- `ntfs_parser/parser.py`: `NTFSMetadata.journal_entries` list
- `motors/motor_b_mft_first.py`: `_fallback_journal()` → retorna lista vacía
- `corruptor/models.py`: `JournalCorruptionModel` → funciona (corrompe $LogFile)
- `config.py`: "journal_corruption" corruption model
- `strategy_profiles.py`: `uses_journal: bool = False`, journal-first profile existe

### Lo que FALTA implementar:
1. Parsing del $UsnJrnl binary format (NTFS Change Journal)
2. Lectura de journal entries (USN_RECORD v2.0 / v3.0 / v4.0)
3. Extracción de: filename, parent_ref, reason flags, timestamp, file_attributes
4. Detección de operaciones de interés: FILE_CREATE, FILE_DELETE, RENAME, DATA_OVERWRITE
5. Integración con Motor B: `_fallback_journal()` que realmente recupere archivos
6. Integración con Motor C: journal strategy que delegue al parser
7. Benchmark: medir journal recovery rate (0% → 90%)

### Formato NTFS $UsnJrnl:
- System file MFT entry 0x1A (26)
- $J data stream: journal records
- USN_RECORD v2.0: 48-byte header + filename (variable)
- USN_RECORD v4.0: 56-byte header + filename (variable)
- Reason flags: USN_REASON_FILE_CREATE, DATA_OVERWRITE, DATA_EXTEND, etc.

---

## Reglas del Proyecto

1. **Cada sprint termina con mejor software, no mejor documentación**
2. **No perseguir 100% en sintéticos sin medir reales primero**
3. **No afirmar que X resolverá Y antes de medir**
4. **Cada sprint tiene una métrica visible**
5. **Pregunta central**: "¿Qué puede recuperar RecoveryLab hoy que ayer no podía?"
6. **Naming**: versiones (v0.2, v0.3...) con checklist, no RC/RP/INST
7. **Prioridad**: software > docs; docs solo si aparece un problema nuevo
8. **Regla de Oro (falsificación)**: "Ningún resultado positivo será considerado válido hasta que haya sobrevivido a al menos un intento serio de refutación"

---

## Naming Convention

Antes: RC-001, RP-001, INST-0002 (tracking de defects/instruments)
Ahora: versiones con checklist

```
v0.2 checklist:
  ✔ PDF Recovery (footer fix)
  ✔ JPEG Recovery (3-tier parser)
  ✔ PNG Recovery (IEND chunk)
  ✔ ZIP Recovery (end-of-central-directory)
  ✔ DOCX Recovery (ZIP-based)
  ✔ BMP false positive eliminated
  ✔ 1000 real JPEGs benchmark: 100%

v0.3 checklist:
  ✔ MFT Parser (filenames, timestamps, data runs)
  ✔ Real filenames (no "carved_0001.jpg")
  ✔ Directory tree reconstruction
  ✔ Deleted file detection
  ✔ 75/75 files metadata: 100%
```

---

## Cómo retomar el proyecto

1. Leer este archivo (`PROJECT_STATUS.md`) para estado completo
2. Leer `worklog.md` para historial detallado de tareas
3. Leer `CHANGELOG.md` para historial de versiones
4. Leer `BLOCKERS.md` para blockers activos
5. Leer `defects/` para defects abiertos
6. El Sprint actual es **Sprint 3: Journal Parser** → ver sección "Journal Parser — Estado Actual"
7. El archivo clave a modificar es `ntfs_parser/parser.py`
8. El método stub a implementar es `motor_b_mft_first.py::_fallback_journal()`

---

## GitHub

- **Repo**: https://github.com/notrabajesmas/RecoveryLab
- **Visibilidad**: Privado
- **Token**: Configurado en remote (push access)
