#!/usr/bin/env python3
"""
DIAG-0001 Deep Dive — Investigar por qué PDF carving falla
============================================================
El DIAG-0001 inicial reveló:
  - ZIP: Carving OU = 1.0 (perfecto)
  - DOCX: Carving OU = 1.0 (perfecto)
  - PDF: Carving OU = 0.0 (15 firmas encontradas, 15 carved, 0 match)
  - JPEG/PNG: Dataset builder falló (volumen insuficiente)

Este script investiga POR QUÉ PDF carving falla:
  1. ¿Los archivos carved tienen el mismo tamaño que los originales?
  2. ¿Los archivos carved tienen los mismos bytes que los originales?
  3. ¿Dónde está la diferencia exacta?
  4. ¿Es un problema de footer detection? ¿De padding? ¿De offset?

También construye datasets JPEG/PNG con volumen más grande.
"""

import sys
import os
import json
import hashlib
import time
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RECOVERYLAB_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(RECOVERYLAB_ROOT))

from dataset_builder.builder import DatasetBuilder
from dataset_builder.manifest import load_manifest, save_manifest
from motors.motor_carving import MotorCarving
from motors.motor_b_mft_first import MotorBMFTFirst
from recovery_judge.judge import RecoveryJudge
from recovery_judge.fqs import compute_overall_utility


def investigate_pdf_carving():
    """Deep dive into why PDF carving produces wrong SHA-256."""
    print("=" * 70)
    print("DIAG-0001 Deep Dive: PDF Carving Investigation")
    print("=" * 70)
    print()

    # Build PDF dataset
    print("[1] Building PDF dataset...")
    builder = DatasetBuilder(
        seed=42,
        num_images=1,
        volume_size=10 * 1024 * 1024,
        cluster_size=4096,
        files_per_image=15,
    )
    image, manifest = builder.build_single_format_dataset(
        extension=".pdf",
        n_files=15,
    )
    print(f"  Image size: {len(image)} bytes")
    print(f"  Files in manifest: {len(manifest.get('files', []))}")
    print()

    # Run carving
    print("[2] Running Carving motor...")
    motor = MotorCarving()
    result = motor.recover(image, manifest, read_budget=0)
    print(f"  Carved files: {len(result.recovered_files)}")
    print(f"  Carving stats: {getattr(result, 'carving_stats', {})}")
    print()

    # Build ground truth lookup
    gt_files = {}
    for f in manifest.get("files", []):
        if not f.get("is_directory", False) and f.get("sha256"):
            gt_files[f["sha256"]] = f

    # Compare each carved file with ground truth
    print("[3] Comparing carved files with ground truth...")
    print()

    for i, rf in enumerate(result.recovered_files):
        # Find the corresponding ground truth file
        # Since we know the PDFs are in order, we can match by index
        gt_file = None
        if i < len(manifest.get("files", [])):
            gt_file = manifest["files"][i]

        if gt_file is None:
            print(f"  {rf.name}: No ground truth match (index {i})")
            continue

        # Check SHA-256
        if rf.sha256 == gt_file.get("sha256", ""):
            print(f"  {rf.name}: SHA-256 MATCH")
            continue

        # SHA-256 mismatch — investigate
        print(f"  {rf.name}: SHA-256 MISMATCH")
        print(f"    Carved SHA-256:   {rf.sha256}")
        print(f"    Ground truth SHA:  {gt_file.get('sha256', 'N/A')}")
        print(f"    Carved size:       {rf.size}")
        print(f"    Ground truth size: {gt_file.get('size', 'N/A')}")

        # Compare sizes
        size_diff = rf.size - gt_file.get("size", 0)
        print(f"    Size difference:   {size_diff} bytes")

        # Check header
        if rf.data:
            print(f"    Carved header:     {rf.data[:20].hex()}")
            print(f"    Carved starts with %PDF-: {rf.data[:5] == b'%PDF-'}")

            # Check footer
            if rf.data.endswith(b'%%EOF\n'):
                print(f"    Carved ends with %%EOF\\n: True")
            elif rf.data.endswith(b'%%EOF'):
                print(f"    Carved ends with %%EOF: True")
            elif rf.data.rstrip(b'\x00').endswith(b'%%EOF\n'):
                print(f"    Carved ends with %%EOF\\n (after stripping nulls): True")
            elif rf.data.rstrip(b'\x00').endswith(b'%%EOF'):
                print(f"    Carved ends with %%EOF (after stripping nulls): True")
            else:
                last_50 = rf.data[-50:]
                print(f"    Carved last 50 bytes: {last_50.hex()}")
                print(f"    Carved last 50 ASCII: {last_50}")

            # Check if the ground truth data is embedded in the carved data
            # The carved data might have extra bytes at the end (cluster padding)
            if gt_file.get("size", 0) > 0 and rf.size > gt_file.get("size", 0):
                truncated = rf.data[:gt_file["size"]]
                truncated_sha = hashlib.sha256(truncated).hexdigest()
                if truncated_sha == gt_file.get("sha256", ""):
                    print(f"    *** TRUNCATED CARVED DATA MATCHES GROUND TRUTH! ***")
                    print(f"    The carved data has {size_diff} extra bytes (cluster padding)")
                    print(f"    The carving motor is including cluster padding after %%EOF")
                else:
                    print(f"    Truncated carved data still doesn't match")
                    print(f"    Truncated SHA-256: {truncated_sha}")

            # Check if the carved data starts with the same bytes as ground truth
            # We need the original file data from the manifest
            # The manifest doesn't store the raw data, so we need to check the image
            # directly at the file's offset
            if gt_file.get("start_cluster") is not None:
                gt_start = gt_file["start_cluster"] * 4096
                gt_size = gt_file.get("size", 0)
                gt_data = image[gt_start:gt_start + gt_size]
                gt_data_sha = hashlib.sha256(gt_data).hexdigest()
                print(f"    GT data from image at cluster {gt_file['start_cluster']}: SHA={gt_data_sha}")
                print(f"    GT data from image matches manifest: {gt_data_sha == gt_file.get('sha256', '')}")

                # Compare first 20 bytes
                print(f"    GT data header:    {gt_data[:20].hex()}")

                # Check if carved data matches GT data
                if rf.data[:gt_size] == gt_data:
                    print(f"    Carved data[:gt_size] == GT data: YES")
                else:
                    print(f"    Carved data[:gt_size] == GT data: NO")
                    # Find first differing byte
                    for j in range(min(len(rf.data), len(gt_data))):
                        if rf.data[j] != gt_data[j]:
                            print(f"    First difference at byte {j}: carved={rf.data[j]:02x} gt={gt_data[j]:02x}")
                            print(f"    Context around byte {j}:")
                            start = max(0, j - 5)
                            end = min(len(rf.data), len(gt_data), j + 10)
                            print(f"      Carved: {rf.data[start:end].hex()}")
                            print(f"      GT:     {gt_data[start:end].hex()}")
                            break

        print()


def investigate_jpeg_png_dataset():
    """Build JPEG/PNG datasets with larger volume size."""
    print("=" * 70)
    print("DIAG-0001 Deep Dive: JPEG/PNG Dataset Building")
    print("=" * 70)
    print()

    for ext, name in [(".jpg", "JPEG"), (".png", "PNG")]:
        print(f"[{name}] Building with 50 MB volume...")
        try:
            builder = DatasetBuilder(
                seed=42,
                num_images=1,
                volume_size=50 * 1024 * 1024,  # 50 MB
                cluster_size=4096,
                files_per_image=15,
            )
            image, manifest = builder.build_single_format_dataset(
                extension=ext,
                n_files=15,
            )
            print(f"  Image size: {len(image)} bytes")
            print(f"  Files in manifest: {len(manifest.get('files', []))}")

            # Run carving
            motor = MotorCarving()
            result = motor.recover(image, manifest, read_budget=0)
            print(f"  Carved files: {len(result.recovered_files)}")
            print(f"  Carving stats: {getattr(result, 'carving_stats', {})}")

            # Run MFT-First for comparison
            motor_mft = MotorBMFTFirst()
            result_mft = motor_mft.recover(image, manifest, read_budget=0)

            # Judge both
            judge = RecoveryJudge(manifest)

            judge_input_carving = [{
                "name": f.name, "sha256": f.sha256, "size": f.size,
                "is_directory": f.is_directory, "data": f.data,
            } for f in result.recovered_files]

            judge_input_mft = [{
                "name": f.name, "sha256": f.sha256, "size": f.size,
                "is_directory": f.is_directory, "data": f.data,
            } for f in result_mft.recovered_files]

            metrics_carving = judge.judge(
                recovered_files=judge_input_carving,
                read_count=result.read_count,
                sectors_wasted=result.sectors_wasted,
                time_to_first_file=result.time_to_first_file,
                mft_entries_parsed=result.mft_entries_parsed,
            )

            metrics_mft = judge.judge(
                recovered_files=judge_input_mft,
                read_count=result_mft.read_count,
                sectors_wasted=result_mft.sectors_wasted,
                time_to_first_file=result_mft.time_to_first_file,
                mft_entries_parsed=result_mft.mft_entries_parsed,
            )

            utility_carving = compute_overall_utility(metrics_carving.rvs, metrics_carving.weighted_functional_score)
            utility_mft = compute_overall_utility(metrics_mft.rvs, metrics_mft.weighted_functional_score)

            print(f"  MFT-First OU:  {utility_mft['overall_utility']:.4f}")
            print(f"  Carving OU:    {utility_carving['overall_utility']:.4f}")
            print(f"  Carving files recovered: {metrics_carving.to_dict().get('files_recovered', 0)}")
            print(f"  Carving correct checksum: {metrics_carving.to_dict().get('files_correct_checksum', 0)}")
            print(f"  Carving false positives: {metrics_carving.false_positives}")

            # Check per-file details
            for rf in result.recovered_files:
                gt_match = judge.ground_truth["files_by_name"].get(rf.name)
                match_method = "name"
                if gt_match is None:
                    gt_match = judge.ground_truth["files_by_sha"].get(rf.sha256)
                    match_method = "sha256" if gt_match else "none"
                status = f"→ {gt_match.get('name', 'N/A')} ({match_method})" if gt_match else "UNMATCHED"
                print(f"    {rf.name} (size={rf.size}): {status}")

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
        print()


if __name__ == "__main__":
    investigate_pdf_carving()
    print("\n\n")
    investigate_jpeg_png_dataset()
