# DIAG-0001 — Diagnóstico del Origen del Cero en Carving

**Date**: 2026-07-30 22:15
**Commit**: 3839ee3
**Protocol**: v1.5 | **Judge**: v1.0
**Pregunta**: ¿El cero proviene del algoritmo o del banco de pruebas?

---

## 1. Resumen por Formato

| Dataset | Formato | Vol. | MFT-First OU | Carving OU | Firmas | Carved | Matched | FP | Trunc-fixable |
|---------|---------|------|-------------|-----------|--------|--------|---------|-----|---------------|
| A | JPEG | 50MB | 1.0000 | 0.0000 | 16 | 3 | 0 | 3 | 2 |
| B | PNG | 50MB | 1.0000 | 0.8709 | 16 | 15 | 14 | 1 | 0 |
| C | PDF | 10MB | 1.0000 | 0.0000 | 15 | 15 | 0 | 15 | 15 |
| D | ZIP | 10MB | 1.0000 | 1.0000 | 45 | 15 | 15 | 0 | 0 |
| E | DOCX | 10MB | 1.0000 | 1.0000 | 45 | 15 | 15 | 0 | 0 |

## 2. Diagnóstico

**Origen del cero**: FORMAT_SPECIFIC_PARSER_ISSUES

**Explicación**:

> El carving funciona para ['B', 'D', 'E'] pero falla para ['A', 'C']. Las causas raíz son específicas por formato: PDF tiene un bug de footer (1 byte), JPEG tiene un problema de deduplicación. El motor de carving en sí funciona — el scanner encuentra firmas correctamente. El problema está en la extracción (footer detection + deduplication), no en la detección (signature scanning).

## 3. Causas Raíz Identificadas

### RC-001: PDF

- **Causa**: Footer mismatch: carving motor uses %%EOF (5 bytes) but file generator produces %%EOF\n (6 bytes)
- **Impacto**: ALL carved PDF files are 1 byte short. SHA-256 doesn't match.
- **Severidad**: HIGH — causes 100% PDF carving failure
- **Corrección sugerida**: Change PDF signature footer from %%EOF to %%EOF\n in motor_carving.py

### RC-002: JPEG

- **Causa**: Deduplication/overlap removal: carving motor finds 15 JPEG signatures but only carves 3 files
- **Impacto**: Most JPEG files are not carved. The 3 carved files are too short (missing millions of bytes).
- **Severidad**: HIGH — causes near-total JPEG carving failure
- **Corrección sugerida**: Investigate why _deduplicate_carves removes 12/15 JPEG carves. Likely: large files overlap with other signatures.

### RC-003: PNG

- **Causa**: 1 false positive: BMP signature detected within PNG data
- **Impacto**: Minor — 14/15 PNG files recovered correctly
- **Severidad**: LOW — minor impact on PNG carving
- **Corrección sugerida**: Improve BMP signature detection to avoid false positives within PNG data

## 4. Análisis por Formato

### Dataset A: JPEG

- Carving OU: 0.0000
- MFT-First OU: 1.0000
- Firmas encontradas: {'JPEG': 15, 'BMP': 1}
- Archivos carved: 3
- Matched a ground truth: 0
- False positives: 3
- Truncation-fixable: 2

**Detalle por archivo carved:**

- `carved_0001.jpg` (size=63101): UNMATCHED [TRUNCATION FIXABLE]
  - Razón: Missing 865081 byte(s) at end: 21 = b'!'. Adding it fixes SHA-256.
- `carved_0002.jpg` (size=206994): UNMATCHED [TRUNCATION FIXABLE]
  - Razón: Missing 923229 byte(s) at end: c8 = b'\xc8'. Adding it fixes SHA-256.
- `carved_0001.bmp` (size=50842112): UNMATCHED
  - Razón: SHA-256 not in ground truth. Data differs from original.

### Dataset B: PNG

- Carving OU: 0.8709
- MFT-First OU: 1.0000
- Firmas encontradas: {'PNG': 15, 'BMP': 1}
- Archivos carved: 15
- Matched a ground truth: 14
- False positives: 1
- Truncation-fixable: 0

**Detalle por archivo carved:**

- `carved_0001.png` (size=928182): → png_0001.png (sha256)
- `carved_0002.png` (size=1130223): → png_0002.png (sha256)
- `carved_0003.png` (size=2615725): → png_0003.png (sha256)
- `carved_0004.png` (size=2492678): → png_0004.png (sha256)
- `carved_0005.png` (size=1958849): → png_0005.png (sha256)
- `carved_0006.png` (size=1521668): → png_0006.png (sha256)
- `carved_0007.png` (size=1231152): → png_0007.png (sha256)
- `carved_0008.png` (size=1555586): → png_0008.png (sha256)
- `carved_0009.png` (size=1186515): → png_0009.png (sha256)
- `carved_0010.png` (size=78858): → png_0010.png (sha256)
- `carved_0011.png` (size=1261992): → png_0011.png (sha256)
- `carved_0012.png` (size=2100790): → png_0012.png (sha256)
- `carved_0013.png` (size=816699): → png_0013.png (sha256)
- `carved_0014.png` (size=2341891): → png_0014.png (sha256)
- `carved_0001.bmp` (size=31589376): UNMATCHED
  - Razón: SHA-256 not in ground truth. Data differs from original.

### Dataset C: PDF

- Carving OU: 0.0000
- MFT-First OU: 1.0000
- Firmas encontradas: {'PDF': 15}
- Archivos carved: 15
- Matched a ground truth: 0
- False positives: 15
- Truncation-fixable: 15

**Detalle por archivo carved:**

- `carved_0001.pdf` (size=480667): UNMATCHED [TRUNCATION FIXABLE]
  - Razón: Missing 1 byte(s) at end: 0a = b'\n'. Adding it fixes SHA-256.
- `carved_0002.pdf` (size=458351): UNMATCHED [TRUNCATION FIXABLE]
  - Razón: Missing 1 byte(s) at end: 0a = b'\n'. Adding it fixes SHA-256.
- `carved_0003.pdf` (size=321714): UNMATCHED [TRUNCATION FIXABLE]
  - Razón: Missing 1 byte(s) at end: 0a = b'\n'. Adding it fixes SHA-256.
- `carved_0004.pdf` (size=306333): UNMATCHED [TRUNCATION FIXABLE]
  - Razón: Missing 1 byte(s) at end: 0a = b'\n'. Adding it fixes SHA-256.
- `carved_0005.pdf` (size=415175): UNMATCHED [TRUNCATION FIXABLE]
  - Razón: Missing 1 byte(s) at end: 0a = b'\n'. Adding it fixes SHA-256.
- `carved_0006.pdf` (size=184957): UNMATCHED [TRUNCATION FIXABLE]
  - Razón: Missing 1 byte(s) at end: 0a = b'\n'. Adding it fixes SHA-256.
- `carved_0007.pdf` (size=373574): UNMATCHED [TRUNCATION FIXABLE]
  - Razón: Missing 1 byte(s) at end: 0a = b'\n'. Adding it fixes SHA-256.
- `carved_0008.pdf` (size=410961): UNMATCHED [TRUNCATION FIXABLE]
  - Razón: Missing 1 byte(s) at end: 0a = b'\n'. Adding it fixes SHA-256.
- `carved_0009.pdf` (size=143063): UNMATCHED [TRUNCATION FIXABLE]
  - Razón: Missing 1 byte(s) at end: 0a = b'\n'. Adding it fixes SHA-256.
- `carved_0010.pdf` (size=475343): UNMATCHED [TRUNCATION FIXABLE]
  - Razón: Missing 1 byte(s) at end: 0a = b'\n'. Adding it fixes SHA-256.
- `carved_0011.pdf` (size=152498): UNMATCHED [TRUNCATION FIXABLE]
  - Razón: Missing 1 byte(s) at end: 0a = b'\n'. Adding it fixes SHA-256.
- `carved_0012.pdf` (size=383545): UNMATCHED [TRUNCATION FIXABLE]
  - Razón: Missing 1 byte(s) at end: 0a = b'\n'. Adding it fixes SHA-256.
- `carved_0013.pdf` (size=96836): UNMATCHED [TRUNCATION FIXABLE]
  - Razón: Missing 1 byte(s) at end: 0a = b'\n'. Adding it fixes SHA-256.
- `carved_0014.pdf` (size=435962): UNMATCHED [TRUNCATION FIXABLE]
  - Razón: Missing 1 byte(s) at end: 0a = b'\n'. Adding it fixes SHA-256.
- `carved_0015.pdf` (size=312950): UNMATCHED [TRUNCATION FIXABLE]
  - Razón: Missing 1 byte(s) at end: 0a = b'\n'. Adding it fixes SHA-256.

### Dataset D: ZIP

- Carving OU: 1.0000
- MFT-First OU: 1.0000
- Firmas encontradas: {'ZIP': 15, 'DOCX': 15, 'XLSX': 15}
- Archivos carved: 15
- Matched a ground truth: 15
- False positives: 0
- Truncation-fixable: 0

**Detalle por archivo carved:**

- `carved_0001.zip` (size=480668): → zip_0001.zip (sha256)
- `carved_0002.zip` (size=458352): → zip_0002.zip (sha256)
- `carved_0003.zip` (size=321715): → zip_0003.zip (sha256)
- `carved_0004.zip` (size=306334): → zip_0004.zip (sha256)
- `carved_0005.zip` (size=415176): → zip_0005.zip (sha256)
- `carved_0006.zip` (size=184958): → zip_0006.zip (sha256)
- `carved_0007.zip` (size=373575): → zip_0007.zip (sha256)
- `carved_0008.zip` (size=410962): → zip_0008.zip (sha256)
- `carved_0009.zip` (size=143064): → zip_0009.zip (sha256)
- `carved_0010.zip` (size=475344): → zip_0010.zip (sha256)
- `carved_0011.zip` (size=152499): → zip_0011.zip (sha256)
- `carved_0012.zip` (size=383546): → zip_0012.zip (sha256)
- `carved_0013.zip` (size=96837): → zip_0013.zip (sha256)
- `carved_0014.zip` (size=435963): → zip_0014.zip (sha256)
- `carved_0015.zip` (size=312951): → zip_0015.zip (sha256)

### Dataset E: DOCX

- Carving OU: 1.0000
- MFT-First OU: 1.0000
- Firmas encontradas: {'ZIP': 15, 'DOCX': 15, 'XLSX': 15}
- Archivos carved: 15
- Matched a ground truth: 15
- False positives: 0
- Truncation-fixable: 0

**Detalle por archivo carved:**

- `carved_0001.zip` (size=480668): → docx_0001.docx (sha256)
- `carved_0002.zip` (size=458352): → docx_0002.docx (sha256)
- `carved_0003.zip` (size=321715): → docx_0003.docx (sha256)
- `carved_0004.zip` (size=306334): → docx_0004.docx (sha256)
- `carved_0005.zip` (size=415176): → docx_0005.docx (sha256)
- `carved_0006.zip` (size=184958): → docx_0006.docx (sha256)
- `carved_0007.zip` (size=373575): → docx_0007.docx (sha256)
- `carved_0008.zip` (size=410962): → docx_0008.docx (sha256)
- `carved_0009.zip` (size=143064): → docx_0009.docx (sha256)
- `carved_0010.zip` (size=475344): → docx_0010.docx (sha256)
- `carved_0011.zip` (size=152499): → docx_0011.docx (sha256)
- `carved_0012.zip` (size=383546): → docx_0012.docx (sha256)
- `carved_0013.zip` (size=96837): → docx_0013.docx (sha256)
- `carved_0014.zip` (size=435963): → docx_0014.docx (sha256)
- `carved_0015.zip` (size=312951): → docx_0015.docx (sha256)

## 5. Ranking de Hipótesis

### 1. H-CARVING-001: El parser de carving tiene un bug

- **Probabilidad**: 🔴 HIGH
- **Evidencia**: PDF footer bug: %%EOF vs %%EOF\n. JPEG deduplication bug: 12/15 files removed.
- **Refinado**: No es un bug general del parser, sino bugs específicos: footer de PDF y deduplicación de JPEG.

### 2. H-CARVING-005: Los footers siguen siendo insuficientes

- **Probabilidad**: 🔴 HIGH
- **Evidencia**: PDF: footer %%EOF no incluye \n. JPEG: footer FF D9 funciona pero deduplicación elimina archivos.
- **Refinado**: El footer de PDF es incorrecto (falta \n). El footer de JPEG funciona pero la deduplicación interfiere.

### 3. H-CARVING-007: La implementación del carving todavía está incompleta

- **Probabilidad**: 🟡 MEDIUM
- **Evidencia**: El scanner funciona (encuentra firmas), pero la extracción tiene bugs (PDF footer, JPEG dedup).
- **Refinado**: El carving está parcialmente implementado: la detección funciona, la extracción tiene bugs.

### 4. H-CARVING-003: El generador produce archivos poco realistas

- **Probabilidad**: 🟢 LOW
- **Evidencia**: ZIP/DOCX/PNG carving funciona perfectamente. Los archivos generados son carveables.
- **Refinado**: El generador produce archivos válidos. El problema está en el carving, no en el generador.

### 5. H-CARVING-002: El dataset no contiene suficientes formatos carveables

- **Probabilidad**: 🟢 LOW
- **Evidencia**: Todos los formatos probados son carveables. El problema es la extracción, no la detección.

### 6. H-CARVING-004: El Judge penaliza excesivamente el carving

- **Probabilidad**: 🟢 LOW
- **Evidencia**: Cuando el carving extrae datos correctos (ZIP/DOCX/PNG), el Judge los puntúa correctamente.

### 7. H-CARVING-006: El RVS/FQS favorecen tipos de archivo que carving no puede recuperar

- **Probabilidad**: 🟢 LOW
- **Evidencia**: Cuando carving funciona (ZIP/DOCX/PNG), RVS/FQS son correctos. No hay sesgo en el scoring.

## 6. Observación Pura (para Evidence Ledger)

> En DIAG-0001, bajo las condiciones evaluadas (5 datasets de formato único,
> 15 archivos cada uno, sin corrupción, Judge API v1.0, Protocol v1.5),
> el Motor Carving obtuvo:
>
> - JPEG: OU = 0.0000
> - PNG: OU = 0.8709
> - PDF: OU = 0.0000
> - ZIP: OU = 1.0000
> - DOCX: OU = 1.0000
>
> El scanner de firmas detectó correctamente los archivos en todos los formatos.
> La falla no está en la detección, sino en la extracción.

## 7. Conclusión

**El cero proviene del algoritmo de extracción, no del banco de pruebas.**

Específicamente:
1. **RC-001 (PDF)**: El footer del carving motor es `%%EOF` (5 bytes) pero el
   generador produce `%%EOF\n` (6 bytes). Cada PDF carved es 1 byte corto.
   Agregar el byte faltante restaura el SHA-256 correcto.
2. **RC-002 (JPEG)**: El motor de deduplicación elimina 12/15 archivos carved
   porque los archivos grandes se superponen. Los 3 archivos carved restantes
   son demasiado cortos (millones de bytes faltantes).

**NO se ha modificado ningún código.** Este diagnóstico localiza el origen del cero.
La corrección requiere una decisión de diseño: ¿cambiar el footer del carving,
el generador, o ambos? Esa decisión requiere un RP-XXX Proposal.

---

*Experiment ID: DIAG-0001 | Protocol: v1.5 | Judge: v1.0*