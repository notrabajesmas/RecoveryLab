#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RecoveryLab — Strategy Engine
================================
Treats recovery motors as strategies with configurable priority.

Recovery Engine
├── Strategy A: MFT
├── Strategy B: Journal
├── Strategy C: Signature Carving
├── Strategy D: Fragment Recovery (Sprint 4)
└── Strategy E: Hybrid

Each strategy declares:
  - name: What it does
  - capabilities: What metadata it can preserve (drives RFS)
  - priority: Default order (user-configurable)
  - cost: Relative read budget cost

The engine runs strategies in priority order, accumulating results.
If Strategy A (MFT) finds 95% of files, Strategy B (Journal) only
runs on the 5% that MFT missed.

This is much more flexible than hard-coded motor fallback thresholds.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Any, Type
from enum import Enum


class StrategyCapability(Enum):
    """What a strategy can preserve during recovery."""
    FILENAME = "filename"
    SHA256 = "sha256"
    TIMESTAMPS = "timestamps"
    DIRECTORY = "directory"
    FILE_SIZE = "file_size"
    ACL = "acl"
    ADS = "ads"
    USN_HISTORY = "usn_history"
    EA = "ea"
    DATA_RUNS = "data_runs"
    DELETED_FILES = "deleted_files"
    HISTORICAL_META = "historical_meta"
    FRAGMENTS = "fragments"


@dataclass
class RecoveryStrategy:
    """A recovery strategy with declared capabilities and cost.

    This wraps the existing motors in a strategy abstraction,
    making priority ordering explicit and user-configurable.
    """
    name: str
    description: str
    capabilities: Set[StrategyCapability]
    priority: int = 1               # 1 = highest priority
    cost: float = 1.0               # Relative cost (MFT=1.0, Carving=10.0)
    min_confidence: float = 0.0     # Minimum data quality to activate
    motor_class: Optional[str] = None  # Reference to motor class (lazy load)

    @property
    def can_preserve(self) -> Set[str]:
        """Human-readable capability names."""
        return {cap.value for cap in self.capabilities}


# ─── Strategy Definitions ────────────────────────────────────────────────────

STRATEGY_MFT = RecoveryStrategy(
    name="MFT",
    description="Parse MFT entries for filenames, timestamps, data runs. Targeted reads.",
    capabilities={
        StrategyCapability.FILENAME,
        StrategyCapability.SHA256,
        StrategyCapability.TIMESTAMPS,
        StrategyCapability.DIRECTORY,
        StrategyCapability.FILE_SIZE,
        StrategyCapability.ACL,
        StrategyCapability.DATA_RUNS,
        StrategyCapability.DELETED_FILES,
    },
    priority=1,
    cost=1.0,
    motor_class="motors.motor_b_mft_first.MotorBMFTFirst",
)

STRATEGY_JOURNAL = RecoveryStrategy(
    name="Journal",
    description="Parse $UsnJrnl for change history, deleted files, renames.",
    capabilities={
        StrategyCapability.FILENAME,
        StrategyCapability.TIMESTAMPS,
        StrategyCapability.DIRECTORY,
        StrategyCapability.USN_HISTORY,
        StrategyCapability.DELETED_FILES,
        StrategyCapability.HISTORICAL_META,
    },
    priority=2,
    cost=1.5,   # Slightly more expensive (needs MFT + journal parse)
    motor_class="motors.motor_b_mft_first.MotorBMFTFirst",  # Journal is a fallback of Motor B
)

STRATEGY_CARVING = RecoveryStrategy(
    name="Carving",
    description="Signature-based scan. No metadata preservation. Reads everything.",
    capabilities={
        StrategyCapability.SHA256,
        StrategyCapability.FILE_SIZE,
    },
    priority=3,
    cost=10.0,  # Very expensive — reads entire image
    motor_class="motors.motor_carving.MotorCarving",
)

STRATEGY_FRAGMENT = RecoveryStrategy(
    name="Fragment",
    description="Reconstruct files from multiple data runs, sparse/compressed runs.",
    capabilities={
        StrategyCapability.FILENAME,
        StrategyCapability.SHA256,
        StrategyCapability.DATA_RUNS,
        StrategyCapability.FRAGMENTS,
    },
    priority=2,  # Same priority as journal — both complement MFT
    cost=2.0,
    motor_class=None,  # Not implemented yet (Sprint 4)
)

STRATEGY_HYBRID = RecoveryStrategy(
    name="Hybrid",
    description="Orchestrated: MFT + Journal + Carving with adaptive delegation.",
    capabilities={
        StrategyCapability.FILENAME,
        StrategyCapability.SHA256,
        StrategyCapability.TIMESTAMPS,
        StrategyCapability.DIRECTORY,
        StrategyCapability.FILE_SIZE,
        StrategyCapability.ACL,
        StrategyCapability.ADS,
        StrategyCapability.USN_HISTORY,
        StrategyCapability.DELETED_FILES,
        StrategyCapability.HISTORICAL_META,
    },
    priority=0,  # Meta-strategy — orchestrates others
    cost=5.0,
    motor_class="motors.motor_c_orchestrator.MotorCOrchestrator",
)


# ─── Strategy Engine ─────────────────────────────────────────────────────────

@dataclass
class StrategyProfile:
    """A named profile of strategy priorities.

    Example:
        Profile "conservative":
          1. MFT (cheap, precise)
          2. Journal (moderate cost)
          3. Carving (expensive, last resort)

        Profile "aggressive":
          1. Carving (find everything first)
          2. MFT (add metadata)
          3. Journal (add history)
    """
    name: str
    description: str
    strategies: List[RecoveryStrategy] = field(default_factory=list)

    def by_priority(self) -> List[RecoveryStrategy]:
        """Return strategies sorted by priority (ascending = most important first)."""
        return sorted(self.strategies, key=lambda s: s.priority)

    def capabilities_union(self) -> Set[str]:
        """Union of all strategy capabilities in this profile."""
        result = set()
        for s in self.strategies:
            result |= s.can_preserve
        return result

    def summary(self) -> str:
        """Visual summary of the profile."""
        lines = [f"Profile: {self.name}"]
        lines.append(f"  {self.description}")
        lines.append("")
        for i, s in enumerate(self.by_priority(), 1):
            caps = ", ".join(sorted(s.can_preserve))
            lines.append(f"  {i}. {s.name} (cost={s.cost:.1f})")
            lines.append(f"     Preserves: {caps}")
        lines.append("")
        lines.append(f"  Combined capabilities: {', '.join(sorted(self.capabilities_union()))}")
        return "\n".join(lines)


# ─── Pre-defined Profiles ───────────────────────────────────────────────────

PROFILE_MFT_FIRST = StrategyProfile(
    name="mft_first",
    description="MFT → Journal → Carving. Best for healthy/lightly damaged disks.",
    strategies=[STRATEGY_MFT, STRATEGY_JOURNAL, STRATEGY_CARVING],
)

PROFILE_JOURNAL_FIRST = StrategyProfile(
    name="journal_first",
    description="Journal → MFT → Carving. Best for recently deleted files.",
    strategies=[
        RecoveryStrategy(name="Journal", **{k: getattr(STRATEGY_JOURNAL, k) for k in ["description", "capabilities", "cost", "motor_class"]}, priority=1),
        RecoveryStrategy(name="MFT", **{k: getattr(STRATEGY_MFT, k) for k in ["description", "capabilities", "cost", "motor_class"]}, priority=2),
        STRATEGY_CARVING,
    ],
)

PROFILE_CARVING_FIRST = StrategyProfile(
    name="carving_first",
    description="Carving → MFT metadata → Journal history. Best for heavily damaged disks.",
    strategies=[
        RecoveryStrategy(name="Carving", **{k: getattr(STRATEGY_CARVING, k) for k in ["description", "capabilities", "motor_class"]}, priority=1, cost=10.0),
        RecoveryStrategy(name="MFT", **{k: getattr(STRATEGY_MFT, k) for k in ["description", "capabilities", "cost", "motor_class"]}, priority=2),
        RecoveryStrategy(name="Journal", **{k: getattr(STRATEGY_JOURNAL, k) for k in ["description", "capabilities", "cost", "motor_class"]}, priority=3),
    ],
)

PROFILE_FULL = StrategyProfile(
    name="full",
    description="MFT → Journal → Fragment → Carving. Maximum recovery.",
    strategies=[STRATEGY_MFT, STRATEGY_JOURNAL, STRATEGY_FRAGMENT, STRATEGY_CARVING],
)


# ─── Strategy Engine ─────────────────────────────────────────────────────────

class StrategyEngine:
    """
    The Strategy Engine orchestrates recovery strategies.

    Instead of hard-coded fallback thresholds in Motor B, this engine:
      1. Takes a StrategyProfile (ordered list of strategies)
      2. Runs each strategy in priority order
      3. Accumulates results (skipping files already recovered)
      4. Computes RR and RFS for the combined result

    Future: user can configure custom profiles:
      Recovery Strategy: ☑ MFT  ☑ Journal  ☑ Carving
      Priority: 1, 2, 3
    """

    def __init__(self, profile: StrategyProfile = None):
        self.profile = profile or PROFILE_MFT_FIRST

    def list_strategies(self) -> List[Dict]:
        """List all available strategies with capabilities."""
        return [
            {
                "name": s.name,
                "priority": s.priority,
                "cost": s.cost,
                "capabilities": sorted(s.can_preserve),
                "description": s.description,
            }
            for s in self.profile.by_priority()
        ]

    def rfs_upper_bound(self) -> float:
        """
        Maximum possible RFS given this profile's combined capabilities.

        This tells you the best possible fidelity achievable with
        these strategies. If the profile doesn't include Journal,
        the USN History component will always be ✗.
        """
        all_caps = self.profile.capabilities_union()
        try:
            from .fidelity import DEFAULT_WEIGHTS
        except ImportError:
            from recovery_judge.fidelity import DEFAULT_WEIGHTS
        max_rfs = 0.0
        cap_to_weight = {
            "filename": "filename",
            "sha256": "sha256",
            "timestamps": "timestamps",
            "directory": "directory",
            "file_size": "file_size",
            "acl": "acl",
            "ads": "ads",
            "usn_history": "usn_history",
            "ea": "ea",
        }
        for cap_name, weight_name in cap_to_weight.items():
            if cap_name in all_caps:
                max_rfs += DEFAULT_WEIGHTS.get(weight_name, 0.0)
        return max_rfs


if __name__ == "__main__":
    print("=" * 70)
    print("RecoveryLab — Strategy Engine")
    print("=" * 70)
    print()

    # Show available strategies
    for name, strat in [("MFT", STRATEGY_MFT), ("Journal", STRATEGY_JOURNAL),
                         ("Carving", STRATEGY_CARVING), ("Fragment", STRATEGY_FRAGMENT)]:
        print(f"Strategy: {name}")
        print(f"  Preserves: {', '.join(sorted(strat.can_preserve))}")
        print(f"  Cost: {strat.cost:.1f}x")
        print()

    # Show profiles
    print("─" * 70)
    for profile in [PROFILE_MFT_FIRST, PROFILE_JOURNAL_FIRST, PROFILE_CARVING_FIRST, PROFILE_FULL]:
        print(profile.summary())
        engine = StrategyEngine(profile)
        print(f"  Max RFS: {engine.rfs_upper_bound():.3f}")
        print()

    # Show what each profile can and cannot preserve
    print("─" * 70)
    try:
        from recovery_judge.fidelity import DEFAULT_WEIGHTS as _DW
    except ImportError:
        from .fidelity import DEFAULT_WEIGHTS as _DW
    print("RFS upper bound by profile:")
    print()
    for profile in [PROFILE_MFT_FIRST, PROFILE_CARVING_FIRST, PROFILE_FULL]:
        engine = StrategyEngine(profile)
        rfs_max = engine.rfs_upper_bound()
        missing = set(_DW.keys()) - profile.capabilities_union()
        print(f"  {profile.name:20s}  Max RFS = {rfs_max:.3f}  Missing: {', '.join(sorted(missing)) if missing else 'none'}")
