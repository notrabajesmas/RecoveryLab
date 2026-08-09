# RecoveryLab — Next Steps

> Read this file at the start of every session.
> It tells you exactly what to do and what's blocked.

## Current version: v0.6.1 — Status: Released

## Philosophy: FROZEN

The Constitution has 11 rules. The evidence framework is defined.
Two development cycles are documented. Metrics are sufficient.
**Do not add more rules, more metrics, or more architecture.**
The greatest risk now is discussing process instead of executing.

---

## Feature Freeze

Until Validation Cycle 001 closes, NO new features, metrics, documents, or
architecture changes. The only accepted changes are:

- Fix a bug discovered during validation
- Reduce friction observed by testers
- Unblock the validation itself

This prevents "while we're at it, let's also..."

---

## Next session: ONE objective

> **Execute Validation Cycle 001.**

That is all. Not architecture. Not new metrics. Not new motors.

Checklist:
1. Get one tester who never saw RecoveryLab.
2. Put them on a clean machine.
3. Give them the mission: "Recover the files from this NTFS image. I can't answer questions. Everything you need should be in the README."
4. Observe in silence. The moderator can only say: *"Do what you would do if I wasn't here."*
5. Register the data on the observation sheet (see experiments/UXR-001.md).
6. Fix ONLY problems that appear repeatedly.
7. **After tester #3**: if the same problem repeats 3 times, stop the cycle, fix the problem, restart the measurement. Don't record the same error ten times.
8. Repeat until 10 testers.

Expected findings (NOT parser problems):
- "Where do I download the image?"
- "I don't understand what scan does."
- "Where did the recovered files go?"
- "Do I use PowerShell or CMD?"
- "I don't see the wheel."
- "I didn't understand the README."

These are exactly the problems a Validation Cycle should discover.

---

## Pre-condition (do first)

Before external testers: install from a completely clean machine yourself.
Follow ONLY the README. If you need to do something the README doesn't say,
that's a bug in the README. Fix it first.

---

## When to open v0.6.1

Not by date. Not by desire. Not because docs are done.
Open v0.6.1 only when you can say:

> Validation Cycle 001 completed.
> 10 participants. TTFS measured.
> Top blockers corrected. UXR documented.
> No remaining repetitive critical problems.

Then — and only then — return to the motor for compressed files.

---

## Product observations (from validation)

- **Imaging dependency**: To recover from a physical disk, users need FTK Imager
  or similar tool first. RecoveryLab can only work with .img files.
  This is a major friction point. Future: `recoverylab image E: disco.img`
- **Full image too large**: A 500GB disk needs 500GB of free space for a full
  image. Partial imaging (first 2GB) is a practical workaround but not documented.
- **Windows works**: v0.6.1 confirmed working on Windows 10 + Python 3.13

---

## NOT doing (explicitly)

- No new parsers
- No new metrics
- No new strategies
- No new optimizations
- No new constitutional rules
- No FAT32, exFAT, ext4, GUI, AI, ML

The motor works. Now prove that a person can use it.

---

## Completed

- v0.6.0 Released (2026-08-06)
- GitHub Release with wheel + sdist + release notes
- README rewritten (user-first, brand identity)
- CONSTITUTION.md (11 rules, two cycles, uncertainty framing)
- Evidence types defined (Demostrado vs Validado)
- Validation Cycle 001 template ready
- All docs synced to GitHub

---

## Session start protocol

1. `CONSTITUTION.md` — rules that never change
2. `README.md` — what is the project and how to use it
3. `PROJECT_STATUS.md` — current state and roadmap
4. `CHANGELOG.md` — what changed in each version
5. `NEXT.md` — this file: exactly what follows and what's blocked

If any proposal conflicts with CONSTITUTION.md, the proposal changes.
