"""
RecoveryLab — Recovery Judge Package
======================================
Four independent components, one orchestrator.

  1. Identity Matcher (SHA-256) — Is this the same file?
  2. Functional Validator — Does the file serve its purpose?
  3. Ground Truth Comparator — What's missing?
  4. RVS Calculator — How much VALUE was recovered?
"""

from .judge import RecoveryJudge
from .metrics import RecoveryMetrics, ComparisonResult, ReadClassification, ConfidenceSweepPoint, ConfidenceSweepResult
from .rvs import RecoveryValueScore, FileCategory, ValueProfile, VALUE_PROFILES
from .functional_validator import (
    FunctionalValidator, RecoveryLevel,
    JPEGValidator, MP4Validator, DOCXValidator, SQLiteValidator,
    ZIPValidator, PDFValidator, PNGValidator,
)
from .read_classification import SectorClassifier, ReadTracker

__all__ = [
    "RecoveryJudge",
    "RecoveryMetrics",
    "ComparisonResult",
    "ReadClassification",
    "ConfidenceSweepPoint",
    "ConfidenceSweepResult",
    "RecoveryValueScore",
    "FileCategory",
    "ValueProfile",
    "VALUE_PROFILES",
    "FunctionalValidator",
    "RecoveryLevel",
    "JPEGValidator",
    "MP4Validator",
    "DOCXValidator",
    "SQLiteValidator",
    "ZIPValidator",
    "PDFValidator",
    "PNGValidator",
    "SectorClassifier",
    "ReadTracker",
]
