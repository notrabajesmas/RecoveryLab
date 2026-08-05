"""
RecoveryLab — Strategy C: Signature Carving
============================================
Signature-based scan. No metadata preservation.
Reads entire image — most expensive but finds everything.

Capabilities: sha256, file_size
Cost: 10.0x (reads entire image)
Motor: MotorCarving
"""
from motors.motor_carving import MotorCarving
from motors.base_motor import BaseMotor


class StrategyC(MotorCarving):
    """
    Strategy C: Signature carving.

    Wraps MotorCarving with strategy-level naming.
    Finds files by their binary signatures — no metadata.
    """

    @property
    def name(self) -> str:
        return "Strategy C (Carving)"

    @property
    def description(self) -> str:
        return "Signature-based scan. No metadata preservation. Reads entire image. 19 format signatures."

    @property
    def strategy_id(self) -> str:
        return "C"

    @property
    def capabilities(self):
        return {"sha256", "file_size"}

    @property
    def cost(self) -> float:
        return 10.0
