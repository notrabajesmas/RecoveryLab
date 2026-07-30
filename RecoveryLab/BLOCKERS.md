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
