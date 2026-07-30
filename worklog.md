# RecoveryLab — Work Log

---
Task ID: 9
Agent: Main
Task: Incorporar tercera ronda de auditoria externa — Research Protocol v1.4

Work Log:
- Updated Research Protocol from v1.3 to v1.4 incorporating five new recommendations from external review
- New Section 16: Separation of Observation and Explanation (6th sacred rule)
  - Stricter than Evidence Gate: even "observamos..." can hide interpretation
  - Pure observation = numbers only, no adjectives, no "porque"
  - Explanation always in separate paragraph, linked to a hypothesis
  - Example: "Observamos que Motor C elige correctamente" = NO
  - Example: "En 27/30 ejecuciones Motor C selecciono carving" = YES
- New Section 17: Evidence Ledger
  - Per-experiment traceability: ID, date, dataset, seed, motor, commit, results, affected claims, threats
  - No claim can cite evidence that doesn't exist in the ledger
  - Ledger is append-only, stored in /data/evidence_ledger.csv
  - Creates complete traceability chain: claim → experiment → commit → code
- New Section 18: Judge API Freeze
  - RVS v1.0, FQS v1.0, Overall Utility v1.0 FROZEN during Phase A
  - If metrics need to evolve: Judge v1.1 + re-execute all affected experiments
  - Never mix results from different Judge versions
  - RVS calibration with users will likely require Judge v1.1
- New Section 19: Reproducibility Contract
  - run_all.py: git clone + python run_all.py = identical results
  - Same datasets, same CSVs, same figures, same claims, same ledger
  - 7 strict rules for reproducibility
  - Non-reproducible results are not laboratory results — they are informal observations
- New Section 20: Reproducible Claims Ratio (RCR) as primary KPI
  - RCR = Reproducible Claims / Total Claims
  - Current: 0/5 = 0%. Phase A target: >= 60%. Phase B target: >= 80%
  - Replaces ★★★ as PRIMARY KPI (★★★ remains as secondary)
  - Measures what matters: how many claims survive when anyone repeats the experiment
- Phase A strict regimen: only 4 activities for several weeks
  1. 30 baseline runs for empirical threshold
  2. RVS calibration with users
  3. JPEG/PNG/PDF validation against external tools
  4. Convert all experiments to reproducible
- Cover page updated with RCR as primary KPI, 6 sacred rules
- Subtitle changed from "Congelar la arquitectura, auditar la ciencia" to "El proyecto que necesita madurar, no reinventarse"
- Generated: /home/z/my-project/download/Research_Protocol_v1.4.docx
- Script: /home/z/my-project/scripts/generate_research_protocol_v1.4.py

Stage Summary:
- The reviewer identified a "punto de inflexion real": the project no longer needs reinvention, it needs maturation
- The next bottleneck is reproducibility, not the laboratory itself
- RCR is the new primary KPI: it measures how many claims survive external verification
- Judge API Freeze prevents the measurement system from changing mid-experiment
- Evidence Ledger creates near-perfect traceability: claim → experiment → commit → code
- Separation of Observation and Explanation is the strictest language control rule yet
- The reviewer's key question: "Que evidencia necesito para que otra persona crea lo que encontre?"

---
Task ID: 8
Agent: Main
Task: Implementar Evidence Gate, tres niveles, experimento RVS, y meta-regla

Work Log:
- Created three-level directory structure: /data, /analysis, /claims
- Implemented evidence_gate.py (core module):
  - 5 EvidenceLevel: OBSERVED → HARDWARE_VALIDATED
  - Language enforcement: "demuestra" forbidden at levels 1-3
  - Claim system with evidence entries, threat links, gate status
  - KPI dashboard (research-based, not code-based)
  - Auto-generated CLAIM-001 to CLAIM-005 markdown files
- Created rvs_calibration_experiment.py:
  - 12 survey pairs (tesis vs thumbnails, RAW vs MP4, etc.)
  - 5 target populations x 30+ respondents
  - Bradley-Terry model implementation (fixed MM algorithm)
  - Synthetic simulation verified: ranking tesis(78.5) > thumbnails(8.7) > ISO(5.0)
  - Survey markdown and experiment design JSON generated
- Updated protocol to v1.3:
  - Section 14: Evidence Gate (language control)
  - Section 15: Three-Level Architecture (/data, /analysis, /claims)
  - Section 16: Meta-Rule ("No agregar feature sin aumentar evidencia")
  - Section 17: RVS Calibration Experiment design
  - Meta-rule on cover page in red
  - Research KPI dashboard (not software dashboard)

Stage Summary:
- The project's three stages are now explicit: (1) build recovery engine, (2) build laboratory, (3) build system that guarantees conclusions are trustworthy
- Evidence Gate is the most important structural change: it controls language based on evidence level
- Three-level architecture separates observation from interpretation
- RVS calibration experiment is designed and ready to distribute
- Meta-rule: "No agregar una sola caracteristica nueva si no aumenta la calidad de la evidencia"

---
Task ID: 7
Agent: Main
Task: Incorporar segunda ronda de auditoría externa — Research Protocol v1.2

Work Log:
- Added Section 12: Threats to Validity (4 subsections)
  - 12.1 Internal Validity: 5 threats (2 mitigated, 3 open)
  - 12.2 External Validity: 5 threats (0 mitigated, 5 open)
  - 12.3 Statistical Validity: 5 threats (2 mitigated, 3 open)
  - 12.4 Construct Validity: 4 threats (0 mitigated, 4 open)
  - Total: 4 mitigated, 12 open, 0 resolved
- Added Section 13: Hypothesis Set v1.0 (Frozen)
  - 6 freezing rules: no rewriting, new = H9+, refuted = marked
  - Full frozen hypothesis table (H1.1-H8, H3 eliminated and documented)
  - Future hypothesis space (H9, H10, H11 candidates)
- Added ★★★ KPI as primary progress metric
  - KPI dashboard on cover page: "Resultados con 3+ estrellas: 2/15"
  - KPI table in Section 4.1 with Phase A/B targets
  - Explicit statement: this is the real bottleneck, not Recovery Rate or Overall Utility
- Generated: /home/z/my-project/download/Research_Protocol_v1.2.docx

Stage Summary:
- Protocol now has 13 sections covering all major scientific rigor dimensions
- Threats to Validity makes the lab's weaknesses explicit and trackable
- Frozen hypothesis set prevents retroactive rewriting and preserves scientific history
- The ★★★ count (2/15) is the single most important number in the project
- The project's true bottleneck is evidence accumulation, not feature development

---
Task ID:6
Agent: Main
Task: Incorporar auditoría externa al Research Protocol — v1.1

Work Log:
- Updated Research Protocol from v1.0 to v1.1 incorporating four critical corrections from external review
- Correction 1 (Section 10): Changed "El producto ES Benchmark Suite" to hypothesis language — "Estamos investigando si el verdadero activo competitivo termina siendo el Benchmark Suite"
- Correction 2 (Section 7.2): Expanded external validation beyond PhotoRec to include 4 tool families: Carving (PhotoRec), MFT-first (R-Studio/ReclaiMe), Hybrid (DMDE), Orchestrator (UFS Explorer)
- Correction 3 (Section 3): Replaced arbitrary 5% threshold with empirical calibration framework — 30 baseline runs, threshold = max(2×σ, 1%), provisional threshold of 3% until calibrated
- Correction 4 (Section 5.4): Added RVS calibration plan with real users — Bradley-Terry pairwise comparison, 5 target populations, 30+ responses per population
- Added Section 11: Immediate Operational Objectives (4 objectives from reviewer feedback)
- Generated script: /home/z/my-project/scripts/generate_research_protocol_v1.1.py
- Generated document: /home/z/my-project/download/Research_Protocol_v1.1.docx

Stage Summary:
- Research Protocol v1.1 is now more scientifically rigorous: product identity is hypothesis, not statement
- External validation now covers all strategy families, not just carving
- Success criterion is empirically calibrated, not arbitrarily chosen
- RVS has a path to real-user calibration (currently the weakest point)
- The four immediate objectives are: (1) golden reference JPEG/PNG/PDF, (2) reach ★★★ on main hypotheses, (3) validate against external tools, (4) get first real-world datasets

---
Task ID: 5
Agent: Main
Task: Congelar la arquitectura y auditar la ciencia — Research Protocol v1.0

Work Log:
- Created confidence_registry.py (recovery_judge/confidence_registry.py):
  - Star-based confidence system: 1 star (isolated observation) → 5 stars (validated with real hardware)
  - Stars can only go UP (accumulation of evidence), never down
  - Contradictions mark results as CONTESTED but don't lower stars
  - Current state: 8 results at 1-star, 5 at 2-star, 2 at 3-star, 0 at 4/5-star
  - Honest assessment: most results are preliminary
- Created fqs.py (recovery_judge/fqs.py):
  - Functional Quality Score (FQS): measures HOW WELL files were recovered
  - Size-weighted: 5MB JPEG with 90% quality contributes more than 1KB TXT
  - FQSResult: per-file scores, level distribution, SHA-256 match rate
  - compute_overall_utility(rvs, fqs): Overall Utility = RVS × FQS
  - Diagnostic: "VALUE-DRIVEN", "QUALITY-DRIVEN", "STRONG", "WEAK"
- Created hypothesis_audit.py (RecoveryLab/hypothesis_audit.py):
  - Audits each hypothesis: IV, DV, success criterion
  - Status: TESTABLE (3), NEEDS_REFORMULATION (5), CONTESTED (1), FROZEN (2)
  - Only H1.1, H6, H1.6 are testable in current form
  - H5 and H8 are FROZEN until Phase C
  - H2 is CONTESTED (crossover is artifact)
- Created Research Protocol v1.0 (docx):
  - 10 sections: Pregunta Central, Variables, Criterio de Exito, Registro de Confianza,
    Decomposicion de Metricas, Auditoria de Hipotesis, Fases, Formatos Congelados,
    Regla de Oro, Producto
  - Generated at /home/z/my-project/download/Research_Protocol_v1.0.docx
- Updated __init__.py to export FQS and ConfidenceRegistry

Stage Summary:
- The science audit is complete: 3/11 hypotheses are testable, 5 need reformulation, 1 contested, 2 frozen
- WFS decomposed into RVS × FQS — now we know WHY a motor won
- Confidence registry provides honest, transparent assessment of evidence strength
- Research Protocol v1.0 is the living document that governs the laboratory
- The central question is: "How to objectively measure the utility of a recovery strategy?"
- Phase A: Freeze, consolidate, execute JPEG/PNG/PDF only
- Phase B: Validate against real tools (PhotoRec, TestDisk)
- Phase C: Controlled expansion with same quality bar

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
