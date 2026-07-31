# RecoveryLab — Work Log

---
Task ID: 18
Agent: Main
Task: INST-0002 — Pipeline Loss Localization (r12 auditoría)

Work Log:
- Auditor confirmed INST-0001 validated Dataset Builder, H6 refuted
- Auditor recommended INST-0002 next: instrument the full pipeline to determine exact loss stage per file
- Designed per-file trace system: Scanner → Delimitation → Dedup → Judge
- Implemented inst_0002_pipeline_loss_localization.py with 4 instrumented stages
- Ran INST-0002 across 5 formats × 3 N values (15, 30, 100) = 525 files traced
- KEY FINDINGS:
  - Scanner: 0% loss — finds all signatures correctly
  - Delimitation: 0% loss — all signatures lead to valid carves
  - Dedup: 44.6% loss — 234/525 files eliminated (BMP false positive cascade)
  - Judge: 24.6% loss — 129/525 files have SHA-256 mismatch (PDF truncation)
- ROOT CAUSE CHAIN:
  - Primary: BMP signature 'BM' (2 bytes) creates 50MB false positive → dedup eliminates real files
  - Secondary: PDF footer %%EOF vs %%EOF\n → 1 byte truncation → SHA-256 mismatch
  - RC-A-003 explained: NOT a scale-dependent algorithmic property, but a constant-size bug (BMP false positive) whose impact scales with N
- Updated artifacts:
  - INST-0002.json: DEFINED → COMPLETED with results
  - IVM: Carving Parser ⚠️ PARTIAL → 🔬 DIAGNOSED
  - RC-A-002: reformulated from "JPEG dedup too aggressive" to "BMP false positive causes dedup cascade"
  - RC-A-003: status IDENTIFIED → ROOT_CAUSE_IDENTIFIED
  - Created RP-002: Remove or constrain BMP signature detection
  - Evidence chain manifest: updated with INST-0002 results and new next_actions

Stage Summary:
- INST-0002 COMPLETED — the "OU=0" mystery is now a complete causal chain
- Two targeted fixes (RP-001 + RP-002) would resolve the vast majority of observed losses
- The auditor's vision is validated: "primero se valida el instrumento; después se estudia el fenómeno"

---
Task ID: 14
Agent: Main
Task: Octava ronda de auditoría — Correcciones metodológicas + DIAG-0001

Work Log:
- Applied auditor's 4 methodological corrections:
  1. CLAIM-001 refined: "MFT-First > Carving" → "En los datasets sintéticos evaluados durante EXP-0001 y EXP-0002, MFT-First obtuvo OU superior al Motor Carving"
  2. RCR corrected: 0.4 → 0.0. REPEATED does not count toward RCR; only REPRODUCIBLE counts. Claims are at REPEATED, not REPRODUCIBLE.
  3. Observation vs. Explanation separation: "Carving OU=0.0" is observation; "Carving doesn't leverage corruption" is explanation (7 compatible hypotheses documented)
  4. CLAIM-DETERMINISM elevated as primary Phase A objective: lab reproducibility is more important than any motor comparison
- Created methodological_corrections_r8.py script generating 4 JSON artifacts
- Designed and implemented DIAG-0001: "¿El cero proviene del algoritmo o del banco de pruebas?"
  - 5 datasets: JPEG-only, PNG-only, PDF-only, ZIP-only, DOCX-only
  - Both motors (MFT-First + Carving) run on each
  - Granular per-file diagnostics: signatures found, files carved, match method, failure reasons
- EXECUTED DIAG-0001 with groundbreaking results:
  - **ZIP**: Carving OU = 1.0 (15/15 files, perfect match by SHA-256)
  - **DOCX**: Carving OU = 1.0 (15/15 files, perfect match by SHA-256)
  - **PNG**: Carving OU = 0.8709 (14/15 match, 1 BMP false positive)
  - **PDF**: Carving OU = 0.0 (15 signatures found, 15 carved, ALL 1 byte short)
  - **JPEG**: Carving OU = 0.0 (15 signatures found, only 3 carved, all too short)
- ROOT CAUSES identified:
  - **RC-001 (PDF)**: Footer mismatch. Carving motor uses %%EOF (5 bytes) but file generator produces %%EOF\n (6 bytes). Every carved PDF is exactly 1 byte short. Adding the missing \n restores correct SHA-256.
  - **RC-002 (JPEG)**: Deduplication bug. Motor finds 15 signatures but only carves 3 files (12 removed by overlap detection). The 3 carved files are millions of bytes short.
  - **RC-003 (PNG)**: Minor BMP false positive within PNG data.
- DIAGNOSIS: FORMAT_SPECIFIC_PARSER_ISSUES — the zero comes from the extraction algorithm, not the test bench
  - The scanner works correctly (finds signatures in all formats)
  - The extraction fails for specific formats (PDF footer, JPEG deduplication)
  - ZIP/DOCX carving works perfectly — the motor is not fundamentally broken
  - The problem is not the Dataset Builder, not the Judge, not the RVS/FQS
- Artifacts generated:
  - /home/z/my-project/output/methodological_corrections_r8/ (4 JSON files)
  - /home/z/my-project/RecoveryLab/output/diag_0001/ (5 artifacts: CSV, summary, report, ledger)

Stage Summary:
- DIAG-0001 definitively answers: "¿El cero proviene del algoritmo o del banco de pruebas?" → ALGORITHM (extraction, not detection)
- The carving motor's scanner works perfectly; the extraction has 2 format-specific bugs
- PDF: 1-byte footer bug (%%EOF vs %%EOF\n) — trivial to fix but requires RP-XXX Proposal
- JPEG: deduplication removes 12/15 files — needs investigation
- ZIP/DOCX: carving works perfectly (OU=1.0)
- RCR corrected to 0.0 — protecting its value as a metric
- CLAIM-DETERMINISM is the primary Phase A objective
- No code was modified — this is a diagnostic, not a fix

---
Task ID: 12
Agent: Main
Task: EXP-0001 — Baseline Stability Characterization (first experiment of Phase A)

Work Log:
- Implemented exp_0001_baseline_stability.py following auditor's exact specifications:
  - Named as experiment, not utility (exp_0001, not baseline.py)
  - Success criteria declared BEFORE execution
  - All variables frozen: same dataset, seed, commit, Judge, protocol, motor, config
  - 7 metrics measured: Overall Utility, RVS, FQS, Recovery Rate, Read Count, Runtime, Hash
  - 5 artifacts produced: baseline_runs.csv, baseline_summary.json, baseline_report.md, ledger_entry.json, claim_updates.json
- Ran 30 executions with MFT-First (primary) and 30 with Carving (secondary/floor)
- Key findings:
  - Laboratory is FULLY DETERMINISTIC under identical conditions (SD=0 for all metrics)
  - MFT-First: OU=0.958900, RVS=0.9725, FQS=0.9860, Recovery Rate=93.33% (all 30 runs identical)
  - Carving: OU=0.0000 on healthy image (expected — no MFT access, cannot identify file boundaries)
  - Runtime is the only source of variability (CV=3.9% for MFT-First, 0.74% for Carving)
  - No temporal drift detected
  - Empirical threshold falls back to floor of 1.0% (SD=0 → threshold = max(2*0, 0.01) = 1%)
- Evidence Debt status:
  - ED-008 (variabilidad desconocida): PAGADA — laboratory is deterministic
  - ED-001 (umbral empirico): EN PROGRESO — threshold calibrated at 1.0% floor, but needs corrupted datasets for meaningful variability
- CLAIM updates:
  - CLAIM-001 (MFT-First > Carving): Can advance to REPEATED on healthy image basis
  - CLAIM-005 (Parsers golden reference): Can advance to REPEATED
  - CLAIM-004 (Crossover artifact): No change — requires corruption experiments
- Important observation: The 1% floor threshold is provisional. Future experiments with corruption
  (non-deterministic conditions) will need their own baseline calibration.
- Script: /home/z/my-project/RecoveryLab/exp_0001_baseline_stability.py
- Artifacts: /home/z/my-project/output/exp_0001/

Stage Summary:
- EXP-0001 successfully demonstrates that the laboratory produces deterministic, stable measurements
- ED-008 is resolved: the laboratory's intrinsic variability is zero under identical conditions
- ED-001 is partially addressed: the 1% floor threshold is defined, but meaningful calibration requires corrupted datasets
- The auditor's distinction between ED-008 and ED-001 proved correct: ED-008 asks "what is the variability?" (answer: zero) while ED-001 asks "can we trust the lab?" (answer: needs more experiments — EXP-0002, EXP-0003)
- Next steps: EXP-0002 (reproducibility on another machine), EXP-0003 (second seed), EXP-0004 (external validation)

---
Task ID: 11
Agent: Main
Task: Incorporar quinta ronda (definitiva) de auditoria externa — Research Protocol v1.5 (Frozen for Phase A) + Research Constitution

Work Log:
- Created Research Protocol v1.5 (Frozen for Phase A) incorporating auditor's definitive review
- Section 0 (NEW): Freeze Clause — protocol frozen for Phase A, changes require RP-XXX proposal
  - Justification explicita, evaluacion de impacto sobre experimentos ejecutados, Decision Log update
  - Criterio: "No se cambia porque aparecio una idea mejor. Se cambia porque la evidencia mostro que el protocolo falla."
- Section 23 (NEW): Decision Log — recording WHY, not just WHAT
  - 8 fields: ID, Fecha, Decision, Motivo, Evidencia, Alternativas, Impacto, RP-XXX
  - 5 initial entries (DL-001 through DL-005)
  - Append-only, stored in /data/decision_log.csv
- Section 24 (NEW): Evidence Debt — structured tracking of evidence gaps
  - 8 fields: ID, Deuda, Impacto, Prioridad, Seccion, Estado, Fecha creacion, Fecha pago
  - 8 initial debts: ED-001 (umbral empirico) through ED-008 (variabilidad desconocida)
  - 4 CRITICAS: ED-001, ED-002, ED-004, ED-008
  - CRITICAL debts must be resolved before Phase A graduation
- Section 25 (NEW): Phase A Graduation Criteria — formal exit conditions
  - 7 mandatory criteria: RCR>=80%, 5+ ★★★, Judge stable, 1+ external validation/family, 30 baseline, RVS calibrated, run_all.py reproducible
  - 4 desirable criteria: 8+ threats mitigated, 3+ golden reference parsers, <4 CRITICAL debts, Decision Log complete
  - 6-step graduation procedure
- Section 26 (NEW): Experiment Versioning — versioning all components per experiment
  - Every experiment records version of ALL components (Protocol, Judge, Builder, Corruptor, Motor, etc.)
  - Current version table for all 9 components
  - Evidence Ledger updated to include "Versiones" field
- Section 27 (NEW): Complexity as Scientific Cost
  - Explicit acknowledgment: "El proyecto no morira por errores. Morira por complejidad."
  - 5 principles of complexity control
  - Auditor's role shift: from questioning conclusions to questioning protocol obedience
- Updated Meta-Regla (Section 22): "Cada nuevo documento, modulo o algoritmo debe responder: Reduce una deuda de evidencia identificada?"
- Cover page updated with:
  - FROZEN FOR PHASE A banner
  - Freeze Clause on cover
  - Complexity risk warning
  - Three assets table (Framework, Protocol, Evidence)
  - Updated graduation target (RCR >= 80%)
- Created Research Constitution v1.0 (separate document, 2 pages, 8 principles)
  - Principle I: Evidence over intuition
  - Principle II: No claim before its evidence
  - Principle III: Hypotheses don't change during a phase
  - Principle IV: Every experiment must be reproducible
  - Principle V: Negative results have equal value
  - Principle VI: Reducing evidence debt > adding features
  - Principle VII: Complexity is a scientific cost
  - Principle VIII: Every interpretation must trace to an observation
- Generated: /home/z/my-project/download/Research_Protocol_v1.5_Frozen_Phase_A.docx
- Generated: /home/z/my-project/download/Research_Constitution_v1.0.docx
- Scripts: /home/z/my-project/scripts/generate_research_protocol_v1.5.py, /home/z/my-project/scripts/generate_research_constitution.py

Stage Summary:
- The auditor's definitive review: "Si yo fuera el auditor que va a firmar el inicio de la Fase A, el protocolo v1.5 ya estaria listo"
- Protocol is now FROZEN for Phase A — changes require formal Proposal (RP-XXX)
- Three gaps closed: Decision Log (why), Evidence Debt (what's missing), Graduation Criteria (when done)
- Research Constitution is a separate document defining principles, not procedures
- The project has three distinct assets: Framework (advanced), Protocol (mature), Evidence (in construction)
- The auditor's single condition for Phase A: "No modificar mas el protocolo salvo que aparezca una evidencia que demuestre que el propio protocolo es insuficiente"
- The project transformation is complete: from building a recovery engine → building a laboratory → building an evidence production system

---
Task ID: 10
Agent: Main
Task: Incorporar cuarta ronda de auditoria externa (final) — Research Protocol v1.5

Work Log:
- Updated Research Protocol from v1.4 to v1.5 incorporating three final recommendations from external review
- New Section 23: Decision Log (why decisions were made, not just what happened)
  - Distinct from Evidence Ledger: records WHY, not WHAT
  - 6 initial entries: D-001 (Eliminar H3), D-002 (Congelar Judge), D-003 (JPEG/PNG/PDF referencia), D-004 (RCR como KPI), D-005 (Fase A estricta), D-006 (Separar observacion)
  - Fields: ID, Decision, Motivo, Evidencia, Alternativas consideradas, Fecha
  - Append-only, stored in /data/decision_log.csv
- New Section 24: Evidence Debt (like technical debt, but for evidence gaps)
  - 10 initial debts: ED-001 (hardware real) to ED-010 (Judge versioning)
  - 3 CRITICAL debts: ED-001 (hardware), ED-003 (reproducibilidad), ED-009 (RCR=0%)
  - Every new module must reduce an identified evidence debt
  - CRITICAL debts must be resolved before Phase A graduation
  - Evidence Debt vs Threats to Validity comparison table
- New Section 25: Phase A Graduation Criteria (formal exit criteria)
  - 7 simultaneous conditions: RCR >= 80%, 5+ Claims ★★★, Judge stable, external validation (4 families), baseline complete, RVS calibrated, evidence debt critical = 0
  - Current vs graduation status table showing gaps
  - Graduation is a Decision Log event with evidence for each criterion
- New Section 26: Complexity Risk (explicitly acknowledged)
  - New risk: not bias, not methodology, but complexity
  - "Un proyecto puede morir no porque este equivocado, sino porque se vuelve imposible de mantener"
  - 7th sacred rule: every new module must reduce an evidence debt
- Cover page updated with:
  - 7 sacred rules (new: "Solo reducir deuda de evidencia")
  - Graduation criteria summary on cover
  - Meta-rule extended: "Cada nuevo documento, modulo o algoritmo debe responder: Reduce una deuda de evidencia identificada?"
  - Subtitle: "De la produccion de software a la produccion de evidencia"
- Generated: /home/z/my-project/download/Research_Protocol_v1.5.docx
- Script: /home/z/my-project/scripts/generate_research_protocol_v1.5.py

Stage Summary:
- The reviewer identified this as the final audit round: "Ya no intentaria agregar secciones grandes"
- Three gaps closed: Decision Log (why), Evidence Debt (what's missing), Graduation Criteria (when done)
- The reviewer's final rule: "Cada nuevo documento, modulo o algoritmo debe responder: Reduce una deuda de evidencia identificada?"
- The project transformation is now complete: from building a recovery engine → building a laboratory → building an evidence production system
- Complexity is the new risk: too many mechanisms, not enough evidence
- Phase A has a formal exit criteria for the first time

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

---
Task ID: 13
Agent: Main
Task: Implement EXP-0002 through EXP-0005 and EXP-SD0 — Evidence Acquisition Cycle

Work Log:
- Implemented EXP-0002 — Seed Variation Reproducibility (4 seeds × 30 runs × 2 motors = 240 executions)
- Implemented EXP-0003 — Cross-Machine Reproduction (reproduction package + same-machine verification)
- Implemented EXP-0004 — Dataset Scaling Robustness (10MB, 100MB, 500MB, 1GB)
- Implemented EXP-0005 — External Strategy Validation (healthy + MFT corruption variants)
- Implemented EXP-SD0 — SD=0 Diagnostic Investigation (nanosecond precision + noise conditions)
- Executed EXP-0002: 240 runs completed successfully
  - Key finding: MFT-First > Carving across ALL 4 seeds (CLAIM-001 is ROBUST)
  - New finding: Carving is NOT always OU=0 on healthy images (sometimes 0.0028-0.0080)
  - Deterministic per-seed: TRUE for all 4 seeds
  - Cross-seed OU CV: 2.30% for MFT-First (reflects genuine dataset composition differences)
- Executed EXP-SD0: SD=0 is QUANTIZATION, not true zero-variability
  - OU and all result metrics are deterministic (integer file counts, fixed RVS profiles)
  - Runtime is the only varying metric (SD=3.2ms, reflects OS scheduling)
  - Per-file details are identical across all runs
  - Conclusion: EXPLANATION_2 — OU is quantized and doesn't capture small differences
- Executed EXP-0003: Same-machine verification PASS
  - OU match with EXP-0001: TRUE
  - Hash match: TRUE
  - Reproduction package generated for cross-machine execution
- Executed EXP-0005: Corruption variants tested
  - healthy_10mb: MFT-First OU=0.9589, Carving OU=0.0000
  - mft20_10mb: MFT-First OU=0.5508, Carving OU=0.0000
  - mft60_10mb: MFT-First OU=0.1794, Carving OU=0.0000
  - No crossover detected — Carving motor not recovering files even on corrupted images
  - Test dataset package generated for external tool comparison

Stage Summary:
- 5 experiment scripts created: exp_0002, exp_0003, exp_0004, exp_0005, exp_sd0
- 3 experiments executed: EXP-0002, EXP-0003, EXP-SD0, EXP-0005
- EXP-0004 (dataset scaling) not yet executed (requires longer runtime)
- CLAIM-001 advances to REPEATED (MFT-First > Carving across 4 seeds)
- CLAIM-005 advances to REPEATED (determinism across 4 seeds)
- SD=0 explained: OU quantization (integer file counts), not true zero-variability
- Carving motor weakness identified: doesn't recover files even on corrupted images
- Evidence chain: EXP-0001 → EXP-0002 → EXP-0003 → EXP-0005 (4 experiments)
- RCR (Reproducible Claims Ratio): 2/5 claims at REPEATED level (40%)

---
Task ID: 15
Agent: Main
Task: Novena ronda de auditoría — RC-001/RC-002, RP-001, VAL-0001, RC-003

Work Log:
- Created formal defect records:
  - RC-001: PDF footer inconsistent (missing \n after %%EOF). Implementation bug, 1 byte off, affects 100% of PDFs.
  - RC-002: JPEG deduplication too aggressive. Algorithmic policy, not a simple bug. 5 design options documented.
  - RC-003: Scale-dependent deduplication (NEW — discovered by VAL-0001). Affects ALL formats when N increases.
- Created RP-001: Remediation Proposal for PDF footer. Formal traceable modification: change footer from %%EOF to %%EOF\n.
  - Risk: LOW. Impact: Only PDF parser. Expected OU after fix: ~1.0.
  - Implementation order: Approve RP-001 → Make change → Run VAL-0001 → Update RC-001 → Commit.
- Designed and implemented VAL-0001: "¿Los parsers individuales funcionan correctamente?"
  - Family: VAL (Validation of measurement instruments)
  - No MFT, no corruption, no RVS, no Judge, no hypotheses
  - Only: Known input → Known output
  - 100 files per format (JPEG, PNG, PDF, ZIP, DOCX)
- EXECUTED VAL-0001 with groundbreaking results:
  - JPEG: 1/100 exact match, 53 carved, 50 truncated (RC-002 + RC-003)
  - PNG: 70/100 exact match, 71 carved, 30 missing (RC-003)
  - PDF: 0/100 exact match, 81 carved, 80 truncated by 1 byte (RC-001)
  - ZIP: 17/100 exact match, 18 carved, 83 missing (RC-003 — catastrophic!)
  - DOCX: 40/100 exact match, 41 carved, 60 missing (RC-003)
- KEY DISCOVERY: Scale-dependent deduplication (RC-003)
  - DIAG-0001 (N=15): ZIP 100%, DOCX 100% — "3 parsers work"
  - VAL-0001 (N=100): ZIP 17%, DOCX 40% — deduplication is the primary problem
  - The scanner detects 100 ZIP signatures but only 18 files are carved
  - ZIP/DOCX/XLSX share PK header → 300 signatures for 100 files → deduplication eliminates most
- Updated CLAIM-001: Amended to be extremely specific, with scale-dependence limitations
- Updated gate_index.json: All claims now reflect VAL-0001 findings
- No code was modified during this entire session — pure observation and documentation

Stage Summary:
- RC-001, RC-002, RC-003 formalized as JSON defect records in /RecoveryLab/defects/
- RP-001 formalized as JSON remediation proposal in /RecoveryLab/remediation_proposals/
- VAL-0001 experiment script and results in /RecoveryLab/output/val_0001/
- CLAIM-001 amended with scale-dependence limitations
- RC-003 is the most important new finding: deduplication is the primary problem, not just JPEG
- The "3 parsers work" conclusion from DIAG-0001 is scale-dependent and only valid at N=15

---
Task ID: 15
Agent: Main
Task: Undécima ronda de auditoría — Reestructuración epistemológica del sistema de trazabilidad

Work Log:
- Reformulated RC-003 as RC-A-003: "Colapso de recuperación dependiente de escala"
  - Changed from "Deduplicación escala-dependiente" (assumed cause) to neutral observation + 6 compatible hypotheses
  - H1: deduplicación elimina demasiado (RC-A)
  - H2: extractor genera regiones excesivamente largas (RC-A)
  - H3: límites de archivos son incorrectos (RC-A)
  - H4: archivos compartiendo el mismo rango (RC-A)
  - H5: resolución ZIP/DOCX/XLSX genera múltiples candidatos (RC-A)
  - H6: Dataset Builder produce layouts adversos (RC-I)
  - RC-A-003 classified tentatively as RC-A — may migrate to RC-I if H6 confirmed
  - Old RC-003 preserved as historical reference
- Created RC Classification Taxonomy (RC-I/RC-A/RC-P)
  - RC-I: Instrument — problems with measurement instruments (Dataset Builder, Judge, RVS, FQS)
  - RC-A: Algorithm — problems with recovery algorithms (parsers, deduplication, delimitation)
  - RC-P: Protocol — problems with experimental protocol (hypothesis, claim, threshold)
  - Renumbered: RC-001 → RC-A-001, RC-002 → RC-A-002, RC-003 → RC-A-003
  - Created RC_TAXONOMY.json with migration rules
- Created Instrument Validation Matrix (IVM-001)
  - 6 instruments tracked: Dataset Builder (❓), Carving Parser (⚠️), Judge (❓), RVS (⚠️), FQS (❓), Evidence Gate (✅)
  - Target: all instruments at ✅ VALIDATED before motor claims have full scientific weight
  - Priority order: INST-0001 > INST-0002 > INST-0003 > INST-0004 > INST-0005
- Created INST experiment family (5 experiments)
  - INST-0001: Dataset Builder validation (discriminates H6 of RC-A-003)
  - INST-0002: Carving Parser validation (discriminates H1-H5 of RC-A-003, subsumes VAL-0001)
  - INST-0003: Judge validation (bias, SHA-256 strictness, 1-byte verdict)
  - INST-0004: RVS validation (Bradley-Terry calibration with human judgment)
  - INST-0005: FQS validation (threshold validity, 1-byte classification)
  - Created INST_FAMILY.json with design principles and relationship to other families
- Updated evidence_chain_manifest.json to v2.0
  - Added experiment families (EXP, DIAG, VAL, INST)
  - Added RC classification section
  - Added instrument validation matrix summary
  - Added instrument_dependency to each claim
  - Added ED-009 (instrument validation debt)
  - Updated key insights (9, 10, 11 from r11)
  - Updated next actions to prioritize INST experiments
- Updated RP-001 defect reference from RC-001 to RC-A-001

Stage Summary:
- Paradigm shift: Motor→Resultado became Instrumento→Validación→Experimento→Evidence Ledger→Claim
- VAL-0001 invalidated a previous conclusion of the lab — exactly what a healthy scientific system should do
- RC-A-003 now records observation, not explanation — protects the record
- RC taxonomy allows immediate identification of where each problem lives
- INST family creates a structured path to validate all measurement instruments
- 10 new documents created: RC-A-001.json, RC-A-002.json, RC-A-003.json, RC_TAXONOMY.json, instrument_validation_matrix.json, INST-0001 through INST-0005.json, INST_FAMILY.json
- 2 documents updated: evidence_chain_manifest.json (v2.0), RP-001.json

---
Task ID: 16
Agent: Main
Task: INST-0001 — Dataset Builder Validation

Work Log:
- Implemented INST-0001 experiment script (inst_0001_dataset_builder_validation.py)
  - 7 validation tests: V1 file count, V2 no overlaps, V3 unique offsets, V4 ground truth, V5 signature density, V6 determinism, V7 adversarial score
  - Tested across 5 formats (ZIP, DOCX, PDF, JPG, PNG) × 3 scales (N=15, 30, 100) with 2 seeds
- Executed INST-0001 — ALL VALIDATIONS PASSED:
  - V1: 13/13 pass — generates exactly the expected number of files
  - V2: 13/13 pass — no involuntary cluster overlaps
  - V3: 13/13 pass — all starting offsets unique
  - V4: 13/13 pass — all SHA-256 ground truth matches
  - V6: 3/3 pass — images bit-for-bit identical (manifests differ only in generated_at timestamp)
  - V7: No adversarial indicators detected
- KEY FINDING: High signature conflict rate (78-96%) caused by random file content
  - BMP signature (0x42 0x4D = 'BM') appears in random data because 'B' and 'M' are common ASCII
  - JPEG signatures appear inside other JPEGs (multiple FF D8 FF markers)
  - This is a property of random data, NOT of the Builder's layout
  - Conflict rate is STABLE across scales (not increasing with N)
- H6 DISCRIMINATION: H6 REFUTADA
  - Dataset Builder is NOT adversarial
  - The collapse of recovery is an ALGORITHMIC problem, not an instrument problem
  - RC-A-003 remains classified as RC-A
- Updated RC-A-003 with h6_investigation_result
- Updated Instrument Validation Matrix: Dataset Builder → ✅ VALIDATED
- Fixed determinism test false negative (manifests differ only in generated_at timestamp)

Stage Summary:
- INST-0001 COMPLETED: Dataset Builder is VALIDATED
- H6 of RC-A-003 eliminated — the collapse is not caused by the Builder
- Remaining hypotheses for RC-A-003: H1-H5, all algorithmic
- High signature conflict rate (78-96%) is a property of random data, not adversarial layout
- Next priority: INST-0002 (Carving Parser validation) to discriminate H1-H5

---
Task ID: 19
Agent: Main
Task: R13 auditoría — Separación observación/explicación + Predicciones falsables en RP-001/RP-002

Work Log:
- Auditor r13 señaló distinción crítica: "BMP False Positive (causa primaria)" es explicación causal, no observación
- INST-0002 OBSERVÓ: 44.6% loss at dedup, 24.6% loss at judge. Eso es un hecho.
- La explicación causal (falso positivo BMP → dedup cascade) es una HIPÓTESIS consistente con la evidencia, no un hecho demostrado
- Revisado INST-0002.json: reemplazado root_cause_chain con sections separadas (observations + causal_hypotheses)
- Revisado RC-A-003.json: status cambiado de ROOT_CAUSE_IDENTIFIED a LOSS_STAGES_LOCALIZED
- Revisado RC-A-003.json: inst_0002_results reformulado con observations + causal_hypotheses
- Revisado RC-A-003.json: root_cause_analysis.status cambiado a "PARTIALLY RESOLVED — loss stages localized, causal hypotheses pending falsification"
- Agregado sección "falsifiable_prediction" a RP-001.json:
  - Predicción: Si incluir 0x0A después de %%EOF → losses_at_judge_for_PDF ↓, losses_at_dedup ≈ iguales, scanner ≈ igual, delimitación ≈ igual
  - Criterio de falsación: si no se cumple, H_PDF queda refutada
- Agregado sección "falsifiable_prediction" a RP-002.json:
  - Predicción: Si eliminar firma BMP → losses_at_dedup ↓ significativamente, signatures_detected ↓, losses_at_judge ≈ igual, PDF ≈ igual
  - Criterio de falsación: si no se cumple, H_BMP queda refutada
- Actualizado orden de ejecución (auditor r13):
  1. RP-001 (con predicción) → re-run INST-0002 → verificar predicción
  2. RP-002 (con predicción) → re-run INST-0002 → verificar predicción
  3. Recién entonces INST-0003 (Judge validation)
- Motivo del orden: Judge ve entradas contaminadas por problemas upstream. Validarlo antes de estabilizar upstream sería invertir tiempo en un instrumento cuya aparente falla es consecuencia de datos defectuosos
- Actualizado IVM: Carving Parser status de DIAGNOSED a LOSS_STAGES_LOCALIZED
- Actualizado IVM: priority_order refleja nuevo orden RP-001 → RP-002 → INST-0003
- Actualizado evidence_chain_manifest: key_insights 12-14 reformulados, next_actions actualizados
- Actualizado RC-A-002 status: de ROOT_CAUSE_CONFIRMED a CAUSAL_HYPOTHESIS_PENDING_FALSIFICATION

Stage Summary:
- Principio metodológico establecido: observación ≠ explicación causal. El modelo observable (Scanner ✓, Delimitación ✓, Dedup ✗ 44.6%, Judge ✗ 24.6%) sobrevivirá incluso si las hipótesis causales resultan incorrectas
- Todo RP ahora requiere predicción falsable obligatoria (r13). La predicción hace explícito qué se espera que cambie y qué debe permanecer igual
- RP-001 y RP-002 aprobados con predicción. Próximo paso: aplicar RP-001, re-ejecutar INST-0002, verificar
- El laboratorio ya no busca "qué arreglar" sino "qué predicción hace cada hipótesis y si esa predicción se cumple tras un cambio controlado"

---
Task ID: 20
Agent: Main
Task: R14 auditoría — Prediction Ledger + Open Alternatives + Predicciones cuantificadas

Work Log:
- Auditor r14 propuso tres adiciones metodológicas:
  1. Prediction Ledger — registro propio de predicciones, separado de los RPs
  2. Predicciones cuantificadas — variable observada, dirección, magnitud esperada, confianza
  3. Open Alternatives — hipótesis alternativas que no deben desaparecer por atracción de otra más llamativa
- Creado prediction_ledger.json con 8 predicciones (PRED-001 a PRED-008):
  - RP-001: PRED-001 (Judge PDF ↓, 90-100%, ★★★), PRED-002 (Dedup ≈ igual, ★★★), PRED-003 (Scanner ≈ igual, ★★★), PRED-004 (Delimitation ≈ igual, ★★★)
  - RP-002: PRED-005 (Dedup ↓, 80-100%, ★★), PRED-006 (Signatures ↓, ★★★), PRED-007 (Judge ≈ igual, ★★★), PRED-008 (PDF ≈ igual, ★★★)
- Cada predicción tiene: variable_observed, prediction (decrease/no_change), expected_magnitude, confidence (★), status (PENDING)
- Agregado bloque "open_alternatives" a INST-0002.json con 6 hipótesis:
  - H_BMP, H_PDF (principales, con PRED-001..008)
  - H_DedupOverlap, H_FragmentationLayout, H_JudgeSensitivity, H_ScaleDependentAlgorithm (alternativas)
  - Cada alternativa tiene: statement, compatible_with_observations, discriminating_experiment, prediction_ledger_refs
- Actualizado RP-001: falsifiable_prediction ahora referencia PRED-001..004
- Actualizado RP-002: falsifiable_prediction ahora referencia PRED-005..008
- Actualizado evidence_chain_manifest: agregado sección prediction_ledger con resumen

Stage Summary:
- Prediction Ledger creado como artefacto propio. 8 predicciones, todas PENDING.
- El laboratorio ahora mide capacidad predictiva, no solo capacidad explicativa.
- Open alternatives evitan que hipótesis desaparezcan por atracción. H_DedupOverlap, H_FragmentationLayout, H_JudgeSensitivity, H_ScaleDependentAlgorithm son alternativas vivas con experimentos discriminadores asignados.
- Hoja de ruta confirmada: RP-001 → INST-0002 → evaluar PRED-001..004 → RP-002 → INST-0002 → evaluar PRED-005..008 → INST-0003

---
Task ID: 21
Agent: Main
Task: R15 auditoría — Criterios de éxito/refutación, Freeze, History, PA

Work Log:
- Auditor r15 propuso cuatro adiciones finales antes de congelar la arquitectura:
  1. Success/Refutation/Inconclusive criteria en cada predicción
  2. Freeze de predicciones cuando el RP entra en ejecución
  3. Prediction History (append-only, transiciones, no overwrites)
  4. Predictive Accuracy (PA) como KPI complementario al RCR
- Reescrito prediction_ledger.json con las 8 predicciones actualizadas:
  - Cada predicción tiene: success_criterion, refutation_criterion, inconclusive_zone
  - Cada predicción tiene: frozen (bool), frozen_date, history (array de transiciones)
  - Ejemplo PRED-001: success >=90%, refutation <50%, inconclusive 50-89%
  - Ejemplo PRED-005: success >=80%, refutation <30%, inconclusive 30-79%
- Agregado freeze_policy: "Una vez que el RP asociado entra en ejecución, las predicciones no pueden modificarse"
- Agregado history_policy: "Nunca se sobrescribe una entrada. Solo se agregan transiciones de estado"
- Transiciones válidas: PENDING → CONFIRMED/REFUTED/INCONCLUSIVE → ARCHIVED
- Agregado PA (Predictive Accuracy) al evidence_chain_manifest:
  - PA = confirmed / evaluated
  - KPI complementario: RCR mide supervivencia de claims, PA mide capacidad predictiva
- Agregado kpi_summary con 4 KPIs: RCR, PA, confidence_distribution, evidence_debt_open
- Agregado architecture_freeze al manifest:
  - Status: FROZEN
  - Rule: "Cualquier documento nuevo debe justificar por qué no puede expresarse con los artefactos existentes"
  - Lista de artefactos existentes que cubren todas las necesidades
- Agregado key_insight #15 sobre arquitectura congelada

Stage Summary:
- Arquitectura de Fase A FROZEN. El laboratorio crece solo en evidencia, no en estructura.
- Prediction Ledger tiene 8 predicciones con criterios explícitos, freeze, e historial.
- PA es el tercer KPI del laboratorio (junto a RCR y evidence debt).
- Próximo paso: ejecutar RP-001 (cambio de 1 byte), re-ejecutar INST-0002, evaluar PRED-001..004.

---
Task ID: 22
Agent: Main
Task: R16 auditoría — Cierre formal de la arquitectura de Fase A

Work Log:
- Auditor r16 declaró la arquitectura de Fase A CERRADA
- Checklist de cierre: todos los 11 ítems ✅ (protocolo, hipótesis, Judge API, Evidence Gate, Evidence Ledger, Prediction Ledger, Decision Log, Evidence Debt, RC/RP, INST framework, KPIs)
- Regla de sustitución agregada a GOLDEN_RULE.txt: "Toda nueva estructura debe justificar la eliminación de una estructura existente"
- Architecture freeze status: FROZEN → CLOSED
- Flujo de artefactos permitido: Experimento → Evidence Ledger → Prediction Ledger (update) → Claims. Nada más.
- El auditor explicitó: "El riesgo ya no es la falta de rigor, sino el sobre-diseño"
- El auditor explicitó: "La disciplina más importante a partir de ahora no es inventar mejores procesos, sino resistir la tentación de hacerlo"

Stage Summary:
- ARQUITECTURA DE FASE A CERRADA. No más documentos, métricas, registros o protocolos.
- El laboratorio crece únicamente en evidencia: experimentos, evaluaciones de predicciones, claims.
- Próximo paso: ejecutar RP-001 → INST-0002 → evaluar PRED-001..004.

---
Task ID: 19
Agent: Main
Task: RP-001 — Aplicar fix PDF footer y verificar predicciones falsables (PRED-001 a PRED-004)

Work Log:
- Architecture closure confirmed by user. Phase A architecture frozen. Only execution from now.
- Applied RP-001: Changed PDF footer in motor_carving.py from b'%%EOF' to b'%%EOF\n' (1 line change)
- Froze predictions PRED-001 to PRED-004 in Prediction Ledger (RP-001 entering execution)
- Re-ran INST-0002 post-RP-001 to verify falsifiable predictions
- RESULTS (post-RP-001 vs baseline):
  - PDF N=15: 15/15 SHA-256 matches (was 0/15) → Judge loss for PDF = 0%
  - PDF N=30: 30/30 SHA-256 matches (was 0/30) → Judge loss for PDF = 0%
  - PDF N=100: 80/81 SHA-256 matches (1 mismatch from dedup, not footer) → Judge loss for PDF ≈ 0%
  - loss_at_dedup: 234/525 = 44.6% (identical to baseline)
  - loss_at_scan: 0% (identical to baseline)
  - loss_at_delimitation: 0% (identical to baseline)
  - Total Judge loss: 4/525 = 0.8% (was 129/525 = 24.6%)
- PREDICTION EVALUATION:
  - PRED-001 (losses_at_judge_for_PDF decrease): CONFIRMED — 100% reduction (was 100%, now 0%)
  - PRED-002 (losses_at_dedup no_change): CONFIRMED — 0% change (44.6% → 44.6%)
  - PRED-003 (losses_at_scan no_change): CONFIRMED — 0% (0% → 0%)
  - PRED-004 (losses_at_delimitation no_change): CONFIRMED — 0% (0% → 0%)
- Updated artifacts:
  - RC-001: status IDENTIFIED → FIXED
  - RP-001: status APPROVED_WITH_PREDICTION → VERIFIED
  - CLAIM-001: amended with RP-001 evidence (PDF carving OU now 1.0)
  - Prediction Ledger: 4 predictions CONFIRMED, PA = 4/4 = 100%
  - KPIs: PA = 100% (first measurement)

Stage Summary:
- RP-001 VERIFIED — 4/4 predictions confirmed. H_PDF is strongly supported.
- The PDF footer bug was a genuine implementation defect, not a strategy limitation.
- PA = 100% (first 4 evaluated predictions). The causal model has excellent predictive capacity.
- Next step: RP-002 (remove BMP signature) to test H_BMP.

---
Task ID: 20
Agent: Main
Task: RP-002 — Eliminar firma BMP + verificación PRED-005 a PRED-008

Work Log:
- Applied RP-002: Removed BMP signature from motor_carving.py (Option A — simplest fix)
- Froze predictions PRED-005 to PRED-008 in Prediction Ledger
- Re-ran INST-0002 post-RP-002
- RESULTS (post-RP-002 vs baseline post-RP-001):
  - loss_at_dedup: 0/525 = 0% (was 234/525 = 44.6%) → 100% reduction
  - BMP signatures detected: 0 (was 2-5 per image)
  - ZIP: 145/145 = 100% recovery (was 49/145 = 33.8%)
  - DOCX: 145/145 = 100% recovery (was 85/145 = 58.6%)
  - PDF: 145/145 = 100% recovery (was 125/145 = 86.2%)
  - PNG: 45/45 = 100% recovery (was 28/45 = 62.2%)
  - JPEG: 0/45 = 0% recovery (Judge loss — truncation, not dedup)
  - Total recovery: 480/525 = 91.4% (was 287/525 = 54.7%)
  - loss_at_judge: 45/525 = 8.6% (was 4/525 = 0.8%) — increase due to JPEG truncation files now reaching Judge instead of being eliminated by dedup
- PREDICTION EVALUATION:
  - PRED-005 (losses_at_dedup decrease): CONFIRMED — 100% reduction (44.6% → 0%)
  - PRED-006 (BMP signatures decrease): CONFIRMED — 0 BMP signatures detected
  - PRED-007 (losses_at_judge no_change): INCONCLUSIVE — 0.8% → 8.6% (+7.8%, exceeds >5% threshold). But the Judge itself didn't change — JPEG truncation files now reach Judge instead of being eliminated by dedup. The prediction didn't anticipate the stage cascade effect.
  - PRED-008 (pdf_losses no_change): CONFIRMED — 0% PDF loss, identical to baseline
- H_BMP STRONGLY CONFIRMED: BMP false positive was the sole cause of dedup loss
- H_DedupOverlap REFUTED: Removing BMP eliminated ALL dedup loss, not just some
- H_FragmentationLayout REFUTED: Same as above
- H_ScaleDependentAlgorithm REFUTED: Same as above
- Updated artifacts:
  - RP-002: APPROVED_WITH_PREDICTION → VERIFIED
  - Prediction Ledger: 7/8 confirmed, 1/8 inconclusive, PA = 87.5%
  - KPIs: PA = 87.5% (above 70% target)

Stage Summary:
- RP-002 VERIFIED — H_BMP is the dominant cause of dedup loss. 7/8 predictions confirmed.
- Post-RP-001+RP-002: 91.4% recovery rate (480/525 files). Only JPEG truncation remains.
- The only remaining carving loss is JPEG truncation (FF D9 footer found too early in data), which is a delimitation issue, not a dedup or Judge issue.
- PA = 87.5% — the causal model has excellent predictive capacity.

---
Task ID: 19
Agent: Main
Task: Formalizar decisiones metodológicas post-RP-002 y ejecutar EXP-JPEG-CAUSALITY

Work Log:
- Formalized three methodological decisions from user review:
  1. PRED-007 PERMANECE INCONCLUSIVE — no reinterpretar como CONFIRMADA
     - Rationale: la predicción cuantitativa congelada era losses_at_judge ≈ sin cambio (cambio <=±2%), el resultado fue +7.8% (0.8% → 8.6%)
     - La explicación causal ('más JPEG llegan al Judge') es coherente pero NO modifica el hecho de que la predicción no se cumplió
     - Added no_reinterpretation_ruling to PRED-007 in prediction_ledger.json
  2. PA = 87.5% tiene valor metodológico precisamente porque hubo una predicción inconclusa
     - Added methodological_significance to prediction_ledger summary
     - "Un ledger donde todo sale bien no es un instrumento científico"
  3. H_JPEGExposure registrada como H9 en hypothesis_registry.py
     - Derived from PRED-007 (INCONCLUSIVE)
     - Two evidence entries: INST-0002 observation + code review of _find_footer()
- Reformulated RC-002 from "Deduplicación JPEG demasiado agresiva" to "Delimitación JPEG prematura"
  - The dedup was a symptom of BMP cascade, not the cause of JPEG truncation
  - The Judge is now a diagnostic instrument, not a suspect
  - Pipeline state: Scanner ✓ → Delimitation JPEG (?) → Dedup ✓ → Judge ✓
- Designed and executed EXP-JPEG-CAUSALITY experiment
  - Question: "¿Por qué exactamente los JPEG terminan truncados?"
  - Method: For each JPEG (N=15), count FFD9 occurrences, compare carved_size with first_ffd9+2
  - KEY RESULT: 15/15 files — carved_size = first_ffd9_offset + 2 (EXACT MATCH)
  - The body pseudo-aleatorio contains ~15-50 FFD9 occurrences per file
  - _find_footer() returns the FIRST FFD9, which is NOT the EOI
  - The real EOI is the LAST FFD9 (at gt_size - 2)
  - Q4 REFUTADO: Dataset Builder generates valid JPEGs (SOI + EOI correct)
  - Q5 PENDIENTE: PhotoRec comparison not yet done
- Updated RC-002 status: ROOT_CAUSE_HYPOTHESIZED → ROOT_CAUSE_CONFIRMED
- Updated RC-A-003 status: LOSS_STAGES_LOCALIZED → PARTIALLY_RESOLVED
- Added RP-001/RP-002 results to RC-A-003
- Next step: Design RP-003 with falsifiable prediction (search LAST FFD9 instead of FIRST)

Stage Summary:
- CAUSA CONFIRMADA: _find_footer() busca la primera ocurrencia de FFD9. El body pseudo-aleatorio contiene múltiples FFD9 por coincidencia estadística. 15/15 match exacto.
- PRED-007 permanece INCONCLUSIVE — no se reinterpretará. Esto preserva la integridad metodológica del Prediction Ledger.
- H9 (H_JPEGExposure) registrada con 2 evidencias consistentes.
- RC-002 reformulado como "Delimitación JPEG prematura" — ROOT_CAUSE_CONFIRMED.
- El experimento EXP-JPEG-CAUSALITY respondió 4 de 5 preguntas. Q5 (PhotoRec) pendiente.
- Próximo paso: diseñar RP-003 con predicción falsable.

---
Task ID: 23
Agent: Main
Task: Cambio de fase — de CAUSALITY_INVESTIGATION a REFERENCE_VALIDATION

Work Log:
- Revisión metodológica del usuario: la causalidad inmediata del truncamiento JPEG está confirmada con una regularidad perfecta (15/15: carved_size = first_ffd9_offset + 2). La pregunta abierta ya no es "¿por qué se truncaron?" sino "¿cuál es el comportamiento correcto que debe imitar RecoveryLab?"
- Tres decisiones metodológicas implementadas:
  1. RENOMBRAR el siguiente experimento: de EXP-JPEG-CAUSALITY a VAL-JPEG-REFERENCE. La causalidad ya fue respondida. El nuevo experimento busca el comportamiento de referencia, no la causa del defecto.
  2. REORDENAR los pasos: VAL-JPEG-REFERENCE → RP-003 → Prediction Ledger → Implementación. No porque se dude de la causa observada, sino porque el diseño de la solución todavía puede mejorar. Si PhotoRec recupera perfectamente, RP-003 puede formular una predicción mucho más fuerte: "Si RecoveryLab adopta una estrategia equivalente a la observada en PhotoRec, esperamos recuperar el 100% de los JPEG sintéticos sin afectar ZIP, PDF, PNG y DOCX."
  3. REGISTRAR la pregunta abierta: "¿Buscar el último FFD9 es realmente la estrategia correcta?" PhotoRec podría usar: (a) el último FFD9, (b) parsing de segmentos JPEG, (c) descarte de archivos ambiguos, (d) heurísticas de longitud. Cada una conduciría a un RP distinto.
- Actualizados artefactos:
  - RC-002.json: status ROOT_CAUSE_CONFIRMED → ROOT_CAUSE_CONFIRMED — REFERENCE_VALIDATION_PENDING. Agregada phase_transition. Actualizadas design_options con Option 0 (VAL-JPEG-REFERENCE) como paso prioritario. Actualizada remediation_proposal. Actualizadas notas.
  - VAL-JPEG-REFERENCE.json: creado como experimento de referencia con 6 posibles outcomes y protocolo detallado.
  - prediction_ledger.json: actualizado meta.current_phase a REFERENCE_VALIDATION con hoja de ruta.

Stage Summary:
- Cambio de fase formalizado: el laboratorio ya no está tratando de descubrir qué falla, sino de descubrir cuál es el comportamiento correcto que debe imitar.
- VAL-JPEG-REFERENCE es el siguiente experimento. Pregunta única: "¿Cómo resuelve una herramienta de referencia exactamente el mismo caso?"
- Si PhotoRec recupera perfectamente, RP-003 puede formular una predicción anclada en comportamiento observado, no en suposición.
- La cadena de evidencia es sólida: 15/15 regularidad perfecta + código inspeccionado + Dataset Builder validado.

---
Task ID: 24
Agent: Main
Task: Restricción observacional para VAL-JPEG-REFERENCE

Work Log:
- Revisión metodológica del usuario: el experimento no debe preguntar "¿Qué hace PhotoRec?" sino "¿Qué comportamiento observable produce PhotoRec sobre exactamente el mismo dataset?"
- Tres decisiones implementadas en VAL-JPEG-REFERENCE.json:
  1. RESTRICCIÓN OBSERVACIONAL: el laboratorio solo puede observar salidas (tamaño, SHA-256, offsets, cantidad de archivos), no algoritmos internos. Toda inferencia sobre la estrategia interna de PhotoRec es una hipótesis inferida, no un hecho observado.
  2. ESTRUCTURA DE DOS NIVELES: Nivel 1 (solo hechos observables, sin interpretación) y Nivel 2 (inferencias marcadas como "Compatible con la evidencia", nunca "Demostrado"). Language enforcement explícito: permitido "Compatible con", "Consistente con", "Incompatible con"; prohibido "Demostrado", "Confirmado", "PhotoRec usa X".
  3. PRIMARY OUTCOME BINARIO: "¿RecoveryLab y PhotoRec producen exactamente el mismo archivo?" (Sí/No). Divide el espacio experimental en dos mitades antes de cualquier pregunta más fina.
- Agregado H_PhotoRecStrategy como hipótesis inferida (no observada) en Nivel 2.
- Actualizado family_description: de "descubrir comportamiento correcto" a "registrar qué comportamiento observable produce la herramienta de referencia".
- Actualizado title: de "Validación de referencia" a "Calibración de referencia" — el experimento calibra, no valida.
- Agregado per_file_template para Nivel 1 con campos observables específicos.
- Agregado language_enforcement para Nivel 2.

Stage Summary:
- VAL-JPEG-REFERENCE ahora tiene una restricción observacional explícita que protege contra confundir compatibilidad con demostración.
- La estructura de dos niveles (observación → inferencia) es consistente con la disciplina del laboratorio: no saltar de la observación a la conclusión.
- El Primary Outcome binario es el primer filtro que divide el espacio experimental antes de preguntas más finas.
- El experimento es de calibración, no de validación del código.
