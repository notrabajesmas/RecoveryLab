# RecoveryLab — Constitution

> These rules do not change.
> Not between versions. Not between roadmaps. Not between AI sessions.
> If a rule here conflicts with a proposal, the proposal changes.

1. **Each version must move a verifiable benchmark.**
   No version starts without answering: "What benchmark number will move?"
   If you can't answer in one line, the version doesn't start.
   A version with zero motor changes but improved UX is a valid version.

2. **Every public claim must be backed by reproducible evidence.**
   "RR = 100%" means CI produced that number, not that we believe it.
   "Users can install it" means UXR measured it, not that we assume it.

3. **If CI fails, the version does not ship.**
   No exceptions. No "it's just a flaky test." No force-pushes past red.

4. **The motor is independent of the GUI.**
   RecoveryEngine works without any visual interface.
   The CLI works without the GUI. The GUI uses the motor, not the other way.

5. **The public API does not break without a MAJOR version bump.**
   `from core import RecoveryEngine` must work across minor versions.
   RecoveryLab is a library. Other tools will build on this API.
   Breaking it breaks trust that takes years to rebuild.

6. **If multiple users get stuck at the same point, change the product.**
   Not the user. Not the docs. The product.
   If 8 people ask the same question, that question is a feature request.

7. **Documentation is part of the product.**
   A README that a stranger can't follow is a bug, not a writing issue.
   UXR measures documentation quality indirectly.
   If `pip install` fails for a new user, the product is broken.

8. **No optimization without measuring before and after.**
   "It feels faster" is not a benchmark.
   Every performance claim needs a number before and a number after.

9. **No new metrics without using the existing ones first.**
   RecoveryLab has: RR, RFS, RC, UXR, TTFS.
   These are sufficient. Use them to make decisions.
   A new metric is only valid if existing metrics can't answer the question.

10. **The project does not change direction without evidence.**
    Roadmaps respond to data. Not to ideas. Not to AI suggestions. Not to "wouldn't it be cool if."
    If UXR says the onboarding is broken, we fix onboarding.
    If UXR says it works, we open the next version.
    Intuition is for generating hypotheses. Evidence is for making decisions.

---

## Two development cycles

**Engineering demonstrates. Users validate. Neither replaces the other.**

### Cycle A — Engineering (Demonstrate)

Objective: move a benchmark.
Input: technical hypothesis.
Output: reproducible evidence.
Question: **¿Funciona?**

Examples: Sparse 0% → 100%, API contract 25/25, Corpus 80/80, CI green.

### Cycle B — Product (Validate)

Objective: reduce friction for a real user.
Input: user observation.
Output: less friction (measured).
Question: **¿La gente puede usarlo?**

Examples: UXR, TTFS, abandonment points, error messages, demo clarity.

A version can contain zero motor changes and still be excellent.
v0.6.0.1 with TTFS 9min → 2min and UXR 4/10 → 9/10
could deliver more value than a new filesystem parser.
