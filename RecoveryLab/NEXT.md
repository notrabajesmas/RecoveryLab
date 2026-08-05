# RecoveryLab — Next Steps

> Read this file at the start of every session.
> It tells you exactly what to do and what's blocked.

## Current version: v0.6.0 — Status: Open

## Immediate (do now)

1. **Publish GitHub Release v0.6.0**
Ejecutar: crear tag v0.6.0, publicar release con wheel + sdist + CHANGELOG + README.
Bloqueado por: nada. Se puede hacer ahora.
Evidence: GitHub Release page exists with attached artifacts.

2. **Run UXR-001 experiment**
   - Find 10 people who never saw RecoveryLab.
   - Give them the same instructions (no help).
   - Record results in `experiments/UXR-001.md`.
   - Blocked by: need 10 participants.
   - Evidence: UXR score, TTFS distribution, failure points, bugs found.

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
