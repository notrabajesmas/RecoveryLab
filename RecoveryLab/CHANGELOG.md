# RecoveryLab — Changelog

## v0.6.0 (2026-08-06) — Released

**GitHub Release published.** Wheel + sdist + release notes at:
https://github.com/notrabajesmas/RecoveryLab/releases/tag/v0.6.0

**README rewritten** — User-first: brand identity, Quick Start prominent,
evidence rule and roadmaps moved to bottom. Install and demo at the top.

**v0.6.0 status changed**: Open → Released.

---

## v0.6.0 (2026-08-05)

**Sparse files: 0% → 100%**

Before this version, RecoveryLab could not recover sparse NTFS files.
The parser silently discarded sparse data runs (treating them as end-of-list),
resulting in truncated or missing file data.

Now RecoveryLab correctly recovers sparse files with zero-filled gaps.

**Benchmark (CI-verified 2026-08-05):**

| Category | Files | RR | RFS | RC | Time | RAM |
|----------|------:|---:|----:|---:|-----:|----:|
| Normal | 20/20 | 100.0% | 0.815 | 0.500 | 0.53s | 117 MB |
| Fragmented | 20/20 | 100.0% | 0.815 | 0.500 | 0.50s | 159 MB |
| Deleted | 20/20 | 100.0% | 0.815 | 0.500 | 0.48s | 159 MB |
| **Sparse** | **20/20** | **100.0%** | **0.850** | **0.500** | **0.19s** | **159 MB** |

**What changed:**

- `ntfs_parser/parser.py`: Fixed `_parse_data_runs()` — sparse runs (offset_size==0) now parsed correctly. Added `is_sparse` flag to `DataRun` and `MFTEntry`.
- `ntfs_parser/parser.py`: Updated `recover_file_data()` — uses `is_sparse` flag to zero-fill sparse runs.
- `core/stages.py`: `FragmentStage` is now sparse-aware.
- `dataset_builder/ntfs_image.py`: Added `add_sparse_file()` method.
- `datasets/ntfs/sparse/`: New corpus — 20 sparse files, 20/20 CI-verified.
- `scripts/ci_full.py`: Sparse category now included in CI pipeline.
- `scripts/build_sparse_corpus.py`: Fixed manifest key (`filename` → `name` for consistency).
- `docs/`: User documentation added.
- `README.md`: Created (was missing — pip install was broken).
- `pyproject.toml`: Added real dependencies (numpy, matplotlib, Pillow, psutil).
- `docs/Installation.md`: Fixed — no longer claims "standard library only".
- `tests/test_carving_impeccable.py`: Fixed PDF footer assertion (19/19 now pass).

**Philosophy changes (still v0.6.0):**

- **CLI identity banner**: `RecoveryLab v0.6.0 / Filesystem Recovery Engine / RR 100% / Sparse 100%` — shown on scan, recover, info, and demo commands. CI-verified benchmarks in the banner.
- **`recoverylab demo` output improved**: ✓ checkmarks per recovered file, recovery summary box (files recovered / RR / output directory), numbered Next steps section with docs link.
- **Versions are Open or Released**: No partial progress shown publicly. "7/9 Done" is internal only. Users see either Open or Released.
- **UXR defined objectively**: 10 participants, specific tasks, binary result (¿Pudo hacerlo?). No opinions, no surveys, no "I liked it". Target: ≥8/10 for v1.0.0. Recording sheet with 6 columns: installed/demo/recovered/TTFS/fail_step/needed_help.
- **TTFS metric added**: Time To First Success — from opening README to first recovered file. Measures the experience, not the motor.
- **Two roadmaps**: Technical (motor: v0.6.1 → compressed, v0.6.2 → ADS, v0.7 → FAT32, v0.8 → exFAT) and Product (experience: UXR-001 → GitHub Release → Docs → Install → CLI → GUI). Never mixed.
- **Evidence rule**: Before any version — "What new evidence will exist when this version finishes?" "More code" is not valid evidence.
- **v0.6.1 explicitly blocked for release**: v0.6.1 cannot be released until UXR-001 has data. However, development on compressed files is allowed in `develop` — if someone wants to contribute, the branch is open. Only releases are gated, not development.
- **Next objective changed**: UXR-001 experiment (10 external testers) instead of v0.6.1 (compressed files). The motor works. Now prove that people can use it.
- **Release branch strategy**: `release/v0.6.0` only allows bugs/docs/packaging/CI. No new features. Prevents scope creep.
- **UXR-001 recording sheet**: `experiments/UXR-001.md` — blank template ready for the experiment.

**Regression: no regressions** — existing corpus (normal/fragmented/deleted) still at 100%.

---

## v0.5.2 (2026-08-05)

**Recovery Cost (RC) + Stability Policy + 7 Profiles + Full CI**

The third dimension of recovery quality. Every strategy now has three axes:
RR (did we find it?), RFS (how well?), RC (how much did it cost?).

**Recovery Cost (RC):**
```python
result = engine.scan("disk.img")
rc = result.statistics.cost

rc.cpu_time_seconds     # CPU time
rc.peak_ram_mb          # Peak RAM
rc.bytes_scanned        # Bytes read from image
rc.strategy_cost_total  # Sum of strategy cost multipliers
rc.strategies_run       # Which stages actually executed
rc.read_efficiency      # Fraction of useful reads (0.0-1.0)

result.statistics.recovery_cost_score  # Normalized 0-1
```

**Stability Policy (STABILITY_POLICY.md):**

Three tiers with different guarantees:
- Tier 1 (Public API): core.* — FROZEN, breaking = MAJOR bump
- Tier 2 (Extension API): RecoveryStrategy, PipelineStage — STABLE
- Tier 3 (Internal): motors/, ntfs_parser/, strategies/ — may change freely

**Full CI pipeline:**
```
python scripts/ci_full.py
```

---

## v0.5.1 (2026-08-05)

**API frozen + CLI usable + Corpus + CI**

The RecoveryEngine public API is FROZEN. 25 API contract tests enforce this.

**API (frozen):**
```python
from core import RecoveryEngine, __version__

engine = RecoveryEngine()
result = engine.scan("disk.img")

for f in result.files:
    print(f.name, f.size, f.confidence, f.status.value)

result.recover("mft_42", output_dir="recovered/")
result.recover_all(output_dir="recovered/")

result.get_file("mft_42")
result.by_source()
result.by_status()

print(result.statistics.summary)
print(__version__)
```

**CLI:**
```
recoverylab scan disco.img
recoverylab scan disco.img --json
recoverylab recover disco.img salida/
recoverylab recover disco.img salida/ --filter .jpg,.png
recoverylab recover disco.img salida/ --min-confidence 0.8
recoverylab info disco.img
recoverylab --version
```

**Corpus permanente:**
```
datasets/ntfs/
    normal/       — 20 files
    fragmented/   — 20 files
    sparse/       — (placeholder, implemented in v0.6.0)
    deleted/      — 20 files
```

---

## v0.5.0 (2026-08-05)

**Multiple Data Runs — 0% → 100%**

RecoveryLab now recovers files split across multiple non-contiguous data runs (extents).

Refactored Motors → Strategies (A-E):
- Strategy A (MFT), B (Journal), C (Carving), D (Fragment), E (Hybrid)
- Each strategy declares capabilities, cost, priority

---

## Earlier versions (v0.1–v0.4)

Initial development: carving motor, MFT parser, USN journal, RFS metric, strategy engine.

Benchmark numbers for these versions were not recorded by automated CI
and should not be treated as verified. CI-verified metrics begin at v0.5.1.
