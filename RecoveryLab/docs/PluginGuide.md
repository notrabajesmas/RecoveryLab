# Plugin Guide

RecoveryLab supports extending the recovery pipeline through plugins.

## Architecture

The recovery pipeline has 8 stages:

```
Image → Detect → NTFS → MFT → Journal → Fragment → Carving → Merge → Score
```

Plugins can:
- **Add new stages** (e.g., a new filesystem parser)
- **Insert before/after** existing stages
- **Replace** existing stages

## Creating a plugin

### 1. Create a PipelineStage

```python
from core.pipeline import PipelineStage, PipelineContext

class FAT32ParseStage(PipelineStage):
    @property
    def name(self) -> str:
        return "fat32_parse"
    
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        # Your FAT32 parsing logic here
        # Add results to ctx.recovered_from_mft or a new list
        return ctx
```

### 2. Create a RecoveryStrategy

```python
from recovery_judge.strategy_engine import RecoveryStrategy

fat32_strategy = RecoveryStrategy(
    name="FAT32",
    strategy_id="F",
    capabilities={"filename", "sha256", "timestamps"},
    cost=1.0,
    priority=10,
)
```

### 3. Register with the pipeline

```python
from core.pipeline import Pipeline
from core.engine import RecoveryEngine

engine = RecoveryEngine()
pipeline = engine._pipeline

# Insert FAT32 parsing after NTFS detection
pipeline.insert_after("ntfs_parse", FAT32ParseStage())
```

## Stability tiers

| Tier | Modules | Guarantee |
|------|---------|-----------|
| Public API | `core.*` | FROZEN — breaking = MAJOR bump |
| Extension API | `RecoveryStrategy`, `PipelineStage` | STABLE — breaking = deprecation period |
| Internal | `motors/`, `ntfs_parser/`, `strategies/` | May change freely |

**Plugin authors should only depend on Public API and Extension API.**
Never import from `motors/`, `ntfs_parser/`, or other internal modules.

## Adding new filesystem support

To add a new filesystem (e.g., ext4):

1. Create `class EXT4ParseStage(PipelineStage)` that parses ext4 superblock and inodes
2. Create `class EXT4RecoveryStage(PipelineStage)` that recovers files from inodes
3. Register with the pipeline: `pipeline.insert_after("detect", EXT4ParseStage())`
4. Update `DetectStage` to recognize the filesystem signature

The existing NTFS pipeline remains untouched.

## Adding new carving signatures

The carving motor supports 19 formats. To add more:

1. Add the signature to `motors/motor_carving.py` in the `SIGNATURES` list
2. Define header and footer bytes
3. The carving motor will automatically detect and recover files with the new signature
