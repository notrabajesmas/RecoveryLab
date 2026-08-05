# RecoveryLab — Stability Policy
==================================

This document defines the stability guarantees for RecoveryLab's API.
It is a CONTRACT — changing it requires updating this document and the CHANGELOG.

---

## Version Rules

### v0.x (Pre-release)
- Breaking changes to **Public API** are allowed, but MUST be documented in CHANGELOG.
- Breaking changes to **Stable Extension API** are allowed with 1 version deprecation notice.
- **Internal** code may change freely at any time.
- Every version MUST pass CI: `python tests/test_api_contract.py` and `python scripts/ci_regression.py`.

### v1.x (Stable release)
- **Public API**: No breaking changes without a new MAJOR version (v2.0).
- **Stable Extension API**: Breaking changes require a MINOR version bump + deprecation notice in CHANGELOG.
- **Internal**: May change freely.
- Semantic versioning: MAJOR.MINOR.PATCH
  - MAJOR: Breaking Public API change
  - MINOR: New feature, backwards-compatible
  - PATCH: Bug fix, no API change

---

## API Tiers

### Tier 1 — Public API (core.*)
**Consumers: CLI, GUI, REST API, scripts, third-party tools**

These types and methods are the ONLY things a consumer should import.

| Type/Method | Stability | Since |
|------------|-----------|-------|
| `core.RecoveryEngine` | FROZEN | v0.5.1 |
| `core.RecoveryEngine.scan()` | FROZEN | v0.5.1 |
| `core.RecoveryEngine.scan_bytes()` | FROZEN | v0.5.1 |
| `core.RecoveryEngine.recover()` | FROZEN | v0.5.1 |
| `core.RecoveryEngine.recover_all()` | FROZEN | v0.5.1 |
| `core.RecoveryEngine.version` | FROZEN | v0.5.1 |
| `core.RecoveryEngine.pipeline_stages` | FROZEN | v0.5.1 |
| `core.ScanResult` | FROZEN | v0.5.1 |
| `core.ScanResult.files` | FROZEN | v0.5.1 |
| `core.ScanResult.statistics` | FROZEN | v0.5.1 |
| `core.ScanResult.errors` | FROZEN | v0.5.1 |
| `core.ScanResult.recover()` | FROZEN | v0.5.1 |
| `core.ScanResult.recover_all()` | FROZEN | v0.5.1 |
| `core.ScanResult.get_file()` | FROZEN | v0.5.1 |
| `core.ScanResult.by_source()` | FROZEN | v0.5.1 |
| `core.ScanResult.by_status()` | FROZEN | v0.5.1 |
| `core.ScanResult.by_extension()` | FROZEN | v0.5.1 |
| `core.RecoveredItem` | FROZEN | v0.5.1 |
| `core.RecoveredItem.id` | FROZEN | v0.5.1 |
| `core.RecoveredItem.name` | FROZEN | v0.5.1 |
| `core.RecoveredItem.size` | FROZEN | v0.5.1 |
| `core.RecoveredItem.status` | FROZEN | v0.5.1 |
| `core.RecoveredItem.source` | FROZEN | v0.5.1 |
| `core.RecoveredItem.confidence` | FROZEN | v0.5.1 |
| `core.RecoveredItem.sha256` | FROZEN | v0.5.1 |
| `core.RecoveredItem.is_fragmented` | FROZEN | v0.5.1 |
| `core.RecoveredItem.fragment_count` | FROZEN | v0.5.1 |
| `core.RecoveryStatistics` | FROZEN | v0.5.1 |
| `core.RecoveryStatistics.recovery_rate` | FROZEN | v0.5.1 |
| `core.RecoveryStatistics.fidelity_score` | FROZEN | v0.5.1 |
| `core.RecoveryStatistics.recovery_cost` | FROZEN | v0.5.2 |
| `core.RecoveryStatistics.scan_time_seconds` | FROZEN | v0.5.1 |
| `core.RecoveryStatistics.peak_ram_mb` | FROZEN | v0.5.1 |
| `core.RecoveryStatistics.summary` | FROZEN | v0.5.1 |
| `core.FileStatus` | FROZEN | v0.5.1 |
| `core.FileSource` | FROZEN | v0.5.1 |
| `core.__version__` | FROZEN | v0.5.1 |

**Rule**: Adding new optional fields to existing types is OK (minor bump).
Removing fields, renaming fields, or changing semantics requires MAJOR bump.

### Tier 2 — Stable Extension API (recovery_judge.strategy_engine.*)
**Consumers: Plugin authors, strategy developers**

| Type/Method | Stability | Since |
|------------|-----------|-------|
| `RecoveryStrategy` | STABLE | v0.4.2 |
| `RecoveryStrategy.name` | STABLE | v0.4.2 |
| `RecoveryStrategy.capabilities` | STABLE | v0.4.2 |
| `RecoveryStrategy.priority` | STABLE | v0.4.2 |
| `RecoveryStrategy.cost` | STABLE | v0.4.2 |
| `StrategyProfile` | STABLE | v0.4.2 |
| `StrategyEngine` | STABLE | v0.4.2 |
| `PipelineStage` (core.pipeline) | STABLE | v0.5.1 |
| `PipelineStage.name` | STABLE | v0.5.1 |
| `PipelineStage.execute()` | STABLE | v0.5.1 |
| `Pipeline.add()` | STABLE | v0.5.1 |
| `Pipeline.insert_before()` | STABLE | v0.5.1 |
| `Pipeline.insert_after()` | STABLE | v0.5.1 |

**Rule**: Plugin authors can subclass `RecoveryStrategy` or `PipelineStage`
without depending on NTFS internals. Breaking these requires deprecation notice.

### Tier 3 — Internal (everything else)
**Consumers: RecoveryLab core developers only**

| Package | Status |
|---------|--------|
| `motors/` | INTERNAL — may change freely |
| `ntfs_parser/` | INTERNAL — may change freely |
| `strategies/` | INTERNAL — may change freely (public contract is via Strategy Engine) |
| `dataset_builder/` | INTERNAL — may change freely |
| `corruptor/` | INTERNAL — may change freely |
| `experiment_runner/` | INTERNAL — may change freely |
| `visualizer/` | INTERNAL — may change freely |

**Rule**: Never import from these packages in consumer code (CLI, GUI, plugins).
If you need something from here, expose it through `core/` instead.

---

## Deprecation Process

When removing or changing a FROZEN/STABLE API:

1. Add `@deprecated(reason="...")` or warning in the NEXT minor version.
2. Document in CHANGELOG under "Deprecated".
3. Keep the old API working for at least 1 minor version.
4. Remove in the next MAJOR version.

Example:
- v0.5.1: `engine.recover()` exists
- v0.6.0: `engine.recover()` deprecated, use `result.recover()` instead
- v1.0.0: `engine.recover()` removed

---

## Enforcement

- **API contract tests** (`tests/test_api_contract.py`) must pass on every commit.
- **CI regression** (`scripts/ci_regression.py`) must pass on every commit.
- If a contract test fails, it means the API was broken → fix or bump MAJOR version.
- The STABILITY_POLICY.md is the source of truth for what is public vs internal.
