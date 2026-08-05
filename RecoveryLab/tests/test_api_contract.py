#!/usr/bin/env python3
"""
RecoveryLab — API Contract Test
=================================
Verifies that the public API (core/) remains stable across versions.

If this test fails, it means someone broke the frozen API.
That requires a MAJOR version bump.

Run:
    python -m pytest tests/test_api_contract.py -v
    # or
    python tests/test_api_contract.py
"""

import sys
import os
import inspect
from dataclasses import fields

# Add project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core import (
    __version__,
    RecoveryEngine,
    ScanResult, RecoveredItem, RecoveryStatistics,
    FileStatus, FileSource,
    Pipeline, PipelineStage,
)


# ── Version ───────────────────────────────────────────────

def test_version_exists():
    """core.__version__ must be a string."""
    assert isinstance(__version__, str)
    parts = __version__.split(".")
    assert len(parts) == 3, f"Version should be semver, got: {__version__}"


def test_engine_version():
    """RecoveryEngine.VERSION must match core.__version__."""
    assert RecoveryEngine.VERSION == __version__


# ── RecoveryEngine API ────────────────────────────────────

def test_engine_init_signature():
    """RecoveryEngine.__init__ must accept these exact parameters."""
    sig = inspect.signature(RecoveryEngine.__init__)
    params = list(sig.parameters.keys())
    # self, profile, cluster_size, enable_carving, enable_journal
    assert "profile" in params
    assert "cluster_size" in params
    assert "enable_carving" in params
    assert "enable_journal" in params


def test_engine_scan_signature():
    """RecoveryEngine.scan must accept (self, image_path, manifest=None)."""
    sig = inspect.signature(RecoveryEngine.scan)
    params = list(sig.parameters.keys())
    assert "image_path" in params
    assert "manifest" in params


def test_engine_scan_returns_scanresult():
    """RecoveryEngine.scan must return ScanResult."""
    # Verify ScanResult has the required dataclass fields
    field_names = {f.name for f in fields(ScanResult)}
    assert 'files' in field_names
    assert 'statistics' in field_names
    assert 'errors' in field_names


def test_engine_recover_signature():
    """RecoveryEngine.recover must accept (self, item, output_dir, filename)."""
    sig = inspect.signature(RecoveryEngine.recover)
    params = list(sig.parameters.keys())
    assert "item" in params
    assert "output_dir" in params


def test_engine_recover_all_exists():
    """RecoveryEngine.recover_all must exist."""
    assert hasattr(RecoveryEngine, 'recover_all')


def test_engine_pipeline_stages():
    """RecoveryEngine.pipeline_stages must be a property."""
    assert isinstance(inspect.getattr_static(RecoveryEngine, 'pipeline_stages'), property)


def test_engine_version_property():
    """RecoveryEngine.version must be a property."""
    assert isinstance(inspect.getattr_static(RecoveryEngine, 'version'), property)


# ── ScanResult API (v0.5.1 additions) ────────────────────

def test_scanresult_has_recover():
    """ScanResult.recover(file_id, output_dir) must exist."""
    assert hasattr(ScanResult, 'recover')
    sig = inspect.signature(ScanResult.recover)
    params = list(sig.parameters.keys())
    assert "file_id" in params
    assert "output_dir" in params


def test_scanresult_has_recover_all():
    """ScanResult.recover_all(output_dir) must exist."""
    assert hasattr(ScanResult, 'recover_all')
    sig = inspect.signature(ScanResult.recover_all)
    params = list(sig.parameters.keys())
    assert "output_dir" in params


def test_scanresult_has_get_file():
    """ScanResult.get_file(file_id) must exist."""
    assert hasattr(ScanResult, 'get_file')
    sig = inspect.signature(ScanResult.get_file)
    params = list(sig.parameters.keys())
    assert "file_id" in params


def test_scanresult_has_by_source():
    """ScanResult.by_source() must exist."""
    assert hasattr(ScanResult, 'by_source')


def test_scanresult_has_by_status():
    """ScanResult.by_status() must exist."""
    assert hasattr(ScanResult, 'by_status')


# ── RecoveredItem fields ─────────────────────────────────

def test_recovereditem_fields():
    """RecoveredItem must have these exact public fields."""
    field_names = {f.name for f in fields(RecoveredItem) if not f.name.startswith('_')}
    required = {'id', 'name', 'size', 'status', 'source', 'confidence',
                'sha256', 'path', 'is_fragmented', 'fragment_count'}
    assert required.issubset(field_names), f"Missing fields: {required - field_names}"


def test_recovereditem_properties():
    """RecoveredItem must have is_recovered and extension properties."""
    assert hasattr(RecoveredItem, 'is_recovered')
    assert hasattr(RecoveredItem, 'extension')


# ── RecoveryStatistics fields ─────────────────────────────

def test_statistics_fields():
    """RecoveryStatistics must have timing, count, and metric fields."""
    field_names = {f.name for f in fields(RecoveryStatistics)}
    required = {
        'scan_time_seconds', 'time_to_first_file',
        'total_files_found', 'total_files_recovered',
        'recovery_rate', 'fidelity_score', 'quality',
        'peak_ram_mb',
    }
    assert required.issubset(field_names), f"Missing fields: {required - field_names}"


def test_statistics_summary():
    """RecoveryStatistics.summary must be a property returning a string."""
    stats = RecoveryStatistics()
    summary = stats.summary
    assert isinstance(summary, str)
    assert "RR=" in summary
    assert "RFS=" in summary


# ── Enums ─────────────────────────────────────────────────

def test_filestatus_values():
    """FileStatus must have at least these values."""
    required = {'recovered', 'partial', 'damaged', 'metadata_only', 'not_recovered'}
    actual = {e.value for e in FileStatus}
    assert required == actual


def test_filesource_values():
    """FileSource must have at least these values."""
    required = {'mft', 'journal', 'carving', 'fragment', 'hybrid'}
    actual = {e.value for e in FileSource}
    assert required.issubset(actual)


# ── Pipeline API ──────────────────────────────────────────

def test_pipeline_default():
    """Pipeline.default() must create a pipeline with 8 stages."""
    pipeline = Pipeline.default()
    stages = pipeline.stages
    assert len(stages) == 8
    assert stages[0] == "detect"
    assert stages[-1] == "scoring"


def test_pipeline_extensible():
    """Pipeline must support add, insert_before, insert_after, remove."""
    assert hasattr(Pipeline, 'add')
    assert hasattr(Pipeline, 'insert_before')
    assert hasattr(Pipeline, 'insert_after')
    assert hasattr(Pipeline, 'remove')


# ── Run ───────────────────────────────────────────────────

if __name__ == "__main__":
    # Simple test runner
    test_funcs = [v for k, v in sorted(globals().items())
                  if k.startswith('test_') and callable(v)]
    
    passed = 0
    failed = 0
    
    for func in test_funcs:
        try:
            func()
            print(f"  PASS  {func.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {func.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {func.__name__}: {e}")
            failed += 1
    
    print()
    print(f"API Contract: {passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
