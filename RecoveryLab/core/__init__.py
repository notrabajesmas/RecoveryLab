"""
RecoveryLab — Core Package
============================
The public API of the Recovery Engine.

This is what consumers use:
  - CLI
  - GUI
  - API REST
  - Plugins

They should NEVER import from motors/, ntfs_parser/, or strategies/ directly.
Everything flows through RecoveryEngine.

Usage:
    from core import RecoveryEngine

    engine = RecoveryEngine()
    result = engine.scan("disk.img")
    for f in result.files:
        print(f.name, f.size, f.confidence)
    engine.recover(result.files[0], output_dir="recovered/")
"""

from .engine import RecoveryEngine
from .result import ScanResult, RecoveredItem, RecoveryStatistics
from .pipeline import Pipeline, PipelineStage

__all__ = [
    'RecoveryEngine',
    'ScanResult', 'RecoveredItem', 'RecoveryStatistics',
    'Pipeline', 'PipelineStage',
]
