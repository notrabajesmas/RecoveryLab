"""
RecoveryLab — Recovery Pipeline
================================
The processing pipeline that transforms a raw image into scan results.

Image → Detect → NTFS → MFT → Journal → Fragment → Carving → Merge → Score → Results

Each stage is a PipelineStage that can be replaced, reordered, or extended.
This makes adding FAT32, exFAT, or EXT4 as simple as inserting a new stage.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class PipelineContext:
    """Shared state passed between pipeline stages.
    
    Each stage reads from and writes to this context.
    This decouples stages from each other.
    """
    # Input
    image: bytes = b""
    image_path: str = ""
    cluster_size: int = 4096
    
    # NTFS detection
    filesystem_type: str = ""           # "NTFS", "FAT32", etc.
    is_valid_image: bool = False
    
    # Parsed structures (stage outputs)
    ntfs_metadata: Any = None           # NTFSMetadata from parser
    mft_entries: List[Any] = field(default_factory=list)
    journal_entries: List[Any] = field(default_factory=list)
    
    # Recovery results (stage outputs)
    recovered_from_mft: List[Any] = field(default_factory=list)
    recovered_from_journal: List[Any] = field(default_factory=list)
    recovered_from_fragment: List[Any] = field(default_factory=list)
    recovered_from_carving: List[Any] = field(default_factory=list)
    
    # Merged results
    all_recovered: List[Any] = field(default_factory=list)
    
    # Scoring
    recovery_rate: float = 0.0
    fidelity_score: float = 0.0
    
    # Manifest (for benchmark comparison)
    manifest: Optional[Dict] = None
    
    # Strategy configuration
    strategy_profile: str = "mft_first"
    fragmentation_rate: float = 0.0
    
    # Timing
    stage_times: Dict[str, float] = field(default_factory=dict)
    
    # Errors
    errors: List[str] = field(default_factory=list)


class PipelineStage(ABC):
    """Base class for a pipeline stage.
    
    To add a new filesystem (e.g., EXT4):
    
        class EXT4ParseStage(PipelineStage):
            name = "ext4_parse"
            
            def execute(self, ctx):
                # Parse EXT4 superblock, inode table, etc.
                ctx.ext4_metadata = parse_ext4(ctx.image)
    
    Then insert it into the pipeline:
        pipeline.insert_after("detect", EXT4ParseStage())
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique stage name."""
        ...
    
    @abstractmethod
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        """Run this stage. Read from ctx, write to ctx."""
        ...
    
    @property
    def enabled(self) -> bool:
        """Can this stage be skipped?"""
        return True


class Pipeline:
    """Ordered sequence of pipeline stages.
    
    Usage:
        pipeline = Pipeline.default()
        ctx = pipeline.run(image_bytes, manifest=manifest)
    
    To customize:
        pipeline = Pipeline()
        pipeline.add(DetectStage())
        pipeline.add(NTFSParseStage())
        pipeline.add(MFTStage())
        # ... etc
    """
    
    def __init__(self):
        self._stages: List[PipelineStage] = []
    
    def add(self, stage: PipelineStage):
        """Add a stage to the end of the pipeline."""
        self._stages.append(stage)
    
    def insert_before(self, target_name: str, stage: PipelineStage):
        """Insert a stage before another stage."""
        for i, s in enumerate(self._stages):
            if s.name == target_name:
                self._stages.insert(i, stage)
                return
        self._stages.append(stage)
    
    def insert_after(self, target_name: str, stage: PipelineStage):
        """Insert a stage after another stage."""
        for i, s in enumerate(self._stages):
            if s.name == target_name:
                self._stages.insert(i + 1, stage)
                return
        self._stages.append(stage)
    
    def remove(self, name: str):
        """Remove a stage by name."""
        self._stages = [s for s in self._stages if s.name != name]
    
    def run(self, image: bytes, manifest: Dict = None,
            strategy_profile: str = "mft_first") -> PipelineContext:
        """Execute all stages in order."""
        ctx = PipelineContext(
            image=image,
            manifest=manifest,
            strategy_profile=strategy_profile,
        )
        
        for stage in self._stages:
            if not stage.enabled:
                continue
            t0 = time.time()
            try:
                ctx = stage.execute(ctx)
            except Exception as e:
                ctx.errors.append(f"{stage.name}: {e}")
            ctx.stage_times[stage.name] = time.time() - t0
        
        return ctx
    
    @property
    def stages(self) -> List[str]:
        """List of stage names."""
        return [s.name for s in self._stages]
    
    @classmethod
    def default(cls) -> 'Pipeline':
        """Create the default NTFS recovery pipeline."""
        from .stages import (
            DetectStage, NTFSParseStage, MFTStage, JournalStage,
            FragmentStage, CarvingStage, MergeStage, ScoringStage,
        )
        
        p = cls()
        p.add(DetectStage())
        p.add(NTFSParseStage())
        p.add(MFTStage())
        p.add(JournalStage())
        p.add(FragmentStage())
        p.add(CarvingStage())
        p.add(MergeStage())
        p.add(ScoringStage())
        return p
