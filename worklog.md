# RecoveryLab — Work Log

---
Task ID: 4
Agent: Main
Task: Quality over quantity — RVS enriquecido, recuperación funcional, Judge refactor, parsers impecables

Work Log:
- Implemented RVS enriquecido (rvs.py v2):
  - Formula: composite = intrinsic_value × (1 - replacement_prob × recreation_time × (1 - emotional_impact))
  - 14 FileCategory values: THESIS (score≈1.0) → THUMBNAIL (score≈0.01)
  - Filename pattern overrides: tesis.docx → THESIS, foto_familia_navidad.jpg → PHOTO_FAMILY
  - Size bonus: logarithmic, 0-10% bonus
  - value_comparison_report(): Motor A vs Motor B with "most valuable lost" file
  - Key result: Motor with thesis+DB = RVS 79.8%, Motor with 3 thumbnails = RVS 0.0%
- Implemented Functional Recovery Validator (functional_validator.py):
  - RecoveryLevel enum: FULL (1.0), FUNCTIONAL (0.8), PARTIAL (0.5), DEGRADED (0.2), FAILED (0.0)
  - Format-specific validators: JPEGValidator, MP4Validator, DOCXValidator, SQLiteValidator, ZIPValidator, PDFValidator, PNGValidator
  - Each validator checks format-specific structure (JPEG: SOI+SOS+EOI, MP4: ftyp+moov+mdat, etc.)
  - FunctionalValidator: unified dispatcher
  - Key insight: JPEG with 2 corrupted bytes → FUNCTIONAL (0.85), not FAILED
- Refactored Judge (judge.py v2):
  - Four independent components: Identity Matcher (SHA-256), Functional Validator, Ground Truth Comparator, RVS Calculator
  - New metrics: functional_recovery_rate, full_recovery_rate, weighted_functional_score, level_distribution
  - RecoveryMetrics now includes: Functional Recovery Rate, Full Recovery Rate, Weighted Functional Score
- Audited carving motor: created test_carving_impeccable.py (19 tests, all passing)
  - JPEG: basic detection, EXIF, multiple files, no false positives, functional validation
  - PNG: basic detection, functional validation, no false positives
  - PDF: basic detection, functional validation, no false positives
  - Signature database: consistency, header specificity, mask consistency
  - Carving purity: never reads MFT
  - RVS integration: thesis vs thumbnail value comparison
- Updated hypothesis_registry.py:
  - Added critical review evidence for H3: "95% crossover is NOT a discovery"
  - Added H6: Functional recovery is not binary
  - Added H7: RVS predicts user satisfaction
  - Added H8: 95% crossover is an artifact

Stage Summary:
- The paradigm shift is complete: "recovered" is no longer binary
- RVS enriquecido: thesis = score 1.0, thumbnail = score 0.01
- Functional validation: JPEG with 2 bad pixels = FUNCTIONAL (0.85), not FAILED
- Weighted Functional Score (WFS) = RVS × functionality — the most important single metric
- 19 tests passing for the three core parsers (JPEG, PNG, PDF)
- 4 new hypotheses registered (H6, H7, H8)
- The 1:1 rule is in effect: 500 lines of recovery code → 500 lines of validation

---
Task ID: 3
Agent: Main
Task: Strategic pivot — caveats, matrix, RVS, per-format experiments

Work Log:
- User identified that crossover at 95% is NOT a discovery — it's an artifact of limited carving
- Softened H3: "La evidencia preliminar es consistente con H3, pero el espacio de estrategias evaluadas aún es reducido para considerarla demostrada"
- Added H4: Damage × Strategy Matrix — the lab's real product
- Added H5: Per-format recovery differs — the experiment axis should be per-format, not per-MFT-degradation
- Added BLOCKER-003: Crossover at 95% is artifact of carving ceiling
- Added BLOCKER-004: Strategy space too small for H3
- Created damage_strategy_matrix.py: DamageType × StrategyID → StrategyOutcome matrix
  - 17 damage types, 10 strategies (3 implemented, 7 future)
  - Verdicts: WINNER/VIABLE/POOR/UNTESTED
  - build_expected_matrix() with theoretical predictions
  - Export to JSON, print as markdown table
- Created recovery_judge/rvs.py: Recovery Value Score
  - Not all files have the same value: thesis.docx = 100 points, thumb.db = 1 point
  - FileValueCategory: CRITICAL/HIGH/MEDIUM_HIGH/MEDIUM/LOW/MINIMAL
  - CRITICAL_PATTERNS: filenames that suggest irreplaceable work
  - Size bonus: logarithmic, larger files are worth more
  - Integrated into Judge: every recovery now computes RVS
  - Added rvs and rvs_breakdown fields to RecoveryMetrics
- Expanded Motor Carving from 6 to 17 signatures:
  - Added: TIFF, TIFF_BE, MOV, XLSX, SQLite, GIF, BMP, RAR, 7Z, PSD, AVI
  - Updated _resolve_zip_docx to handle XLSX (xl/ internal path)
  - Updated FILE_FOOTERS in file_generator.py with new formats
- Created per_format_experiment.py: Per-format experiment runner
  - 10 formats: JPEG, PNG, PDF, DOCX, XLSX, MP4, CR2, NEF, SQLite, TXT
  - Corruption levels: 0%→100% in 10% steps (11 points)
  - For each format × corruption level: Carving vs MFT-First
  - Measures: recovery rate, RVS, efficiency, false positives
  - Fills the Damage × Strategy Matrix with real data
- Added build_single_format_dataset() to DatasetBuilder
  - Generates images with predominantly one file format
  - Per-format size ranges (photos larger, docs smaller)

Stage Summary:
- The project's question has transformed: from "can we build better software?" to "can we build the best laboratory to discover when each strategy works best?"
- The crossover at 95% is downgraded from "strong" to "moderate" — it's an artifact
- H3 is downgraded from "moderate" to "weak" — strategy space too small
- The REAL solid conclusion: "metadata-based and signature-based strategies fail differently"
- Two new key artifacts: the Damage × Strategy Matrix and the RVS
- The per-format experiment is the next major experiment to run

---
Task ID: 2
Agent: Main
Task: Strategy Crossover Curve — H2 and H3

Work Log:
- Reframed H2: "Existe una frontera observable donde la estrategia óptima cambia según el estado del medio"
- Created H3: "No existe una estrategia de recuperación universalmente óptima"
- Built crossover_curve.py: progressive MFT degradation (0%→100%) with 3 strategies
  - 21 data points, 5 repetitions per point, statistical analysis (CI, p-value, Cohen's d)
  - Visualization with 4 panels: Recovery Rate, Delta, Significance, Effect Size
- Ran crossover curve experiment
  - Crossover at 95% MFT damage (gradual)
  - Carving is constant at 6.7% (doesn't depend on MFT)
  - MFT-First degrades linearly with MFT damage
  - At 100% MFT damage, Carving wins (6.7% vs 0.0%)
- H3 is now SUPPORTED (1S/0R): MFT-First doesn't win everywhere, Carving doesn't win everywhere
- H2 is INCONCLUSIVE (2S/1R): Frontier exists but crossover is at 95% (too high for practical use)

Stage Summary:
- Key finding: Carving is constant (6.7%) regardless of MFT damage — this is the "floor" of recovery
- MFT-First degrades linearly — it crosses the Carving floor at 95% damage
- The crossover exists but is at a very high damage level
- Problem: Carving only recovers files with detectable signatures (JPEG, PNG, PDF)
- Files without signatures (TXT, EXE, DLL, AVI, CR2, NEF, MOV, JSON) are invisible to Carving
- This means the crossover curve is dominated by the "invisible files" problem
- Next step: Need to separate the crossover by FILE TYPE (JPEG vs PDF vs TXT)
