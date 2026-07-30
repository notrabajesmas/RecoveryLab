"""
RecoveryLab — Recovery Value Score (RVS)
==========================================
Not all files have the same value.

A motor that recovers tesis.docx and a motor that recovers 10 thumbnails
may have the same "files recovered" count. But from the user's perspective,
they didn't tie. One clearly won.

RVS weights each file by its importance:
  - Documents (thesis, reports, contracts): HIGH value
  - Photos (JPEG, PNG, RAW): MEDIUM-HIGH value
  - Videos (MP4, MOV): MEDIUM value
  - Archives (ZIP, DOCX without content): MEDIUM value
  - System files (DLL, EXE, SYS): LOW value
  - Logs, temp files, thumbnails: MINIMAL value

Usage:
    from recovery_judge.rvs import RecoveryValueScore, FileValueProfile

    rvs = RecoveryValueScore()
    rvs.register_file("tesis.docx", 50000)
    rvs.register_file("thumb001.jpg", 2000)

    score = rvs.compute_score(recovered_files, ground_truth)
    print(f"RVS: {score:.2%}")
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from enum import Enum
from pathlib import Path


class FileValueCategory(Enum):
    """Categories of file value based on user importance."""
    CRITICAL = "critical"      # Thesis, legal documents, financial records
    HIGH = "high"             # Documents, spreadsheets, presentations
    MEDIUM_HIGH = "medium_high"  # Photos, RAW images
    MEDIUM = "medium"         # Videos, archives, databases
    LOW = "low"              # System files, executables
    MINIMAL = "minimal"      # Logs, temp files, thumbnails, cache


# ─── Value mapping ────────────────────────────────────────────────────────────

# Base value per category (0-100 scale)
CATEGORY_VALUES = {
    FileValueCategory.CRITICAL: 100,
    FileValueCategory.HIGH: 80,
    FileValueCategory.MEDIUM_HIGH: 60,
    FileValueCategory.MEDIUM: 40,
    FileValueCategory.LOW: 10,
    FileValueCategory.MINIMAL: 1,
}

# Extension → category mapping
EXTENSION_CATEGORIES = {
    # CRITICAL — documents that represent irreplaceable work
    ".docx": FileValueCategory.HIGH,       # Could be thesis, contract
    ".doc": FileValueCategory.HIGH,
    ".xlsx": FileValueCategory.HIGH,
    ".xls": FileValueCategory.HIGH,
    ".pptx": FileValueCategory.HIGH,
    ".odt": FileValueCategory.HIGH,

    # HIGH — important documents
    ".pdf": FileValueCategory.HIGH,
    ".rtf": FileValueCategory.HIGH,

    # MEDIUM_HIGH — photos and RAW
    ".jpg": FileValueCategory.MEDIUM_HIGH,
    ".jpeg": FileValueCategory.MEDIUM_HIGH,
    ".png": FileValueCategory.MEDIUM_HIGH,
    ".cr2": FileValueCategory.MEDIUM_HIGH,   # Canon RAW
    ".nef": FileValueCategory.MEDIUM_HIGH,   # Nikon RAW
    ".tiff": FileValueCategory.MEDIUM_HIGH,
    ".tif": FileValueCategory.MEDIUM_HIGH,
    ".psd": FileValueCategory.MEDIUM_HIGH,   # Photoshop
    ".dng": FileValueCategory.MEDIUM_HIGH,   # Digital Negative
    ".heic": FileValueCategory.MEDIUM_HIGH,

    # MEDIUM — videos, archives, databases
    ".mp4": FileValueCategory.MEDIUM,
    ".mov": FileValueCategory.MEDIUM,
    ".avi": FileValueCategory.MEDIUM,
    ".mkv": FileValueCategory.MEDIUM,
    ".zip": FileValueCategory.MEDIUM,
    ".rar": FileValueCategory.MEDIUM,
    ".7z": FileValueCategory.MEDIUM,
    ".sqlite": FileValueCategory.MEDIUM,
    ".db": FileValueCategory.MEDIUM,
    ".mdb": FileValueCategory.MEDIUM,

    # LOW — system files
    ".dll": FileValueCategory.LOW,
    ".exe": FileValueCategory.LOW,
    ".sys": FileValueCategory.LOW,
    ".dat": FileValueCategory.LOW,
    ".ini": FileValueCategory.LOW,
    ".cfg": FileValueCategory.LOW,

    # MINIMAL — logs, temp, cache
    ".log": FileValueCategory.MINIMAL,
    ".tmp": FileValueCategory.MINIMAL,
    ".txt": FileValueCategory.MINIMAL,  # Generic text — low value by default
    ".xml": FileValueCategory.MINIMAL,
    ".json": FileValueCategory.MINIMAL,
}


# ─── Filename heuristics for CRITICAL detection ──────────────────────────────

# Filenames that suggest CRITICAL value (regardless of extension)
CRITICAL_PATTERNS = [
    "tesis", "thesis", "dissertation",
    "contrato", "contract", "agreement",
    "balance", "financial", "tax", "impuesto",
    "passport", "pasaporte", "identidad",
    "certificado", "certificate", "diploma",
    "proyecto", "project", "final",
    "backup", "copia", "respaldo",
    "master", "definitivo", "original",
    "curriculum", "resume", "cv",
]


@dataclass
class FileValue:
    """The value of a single file."""
    name: str
    extension: str
    category: FileValueCategory
    base_value: int            # 0-100 based on category
    size_bonus: float = 0.0   # Larger files are worth more (diminishing returns)
    name_bonus: float = 0.0   # Critical filename patterns
    total_value: float = 0.0  # Final weighted value

    def __post_init__(self):
        self.total_value = self.base_value + self.size_bonus + self.name_bonus


class RecoveryValueScore:
    """
    Computes the Recovery Value Score for a recovery attempt.

    The RVS answers: "From the user's perspective, how much value was recovered?"

    This is different from "how many files were recovered" because:
      - A thesis.docx is worth more than 10 thumbnails
      - A RAW photo is worth more than a system DLL
      - A contract is worth more than a log file

    RVS = sum(recovered file values) / sum(ground truth file values)

    This produces a 0.0-1.0 score that reflects the user's actual loss.
    """

    def __init__(self, custom_values: Optional[Dict[str, int]] = None):
        """
        Args:
            custom_values: Optional override for extension values.
                e.g., {".docx": 100} to make all DOCX files critical.
        """
        self.file_values: Dict[str, FileValue] = {}
        self._custom_values = custom_values or {}

    def classify_file(self, name: str, size: int = 0) -> FileValue:
        """
        Classify a file and compute its value.

        Args:
            name: Filename (with extension)
            size: File size in bytes

        Returns:
            FileValue with computed total_value
        """
        ext = Path(name).suffix.lower()
        name_lower = Path(name).stem.lower()

        # Check custom values first
        if ext in self._custom_values:
            base_value = self._custom_values[ext]
            category = FileValueCategory.CRITICAL if base_value >= 100 else \
                       FileValueCategory.HIGH if base_value >= 80 else \
                       FileValueCategory.MEDIUM if base_value >= 40 else \
                       FileValueCategory.LOW if base_value >= 10 else \
                       FileValueCategory.MINIMAL
        else:
            category = EXTENSION_CATEGORIES.get(ext, FileValueCategory.MINIMAL)
            base_value = CATEGORY_VALUES[category]

        # Size bonus: larger files are worth more (logarithmic)
        # A 10MB file is worth more than a 10KB file
        import math
        if size > 0:
            size_bonus = min(20.0, 5.0 * math.log10(max(size, 1)))
        else:
            size_bonus = 0.0

        # Name bonus: check for critical patterns
        name_bonus = 0.0
        for pattern in CRITICAL_PATTERNS:
            if pattern in name_lower:
                name_bonus = 20.0  # Promote to CRITICAL
                category = FileValueCategory.CRITICAL
                break

        fv = FileValue(
            name=name,
            extension=ext,
            category=category,
            base_value=base_value,
            size_bonus=size_bonus,
            name_bonus=name_bonus,
        )

        self.file_values[name] = fv
        return fv

    def compute_score(self, recovered_names: Set[str],
                      ground_truth_names: Set[str],
                      file_sizes: Optional[Dict[str, int]] = None) -> Dict:
        """
        Compute the Recovery Value Score.

        Args:
            recovered_names: Set of filenames that were recovered
            ground_truth_names: Set of filenames in ground truth
            file_sizes: Optional mapping of filename → size

        Returns:
            Dict with:
                rvs: float (0.0-1.0) — the score
                total_ground_truth_value: float
                total_recovered_value: float
                recovered_by_category: dict
                missing_by_category: dict
        """
        file_sizes = file_sizes or {}

        # Classify all ground truth files
        gt_values = {}
        for name in ground_truth_names:
            size = file_sizes.get(name, 0)
            fv = self.classify_file(name, size)
            gt_values[name] = fv.total_value

        # Classify recovered files
        recovered_values = {}
        for name in recovered_names:
            if name in gt_values:
                recovered_values[name] = gt_values[name]

        # Compute totals
        total_gt_value = sum(gt_values.values())
        total_recovered_value = sum(recovered_values.values())

        # RVS
        rvs = total_recovered_value / total_gt_value if total_gt_value > 0 else 0.0

        # Breakdown by category
        recovered_by_category = {}
        missing_by_category = {}
        for name, value in gt_values.items():
            fv = self.file_values[name]
            cat = fv.category.value
            if name in recovered_names:
                recovered_by_category[cat] = recovered_by_category.get(cat, 0.0) + value
            else:
                missing_by_category[cat] = missing_by_category.get(cat, 0.0) + value

        return {
            "rvs": round(rvs, 4),
            "total_ground_truth_value": round(total_gt_value, 1),
            "total_recovered_value": round(total_recovered_value, 1),
            "recovered_by_category": recovered_by_category,
            "missing_by_category": missing_by_category,
        }

    def compute_rvs_simple(self, recovered_names: Set[str],
                           ground_truth_names: Set[str],
                           file_sizes: Optional[Dict[str, int]] = None) -> float:
        """Compute just the RVS score (0.0-1.0)."""
        result = self.compute_score(recovered_names, ground_truth_names, file_sizes)
        return result["rvs"]


if __name__ == "__main__":
    rvs = RecoveryValueScore()

    # Example: two motors with same file count but different value
    ground_truth = {
        "tesis.docx", "photo001.jpg", "photo002.jpg",
        "photo003.jpg", "photo004.jpg", "photo005.jpg",
        "thumb001.jpg", "thumb002.jpg", "thumb003.jpg",
        "log001.txt", "log002.txt",
        "system.dll",
    }

    sizes = {
        "tesis.docx": 500000,
        "photo001.jpg": 3000000,
        "photo002.jpg": 2500000,
        "photo003.jpg": 2800000,
        "photo004.jpg": 2200000,
        "photo005.jpg": 3100000,
        "thumb001.jpg": 5000,
        "thumb002.jpg": 4000,
        "thumb003.jpg": 6000,
        "log001.txt": 1000,
        "log002.txt": 2000,
        "system.dll": 500000,
    }

    # Motor A: recovers 5 files (thesis + 4 photos)
    motor_a = {"tesis.docx", "photo001.jpg", "photo002.jpg",
               "photo003.jpg", "photo004.jpg"}

    # Motor B: recovers 5 files (5 thumbnails + logs)
    motor_b = {"thumb001.jpg", "thumb002.jpg", "thumb003.jpg",
               "log001.txt", "log002.txt"}

    rvs_a = rvs.compute_score(motor_a, ground_truth, sizes)
    rvs_b = rvs.compute_score(motor_b, ground_truth, sizes)

    print(f"Motor A: {len(motor_a)} files, RVS = {rvs_a['rvs']:.2%}")
    print(f"Motor B: {len(motor_b)} files, RVS = {rvs_b['rvs']:.2%}")
    print()
    print(f"Motor A recovered value: {rvs_a['total_recovered_value']:.0f}")
    print(f"Motor B recovered value: {rvs_b['total_recovered_value']:.0f}")
    print()
    print("Motor A clearly won — same file count, but saved the thesis.")
    print("RVS captures this. Simple file count does not.")
