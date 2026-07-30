"""
RecoveryLab — Corruptor Package
"""

from .corruptor import Corruptor, ATTACK_MATRIX
from .models import (
    CorruptionType, CorruptionModel, CorruptionEntry, CorruptionResult,
    get_model, CORRUPTION_MODEL_REGISTRY,
    HeadCrashStartModel, HeadCrashEndModel, ScratchContinuousModel,
    IntermittentSectorsModel, MFTPartialDeleteModel, BitmapCorruptionModel,
    JournalCorruptionModel, CRCErrorsModel, SlowSectorsModel, TimeoutPatternModel,
)

__all__ = [
    'Corruptor', 'ATTACK_MATRIX',
    'CorruptionType', 'CorruptionModel', 'CorruptionEntry', 'CorruptionResult',
    'get_model', 'CORRUPTION_MODEL_REGISTRY',
]
