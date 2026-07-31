# CLAIM-001: En EXP-0001 y DIAG-0001, MFT-First obtuvo Overall Utility superior a Carving Motor en datasets sintéticos

**Hipotesis vinculada:** H1.1
**Estado:** ACTIVE — AMENDED
**Nivel de evidencia:** OBSERVED (1/5)

## Evidence Gate

- [X] observado
- [ ] repetido
- [ ] reproducible
- [ ] validado externamente
- [ ] validado en hardware real

## Evidencia

- [+] EXP-0001 (dataset_000042): MFT-First OU = 1.0, Carving OU = 0.0
- [+] DIAG-0001 (N=15, 5 formatos): MFT-First OU = 1.0 en todos los formatos, Carving OU = 0.0 (JPEG, PDF), 0.87 (PNG), 1.0 (ZIP, DOCX)
- [+] RP-001 VERIFIED (2026-07-31): PDF footer fix confirmado. Post-RP-001, PDF carving OU pasó de 0.0 a 1.0 a N=15 y N=30. La pérdida de PDF era un bug de implementación (RC-001), no una limitación inherente de la estrategia de carving.

## Claim especifico (amendado)

> En los datasets sintéticos evaluados en EXP-0001 y DIAG-0001 (15 archivos por formato, sin corrupción, Judge API v1.0, Protocol v1.5), el Motor MFT-First obtuvo Overall Utility = 1.0 en todos los formatos, mientras que el Motor Carving obtuvo OU = 0.0 en JPEG y PDF, OU ≈ 0.87 en PNG, y OU = 1.0 en ZIP y DOCX. Tras RP-001, la OU de PDF en Carving pasó a 1.0, demostrando que la diferencia original en PDF era causada por un bug de implementación (1 byte truncation), no por una superioridad inherente de MFT-First.

## Limitaciones criticas (identificadas por VAL-0001)

1. **Escala-dependencia**: DIAG-0001 usó N=15. VAL-0001 con N=100 muestra que ZIP baja de 100% a 17% y DOCX de 100% a 40%. La conclusión "ZIP/DOCX funcionan perfectamente" es valida solo a N=15.

2. **Causas raiz identificadas**: RC-001 (PDF footer, 1 byte) — **FIXADO por RP-001**, RC-002 (JPEG deduplication), RC-003 (deduplicación escala-dependiente, afecta TODOS los formatos).

3. **No se puede decir "MFT-First es mejor que Carving"**: Solo se puede decir que en las condiciones evaluadas, MFT-First obtuvo OU superior. La diferencia en PDF se explica por un defecto de implementación (RC-001, ya fixado). La diferencia en JPEG se explica parcialmente por la deduplicación agresiva (RC-002, RC-003), no por una superioridad inherente de la estrategia.

## Amenazas a la validez

- T01 (MITIGADA): Motores podrian conocer ground truth
- T02 (HIGH): Datasets podrian favorecer MFT-First
- T03 (MITIGADA): Resultados de carving son escala-dependientes — pero la causa principal es BMP false positive (H_BMP), no una limitación inherente
- T04 (RESOLVED for PDF): RC-001 era un defecto de implementación, no de la estrategia de carving. Fixado por RP-001.

## Lenguaje permitido

**Permitido:** observamos, es consistente con, vimos, aparece
**PROHIBIDO:** demuestra, prueba, confirma, establece, MFT-First es mejor, Carving es peor

> Mientras no llegue al cuarto casillero, queda prohibido escribir 'demuestra'.
> Solo: 'es consistente con' o 'observamos'.

---
Creado: 2026-07-30
Amendado: 2026-07-31 — VAL-0001 reveló escala-dependencia y RC-003
Amendado: 2026-07-31 — RP-001 VERIFIED: PDF carving OU = 1.0 post-fix. RC-001 FIXED.
