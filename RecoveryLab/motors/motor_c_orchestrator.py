"""
RecoveryLab — Motor C (Orchestrator)
======================================
The director of the orchestra. Not a strategy — a system that chooses.

H1.1: "Priorizar metadatos recuperables reduce significativamente el costo
       de adquisición cuando los metadatos son suficientemente confiables."

H1.2: "Cuando la confianza en los metadatos cae por debajo de un umbral,
       la estrategia óptima deja de ser la priorización y pasa a ser
       una estrategia híbrida."

Motor C implements both hypotheses:

  1. Diagnose the disk
  2. Calculate MFT confidence
  3. If confidence > 85% → MFT-first mode
  4. If journal valid → Journal-guided mode
  5. If bitmap useful → Bitmap-guided mode
  6. Otherwise → Carving mode

The key innovation: Motor C doesn't just pick a strategy.
It can RETREAT from a strategy when it stops working.
"""

import hashlib
import struct
import math
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass

from .base_motor import BaseMotor, MotorResult, RecoveredFile
from .motor_a_sequential import MotorASequential
from .motor_b_mft_first import MotorBMFTFirst


# ─── Confidence Thresholds ────────────────────────────────────────────────────

CONFIDENCE_HIGH = 0.85      # Above this → MFT-first
CONFIDENCE_MEDIUM = 0.50    # Above this → Hybrid (MFT + fallback)
CONFIDENCE_LOW = 0.20       # Above this → Journal/Bitmap guided
# Below CONFIDENCE_LOW → Carving

# ─── Strategy Names ───────────────────────────────────────────────────────────

STRATEGY_MFT_FIRST = "mft_first"
STRATEGY_HYBRID = "hybrid"
STRATEGY_JOURNAL = "journal"
STRATEGY_BITMAP = "bitmap"
STRATEGY_CARVING = "carving"


@dataclass
class DiagnosisResult:
    """Result of diagnosing a disk image."""
    vbr_valid: bool = False
    mft_found: bool = False
    mft_confidence: float = 0.0        # 0.0-1.0
    mft_entries_total: int = 0
    mft_entries_readable: int = 0
    mft_entries_in_use: int = 0
    bitmap_valid: bool = False
    bitmap_confidence: float = 0.0
    journal_valid: bool = False
    journal_confidence: float = 0.0
    recommended_strategy: str = STRATEGY_CARVING
    diagnosis_reads: int = 0


class MotorCOrchestrator(BaseMotor):
    """
    Motor C: The Orchestrator.

    Diagnoses the disk, calculates confidence, and selects the
    optimal strategy. Can retreat from a strategy when it stops working.

    This is NOT a single recovery strategy — it's a system that CHOOSES.
    """

    @property
    def name(self) -> str:
        return "Motor C (Orchestrator)"

    @property
    def description(self) -> str:
        return "Diagnoses disk, calculates confidence, selects optimal strategy. Can retreat."

    def __init__(self):
        self._motor_a = MotorASequential()
        self._motor_b = MotorBMFTFirst()
        self._confidence_threshold = CONFIDENCE_HIGH

    def recover(self, image: bytes, manifest: Dict,
                read_budget: int = 0,
                corruption_metadata: Optional[Dict] = None) -> MotorResult:
        """
        Run the orchestrated recovery.

        Step 1: Diagnose the disk
        Step 2: Calculate confidence
        Step 3: Select strategy
        Step 4: Execute with monitoring
        Step 5: Retreat if strategy fails
        """
        result = MotorResult(motor_name=self.name)

        # ─── Step 1: Diagnose ─────────────────────────────────────────
        diagnosis = self._diagnose(image, manifest)
        result.metadata["diagnosis"] = {
            "vbr_valid": diagnosis.vbr_valid,
            "mft_found": diagnosis.mft_found,
            "mft_confidence": round(diagnosis.mft_confidence, 4),
            "mft_entries_total": diagnosis.mft_entries_total,
            "mft_entries_readable": diagnosis.mft_entries_readable,
            "bitmap_valid": diagnosis.bitmap_valid,
            "journal_valid": diagnosis.journal_valid,
            "recommended_strategy": diagnosis.recommended_strategy,
        }

        # ─── Step 2: Select strategy based on confidence ──────────────
        strategy = diagnosis.recommended_strategy
        result.metadata["strategy_selected"] = strategy

        # ─── Step 3: Execute strategy ─────────────────────────────────
        if strategy == STRATEGY_MFT_FIRST:
            # High confidence → use MFT-first
            sub_result = self._motor_b.recover(
                image, manifest, read_budget=read_budget,
                corruption_metadata=corruption_metadata,
            )
            result = self._merge_results(result, sub_result, strategy)

        elif strategy == STRATEGY_HYBRID:
            # Medium confidence → try MFT-first, fall back to carving
            sub_result = self._motor_b.recover(
                image, manifest, read_budget=read_budget,
                corruption_metadata=corruption_metadata,
            )

            # Check if MFT-first recovered enough
            recovery_rate = self._estimate_recovery_rate(sub_result, manifest)

            if recovery_rate < 0.5:
                # MFT-first didn't work well → supplement with carving
                result.metadata["retreat"] = True
                result.metadata["retreat_reason"] = f"MFT-first recovery rate too low ({recovery_rate:.1%})"

                # Run carving (Motor A) for files not yet recovered
                carving_result = self._motor_a.recover(
                    image, manifest, read_budget=read_budget,
                    corruption_metadata=corruption_metadata,
                )
                result = self._merge_hybrid_results(
                    result, sub_result, carving_result, manifest
                )
            else:
                result = self._merge_results(result, sub_result, strategy)

        elif strategy == STRATEGY_JOURNAL:
            # Journal-guided (placeholder — would parse journal for file refs)
            # For now, fall through to carving
            sub_result = self._motor_a.recover(
                image, manifest, read_budget=read_budget,
                corruption_metadata=corruption_metadata,
            )
            result = self._merge_results(result, sub_result, strategy)

        elif strategy == STRATEGY_BITMAP:
            # Bitmap-guided (placeholder — would read bitmap to find allocated clusters)
            # For now, fall through to carving
            sub_result = self._motor_a.recover(
                image, manifest, read_budget=read_budget,
                corruption_metadata=corruption_metadata,
            )
            result = self._merge_results(result, sub_result, strategy)

        else:  # STRATEGY_CARVING
            # Low confidence → full carving
            sub_result = self._motor_a.recover(
                image, manifest, read_budget=read_budget,
                corruption_metadata=corruption_metadata,
            )
            result = self._merge_results(result, sub_result, strategy)

        # Add diagnosis reads to total
        result.read_count += diagnosis.diagnosis_reads
        result.metadata["mft_confidence"] = round(diagnosis.mft_confidence, 4)

        return result

    def _diagnose(self, image: bytes, manifest: Dict) -> DiagnosisResult:
        """
        Diagnose the disk image to determine the best strategy.

        This is the key innovation: instead of blindly choosing a strategy,
        we first CHECK what's available.
        """
        diag = DiagnosisResult()
        cluster_size = manifest.get("cluster_size", 4096)
        mft_info = manifest.get("mft", {})
        mft_start = mft_info.get("start_cluster", 0)
        mft_record_count = mft_info.get("record_count", 0)
        diag_reads = 0

        # ─── Check VBR ────────────────────────────────────────────────
        if len(image) >= 512:
            oem_id = image[3:11]
            if oem_id == b'NTFS    ':
                diag.vbr_valid = True
                # Read MFT location from VBR
                try:
                    vbr_mft_cluster = struct.unpack_from('<Q', image, 48)[0]
                    if vbr_mft_cluster == mft_start:
                        diag.mft_found = True
                except:
                    pass
            diag_reads += 1

        # ─── Check MFT ────────────────────────────────────────────────
        if diag.mft_found:
            mft_offset = mft_start * cluster_size
            readable = 0
            in_use = 0

            for rec_num in range(mft_record_count):
                rec_offset = mft_offset + rec_num * 1024
                if rec_offset + 1024 > len(image):
                    break

                # Check if record is valid
                sig = image[rec_offset:rec_offset + 4]
                if sig == b'FILE':
                    readable += 1
                    try:
                        flags = struct.unpack_from('<H', image, rec_offset + 22)[0]
                        if flags & 0x0001:  # In use
                            in_use += 1
                    except:
                        pass

                # Count reads for MFT check
                if rec_num % 4 == 0:  # Each cluster = 4 records
                    diag_reads += cluster_size // 512

            diag.mft_entries_total = mft_record_count
            diag.mft_entries_readable = readable
            diag.mft_entries_in_use = in_use

            # Calculate MFT confidence
            if mft_record_count > 0:
                # Confidence based on: readable entries / total entries
                # Weighted by the fraction of user entries that are readable
                user_total = mft_record_count - 12  # Exclude system files
                user_readable = max(0, readable - 12)  # System files always readable if present

                if user_total > 0:
                    diag.mft_confidence = user_readable / user_total
                else:
                    diag.mft_confidence = 1.0 if readable > 0 else 0.0

        # ─── Check Bitmap ─────────────────────────────────────────────
        bitmap_info = manifest.get("bitmap", {})
        bitmap_start = bitmap_info.get("start_cluster", 0)
        if bitmap_start > 0:
            bitmap_offset = bitmap_start * cluster_size
            if bitmap_offset + cluster_size <= len(image):
                # Check if bitmap has non-zero data
                bitmap_data = image[bitmap_offset:bitmap_offset + cluster_size]
                nonzero_bytes = sum(1 for b in bitmap_data if b != 0)
                if nonzero_bytes > 0:
                    diag.bitmap_valid = True
                    diag.bitmap_confidence = nonzero_bytes / len(bitmap_data)
                diag_reads += cluster_size // 512

        # ─── Check Journal ────────────────────────────────────────────
        logfile_info = manifest.get("logfile", {})
        logfile_start = logfile_info.get("start_cluster", 0)
        if logfile_start > 0:
            logfile_offset = logfile_start * cluster_size
            if logfile_offset + cluster_size <= len(image):
                # Check if journal has valid restart page signature
                journal_sig = image[logfile_offset:logfile_offset + 4]
                if journal_sig == b'NTFS' or journal_sig != b'\x00' * 4:
                    diag.journal_valid = True
                    diag.journal_confidence = 0.5  # Basic check
                diag_reads += cluster_size // 512

        # ─── Select strategy ──────────────────────────────────────────
        diag.recommended_strategy = self._select_strategy(diag)
        diag.diagnosis_reads = diag_reads

        return diag

    def _select_strategy(self, diag: DiagnosisResult) -> str:
        """
        Select the optimal recovery strategy based on diagnosis.

        Decision tree:
          - VBR invalid → carving
          - MFT confidence > 85% → MFT-first
          - MFT confidence > 50% → hybrid (MFT + carving fallback)
          - Journal valid → journal-guided
          - Bitmap valid → bitmap-guided
          - Otherwise → carving
        """
        if not diag.vbr_valid:
            return STRATEGY_CARVING

        if diag.mft_confidence >= CONFIDENCE_HIGH:
            return STRATEGY_MFT_FIRST

        if diag.mft_confidence >= CONFIDENCE_MEDIUM:
            return STRATEGY_HYBRID

        if diag.journal_valid and diag.journal_confidence > 0.5:
            return STRATEGY_JOURNAL

        if diag.bitmap_valid and diag.bitmap_confidence > 0.1:
            return STRATEGY_BITMAP

        return STRATEGY_CARVING

    def _estimate_recovery_rate(self, sub_result: MotorResult,
                                 manifest: Dict) -> float:
        """Estimate the recovery rate from a sub-result."""
        total_files = len([f for f in manifest.get("files", [])
                          if not f.get("is_directory", False)])
        if total_files == 0:
            return 0.0
        recovered = len([f for f in sub_result.recovered_files
                        if not f.is_directory])
        return recovered / total_files

    def _merge_results(self, main_result: MotorResult,
                       sub_result: MotorResult,
                       strategy: str) -> MotorResult:
        """Merge a sub-result into the main result."""
        main_result.recovered_files = sub_result.recovered_files
        main_result.read_count = sub_result.read_count
        main_result.sectors_wasted = sub_result.sectors_wasted
        main_result.time_to_first_file = sub_result.time_to_first_file
        main_result.mft_entries_parsed = sub_result.mft_entries_parsed
        main_result.directories_rebuilt = sub_result.directories_rebuilt
        main_result.total_time_seconds = sub_result.total_time_seconds
        main_result.metadata["strategy_executed"] = strategy
        return main_result

    def _merge_hybrid_results(self, main_result: MotorResult,
                               mft_result: MotorResult,
                               carving_result: MotorResult,
                               manifest: Dict) -> MotorResult:
        """
        Merge results from MFT-first and carving strategies.

        For hybrid mode, we take:
          - Files recovered by MFT-first (high confidence)
          - Files recovered by carving that weren't found by MFT
          - No duplicates
        """
        # Track which files were already recovered
        recovered_names = set()

        # First, add MFT-first results (high confidence)
        for f in mft_result.recovered_files:
            if f.name not in recovered_names:
                main_result.recovered_files.append(f)
                recovered_names.add(f.name)

        # Then, add carving results that weren't found by MFT
        for f in carving_result.recovered_files:
            if f.name not in recovered_names:
                f.source = "carving_fallback"
                main_result.recovered_files.append(f)
                recovered_names.add(f.name)
            else:
                main_result.duplicates += 1

        # Sum reads
        main_result.read_count = mft_result.read_count + carving_result.read_count
        main_result.sectors_wasted = mft_result.sectors_wasted + carving_result.sectors_wasted
        main_result.time_to_first_file = mft_result.time_to_first_file
        main_result.mft_entries_parsed = mft_result.mft_entries_parsed
        main_result.directories_rebuilt = max(
            mft_result.directories_rebuilt,
            carving_result.directories_rebuilt,
        )
        main_result.metadata["strategy_executed"] = STRATEGY_HYBRID
        main_result.metadata["mft_recovery_count"] = len(mft_result.recovered_files)
        main_result.metadata["carving_recovery_count"] = len(carving_result.recovered_files)

        return main_result

    def compute_mft_confidence(self, image: bytes, manifest: Dict) -> float:
        """
        Compute MFT confidence for an image.

        Public method for the Confidence Sweep experiment.
        """
        diag = self._diagnose(image, manifest)
        return diag.mft_confidence
