"""
RecoveryLab — Strategy A: MFT
================================
Parse MFT entries for filenames, timestamps, data runs.
Read ONLY clusters referenced by MFT — minimal I/O.

Capabilities: filename, sha256, timestamps, directory, file_size, acl, data_runs, deleted_files
Cost: 1.0x (cheapest — targeted reads)
Motor: MotorBMFTFirst
"""
from motors.motor_b_mft_first import MotorBMFTFirst
from motors.base_motor import BaseMotor


class StrategyA(MotorBMFTFirst):
    """
    Strategy A: MFT-first recovery.

    Wraps Motor B with strategy-level naming.
    The motor already does MFT → Journal → INDX → Bitmap → Carving fallback.
    """

    @property
    def name(self) -> str:
        return "Strategy A (MFT)"

    @property
    def description(self) -> str:
        return "MFT-first: parse MFT entries, read only referenced clusters. Fallback cascade when MFT damaged."

    @property
    def strategy_id(self) -> str:
        return "A"

    @property
    def capabilities(self):
        return {"filename", "sha256", "timestamps", "directory", "file_size",
                "acl", "data_runs", "deleted_files"}

    @property
    def cost(self) -> float:
        return 1.0
