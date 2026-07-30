"""
RecoveryLab — Corruptor
========================
Applies corruption patterns to disk images based on real failure models.

Each corruption is logged exactly — reproducibility is paramount.

Usage:
    from corruptor import Corruptor
    corruptor = Corruptor(seed=42)
    result = corruptor.apply(image_bytes, manifest, corruption_type="mft_partial_delete", severity=0.40)
    # result.corrupted_image  — the corrupted image
    # result.corruption_log   — exact log of what was changed
    # result.manifest_corruption — info to add to manifest
"""

import json
import random
import hashlib
import copy
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone

from .models import (
    CorruptionType, CorruptionModel, CorruptionEntry, CorruptionResult,
    get_model, CORRUPTION_MODEL_REGISTRY,
)


class Corruptor:
    """
    Applies corruption to disk images with full logging.

    Every corruption is:
      1. Based on a real failure model
      2. Deterministic (seed-based)
      3. Exactly logged (sectors, clusters, bytes, severity)
      4. Reproducible (same seed + same image → same result)
    """

    def __init__(self, seed: int = 42, output_dir: Optional[Path] = None):
        self.seed = seed
        self.rng = random.Random(seed)
        self.output_dir = output_dir

    def apply(self, image: bytes, manifest: Dict,
              corruption_type: str,
              severity: float = 0.40,
              **kwargs) -> CorruptionResult:
        """
        Apply a single corruption pattern to an image.

        Args:
            image: Raw disk image bytes
            manifest: Ground truth manifest dict
            corruption_type: One of the CorruptionType values
            severity: How severe the corruption should be (0.0-1.0)
            **kwargs: Additional parameters for specific models

        Returns:
            CorruptionResult with corrupted image, log, and manifest data
        """
        # Convert string to enum
        if isinstance(corruption_type, str):
            corruption_type = CorruptionType(corruption_type)

        # Create a seeded model instance
        model_seed = self.rng.randint(0, 2**32 - 1)
        model = get_model(corruption_type, seed=model_seed)

        # Apply corruption
        image_copy = bytearray(image)
        result = model.apply(image_copy, manifest, severity=severity, **kwargs)

        return result

    def apply_scenario(self, image: bytes, manifest: Dict,
                       scenario: Dict) -> CorruptionResult:
        """
        Apply a complete corruption scenario (multiple corruptions).

        Args:
            scenario: Dict with "name", "corruptions" list
                Each corruption has "type", "severity", and optional kwargs

        Returns:
            Combined CorruptionResult
        """
        all_logs = []
        all_manifest_corruptions = []
        current_image = bytearray(image)

        for corr in scenario["corruptions"]:
            ctype = corr["type"]
            severity = corr.get("severity", 0.40)
            kwargs = {k: v for k, v in corr.items() if k not in ("type", "severity")}

            result = self.apply(bytes(current_image), manifest,
                              corruption_type=ctype, severity=severity, **kwargs)

            current_image = bytearray(result.corrupted_image)
            all_logs.extend(result.corruption_log)
            all_manifest_corruptions.append(result.manifest_corruption)

        return CorruptionResult(
            corrupted_image=bytes(current_image),
            corruption_log=all_logs,
            manifest_corruption={
                "scenario_name": scenario.get("name", "unnamed"),
                "corruptions_applied": all_manifest_corruptions,
            },
        )

    def apply_attack_matrix(self, image: bytes, manifest: Dict,
                            attacks: List[Dict]) -> Dict[str, CorruptionResult]:
        """
        Apply the full attack matrix (A1-A14 from Fase 3.5).

        Each attack is designed to try to refute H1.

        Args:
            attacks: List of attack dicts with "id", "name", "corruptions"

        Returns:
            Dict mapping attack_id → CorruptionResult
        """
        results = {}

        for attack in attacks:
            attack_id = attack["id"]
            print(f"  Applying attack {attack_id}: {attack['name']}")

            result = self.apply_scenario(image, manifest, attack)
            results[attack_id] = result

        return results

    def save_corrupted_image(self, result: CorruptionResult,
                             base_name: str, index: int = 0) -> Path:
        """Save a corrupted image and its corruption log."""
        if self.output_dir is None:
            from config import CORRUPTED_DIR
            self.output_dir = CORRUPTED_DIR

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Save corrupted image
        img_path = self.output_dir / f"{base_name}_corrupted_{index:03d}.img"
        with open(img_path, 'wb') as f:
            f.write(result.corrupted_image)

        # Save corruption log
        log_path = self.output_dir / f"{base_name}_corruption_log_{index:03d}.json"
        log_data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "corruptor_seed": self.seed,
            "entries": [
                {
                    "type": e.type.value,
                    "description": e.description,
                    "sectors_affected": e.sectors_affected[:100],  # Limit for JSON size
                    "clusters_affected": e.clusters_affected[:100],
                    "byte_range": list(e.byte_range),
                    "severity": e.severity,
                    "details": e.details,
                }
                for e in result.corruption_log
            ],
            "manifest_corruption": result.manifest_corruption,
        }
        with open(log_path, 'w') as f:
            json.dump(log_data, f, indent=2, default=str)

        return img_path


# ─── Predefined Attack Matrix ─────────────────────────────────────────────────

ATTACK_MATRIX = [
    {
        "id": "A01",
        "name": "MFT 20% destruido",
        "description": "Si MFT está parcialmente dañado, ¿Motor B sigue siendo mejor?",
        "corruptions": [
            {"type": "mft_partial_delete", "severity": 0.20},
        ],
    },
    {
        "id": "A02",
        "name": "MFT 40% destruido",
        "description": "MFT significativamente dañado — ¿fallback cascade funciona?",
        "corruptions": [
            {"type": "mft_partial_delete", "severity": 0.40},
        ],
    },
    {
        "id": "A03",
        "name": "MFT 60% destruido",
        "description": "MFT mayormente dañado — ¿Motor B colapsa?",
        "corruptions": [
            {"type": "mft_partial_delete", "severity": 0.60},
        ],
    },
    {
        "id": "A04",
        "name": "Bitmap eliminado",
        "description": "Sin bitmap, ¿Motor B puede seguir funcionando?",
        "corruptions": [
            {"type": "bitmap_corruption", "severity": 1.0},
        ],
    },
    {
        "id": "A05",
        "name": "Journal corrupto",
        "description": "Sin journal, ¿la recuperación de MFT se degrada?",
        "corruptions": [
            {"type": "journal_corruption", "severity": 1.0},
        ],
    },
    {
        "id": "A06",
        "name": "Head crash inicio",
        "description": "Daño en primeros sectores — ¿MFT sobrevive?",
        "corruptions": [
            {"type": "head_crash_start", "severity": 0.05},
        ],
    },
    {
        "id": "A07",
        "name": "Head crash final",
        "description": "Daño en últimos sectores — datos de usuario afectados",
        "corruptions": [
            {"type": "head_crash_end", "severity": 0.05},
        ],
    },
    {
        "id": "A08",
        "name": "Scratch continuo",
        "description": "Zona continua de daño — ¿archivos en esa zona se pierden?",
        "corruptions": [
            {"type": "scratch_continuous", "severity": 0.05},
        ],
    },
    {
        "id": "A09",
        "name": "Sectores intermitentes",
        "description": "Cada N-ésimo sector falla — ¿lecturas desperdiciadas?",
        "corruptions": [
            {"type": "intermittent_sectors", "severity": 0.02},
        ],
    },
    {
        "id": "A10",
        "name": "CRC errors",
        "description": "Bit flips aleatorios — ¿datos corruptos detectados?",
        "corruptions": [
            {"type": "crc_errors", "severity": 0.005},
        ],
    },
    {
        "id": "A11",
        "name": "MFT + Bitmap destruidos",
        "description": "Combinación: ¿Motor B sin sus dos fuentes principales?",
        "corruptions": [
            {"type": "mft_partial_delete", "severity": 0.40},
            {"type": "bitmap_corruption", "severity": 1.0},
        ],
    },
    {
        "id": "A12",
        "name": "MFT + Journal + Bitmap",
        "description": "Triple ataque: ¿solo queda carving?",
        "corruptions": [
            {"type": "mft_partial_delete", "severity": 0.40},
            {"type": "journal_corruption", "severity": 1.0},
            {"type": "bitmap_corruption", "severity": 1.0},
        ],
    },
    {
        "id": "A13",
        "name": "Sectores lentos + MFT parcial",
        "description": "Simula disco moribundo: MFT parcial + lecturas lentas",
        "corruptions": [
            {"type": "mft_partial_delete", "severity": 0.20},
            {"type": "slow_sectors", "severity": 0.02},
        ],
    },
    {
        "id": "A14",
        "name": "Timeout + MFT parcial",
        "description": "Presupuesto de lectura limitado: timeouts + MFT parcial",
        "corruptions": [
            {"type": "mft_partial_delete", "severity": 0.20},
            {"type": "timeout_pattern", "severity": 0.01},
        ],
    },
]


if __name__ == "__main__":
    import argparse
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from dataset_builder.manifest import load_manifest

    parser = argparse.ArgumentParser(description="RecoveryLab Corruptor")
    parser.add_argument("--image", required=True, help="Path to .img file")
    parser.add_argument("--manifest", required=True, help="Path to manifest.json")
    parser.add_argument("--attack", default=None, help="Attack ID (e.g. A01)")
    parser.add_argument("--all-attacks", action="store_true", help="Run all attacks")
    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()

    with open(args.image, 'rb') as f:
        image = f.read()
    manifest = load_manifest(Path(args.manifest))

    corruptor = Corruptor(seed=args.seed)

    if args.all_attacks:
        results = corruptor.apply_attack_matrix(image, manifest, ATTACK_MATRIX)
        for attack_id, result in results.items():
            path = corruptor.save_corrupted_image(result, "attack", int(attack_id[1:]))
            print(f"  {attack_id}: {path}")
    elif args.attack:
        attack = next(a for a in ATTACK_MATRIX if a["id"] == args.attack)
        result = corruptor.apply_scenario(image, manifest, attack)
        path = corruptor.save_corrupted_image(result, "attack", int(args.attack[1:]))
        print(f"  {args.attack}: {path}")
