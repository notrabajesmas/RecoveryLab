"""
RecoveryLab — Recovery Value Score (RVS) v2
==============================================
The most important metric in the project.

NOT just "how many files were recovered."
But "how much VALUE was recovered for the user."

A motor that recovers 200 thumbnails but loses the thesis
has objectively done a worse job than one that recovers
the thesis and 50 photos.

v2 Formula:
    RVS = SUM(value_i × replacement_i × recreation_i × emotional_i)
          / SUM(value_i × replacement_i × recreation_i × emotional_i) for ground truth

Where each factor is 0.0-1.0:
    - Value: Intrinsic value of the file type (0.0-1.0)
    - Replacement: How hard is it to replace? (0.0-1.0)
    - Recreation: How long to recreate? (0.0-1.0)
    - Emotional: Emotional impact of loss? (0.0-1.0)

This transforms the evaluation from "count recovered" to "value recovered."

Example:
    tesis.docx:  Value=1.0 × Replacement=0.05 × Recreation=0.05 × Emotional=0.95
                 = 0.002375 (very low product = very high impact if lost)
    thumbnail:   Value=0.01 × Replacement=0.95 × Recreation=0.95 × Emotional=0.05
                 = 0.000451 (very high product = very low impact if lost)

Note: The product is INVERTED for scoring — a low product means the file is
      IRREPLACEABLE and therefore MORE valuable to recover.
      We use: score = 1.0 - (replacement × recreation × (1 - emotional))
      This gives: thesis = 1.0 - (0.05 × 0.05 × 0.05) = 0.999875
                  thumbnail = 1.0 - (0.95 × 0.95 × 0.95) = 0.143
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from enum import Enum


# ─── File Value Profiles ─────────────────────────────────────────────────────

class FileCategory(Enum):
    """Category of file for value assessment."""
    THESIS = "thesis"               # Academic work, dissertations
    DATABASE = "database"           # SQLite, Access, etc.
    LEGAL = "legal"                 # Contracts, legal documents
    PERSONAL_DOC = "personal_doc"   # Personal documents (diary, notes)
    PHOTO_FAMILY = "photo_family"   # Family photos
    VIDEO_PERSONAL = "video_personal"  # Personal videos
    WORK_DOC = "work_doc"           # Work documents
    PHOTO_RAW = "photo_raw"         # RAW photos (CR2, NEF, DNG)
    PHOTO_PROCESSED = "photo_processed"  # JPEG, PNG photos
    VIDEO_DOWNLOADED = "video_downloaded"  # Downloaded videos
    ARCHIVE = "archive"             # ZIP, RAR, 7Z
    SYSTEM = "system"               # DLL, SYS, EXE
    LOG = "log"                     # Log files
    TEMP = "temp"                   # Temporary files
    THUMBNAIL = "thumbnail"         # Thumbnails, cache


@dataclass
class ValueProfile:
    """
    Complete value profile for a file type.

    Each factor is 0.0-1.0:
      - intrinsic_value: How valuable is this type of file? (1.0 = priceless)
      - replacement_prob: How easy is it to replace? (1.0 = trivially replaceable)
      - recreation_time: How long to recreate? (1.0 = instant, 0.0 = impossible)
      - emotional_impact: How emotionally devastating is the loss? (1.0 = devastating)

    The composite score uses the formula:
      score = intrinsic_value × (1.0 - replacement_prob × recreation_time × (1 - emotional_impact))

    This ensures:
      - High intrinsic value + irreplaceable + high emotional = very high score
      - Low intrinsic value + replaceable + low emotional = very low score
    """
    intrinsic_value: float       # 0.0-1.0
    replacement_prob: float      # 0.0-1.0 (1.0 = easy to replace)
    recreation_time: float       # 0.0-1.0 (1.0 = instant, 0.0 = impossible)
    emotional_impact: float      # 0.0-1.0 (1.0 = devastating loss)

    @property
    def composite_score(self) -> float:
        """
        Compute the composite value score.

        Formula: intrinsic_value × (1.0 - replacement_prob × recreation_time × (1 - emotional_impact))

        This means:
        - A thesis (irreplaceable, high emotional) gets a score near 1.0
        - A thumbnail (easily replaced, no emotional) gets a score near 0.0
        - A system file (low emotional, easily replaced) gets a very low score
        """
        replaceability = self.replacement_prob * self.recreation_time * (1.0 - self.emotional_impact)
        return self.intrinsic_value * (1.0 - replaceability)


# ─── Predefined Value Profiles ───────────────────────────────────────────────

VALUE_PROFILES: Dict[FileCategory, ValueProfile] = {
    # ── Critical (score ≈ 0.95-1.0) ──
    FileCategory.THESIS: ValueProfile(
        intrinsic_value=1.0,
        replacement_prob=0.02,   # Almost impossible to replace
        recreation_time=0.02,    # Months/years of work
        emotional_impact=0.95,   # Devastating
    ),
    FileCategory.DATABASE: ValueProfile(
        intrinsic_value=0.95,
        replacement_prob=0.05,   # Very hard to replace
        recreation_time=0.03,    # Data is unique
        emotional_impact=0.90,   # Business-critical
    ),
    FileCategory.LEGAL: ValueProfile(
        intrinsic_value=0.95,
        replacement_prob=0.10,   # Hard to replace
        recreation_time=0.05,    # Legal process
        emotional_impact=0.85,   # Very high
    ),

    # ── High (score ≈ 0.70-0.90) ──
    FileCategory.PERSONAL_DOC: ValueProfile(
        intrinsic_value=0.85,
        replacement_prob=0.10,   # Hard to replace
        recreation_time=0.10,    # Personal notes
        emotional_impact=0.80,   # High
    ),
    FileCategory.PHOTO_FAMILY: ValueProfile(
        intrinsic_value=0.80,
        replacement_prob=0.05,   # Impossible to replace
        recreation_time=0.01,    # Moments are unique
        emotional_impact=0.90,   # Very high
    ),
    FileCategory.VIDEO_PERSONAL: ValueProfile(
        intrinsic_value=0.75,
        replacement_prob=0.05,   # Impossible to replace
        recreation_time=0.01,    # Moments are unique
        emotional_impact=0.70,   # High
    ),
    FileCategory.WORK_DOC: ValueProfile(
        intrinsic_value=0.80,
        replacement_prob=0.30,   # Sometimes replaceable
        recreation_time=0.20,    # Hours of work
        emotional_impact=0.60,   # Moderate-high
    ),

    # ── Medium (score ≈ 0.40-0.65) ──
    FileCategory.PHOTO_RAW: ValueProfile(
        intrinsic_value=0.70,
        replacement_prob=0.05,   # Impossible to replace
        recreation_time=0.01,    # Unique capture
        emotional_impact=0.50,   # Moderate (professional, not personal)
    ),
    FileCategory.PHOTO_PROCESSED: ValueProfile(
        intrinsic_value=0.50,
        replacement_prob=0.20,   # Can re-process from RAW
        recreation_time=0.15,    # Minutes of work
        emotional_impact=0.40,   # Moderate
    ),
    FileCategory.VIDEO_DOWNLOADED: ValueProfile(
        intrinsic_value=0.20,
        replacement_prob=0.80,   # Can re-download
        recreation_time=0.70,    # Hours to download
        emotional_impact=0.10,   # Low
    ),
    FileCategory.ARCHIVE: ValueProfile(
        intrinsic_value=0.45,
        replacement_prob=0.40,   # Sometimes replaceable
        recreation_time=0.30,    # Hours to re-create
        emotional_impact=0.30,   # Moderate
    ),

    # ── Low (score ≈ 0.01-0.15) ──
    FileCategory.SYSTEM: ValueProfile(
        intrinsic_value=0.10,
        replacement_prob=0.90,   # Can reinstall
        recreation_time=0.80,    # Minutes to reinstall
        emotional_impact=0.05,   # Very low
    ),
    FileCategory.LOG: ValueProfile(
        intrinsic_value=0.05,
        replacement_prob=0.95,   # Logs are generated
        recreation_time=0.90,    # Auto-generated
        emotional_impact=0.02,   # Minimal
    ),
    FileCategory.TEMP: ValueProfile(
        intrinsic_value=0.02,
        replacement_prob=0.98,   # By definition temporary
        recreation_time=0.95,    # Auto-generated
        emotional_impact=0.01,   # None
    ),
    FileCategory.THUMBNAIL: ValueProfile(
        intrinsic_value=0.01,
        replacement_prob=0.99,   # Auto-generated
        recreation_time=0.99,    # Instant
        emotional_impact=0.01,   # None
    ),
}


# ─── Extension → Category Mapping ────────────────────────────────────────────

# Maps file extensions to their value categories
# This is the DEFAULT mapping — can be overridden by filename patterns
EXTENSION_CATEGORY_MAP: Dict[str, FileCategory] = {
    # Documents
    ".docx": FileCategory.WORK_DOC,
    ".doc":  FileCategory.WORK_DOC,
    ".xlsx": FileCategory.WORK_DOC,
    ".xls":  FileCategory.WORK_DOC,
    ".pptx": FileCategory.WORK_DOC,
    ".odt":  FileCategory.WORK_DOC,
    ".pdf":  FileCategory.WORK_DOC,
    ".txt":  FileCategory.PERSONAL_DOC,
    ".rtf":  FileCategory.PERSONAL_DOC,

    # Databases
    ".sqlite": FileCategory.DATABASE,
    ".db":     FileCategory.DATABASE,
    ".mdb":    FileCategory.DATABASE,
    ".accdb":  FileCategory.DATABASE,

    # Photos
    ".jpg":  FileCategory.PHOTO_PROCESSED,
    ".jpeg": FileCategory.PHOTO_PROCESSED,
    ".png":  FileCategory.PHOTO_PROCESSED,
    ".gif":  FileCategory.PHOTO_PROCESSED,
    ".bmp":  FileCategory.PHOTO_PROCESSED,
    ".heic": FileCategory.PHOTO_PROCESSED,
    ".cr2":  FileCategory.PHOTO_RAW,
    ".nef":  FileCategory.PHOTO_RAW,
    ".dng":  FileCategory.PHOTO_RAW,
    ".arw":  FileCategory.PHOTO_RAW,
    ".psd":  FileCategory.PHOTO_RAW,

    # Videos
    ".mp4":  FileCategory.VIDEO_DOWNLOADED,
    ".mov":  FileCategory.VIDEO_DOWNLOADED,
    ".avi":  FileCategory.VIDEO_DOWNLOADED,
    ".mkv":  FileCategory.VIDEO_DOWNLOADED,
    ".wmv":  FileCategory.VIDEO_DOWNLOADED,

    # Archives
    ".zip":  FileCategory.ARCHIVE,
    ".rar":  FileCategory.ARCHIVE,
    ".7z":   FileCategory.ARCHIVE,
    ".tar":  FileCategory.ARCHIVE,
    ".gz":   FileCategory.ARCHIVE,

    # System
    ".exe":  FileCategory.SYSTEM,
    ".dll":  FileCategory.SYSTEM,
    ".sys":  FileCategory.SYSTEM,
    ".dat":  FileCategory.SYSTEM,
    ".ini":  FileCategory.SYSTEM,

    # Logs
    ".log":  FileCategory.LOG,
    ".xml":  FileCategory.LOG,
    ".json": FileCategory.LOG,

    # Temp
    ".tmp":  FileCategory.TEMP,
    ".bak":  FileCategory.TEMP,
    ".cache": FileCategory.TEMP,
}


# ─── Filename Pattern Overrides ──────────────────────────────────────────────

# These patterns override the extension-based category.
# For example, a file named "tesis.docx" should be THESIS, not WORK_DOC.
FILENAME_PATTERN_OVERRIDES: List[Tuple[str, FileCategory]] = [
    # Thesis / academic work
    (r"(?i)(tesis|thesis|dissertation|monografia|trabajo.final)", FileCategory.THESIS),
    (r"(?i)(capitulo|chapter)\s*\d", FileCategory.THESIS),
    (r"(?i)(paper|articulo|article|paper)", FileCategory.THESIS),

    # Legal documents
    (r"(?i)(contrato|contract|legal|acuerdo|agreement|sentencia|demanda)", FileCategory.LEGAL),
    (r"(?i)(notaria|escritura|poder|testamento)", FileCategory.LEGAL),

    # Personal documents
    (r"(?i)(diario|diary|personal|carta|letter|notas|notes)", FileCategory.PERSONAL_DOC),
    (r"(?i)(curriculum|resume|cv)", FileCategory.PERSONAL_DOC),

    # Family photos
    (r"(?i)(familia|family|boda|wedding|casamiento|cumple|birthday|navidad|christmas)", FileCategory.PHOTO_FAMILY),
    (r"(?i)(img_\d{4}|dsc_\d{4}|_mg_\d{4})", FileCategory.PHOTO_FAMILY),  # Camera naming

    # Personal videos
    (r"(?i)(video|clip|grabacion).*(familia|family|boda|wedding|cumple|birthday)", FileCategory.VIDEO_PERSONAL),
    (r"(?i)(vid_\d{4})", FileCategory.VIDEO_PERSONAL),  # Phone video naming

    # Databases
    (r"(?i)(database|base.datos|datos|proyecto|project).*(sqlite|db|mdb)", FileCategory.DATABASE),

    # Thumbnails
    (r"(?i)(thumb|thumbnail|cache|icon|favicon|\.thumb)", FileCategory.THUMBNAIL),

    # Temp
    (r"(?i)(~\$|temp|tmp|cache|\.swp|\.bak)", FileCategory.TEMP),
]


# ─── Recovery Value Score Calculator ─────────────────────────────────────────

class RecoveryValueScore:
    """
    Calculate the Recovery Value Score (RVS) for a set of recovered files.

    RVS measures the VALUE of recovery, not just the count.

    Usage:
        rvs = RecoveryValueScore()
        result = rvs.compute_score(
            recovered_names={"photo_0001.jpg", "tesis.docx"},
            ground_truth_names={"photo_0001.jpg", "tesis.docx", "thumbnail_0001.jpg"},
            file_sizes={"photo_0001.jpg": 500000, "tesis.docx": 200000, "thumbnail_0001.jpg": 5000},
        )
        print(result["rvs"])  # 0.85 (high value — thesis recovered)
    """

    def __init__(self):
        self.profiles = VALUE_PROFILES
        self.ext_map = EXTENSION_CATEGORY_MAP
        self.pattern_overrides = FILENAME_PATTERN_OVERRIDES

    def classify_file(self, filename: str) -> FileCategory:
        """
        Classify a file into its value category.

        Priority:
          1. Filename pattern overrides (most specific)
          2. Extension-based mapping (default)
          3. PERSONAL_DOC (safe fallback)
        """
        # Check pattern overrides first
        for pattern, category in self.pattern_overrides:
            if re.search(pattern, filename):
                return category

        # Check extension
        ext = Path(filename).suffix.lower()
        if ext in self.ext_map:
            return self.ext_map[ext]

        # Fallback
        return FileCategory.PERSONAL_DOC

    def file_value(self, filename: str) -> float:
        """
        Calculate the composite value score for a single file.

        Returns a float 0.0-1.0 where:
          1.0 = thesis, database, legal (irreplaceable)
          0.0 = thumbnail, temp (essentially worthless)
        """
        category = self.classify_file(filename)
        profile = self.profiles.get(category)
        if profile is None:
            return 0.5  # Unknown files get medium value
        return profile.composite_score

    def compute_score(self,
                      recovered_names: set,
                      ground_truth_names: set,
                      file_sizes: Optional[Dict[str, int]] = None) -> Dict:
        """
        Compute the full RVS for a recovery result.

        Args:
            recovered_names: Set of filenames that were recovered
            ground_truth_names: Set of all filenames in ground truth
            file_sizes: Optional dict of filename → size for size bonus

        Returns:
            Dict with:
              - rvs: Overall RVS score (0.0-1.0)
              - total_value_recovered: Sum of values of recovered files
              - total_value_ground_truth: Sum of values of all ground truth files
              - per_file_details: Dict of filename → value breakdown
              - lost_value: Value of files NOT recovered
              - most_valuable_lost: The highest-value file that was NOT recovered
        """
        file_sizes = file_sizes or {}

        # Compute value for each ground truth file
        per_file_details = {}
        total_value_gt = 0.0
        total_value_recovered = 0.0
        lost_files = []

        for name in ground_truth_names:
            base_value = self.file_value(name)

            # Size bonus: larger files get a slight bonus (logarithmic)
            # This prevents a 1-byte file from having the same value as a 100MB file
            size = file_sizes.get(name, 0)
            if size > 0:
                import math
                size_bonus = 1.0 + 0.1 * math.log10(max(size, 1)) / 8.0  # 0-10% bonus
                size_bonus = min(size_bonus, 1.10)
            else:
                size_bonus = 1.0

            file_value = base_value * size_bonus

            per_file_details[name] = {
                "base_value": round(base_value, 4),
                "size_bonus": round(size_bonus, 4),
                "file_value": round(file_value, 4),
                "category": self.classify_file(name).value,
                "recovered": name in recovered_names,
            }

            total_value_gt += file_value

            if name in recovered_names:
                total_value_recovered += file_value
            else:
                lost_files.append((name, file_value))

        # RVS = recovered value / total value
        rvs = total_value_recovered / total_value_gt if total_value_gt > 0 else 0.0

        # Find the most valuable lost file
        most_valuable_lost = None
        if lost_files:
            lost_files.sort(key=lambda x: -x[1])
            most_valuable_lost = {
                "name": lost_files[0][0],
                "value": round(lost_files[0][1], 4),
                "category": self.classify_file(lost_files[0][0]).value,
            }

        # Top 5 lost files by value
        top_lost = [
            {"name": name, "value": round(val, 4), "category": self.classify_file(name).value}
            for name, val in lost_files[:5]
        ]

        return {
            "rvs": round(rvs, 4),
            "total_value_recovered": round(total_value_recovered, 4),
            "total_value_ground_truth": round(total_value_gt, 4),
            "per_file_details": per_file_details,
            "lost_value": round(total_value_gt - total_value_recovered, 4),
            "most_valuable_lost": most_valuable_lost,
            "top_5_lost": top_lost,
            "n_recovered": len(recovered_names & ground_truth_names),
            "n_ground_truth": len(ground_truth_names),
        }

    def compute_rvs_simple(self,
                           recovered_names: set,
                           ground_truth_names: set,
                           file_sizes: Optional[Dict[str, int]] = None) -> float:
        """
        Compute just the RVS score (0.0-1.0) without full details.

        This is the quick interface for when you only need the number.
        """
        result = self.compute_score(recovered_names, ground_truth_names, file_sizes)
        return result["rvs"]

    def value_comparison_report(self,
                                recovered_a: set,
                                recovered_b: set,
                                ground_truth: set,
                                file_sizes: Optional[Dict[str, int]] = None,
                                name_a: str = "Motor A",
                                name_b: str = "Motor B") -> str:
        """
        Generate a human-readable comparison of two motors' RVS.

        This is the "so what?" report — it tells you which motor
        recovered more VALUE, not just more files.
        """
        rvs_a = self.compute_score(recovered_a, ground_truth, file_sizes)
        rvs_b = self.compute_score(recovered_b, ground_truth, file_sizes)

        lines = [
            f"╔══════════════════════════════════════════════════════════════╗",
            f"║           RECOVERY VALUE SCORE COMPARISON                   ║",
            f"╠══════════════════════════════════════════════════════════════╣",
            f"║  {name_a:20s}  RVS: {rvs_a['rvs']:.1%}  "
            f"({rvs_a['n_recovered']}/{rvs_a['n_ground_truth']} files)       ║",
            f"║  {name_b:20s}  RVS: {rvs_b['rvs']:.1%}  "
            f"({rvs_b['n_recovered']}/{rvs_b['n_ground_truth']} files)       ║",
            f"╠══════════════════════════════════════════════════════════════╣",
        ]

        # Which motor recovered more value?
        delta = rvs_a["rvs"] - rvs_b["rvs"]
        if abs(delta) < 0.01:
            lines.append(f"║  RESULT: Tie (RVS difference < 1%)                         ║")
        elif delta > 0:
            lines.append(f"║  RESULT: {name_a} recovers {delta:.1%} MORE VALUE              ║")
        else:
            lines.append(f"║  RESULT: {name_b} recovers {-delta:.1%} MORE VALUE              ║")

        # Most valuable lost file
        if rvs_a["most_valuable_lost"] and rvs_b["most_valuable_lost"]:
            lines.append(f"╠══════════════════════════════════════════════════════════════╣")
            lines.append(f"║  Most valuable file LOST by {name_a}:")
            lines.append(f"║    {rvs_a['most_valuable_lost']['name']} "
                        f"(value={rvs_a['most_valuable_lost']['value']:.3f})")
            lines.append(f"║  Most valuable file LOST by {name_b}:")
            lines.append(f"║    {rvs_b['most_valuable_lost']['name']} "
                        f"(value={rvs_b['most_valuable_lost']['value']:.3f})")

        lines.append(f"╚══════════════════════════════════════════════════════════════╝")

        return "\n".join(lines)


# ─── Category Value Table (for documentation) ────────────────────────────────

def print_value_table() -> str:
    """
    Print the complete value table for documentation.

    This shows the composite score for each file category,
    so you can see exactly how the RVS weights different files.
    """
    lines = [
        "# Recovery Value Score (RVS) — Value Table",
        "",
        "| Category | Intrinsic | Replacement | Recreation | Emotional | Composite |",
        "|----------|-----------|-------------|------------|-----------|-----------|",
    ]

    for category in FileCategory:
        profile = VALUE_PROFILES[category]
        lines.append(
            f"| {category.value:20s} | {profile.intrinsic_value:.2f} | "
            f"{profile.replacement_prob:.2f} | {profile.recreation_time:.2f} | "
            f"{profile.emotional_impact:.2f} | {profile.composite_score:.4f} |"
        )

    lines.append("")
    lines.append("Composite = intrinsic_value × (1 - replacement × recreation × (1 - emotional))")
    lines.append("")
    lines.append("Example files and their RVS scores:")
    lines.append("")

    example_files = [
        "tesis_final.docx",
        "proyecto.sqlite",
        "contrato_alquiler.pdf",
        "diario_personal.txt",
        "foto_familia_navidad.jpg",
        "video_boda.mp4",
        "presentacion_trabajo.pptx",
        "foto_cr2.cr2",
        "imagen_procesada.png",
        "pelicula_descargada.mp4",
        "backup_proyecto.zip",
        "kernel32.dll",
        "app.log",
        "thumb_cache.dat",
        "~$tesis.docx",
    ]

    rvs = RecoveryValueScore()
    lines.append("| File | Category | Value |")
    lines.append("|------|----------|-------|")
    for f in example_files:
        cat = rvs.classify_file(f)
        val = rvs.file_value(f)
        lines.append(f"| {f:30s} | {cat.value:20s} | {val:.4f} |")

    return "\n".join(lines)


if __name__ == "__main__":
    print(print_value_table())
