# RecoveryLab — Work Log

---
Task ID: 1
Agent: Main
Task: Build RecoveryLab framework from scratch

Work Log:
- Verified system capabilities (no mkntfs/ntfs-3g, no sudo, python-ntfs available)
- Created full project structure with 8 modules
- Implemented NTFS Image Creator (pure Python, no external dependencies)
- Implemented Dataset Builder with enhanced manifest (seed, serial, volume_size, mft/bitmap/logfile info, file fragmentation, integrity hash)
- Implemented Corruptor with 10 real failure models (head crash, scratch, intermittent, MFT partial, bitmap, journal, CRC, slow sectors, timeout)
- Implemented Recovery Judge with 13+ metrics (recovery rate, byte recovery, read efficiency, corruption rate, false positives, duplicates, integrity score, time to first file, budget tracking)
- Implemented Motor A (Sequential) and Motor B (MFT-first) with data trimming fix
- Implemented Experiment Runner with full pipeline (Dataset → Motor A → Judge → Motor B → Judge → Comparison → Report)
- Implemented Disk Layout Visualizer (ASCII + PNG)
- Configured Gold Images (10 fixed images, locked)
- Built 5 test images, ran 75 scenarios (5 datasets × 15 attacks including baseline)
- Fixed data trimming bug (padded cluster data → trimmed to actual file size)
- Fixed aggregation bug in experiment runner

Stage Summary:
- RecoveryLab is fully functional end-to-end
- 75 scenarios tested, 93.3% support H1 (Motor B uses fewer reads)
- Key finding: Motor B uses 50-60% fewer reads with 100% read efficiency
- Key finding: A09 (intermittent sectors) STRONGLY REFUTES H1 — Motor B fails when MFT entries are in corrupted sectors
- Key finding: A06 (head crash start) destroys VBR — both motors fail
- Average Δ reads saved: +9,354 (Motor B is dramatically more efficient)
- Average Δ recovery rate: -2.04% (Motor B slightly worse due to A06/A09 failures)
- Verdict: NUANCED — H1 supported for efficiency, partially refuted for recovery rate

---
Task ID: 2
Agent: Main
Task: Refine H1, implement Confidence Sweep, Motor C, and formalize read classification

Work Log:
- Refined H1 into H1.1 (metadata reduces acquisition cost when reliable) and H1.2 (strategy switches when confidence drops below threshold)
- Formalized "useful reads" into 5 categories: DATA_READ, METADATA_READ, DIAGNOSTIC_READ, REDUNDANT_READ, WASTED_READ
- Implemented ReadClassification with efficiency_v1 (broad) and efficiency_v2 (strict)
- Implemented Motor C (Orchestrator) — diagnoses disk, calculates confidence, selects strategy
- Motor C decision tree: confidence > 85% → MFT-first, > 50% → hybrid, < 50% → carving
- Motor C can RETREAT from a strategy when it stops working
- Implemented Confidence Sweep experiment (progressive MFT degradation 0-100%)
- Generated 21-point sweep curve with visualization

Stage Summary:
- Confidence Sweep reveals: Motor B and Motor A have IDENTICAL recovery rates at every MFT damage level
- Motor B uses 50-60% fewer reads at every damage level
- Motor C correctly transitions: mft_first (0-15%) → hybrid (20-50%) → carving (55%+)
- The confidence threshold is approximately 50% — below this, Motor C switches to carving
- The A09 result is a DIFFERENT failure mode: it's not about MFT damage percentage, but about the PATTERN of damage (intermittent sectors hitting MFT entries)
- Key insight: With MFT partial deletion, Motor B is always at least as good as Motor A. The problem is only with specific damage patterns (intermittent sectors)
- This confirms H1.1 (metadata reduces cost when reliable) and validates the Motor C approach

