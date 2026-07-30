---
Task ID: 1
Agent: Main Agent
Task: Investigación de viabilidad para software de recuperación de datos - Documento PDF

Work Log:
- Ejecuté 18+ búsquedas web para cubrir los 8 bloques de investigación
- Investigué el mercado: tamaño ($14.7B en 2025, CAGR 8.9%), segmentos, modelos de negocio
- Analicé 8 competidores en profundidad: Disk Drill, EaseUS, Stellar, R-Studio, UFS Explorer, ReclaiMe, TestDisk/PhotoRec, DMDE
- Investigué técnicas de ingeniería: file carving, reconstrucción de filesystems, desafíos SSD/TRIM
- Investigué aplicaciones de IA en recuperación de datos e image inpainting
- Investigué el panorama de patentes y espacio libre para innovar
- Recopilé opiniones de la comunidad profesional desde Reddit y foros especializados
- Analicé oportunidades de innovación, viabilidad financiera y modelo de MVP
- Generé documento PDF profesional de 23 páginas con ReportLab + portada Playwright
- Pasó control de calidad PDF (10/10 checks passed, 3 warnings menores)

Stage Summary:
- PDF generado: /home/z/my-project/download/Investigacion_Recuperacion_Datos.pdf (23 páginas, 147 KB)
- Conclusión: Sí existe una oportunidad real, con condiciones (motor de recuperación potente + UX moderna)
- Inversión estimada: $240K-$510K primer año
- MVP recomendado: diagnóstico inteligente + checkpoints + interfaz honesta
---
Task ID: 2
Agent: Main Agent
Task: Fase 2 - Investigación profunda de viabilidad (intento de refutación)

Work Log:
- Ejecuté 18+ búsquedas web adicionales para la Fase 2
- Investigé workflows de laboratorios profesionales (DriveSavers, Ontrack)
- Analicé decisiones de técnicos: clonar antes de tocar, cuándo detener escaneo, priorización
- Identifiqué 3 categorías de limitaciones: física genuina, hardware bajo falla, nunca automatizada
- Mapeé 5 áreas donde IA puede automatizar sin inventar datos
- Analicé patentes específicas y espacio libre para innovar
- Identifiqué 3 ventajas competitivas difíciles de copiar: motor de recuperación, base de datos de diagnóstico, modelo de decisión adaptativo
- Recopilé patrones de fracaso reales: JPEG con mitad gris, MP4 con moov dañado, SSD con TRIM, MFT parcialmente destruida
- Generé documento PDF de 12 páginas con portada

Stage Summary:
- PDF generado: /home/z/my-project/download/Fase2_Investigacion_Profunda_Recuperacion_Datos.pdf (12 páginas, 121 KB)
- Conclusión: La hipótesis sobrevive al intento de refutación
- Oportunidad más concreta: motor de decisión adaptativo que analiza el disco antes de tocarlo
- Recomendación: proceder con MVP enfocado en diagnóstico inteligente + checkpoints + priorización

---
Task ID: 3.5-benchmark-lab
Agent: Main
Task: Build RecoveryLab — Dataset Builder, Corruptor, and Visualizer

Work Log:
- Created RecoveryLab directory structure (tools/, datasets/ntfs/{healthy,damaged}/, benchmarks/, results/)
- Wrote GOLDEN_RULE.txt with the project's philosophical foundation
- Implemented NTFSImageBuilder in pure Python (no system dependencies)
  - Boot sector with correct BPB fields
  - MFT entries with attributes ($STANDARD_INFORMATION, $FILE_NAME, $DATA)
  - Data runs encoding (NTFS format)
  - Resident and non-resident file support
  - Deterministic: same seed → same image, bit by bit
- Implemented NTFSImageCorruptor with 8 corruption patterns (C01-C10)
  - MFT deletion (20%/40%/60%)
  - MFT partial unreadability
  - Journal corruption
  - Data sector damage
  - Combined patterns
  - Every corruption is recorded in a JSON log
- Implemented Visualizer (both PNG and ASCII)
  - Cluster map showing MFT, data, journal, bitmap, free space
  - Corruption overlay
  - Legend and statistics
- Generated 20 healthy NTFS images (10MB each, 50 files each)
- Verified determinism: same seed produces identical images
- Verified manifest integrity: all files have valid cluster references and SHA-256
- Applied all 8 corruption patterns to dataset_000042

Stage Summary:
- RecoveryLab is operational with 3 tools
- 20 images × 10MB = 200MB of test data
- Each image has a manifest.json (ground truth) with SHA-256 per file
- All corruption is deterministic and recorded
- Visualizer produces both PNG and ASCII layouts
- Next step: implement Motor A (sequential) and Motor B (MFT-first)
