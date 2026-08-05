"""
RecoveryLab — Strategy E: Hybrid
==================================
Orchestrated: MFT + Journal + Carving with adaptive delegation.
Diagnoses disk state, selects best strategy, explains reasoning.

Capabilities: filename, sha256, timestamps, directory, file_size, acl, ads, usn_history, deleted_files, historical_meta
Cost: 5.0x (runs multiple strategies)
Motor: MotorCOrchestrator
"""
from motors.motor_c_orchestrator import MotorCOrchestrator
from motors.base_motor import BaseMotor


class StrategyE(MotorCOrchestrator):
    """
    Strategy E: Hybrid (Adaptive Orchestrator).

    Wraps Motor C with strategy-level naming.
    Diagnoses disk state and selects the best strategy
    with full decision trace.
    """

    @property
    def name(self) -> str:
        return "Strategy E (Hybrid)"

    @property
    def description(self) -> str:
        return "Adaptive: diagnose disk, select strategy (MFT/Journal/Carving/Fragment), explain reasoning."

    @property
    def strategy_id(self) -> str:
        return "E"

    @property
    def capabilities(self):
        return {"filename", "sha256", "timestamps", "directory", "file_size",
                "acl", "ads", "usn_history", "deleted_files", "historical_meta"}

    @property
    def cost(self) -> float:
        return 5.0
