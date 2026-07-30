"""
RecoveryLab — Recovery Judge Package
======================================
Six independent components, one orchestrator.

  1. Identity Matcher (SHA-256) — Is this the same file?
  2. Functional Validator — Does the file serve its purpose?
  3. Ground Truth Comparator — What's missing?
  4. RVS Calculator — How much VALUE was recovered? (what)
  5. FQS Calculator — How WELL was it recovered? (quality)
  6. Confidence Registry — How much do we trust this result?

Key decomposition:
  Overall Utility = RVS × FQS
  (What you recovered × How well you recovered it)
"""

from .judge import RecoveryJudge
from .metrics import RecoveryMetrics, ComparisonResult, ReadClassification, ConfidenceSweepPoint, ConfidenceSweepResult
from .rvs import RecoveryValueScore, FileCategory, ValueProfile, VALUE_PROFILES
from .fqs import FunctionalQualityScore, FQSResult, compute_overall_utility
from .functional_validator import (
    FunctionalValidator, RecoveryLevel,
    JPEGValidator, MP4Validator, DOCXValidator, SQLiteValidator,
    ZIPValidator, PDFValidator, PNGValidator,
)
from .read_classification import SectorClassifier, ReadTracker
from .confidence_registry import ConfidenceRegistry, ConfidenceLevel, get_confidence_registry

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
    "FunctionalQualityScore",
    "FQSResult",
    "compute_overall_utility",
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
    "ConfidenceRegistry",
    "ConfidenceLevel",
    "get_confidence_registry",
]
