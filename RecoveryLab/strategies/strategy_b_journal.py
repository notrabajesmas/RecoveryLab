"""
RecoveryLab — Strategy B: Journal
==================================
Parse $UsnJrnl for change history, deleted files, renames.
Used as fallback when MFT is partially damaged.

Capabilities: filename, timestamps, directory, usn_history, deleted_files, historical_meta
Cost: 1.5x (needs MFT + journal parse)
Motor: MotorBMFTFirst (journal fallback path)
"""
from motors.motor_b_mft_first import MotorBMFTFirst
from motors.base_motor import BaseMotor


class StrategyB(MotorBMFTFirst):
    """
    Strategy B: Journal-based recovery.

    Uses Motor B but forces journal fallback as primary path.
    Best for recently deleted files and renamed files.
    """

    @property
    def name(self) -> str:
        return "Strategy B (Journal)"

    @property
    def description(self) -> str:
        return "Journal-first: use $UsnJrnl to find deleted/renamed files, then recover from MFT records."

    @property
    def strategy_id(self) -> str:
        return "B"

    @property
    def capabilities(self):
        return {"filename", "timestamps", "directory", "usn_history",
                "deleted_files", "historical_meta"}

    @property
    def cost(self) -> float:
        return 1.5
