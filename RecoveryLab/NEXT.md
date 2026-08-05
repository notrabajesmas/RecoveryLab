# RecoveryLab — Next Steps

> Read this file at the start of every session.
> It tells you exactly what to do and what's blocked.

## Current version: v0.6.0 — Status: Released

## Immediate (do now)

1. **Run UXR-001 experiment** — THIS IS THE #1 PRIORITY
   - Find 10 people who never saw RecoveryLab.
   - Give them exactly these instructions (no help):
     ```
     pip install recoverylab
     recoverylab demo
     recoverylab scan example.img
     recoverylab recover example.img salida/
     ```
   - Record results in `experiments/UXR-001.md`.
   - Record: TTFS, UXR, where they got stuck, what error appeared, what command they didn't understand.
   - Evidence: UXR score, TTFS distribution, failure points, bugs found.

2. **Fix everything that appears from UXR-001**
   - If 7 people ask the same question → don't answer the question, change the product.
   - This is where RecoveryLab stops being code and becomes a tool.

## Completed this session

- **GitHub Release v0.6.0** — Published 2026-08-06
  - Tag: v0.6.0
  - Wheel: recoverylab-0.6.0-py3-none-any.whl (173K)
  - Source: recoverylab-0.6.0.tar.gz (156K)
  - Release notes with CI-verified metrics and Quick Start
  - URL: https://github.com/notrabajesmas/RecoveryLab/releases/tag/v0.6.0
  - Evidence: Release page exists with attached artifacts.

- **README rewritten** — User-first, brand identity, Quick Start prominent
- **PROJECT_STATUS.md** — v0.6.0 marked as Released

## Blocked (cannot start until unblocked)

1. **v0.6.1 — NTFS compressed files**
   - Blocked by: UXR-001 results not available yet.
   - Development allowed in `develop` branch.
   - Release NOT allowed until UXR-001 has data.
   - Unblock condition: UXR-001 experiment completed with results recorded.

2. **v0.6.2 — Alternate Data Streams**
   - Blocked by: v0.6.1 not released.
   - Evidence: ADS corpus CI-verified.

3. **v0.7.0 — FAT32**
   - Blocked by: v0.6.2 not released.
   - Evidence: FAT32 corpus CI-verified.

## NOT starting (explicitly)

Per maintainer direction:
- FAT32, exFAT, ext4 — not yet
- GUI — not yet
- AI / ML — not yet
- Any new filesystem support — not yet

The motor works. Now prove that a person can use it.

## Product work (parallel, doesn't block technical)

1. **Improve README** based on UXR-001 failure points.
2. **Improve installation flow** if UXR shows install failures.
3. **Improve CLI help text** if UXR shows confusion at scan/recover.
4. **GUI** — long-term, only after CLI UXR ≥ 8/10.

## Decision rules from UXR-001

| UXR result | Action |
|------------|--------|
| ≥ 8/10 | Close UXR-001. Open v0.6.1 release. |
| 5–7/10 | Fix top blockers found. Run UXR-002. |
| < 5/10 | Stop feature work. Redesign onboarding. Run UXR-002. |

## Session start protocol

At the start of every session, read:
1. `README.md` — what is the project and how to use it
2. `PROJECT_STATUS.md` — current state and roadmap
3. `CHANGELOG.md` — what changed in each version
4. `NEXT.md` — this file: exactly what follows and what's blocked

This ensures any AI can resume the project without conversation memory.
