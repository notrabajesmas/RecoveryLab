"""
RecoveryLab — Strategies Package
=================================
Treats recovery motors as first-class strategies with configurable priority.

Recovery Engine
├── Strategy A: MFT          — Parse MFT entries, targeted reads
├── Strategy B: Journal      — USN Journal for deleted/renamed files
├── Strategy C: Carving      — Signature-based scan, no metadata
├── Strategy D: Fragment     — Reconstruct from multiple data runs
└── Strategy E: Hybrid       — Orchestrated adaptive delegation

Each strategy is a thin wrapper over the corresponding motor,
adding strategy-level metadata (capabilities, cost, priority).

Usage:
    from strategies import StrategyA, StrategyB, StrategyC, StrategyD, StrategyE

    # Run a single strategy
    result = StrategyA().recover(image, manifest)

    # Run a profile (ordered combination)
    from recovery_judge.strategy_engine import PROFILE_MFT_FIRST, StrategyEngine
    engine = StrategyEngine(PROFILE_MFT_FIRST)
"""

# Strategy A: MFT — uses Motor B (MFT-First) as its core
from .strategy_a_mft import StrategyA

# Strategy B: Journal — uses Motor B's journal fallback
from .strategy_b_journal import StrategyB

# Strategy C: Carving — uses MotorCarving
from .strategy_c_carving import StrategyC

# Strategy D: Fragment — reconstructs files from multiple data runs
from .strategy_d_fragment import StrategyD

# Strategy E: Hybrid — uses MotorCOrchestrator
from .strategy_e_hybrid import StrategyE

__all__ = [
    'StrategyA', 'StrategyB', 'StrategyC', 'StrategyD', 'StrategyE',
]
