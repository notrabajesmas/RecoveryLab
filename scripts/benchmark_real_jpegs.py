#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RecoveryLab — Sprint 2: Benchmark con JPEGs Reales (Directo)
==============================================================
En lugar de construir imágenes NTFS completas (lento), creamos
una imagen raw con JPEGs reales colocados a intervalos de cluster.
El carving motor NO usa NTFS — solo escanea bytes. Esto es válido.

Proceso:
1. Generar JPEGs reales con Pillow
2. Colocarlos en imagen raw a intervalos de cluster
3. Crear manifiesto ground truth
4. Ejecutar MotorCarving
5. Comparar SHA-256
"""

import hashlib
import io
import json
import random
import sys
import time
import gc
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "RecoveryLab"))

from PIL import Image, ImageDraw

# ─── Config ───────────────────────────────────────────────────────────────────

NUM_JPEGS = 1000
CLUSTER_SIZE = 4096
SEED = 42
RESULTS_DIR = Path("/home/z/my-project/RecoveryLab/results")

# ─── JPEG Generator ──────────────────────────────────────────────────────────

def generate_real_jpeg(seed, width, height, quality, mode):
    rng = np.random.RandomState(seed)
    py_rng = random.Random(seed)
    
    if mode == "photo":
        r = rng.randint(30, 200, size=(height, width)).astype(np.uint8)
        g = rng.randint(30, 200, size=(height, width)).astype(np.uint8)
        b = rng.randint(30, 200, size=(height, width)).astype(np.uint8)
        grad = np.linspace(0.3, 1.0, height).reshape(-1, 1)
        arr = np.stack([(r * grad).astype(np.uint8),
                        (g * grad).astype(np.uint8),
                        (b * grad).astype(np.uint8)], axis=2)
        img = Image.fromarray(arr, 'RGB')
        draw = ImageDraw.Draw(img)
        for _ in range(py_rng.randint(2, 8)):
            x1 = py_rng.randint(0, width)
            y1 = py_rng.randint(0, height)
            x2 = min(x1 + py_rng.randint(50, 300), width)
            y2 = min(y1 + py_rng.randint(50, 300), height)
            color = (py_rng.randint(0, 255), py_rng.randint(0, 255), py_rng.randint(0, 255))
            draw.rectangle([x1, y1, x2, y2], fill=color)
    
    elif mode == "landscape":
        arr = np.zeros((height, width, 3), dtype=np.uint8)
        mid = height // 2
        for y in range(mid):
            arr[y, :, 0] = min(255, int(100 + 100 * y / max(mid, 1)))
            arr[y, :, 1] = min(255, int(150 + 80 * y / max(mid, 1)))
            arr[y, :, 2] = min(255, int(200 + 55 * y / max(mid, 1)))
        for y in range(mid, height):
            arr[y, :, 0] = min(255, int(50 + 80 * (y - mid) / max(mid, 1)))
            arr[y, :, 1] = min(255, int(100 + 60 * (y - mid) / max(mid, 1)))
            arr[y, :, 2] = min(255, int(20 + 30 * (y - mid) / max(mid, 1)))
        img = Image.fromarray(arr, 'RGB')
    
    elif mode == "noise":
        arr = rng.randint(0, 256, size=(height, width, 3)).astype(np.uint8)
        img = Image.fromarray(arr, 'RGB')
    
    elif mode == "text":
        img = Image.new("RGB", (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        for _ in range(py_rng.randint(5, 15)):
            tx = py_rng.randint(0, max(1, width - 100))
            ty = py_rng.randint(0, max(1, height - 20))
            draw.text((tx, ty), "Sample text ABC123", fill=(0, 0, 0))
    
    elif mode == "screenshot":
        img = Image.new("RGB", (width, height), color=(240, 240, 240))
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, width, min(30, height // 10)], fill=(0, 120, 215))
        draw.rectangle([10, 40, width - 10, height - 40], fill=(255, 255, 255),
                       outline=(200, 200, 200))
    
    elif mode == "portrait":
        arr = rng.randint(180, 240, size=(height, width, 3)).astype(np.uint8)
        arr[:, :, 2] = (arr[:, :, 2] * 0.7).astype(np.uint8)
        img = Image.fromarray(arr, 'RGB')
    
    else:
        img = Image.new("RGB", (width, height), color=(py_rng.randint(0, 255),) * 3)
    
    buf = io.BytesIO()
    progressive = py_rng.random() > 0.7
    img.save(buf, format="JPEG", quality=quality, progressive=progressive)
    return buf.getvalue()


def run_benchmark():
    print("=" * 70)
    print("  RECOVERYLAB — SPRINT 2: BENCHMARK JPEGs REALES")
    print("=" * 70)
    print(f"  JPEGs: {NUM_JPEGS}")
    print(f"  Método: Directo (raw image + carving motor)")
    print()
    
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    
    # ─── Phase 1: Generate JPEGs and build raw image ─────────────────────
    print("─" * 70)
    print("  PHASE 1: Generando JPEGs reales + imagen raw")
    print("─" * 70)
    
    modes = ["photo", "landscape", "noise", "text", "screenshot", "portrait"]
    mode_weights = [0.30, 0.12, 0.18, 0.12, 0.13, 0.15]
    
    size_categories = [
        ("thumbnail", (100, 100), (200, 200), 60, 80),
        ("small", (320, 240), (640, 480), 65, 90),
        ("medium", (800, 600), (1600, 1200), 70, 95),
        ("large", (1600, 1200), (3000, 2000), 75, 95),
        ("fullsize", (3000, 2000), (5000, 3500), 80, 95),
    ]
    size_weights = [0.15, 0.25, 0.30, 0.20, 0.10]
    
    # We'll process in batches of 100 JPEGs to avoid OOM
    BATCH_SIZE = 100
    num_batches = (NUM_JPEGS + BATCH_SIZE - 1) // BATCH_SIZE
    
    total_correct = 0
    total_corrupt = 0
    total_missing = 0
    total_false_positives = 0
    total_files = 0
    failure_details = []
    per_batch_results = []
    
    t0 = time.time()
    
    for batch_idx in range(num_batches):
        batch_start = batch_idx * BATCH_SIZE
        batch_end = min(batch_start + BATCH_SIZE, NUM_JPEGS)
        batch_count = batch_end - batch_start
        
        # Generate JPEGs for this batch
        jpeg_list = []
        for i in range(batch_start, batch_end):
            mode = rng.choices(modes, weights=mode_weights, k=1)[0]
            cat_name, (min_w, min_h), (max_w, max_h), min_q, max_q = \
                rng.choices(size_categories, weights=size_weights, k=1)[0]
            width = rng.randint(min_w, max_w)
            height = rng.randint(min_h, max_h)
            quality = rng.randint(min_q, max_q)
            jpeg_seed = rng.randint(0, 2**32 - 1)
            
            jpeg_bytes = generate_real_jpeg(jpeg_seed, width, height, quality, mode)
            sha256 = hashlib.sha256(jpeg_bytes).hexdigest()
            
            jpeg_list.append({
                "index": i,
                "sha256": sha256,
                "bytes": jpeg_bytes,
                "size": len(jpeg_bytes),
                "mode": mode,
                "size_category": cat_name,
                "width": width,
                "height": height,
                "quality": quality,
            })
        
        # Build raw image: place JPEGs at cluster-aligned offsets
        # with padding between them
        # Each JPEG gets enough clusters for its data + 1-3 clusters padding
        image_parts = bytearray()
        file_offsets = []  # (offset, size, sha256, index)
        
        # Add some initial padding (simulating NTFS metadata area)
        padding_size = CLUSTER_SIZE * 10  # 10 clusters of padding
        image_parts.extend(b'\x00' * padding_size)
        
        for jd in jpeg_list:
            offset = len(image_parts)
            # Align to cluster boundary
            if offset % CLUSTER_SIZE != 0:
                padding = CLUSTER_SIZE - (offset % CLUSTER_SIZE)
                image_parts.extend(b'\x00' * padding)
                offset = len(image_parts)
            
            # Write JPEG data
            image_parts.extend(jd["bytes"])
            file_offsets.append((offset, jd["size"], jd["sha256"], jd["index"]))
            
            # Add 1-3 clusters of padding between JPEGs
            pad_clusters = rng.randint(1, 3)
            image_parts.extend(b'\x00' * (CLUSTER_SIZE * pad_clusters))
        
        # Add some trailing padding
        image_parts.extend(b'\x00' * (CLUSTER_SIZE * 5))
        
        image_bytes = bytes(image_parts)
        total_clusters = len(image_bytes) // CLUSTER_SIZE
        
        # Build a simple manifest for the carving motor
        manifest = {
            "cluster_size": CLUSTER_SIZE,
            "total_clusters": total_clusters,
            "sector_size": 512,
            "files": [],
            "mft": {"start_cluster": 0, "record_count": 0},
        }
        
        for offset, size, sha256, idx in file_offsets:
            manifest["files"].append({
                "name": f"real_{idx:04d}.jpg",
                "sha256": sha256,
                "size": size,
                "start_cluster": offset // CLUSTER_SIZE,
            })
        
        # ─── Run carving motor ───────────────────────────────────────────
        from motors.motor_carving import MotorCarving
        
        motor = MotorCarving()
        result = motor.recover(image_bytes, manifest)
        
        # ─── Compare results ─────────────────────────────────────────────
        # Build ground truth SHA set
        gt_shas = {fo[2]: fo[3] for fo in file_offsets}  # sha256 -> index
        
        # Check each recovered file
        recovered_shas = set()
        batch_correct = 0
        batch_corrupt = 0
        batch_missing = 0
        batch_fp = 0
        
        for rf in result.recovered_files:
            if rf.sha256 in gt_shas:
                batch_correct += 1
                recovered_shas.add(rf.sha256)
            else:
                # Check if it's a partial match (corrupt)
                # Find the closest ground truth file by offset
                matched = False
                for offset, size, sha256, idx in file_offsets:
                    if offset <= rf.read_count and offset + size > rf.read_count:
                        # Likely a match but wrong SHA
                        if rf.sha256 != sha256:
                            batch_corrupt += 1
                            matched = True
                            failure_details.append({
                                "batch": batch_idx,
                                "index": idx,
                                "name": f"real_{idx:04d}.jpg",
                                "status": "corrupt",
                                "expected_sha256": sha256,
                                "actual_sha256": rf.sha256,
                                "size": rf.size,
                            })
                            break
                
                if not matched:
                    batch_fp += 1
        
        # Find missing files
        for offset, size, sha256, idx in file_offsets:
            if sha256 not in recovered_shas:
                batch_missing += 1
                failure_details.append({
                    "batch": batch_idx,
                    "index": idx,
                    "name": f"real_{idx:04d}.jpg",
                    "status": "missing",
                    "sha256": sha256,
                    "size": size,
                })
        
        total_correct += batch_correct
        total_corrupt += batch_corrupt
        total_missing += batch_missing
        total_false_positives += batch_fp
        total_files += batch_count
        
        elapsed = time.time() - t0
        running_rate = total_correct / total_files if total_files else 0
        print(f"  Batch {batch_idx + 1}/{num_batches}: "
              f"{batch_correct}/{batch_count} correct, "
              f"{batch_corrupt} corrupt, {batch_missing} missing "
              f"| Running: {total_correct}/{total_files} "
              f"({100 * running_rate:.2f}%) [{elapsed:.1f}s]")
        
        per_batch_results.append({
            "batch": batch_idx,
            "correct": batch_correct,
            "corrupt": batch_corrupt,
            "missing": batch_missing,
            "false_positives": batch_fp,
            "total": batch_count,
        })
        
        # Free memory
        del image_parts, image_bytes, jpeg_list, result
        gc.collect()
    
    elapsed = time.time() - t0
    
    # ─── Results ──────────────────────────────────────────────────────────
    print("\n" + "═" * 70)
    print("  RESULTADOS")
    print("═" * 70)
    
    recovery_rate = total_correct / total_files if total_files else 0
    corruption_rate = total_corrupt / total_files if total_files else 0
    missing_rate = total_missing / total_files if total_files else 0
    
    print(f"\n  JPEGs totales:          {total_files}")
    print(f"  Correct (SHA-256):      {total_correct}  ({100 * recovery_rate:.2f}%)")
    print(f"  Corrupt (SHA mismatch): {total_corrupt}  ({100 * corruption_rate:.2f}%)")
    print(f"  Missing:                {total_missing}  ({100 * missing_rate:.2f}%)")
    print(f"  False positives:        {total_false_positives}")
    print(f"  Tiempo total:           {elapsed:.1f}s")
    
    if failure_details:
        print(f"\n  --- ANÁLISIS DE FALLOS ({len(failure_details)} total) ---")
        corrupt = [f for f in failure_details if f["status"] == "corrupt"]
        missing = [f for f in failure_details if f["status"] == "missing"]
        
        if corrupt:
            print(f"\n  Corruptos ({len(corrupt)}):")
            for f in corrupt[:20]:
                print(f"    {f['name']} (batch {f['batch']}) size={f['size']}")
            if len(corrupt) > 20:
                print(f"    ... y {len(corrupt) - 20} más")
        
        if missing:
            print(f"\n  Missing ({len(missing)}):")
            for f in missing[:20]:
                print(f"    {f['name']} (batch {f['batch']}) size={f['size']}")
            if len(missing) > 20:
                print(f"    ... y {len(missing) - 20} más")
    
    # Verdict
    print(f"\n" + "═" * 70)
    print(f"  VEREDICTO")
    print(f"═" * 70)
    
    if recovery_rate >= 0.999:
        verdict = "A"
        print(f"\n  ★ CASO A: {100 * recovery_rate:.2f}%")
        print(f"  JPEGs reales: prácticamente perfecto.")
        print(f"  El 1/525 fallido en sintéticos NO es un problema real.")
        print(f"  RC-002 puede cerrarse.")
    elif recovery_rate >= 0.95:
        verdict = "B"
        print(f"\n  ◐ CASO B: {100 * recovery_rate:.2f}%")
        print(f"  Hay trabajo que hacer en JPEGs reales.")
    else:
        verdict = "C"
        print(f"\n  ○ CASO C: {100 * recovery_rate:.2f}%")
        print(f"  El problema era más grave de lo esperado.")
    
    # Save
    results = {
        "benchmark": "real_jpeg_benchmark_direct",
        "sprint": 2,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "config": {
            "num_jpegs": NUM_JPEGS,
            "batch_size": BATCH_SIZE,
            "cluster_size": CLUSTER_SIZE,
            "seed": SEED,
        },
        "summary": {
            "total_files": total_files,
            "correct": total_correct,
            "corrupt": total_corrupt,
            "missing": total_missing,
            "false_positives": total_false_positives,
            "recovery_rate": round(recovery_rate, 4),
            "corruption_rate": round(corruption_rate, 4),
            "missing_rate": round(missing_rate, 4),
            "elapsed_seconds": round(elapsed, 1),
        },
        "per_batch": per_batch_results,
        "failures": failure_details[:100],  # Cap at 100 for JSON size
        "verdict": verdict,
    }
    
    results_path = RESULTS_DIR / "benchmark_real_jpegs_results.json"
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results: {results_path}")
    
    return results


if __name__ == "__main__":
    results = run_benchmark()
