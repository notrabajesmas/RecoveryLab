# RecoveryLab — BLOCKERS

Issues que bloquean la validez científica del laboratorio.
Hasta que no se resuelvan, los resultados experimentales NO son interpretables.

---

## BLOCKER-001: Motor A no representa una estrategia de carving

**Estado**: ACTIVO  
**Severidad**: CRITICAL — invalida todas las comparaciones A vs B  
**Descubierto**: 2026-07-30  
**Fuente**: Revisión externa adversarial

### Descripción

Motor A (Sequential Scan) y Motor B (MFT-First) **no representan estrategias distintas**. Ambos dependen exclusivamente del MFT para identificar y recuperar archivos. La única diferencia es el **orden de lectura**:

- Motor A: Leer todo → Parsear MFT → Recuperar
- Motor B: Leer MFT → Leer datos referenciados → Recuperar

Motor A tiene un diccionario `FILE_SIGNATURES` pero **jamás lo usa** para recuperar archivos. Siempre parsea MFT records. Es "MFT-last", no "carving".

### Consecuencia

La comparación A vs B no testa H1 ("¿los metadatos reducen el costo?"). Testa "¿leer MFT primero es más eficiente que leer MFT después?". Eso es una tautología, no un experimento.

### Resolución requerida

1. Implementar un **Motor Carving real** que:
   - Use SOLO firmas de archivo (JPEG, PNG, PDF, ZIP, MP4, DOCX)
   - NUNCA lea el MFT
   - NUNCA dependa de metadatos del sistema de archivos
   - Recupere archivos por contenido, no por estructura

2. Renombrar Motor A como "Motor MFT-Sequential" (no "carving")

3. Re-ejecutar TODOS los experimentos con tres estrategias genuinamente distintas:
   - **Carving puro** (sin MFT)
   - **MFT puro** (sin carving)
   - **Motor C** (adaptativo)

### Criterio de cierre

- [ ] Motor Carving implementado y funcional
- [ ] Motor Carving recupera archivos sin NUNCA leer MFT
- [ ] Experimentos re-ejecutados con 3 estrategias
- [ ] H1.1 re-evaluada con datos nuevos

---

## BLOCKER-003: Crossover al 95% es artefacto del carving actual

**Estado**: ACTIVO  
**Severidad**: HIGH — invalida el crossover al 95% como descubrimiento  
**Descubierto**: 2026-07-30  
**Fuente**: Revisión externa adversarial

### Descripción

El crossover al 95% de daño del MFT NO es un descubrimiento científico. Es una propiedad del carving actual.

El Motor Carving actual solo soporta 6 firmas (JPEG, PNG, PDF, ZIP, MP4, DOCX). Esto le da un techo artificial de ~6.7% de recuperación (1/15 archivos). La curva de carving está "pegada al piso" casi por definición.

Si el carving soportara TIFF, CR2, NEF, MOV, SQLite, XLSX, y otros formatos, la curva cambiaría completamente. El punto de crossover se movería a un valor distinto.

### Consecuencia

- No publicar el número "95%" como descubrimiento
- El crossover SÍ existe (las curvas se cruzan), pero el punto exacto no es confiable
- Lo que SÍ es sólido: "una estrategia basada en metadatos y una basada en firmas no fallan de la misma manera"

### Resolución requerida

1. Expandir el Motor Carving con más firmas (TIFF, CR2, NEF, MOV, SQLite, XLSX)
2. Cambiar el eje experimental: degradar por FORMATO (JPEG 0→100%, MP4 0→100%, etc.), no por MFT
3. Medir la tasa de recuperación por formato para cada estrategia
4. Solo reportar el punto de crossover cuando el carving tenga cobertura suficiente

### Criterio de cierre

- [ ] Motor Carving soporta al menos 12 firmas
- [ ] Experimento por formato ejecutado (JPEG, MP4, DOCX, SQLite, RAW)
- [ ] Crossover recalculado con carving expandido
- [ ] H2 actualizada con caveat explícito

---

## BLOCKER-004: El espacio de estrategias evaluadas es demasiado reducido para H3

**Estado**: ACTIVO  
**Severidad**: MEDIUM — H3 no puede considerarse demostrada  
**Descubierto**: 2026-07-30  
**Fuente**: Revisión externa adversarial

### Descripción

H3 ("No existe una estrategia universalmente óptima") solo se evaluó con:
- Un parser MFT básico
- Un carving muy básico (6 firmas)

Faltan muchísimas estrategias reales:
- carving avanzado
- journal-first
- bitmap-guided
- USN-guided
- MFT Mirror recovery
- parser tolerante a corrupción
- carving probabilístico

### Consecuencia

H3 debe escribirse como: "La evidencia preliminar es consistente con H3, pero el espacio de estrategias evaluadas aún es reducido para considerarla demostrada."

### Resolución requerida

- Implementar al menos 3 estrategias adicionales antes de reclamar H3
- Cada estrategia nueva debe tener ficha técnica formal
- Re-evaluar H3 después de cada nueva estrategia

### Criterio de cierre

- [ ] Al menos 5 estrategias genuinamente distintas evaluadas
- [ ] H3 re-evaluada con datos de todas las estrategias
- [ ] Lenguaje de H3 actualizado en el registro

---

## BLOCKER-002: Benchmark autocomplaciente (pendiente)

**Estado**: PENDIENTE (no se puede resolver hasta BLOCKER-001)  
**Severidad**: HIGH  
**Descubierto**: 2026-07-30

### Descripción

Dataset + Corruptor + Motores + Judge todos del mismo laboratorio. Comparten supuestos. Necesita validación externa.

### Resolución requerida

- Imágenes NTFS creadas por Windows real
- Comparación contra herramientas existentes (TestDisk, PhotoRec)
- O validación cruzada con imágenes de hardware real

---
