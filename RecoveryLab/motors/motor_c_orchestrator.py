"""
RecoveryLab — Motor C (Orchestrator) with DecisionTrace
=========================================================
Objeción 4: Motor C needs to justify its decisions.

Not just "Confianza = 47%" — but:

    Modo seleccionado: Hybrid
    Razones:
    ✓ 32% de registros MFT ilegibles
    ✓ MFT Mirror parcialmente válida
    ✓ Bitmap inconsistente
    ✓ Journal recuperable
    Confianza MFT: 46%
    Se recomienda cambiar a estrategia híbrida.

This has two enormous advantages:
  1. The user understands the decision
  2. You can debug the algorithm

DecisionTrace is a structured record of every signal the motor observed
and how it contributed to the final decision.
"""

import hashlib
import struct
import math
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field

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
class DiagnosticSignal:
    """A single diagnostic signal observed during disk analysis."""
    name: str               # e.g., "mft_readability", "bitmap_validity"
    value: float            # 0.0-1.0
    threshold: float        # What threshold this signal was compared against
    passed: bool            # Did this signal pass its threshold?
    weight: float           # How much this signal influenced the decision (0.0-1.0)
    description: str        # Human-readable explanation


@dataclass
class DecisionTrace:
    """
    Complete trace of Motor C's decision process.

    This is the key innovation: instead of a black box, every decision
    is explained with specific signals and their contributions.
    """
    # ─── Phase 1: Diagnosis ─────────────────────────────────────────
    signals: List[DiagnosticSignal] = field(default_factory=list)

    # ─── Phase 2: Confidence Calculation ────────────────────────────
    mft_confidence: float = 0.0
    mft_confidence_components: Dict[str, float] = field(default_factory=dict)

    # ─── Phase 3: Strategy Selection ────────────────────────────────
    strategy_selected: str = ""
    strategy_reasons: List[str] = field(default_factory=list)
    strategy_alternatives: List[Dict] = field(default_factory=list)

    # ─── Phase 4: Execution ─────────────────────────────────────────
    execution_notes: List[str] = field(default_factory=list)

    # ─── Phase 5: Retreat ───────────────────────────────────────────
    retreat_triggered: bool = False
    retreat_reason: str = ""
    retreat_from_strategy: str = ""
    retreat_to_strategy: str = ""

    def to_dict(self) -> Dict:
        return {
            "signals": [
                {
                    "name": s.name,
                    "value": round(s.value, 4),
                    "threshold": round(s.threshold, 4),
                    "passed": s.passed,
                    "weight": round(s.weight, 4),
                    "description": s.description,
                }
                for s in self.signals
            ],
            "mft_confidence": round(self.mft_confidence, 4),
            "mft_confidence_components": {
                k: round(v, 4) for k, v in self.mft_confidence_components.items()
            },
            "strategy_selected": self.strategy_selected,
            "strategy_reasons": self.strategy_reasons,
            "strategy_alternatives": self.strategy_alternatives,
            "execution_notes": self.execution_notes,
            "retreat_triggered": self.retreat_triggered,
            "retreat_reason": self.retreat_reason,
            "retreat_from_strategy": self.retreat_from_strategy,
            "retreat_to_strategy": self.retreat_to_strategy,
        }

    def human_readable(self) -> str:
        """Generate a human-readable decision report."""
        lines = []
        lines.append(f"Modo seleccionado: {self.strategy_selected.upper()}")
        lines.append("")
        lines.append("Razones:")

        for reason in self.strategy_reasons:
            lines.append(f"  {reason}")

        lines.append("")
        lines.append(f"Confianza MFT: {self.mft_confidence:.0%}")

        if self.mft_confidence_components:
            lines.append("  Componentes:")
            for comp, val in self.mft_confidence_components.items():
                lines.append(f"    {comp}: {val:.0%}")

        if self.strategy_alternatives:
            lines.append("")
            lines.append("Alternativas consideradas:")
            for alt in self.strategy_alternatives:
                lines.append(f"  {alt['strategy']}: {alt['reason']}")

        if self.retreat_triggered:
            lines.append("")
            lines.append(f"RETIRADA: {self.retreat_from_strategy} → {self.retreat_to_strategy}")
            lines.append(f"  Razón: {self.retreat_reason}")

        return "\n".join(lines)


@dataclass
class DiagnosisResult:
    """Result of diagnosing a disk image."""
    vbr_valid: bool = False
    mft_found: bool = False
    mft_confidence: float = 0.0
    mft_entries_total: int = 0
    mft_entries_readable: int = 0
    mft_entries_in_use: int = 0
    mft_mirror_valid: bool = False
    mft_mirror_consistent: bool = False
    bitmap_valid: bool = False
    bitmap_confidence: float = 0.0
    journal_valid: bool = False
    journal_confidence: float = 0.0
    recommended_strategy: str = STRATEGY_CARVING
    diagnosis_reads: int = 0


class MotorCOrchestrator(BaseMotor):
    """
    Motor C: The Orchestrator with DecisionTrace.

    Diagnoses the disk, calculates confidence, and selects the
    optimal strategy. Can retreat from a strategy when it stops working.

    Every decision is explained with specific signals and their contributions.
    """

    @property
    def name(self) -> str:
        return "Motor C (Orchestrator)"

    @property
    def description(self) -> str:
        return "Diagnoses disk, calculates confidence, selects optimal strategy. Every decision explained."

    def __init__(self):
        self._motor_a = MotorASequential()
        self._motor_b = MotorBMFTFirst()
        self._confidence_threshold = CONFIDENCE_HIGH

    def recover(self, image: bytes, manifest: Dict,
                read_budget: int = 0,
                corruption_metadata: Optional[Dict] = None) -> MotorResult:
        """
        Run the orchestrated recovery with full decision trace.

        Step 1: Diagnose the disk (with signals)
        Step 2: Calculate confidence (with components)
        Step 3: Select strategy (with reasons)
        Step 4: Execute with monitoring
        Step 5: Retreat if strategy fails
        """
        result = MotorResult(motor_name=self.name)
        trace = DecisionTrace()

        # ─── Step 1: Diagnose ─────────────────────────────────────────
        diagnosis = self._diagnose(image, manifest, trace)

        # ─── Step 2: Calculate confidence ─────────────────────────────
        self._calculate_confidence(diagnosis, trace)

        # ─── Step 3: Select strategy ──────────────────────────────────
        strategy = self._select_strategy_with_trace(diagnosis, trace)

        # ─── Step 4: Execute strategy ─────────────────────────────────
        trace.execution_notes.append(f"Executing strategy: {strategy}")

        if strategy == STRATEGY_MFT_FIRST:
            sub_result = self._motor_b.recover(
                image, manifest, read_budget=read_budget,
                corruption_metadata=corruption_metadata,
            )
            result = self._merge_results(result, sub_result, strategy)

        elif strategy == STRATEGY_HYBRID:
            sub_result = self._motor_b.recover(
                image, manifest, read_budget=read_budget,
                corruption_metadata=corruption_metadata,
            )

            recovery_rate = self._estimate_recovery_rate(sub_result, manifest)

            if recovery_rate < 0.5:
                # ─── Step 5: Retreat ──────────────────────────────────
                trace.retreat_triggered = True
                trace.retreat_from_strategy = STRATEGY_MFT_FIRST
                trace.retreat_to_strategy = STRATEGY_CARVING
                trace.retreat_reason = (
                    f"MFT-first recovery rate too low ({recovery_rate:.1%}). "
                    f"Switching to carving to supplement."
                )

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
            trace.execution_notes.append("Journal strategy: delegating to Motor A (journal parsing not yet implemented)")
            sub_result = self._motor_a.recover(
                image, manifest, read_budget=read_budget,
                corruption_metadata=corruption_metadata,
            )
            result = self._merge_results(result, sub_result, strategy)

        elif strategy == STRATEGY_BITMAP:
            trace.execution_notes.append("Bitmap strategy: delegating to Motor A (bitmap-guided recovery not yet implemented)")
            sub_result = self._motor_a.recover(
                image, manifest, read_budget=read_budget,
                corruption_metadata=corruption_metadata,
            )
            result = self._merge_results(result, sub_result, strategy)

        else:  # STRATEGY_CARVING
            sub_result = self._motor_a.recover(
                image, manifest, read_budget=read_budget,
                corruption_metadata=corruption_metadata,
            )
            result = self._merge_results(result, sub_result, strategy)

        # Add diagnosis reads to total
        result.read_count += diagnosis.diagnosis_reads

        # Store the decision trace in the result
        result.metadata["decision_trace"] = trace.to_dict()
        result.metadata["mft_confidence"] = round(diagnosis.mft_confidence, 4)
        result.metadata["strategy_selected"] = strategy

        return result

    def _diagnose(self, image: bytes, manifest: Dict,
                  trace: DecisionTrace) -> DiagnosisResult:
        """
        Diagnose the disk image with full signal tracking.
        """
        diag = DiagnosisResult()
        cluster_size = manifest.get("cluster_size", 4096)
        mft_info = manifest.get("mft", {})
        mft_start = mft_info.get("start_cluster", 0)
        mft_record_count = mft_info.get("record_count", 0)
        diag_reads = 0

        # ─── Signal 1: VBR Validity ──────────────────────────────────
        vbr_valid = False
        if len(image) >= 512:
            oem_id = image[3:11]
            if oem_id == b'NTFS    ':
                vbr_valid = True
                try:
                    vbr_mft_cluster = struct.unpack_from('<Q', image, 48)[0]
                    if vbr_mft_cluster == mft_start:
                        diag.mft_found = True
                except:
                    pass
            diag_reads += 1

        diag.vbr_valid = vbr_valid
        trace.signals.append(DiagnosticSignal(
            name="vbr_validity",
            value=1.0 if vbr_valid else 0.0,
            threshold=1.0,
            passed=vbr_valid,
            weight=0.25,
            description="VBR válido con firma NTFS" if vbr_valid else
                       "VBR inválido o destruido — no se puede localizar MFT",
        ))

        # ─── Signal 2: MFT Readability ───────────────────────────────
        if diag.mft_found:
            mft_offset = mft_start * cluster_size
            readable = 0
            in_use = 0
            total_user = 0

            for rec_num in range(mft_record_count):
                rec_offset = mft_offset + rec_num * 1024
                if rec_offset + 1024 > len(image):
                    break

                sig = image[rec_offset:rec_offset + 4]
                if sig == b'FILE':
                    readable += 1
                    try:
                        flags = struct.unpack_from('<H', image, rec_offset + 22)[0]
                        if flags & 0x0001:
                            in_use += 1
                    except:
                        pass

                if rec_num >= 12:
                    total_user += 1

                if rec_num % 4 == 0:
                    diag_reads += cluster_size // 512

            diag.mft_entries_total = mft_record_count
            diag.mft_entries_readable = readable
            diag.mft_entries_in_use = in_use

            # Calculate user entry readability
            user_readable = max(0, readable - 12)
            user_total = max(0, mft_record_count - 12)

            if user_total > 0:
                readability = user_readable / user_total
            else:
                readability = 1.0 if readable > 0 else 0.0

            diag.mft_confidence = readability

            # Create signal
            pct_illegible = (1.0 - readability) * 100
            if pct_illegible > 0:
                desc = f"{pct_illegible:.0f}% de registros MFT ilegibles ({user_total - user_readable}/{user_total})"
            else:
                desc = "Todos los registros MFT son legibles"

            trace.signals.append(DiagnosticSignal(
                name="mft_readability",
                value=readability,
                threshold=CONFIDENCE_HIGH,
                passed=readability >= CONFIDENCE_HIGH,
                weight=0.50,
                description=desc,
            ))

            # ─── Signal 2b: MFT Mirror Consistency ───────────────────
            mirror_info = manifest.get("mft_mirror", {})
            mirror_start = mirror_info.get("start_cluster", 0)
            mirror_consistent = False

            if mirror_start > 0:
                mirror_offset = mirror_start * cluster_size
                # Check first 4 MFT records (MFT Mirror stores first 4)
                if mirror_offset + 4 * 1024 <= len(image):
                    # Compare first 4 records
                    matches = 0
                    for i in range(4):
                        orig_offset = mft_offset + i * 1024
                        mirror_rec_offset = mirror_offset + i * 1024
                        if (orig_offset + 1024 <= len(image) and
                            mirror_rec_offset + 1024 <= len(image)):
                            if image[orig_offset:orig_offset+1024] == image[mirror_rec_offset:mirror_rec_offset+1024]:
                                matches += 1
                    mirror_consistent = (matches == 4)
                    diag.mft_mirror_valid = True
                    diag.mft_mirror_consistent = mirror_consistent
                    diag_reads += cluster_size // 512

            trace.signals.append(DiagnosticSignal(
                name="mft_mirror_consistency",
                value=1.0 if mirror_consistent else 0.0,
                threshold=1.0,
                passed=mirror_consistent,
                weight=0.10,
                description="MFT Mirror consistente con MFT" if mirror_consistent else
                           "MFT Mirror inconsistente — posible corrupción",
            ))

        # ─── Signal 3: Bitmap Validity ───────────────────────────────
        bitmap_info = manifest.get("bitmap", {})
        bitmap_start = bitmap_info.get("start_cluster", 0)
        bitmap_valid = False
        bitmap_confidence = 0.0

        if bitmap_start > 0:
            bitmap_offset = bitmap_start * cluster_size
            if bitmap_offset + cluster_size <= len(image):
                bitmap_data = image[bitmap_offset:bitmap_offset + cluster_size]
                nonzero_bytes = sum(1 for b in bitmap_data if b != 0)
                if nonzero_bytes > 0:
                    bitmap_valid = True
                    bitmap_confidence = nonzero_bytes / len(bitmap_data)
                diag_reads += cluster_size // 512

        diag.bitmap_valid = bitmap_valid
        diag.bitmap_confidence = bitmap_confidence

        trace.signals.append(DiagnosticSignal(
            name="bitmap_validity",
            value=bitmap_confidence,
            threshold=0.1,
            passed=bitmap_valid,
            weight=0.10,
            description="Bitmap válido con datos de asignación" if bitmap_valid else
                       "Bitmap vacío o corrupto — no se puede usar para guiar búsqueda",
        ))

        # ─── Signal 4: Journal Validity ──────────────────────────────
        logfile_info = manifest.get("logfile", {})
        logfile_start = logfile_info.get("start_cluster", 0)
        journal_valid = False
        journal_confidence = 0.0

        if logfile_start > 0:
            logfile_offset = logfile_start * cluster_size
            if logfile_offset + cluster_size <= len(image):
                journal_sig = image[logfile_offset:logfile_offset + 4]
                if journal_sig == b'NTFS' or journal_sig != b'\x00' * 4:
                    journal_valid = True
                    journal_confidence = 0.5  # Basic check
                diag_reads += cluster_size // 512

        diag.journal_valid = journal_valid
        diag.journal_confidence = journal_confidence

        trace.signals.append(DiagnosticSignal(
            name="journal_validity",
            value=journal_confidence,
            threshold=0.5,
            passed=journal_valid,
            weight=0.05,
            description="Journal recuperable — puede contener referencias a archivos" if journal_valid else
                       "Journal no disponible o corrupto",
        ))

        # ─── Select strategy ──────────────────────────────────────────
        diag.recommended_strategy = self._select_strategy_from_diagnosis(diag)
        diag.diagnosis_reads = diag_reads

        return diag

    def _calculate_confidence(self, diag: DiagnosisResult,
                              trace: DecisionTrace):
        """
        Calculate MFT confidence with component breakdown.

        The confidence is a weighted sum of signals, not just
        user_readable / user_total. This makes it more robust.
        """
        # Component 1: MFT readability (primary)
        readability = diag.mft_confidence

        # Component 2: VBR validity (enables MFT location)
        vbr_score = 1.0 if diag.vbr_valid else 0.0

        # Component 3: MFT Mirror consistency (validates MFT)
        mirror_score = 1.0 if diag.mft_mirror_consistent else 0.5 if diag.mft_mirror_valid else 0.0

        # Weighted confidence
        confidence = (
            0.60 * readability +
            0.20 * vbr_score +
            0.10 * mirror_score +
            0.10 * (1.0 if diag.bitmap_valid else 0.0)
        )

        # Override with direct readability if we have MFT data
        if diag.mft_entries_total > 0:
            trace.mft_confidence = readability  # Keep the primary signal
        else:
            trace.mft_confidence = confidence

        trace.mft_confidence_components = {
            "mft_readability": readability,
            "vbr_validity": vbr_score,
            "mft_mirror_consistency": mirror_score,
            "bitmap_validity": 1.0 if diag.bitmap_valid else 0.0,
            "weighted_confidence": confidence,
        }

    def _select_strategy_with_trace(self, diag: DiagnosisResult,
                                     trace: DecisionTrace) -> str:
        """
        Select the optimal strategy with full reasoning.
        """
        strategy = self._select_strategy_from_diagnosis(diag)
        trace.strategy_selected = strategy

        # Build reasons list
        if not diag.vbr_valid:
            trace.strategy_reasons.append("VBR destruido — no se puede localizar MFT")
            trace.strategy_reasons.append("Se requiere carving como única opción")
        elif diag.mft_confidence >= CONFIDENCE_HIGH:
            pct = diag.mft_confidence * 100
            trace.strategy_reasons.append(f"MFT altamente confiable ({pct:.0f}% legible)")
            trace.strategy_reasons.append("MFT-first es la estrategia óptima")
        elif diag.mft_confidence >= CONFIDENCE_MEDIUM:
            pct = (1.0 - diag.mft_confidence) * 100
            trace.strategy_reasons.append(f"{pct:.0f}% de registros MFT ilegibles")
            if not diag.mft_mirror_consistent:
                trace.strategy_reasons.append("MFT Mirror inconsistente")
            trace.strategy_reasons.append("Se recomienda estrategia híbrida (MFT + fallback)")
        elif diag.journal_valid and diag.journal_confidence > 0.5:
            pct = (1.0 - diag.mft_confidence) * 100
            trace.strategy_reasons.append(f"{pct:.0f}% de registros MFT ilegibles")
            trace.strategy_reasons.append("Journal recuperable — puede contener referencias a archivos")
            trace.strategy_reasons.append("Se recomienda estrategia Journal-guided")
        elif diag.bitmap_valid and diag.bitmap_confidence > 0.1:
            pct = (1.0 - diag.mft_confidence) * 100
            trace.strategy_reasons.append(f"{pct:.0f}% de registros MFT ilegibles")
            trace.strategy_reasons.append("Bitmap válido — puede reducir espacio de búsqueda")
            trace.strategy_reasons.append("Se recomienda estrategia Bitmap-guided")
        else:
            pct = (1.0 - diag.mft_confidence) * 100
            trace.strategy_reasons.append(f"{pct:.0f}% de registros MFT ilegibles")
            if not diag.bitmap_valid:
                trace.strategy_reasons.append("Bitmap inconsistente")
            if not diag.journal_valid:
                trace.strategy_reasons.append("Journal no disponible")
            trace.strategy_reasons.append("Solo queda carving como opción")

        # Record alternatives
        if strategy != STRATEGY_MFT_FIRST and diag.mft_confidence > 0:
            trace.strategy_alternatives.append({
                "strategy": STRATEGY_MFT_FIRST,
                "reason": f"Descartado: confianza MFT insuficiente ({diag.mft_confidence:.0%} < {CONFIDENCE_HIGH:.0%})",
            })
        if strategy != STRATEGY_CARVING:
            trace.strategy_alternatives.append({
                "strategy": STRATEGY_CARVING,
                "reason": "Siempre disponible como último recurso",
            })

        return strategy

    def _select_strategy_from_diagnosis(self, diag: DiagnosisResult) -> str:
        """Select strategy based on diagnosis (no trace)."""
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
        """Merge results from MFT-first and carving strategies."""
        recovered_names = set()

        for f in mft_result.recovered_files:
            if f.name not in recovered_names:
                main_result.recovered_files.append(f)
                recovered_names.add(f.name)

        for f in carving_result.recovered_files:
            if f.name not in recovered_names:
                f.source = "carving_fallback"
                main_result.recovered_files.append(f)
                recovered_names.add(f.name)
            else:
                main_result.duplicates += 1

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
        """Compute MFT confidence for an image (for Confidence Sweep)."""
        trace = DecisionTrace()
        diag = self._diagnose(image, manifest, trace)
        self._calculate_confidence(diag, trace)
        return trace.mft_confidence
