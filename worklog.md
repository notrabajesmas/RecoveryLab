# RecoveryLab — Work Log

---
Task ID: 1
Agent: Main
Task: BLOCKER-001 resolution — Build Motor Carving, update hypotheses, re-run experiments

Work Log:
- Created BLOCKER-001 in BLOCKERS.md: Motor A is NOT carving, it's MFT-last
- Built MotorCarving (motor_carving.py): genuine signature-based recovery that NEVER reads MFT
  - Supports JPEG, PNG, PDF, ZIP, MP4, DOCX signatures
  - Uses footer detection (FF D9, IEND, %%EOF, PK\x05\x06)
  - Deduplication and ZIP/DOCX resolution
- Created strategy_profiles.py: ficha técnica for each strategy
  - Validates that Carving vs MFT-First is a VALID comparison
  - Validates that MFT-Sequential vs MFT-Only is NOT VALID (same data source)
- Updated file_generator.py: files now include proper footers for carving
- Updated Judge: SHA-256 matching for carved files (generic names don't block matching)
- Updated hypothesis_registry.py: H1.1 refined, H2 added, BLOCKER-001 added
- Created runner_v2.py: 3-strategy experiment runner (Carving, MFT-First, Motor C)
- Regenerated datasets with footers
- Ran full experiment: 5 datasets × 20 attacks = 100 scenarios × 3 strategies

Stage Summary:
- BLOCKER-001: RESOLVED — Motor Carving is a genuine adversarial strategy
- H1.1: INCONCLUSIVE (2S/2R) — MFT-First beats Carving in 90/100 scenarios, but Carving beats MFT-First in A09
- H2: IN_EVALUATION (1S/1R) — Motor C recovers 4/15 in A09 where both others fail, but barely improves in normal cases
- Key discovery: A09 is the ONLY scenario where Carving > MFT-First, and Motor C is the only one that recovers anything
- Carving vs MFT-First: +43.87% Δ recovery (MFT-First wins), 100% support
- MFT-First vs Motor C: +1.40% Δ recovery (Motor C barely improves), 5% support
- Motor C's fallbacks are stubs — Journal/Bitmap/INDX return empty lists
