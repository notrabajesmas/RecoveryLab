"""
RecoveryLab — Global Configuration
====================================
Central configuration for the entire RecoveryLab framework.
All paths are relative to the project root.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

# ─── Project Root ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR   = PROJECT_ROOT / "output"

# ─── Output Subdirectories ────────────────────────────────────────────────────
DATASETS_DIR   = OUTPUT_DIR / "datasets"
CORRUPTED_DIR  = OUTPUT_DIR / "corrupted"
GOLD_DIR       = OUTPUT_DIR / "gold"
RESULTS_DIR    = OUTPUT_DIR / "results"
REPORTS_DIR    = OUTPUT_DIR / "reports"

# ─── NTFS Defaults ────────────────────────────────────────────────────────────
NTFS_SECTOR_SIZE    = 512          # bytes per sector
NTFS_CLUSTER_SIZE   = 4096         # bytes per cluster (8 sectors)
NTFS_MFT_RECORD_SIZE = 1024        # bytes per MFT record
NTFS_INDEX_RECORD_SIZE = 4096      # bytes per INDX record
NTFS_VOLUME_SIZE    = 10 * 1024 * 1024  # 10 MB default image size

# ─── MFT System Files ─────────────────────────────────────────────────────────
MFT_SYSTEM_FILES = {
    0:  "$MFT",
    1:  "$MFTMirr",
    2:  "$LogFile",
    3:  "$Volume",
    4:  "$AttrDef",
    5:  ".",           # Root directory
    6:  "$Bitmap",
    7:  "$Boot",
    8:  "$BadClus",
    9:  "$Secure",
    10: "$UpCase",
    11: "$Extend",
}

# Number of system MFT entries (0-11)
MFT_SYSTEM_COUNT = 12

# ─── Dataset Defaults ─────────────────────────────────────────────────────────
DEFAULT_NUM_IMAGES   = 20
DEFAULT_SEED         = 42
DEFAULT_VOLUME_SIZE  = NTFS_VOLUME_SIZE
DEFAULT_CLUSTER_SIZE = NTFS_CLUSTER_SIZE

# ─── File Generation Profiles ─────────────────────────────────────────────────
# Each profile defines a file type distribution for dataset diversity
FILE_PROFILES = {
    "photos": {
        "extensions": [".jpg", ".png", ".cr2", ".nef"],
        "size_range": (50_000, 5_000_000),     # 50KB - 5MB
        "weight": 0.40,                          # 40% of files
    },
    "documents": {
        "extensions": [".pdf", ".docx", ".xlsx", ".txt"],
        "size_range": (1_000, 500_000),          # 1KB - 500KB
        "weight": 0.30,
    },
    "videos": {
        "extensions": [".mp4", ".mov", ".avi"],
        "size_range": (500_000, 8_000_000),      # 500KB - 8MB
        "weight": 0.10,
    },
    "system": {
        "extensions": [".dll", ".sys", ".exe", ".dat"],
        "size_range": (10_000, 2_000_000),       # 10KB - 2MB
        "weight": 0.15,
    },
    "misc": {
        "extensions": [".zip", ".xml", ".json", ".log"],
        "size_range": (500, 200_000),             # 500B - 200KB
        "weight": 0.05,
    },
}

# ─── Corruption Models (Real Failure Patterns) ────────────────────────────────
CORRUPTION_MODELS = {
    "head_crash_start": {
        "description": "First sectors damaged (head crash at start of platter)",
        "zones": "start",
        "severity_range": (0.01, 0.10),  # 1-10% of volume
    },
    "head_crash_end": {
        "description": "Last sectors damaged (end of platter)",
        "zones": "end",
        "severity_range": (0.01, 0.10),
    },
    "scratch_continuous": {
        "description": "Continuous zone of damage (scratch across platter)",
        "zones": "continuous",
        "severity_range": (0.02, 0.15),
    },
    "intermittent_sectors": {
        "description": "Intermittent sectors (failing head — every Nth sector)",
        "zones": "intermittent",
        "severity_range": (0.01, 0.05),
    },
    "mft_partial_delete": {
        "description": "Partial MFT deletion (20%/40%/60% of MFT entries zeroed)",
        "zones": "mft",
        "severity_range": (0.20, 0.60),
    },
    "bitmap_corruption": {
        "description": "Bitmap partially or fully zeroed",
        "zones": "bitmap",
        "severity_range": (0.30, 1.00),
    },
    "journal_corruption": {
        "description": "Journal (USN/$LogFile) corrupted",
        "zones": "journal",
        "severity_range": (0.50, 1.00),
    },
    "crc_errors": {
        "description": "Random bit flips in data sectors (CRC errors)",
        "zones": "random_bits",
        "severity_range": (0.001, 0.01),
    },
    "slow_sectors": {
        "description": "Sectors marked as slow (simulated via metadata, not actual delay)",
        "zones": "slow_meta",
        "severity_range": (0.01, 0.05),
    },
    "timeout_pattern": {
        "description": "Every Nth sector times out (simulated via metadata)",
        "zones": "timeout_meta",
        "severity_range": (0.01, 0.05),
    },
}

# ─── Gold Images ──────────────────────────────────────────────────────────────
GOLD_IMAGE_COUNT = 10
GOLD_SEEDS = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]

# ─── Judge Metrics ─────────────────────────────────────────────────────────────
JUDGE_METRICS = [
    "files_recovered",        # Total files recovered
    "files_correct_checksum", # Files with correct SHA-256
    "files_corrupt",          # Files recovered but with wrong checksum
    "bytes_recovered",        # Total bytes recovered
    "directories_rebuilt",    # Directory structures reconstructed
    "read_count",             # Total sector reads performed
    "sectors_wasted",         # Reads that returned no useful data
    "false_positives",        # Files reported that don't match ground truth
    "duplicates",             # Same file recovered multiple times
    "integrity_score",        # 0.0-1.0 composite score
    "time_to_first_file",     # Reads before first file recovered
    "mft_entries_parsed",     # How many MFT entries were successfully parsed
    "total_time_seconds",     # Wall-clock time
]

# ─── Decision Thresholds (from Fase 3.5) ──────────────────────────────────────
THRESHOLD_BUILD    = 0.10   # >10% improvement → build the motor
THRESHOLD_HYBRID   = 0.03   # 3-10% → hybrid approach
THRESHOLD_INVEST   = 0.01   # 1-3% → investigate more
THRESHOLD_ABANDON  = 0.01   # <1% → abandon or refute
