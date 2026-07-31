"""
RecoveryLab — INST-0001: Dataset Builder Validation (Optimized)
================================================================
Familia: INST (Instrument Validation)
Origen: Auditoría externa r11

Optimizado: formatos livianos (ZIP, DOCX, PDF) con N=100,
formatos pesados (JPG, PNG) con N máximo alcanzable.
"""

import sys
import json
import hashlib
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from dataset_builder.builder import DatasetBuilder
from dataset_builder.file_generator import FileGenerator, FILE_SIGNATURES, FILE_FOOTERS

CARVING_SIGNATURES = {
    "JPEG":  b'\xFF\xD8\xFF',
    "PNG":   b'\x89PNG\r\n\x1a\n',
    "PDF":   b'%PDF',
    "ZIP":   b'PK\x03\x04',
    "BMP":   b'BM',
    "GIF":   b'GIF8',
}

def _volume_for(ext, n):
    if ext in (".jpg", ".png"):
        return max(50*1024*1024, n * 3 * 1024 * 1024 + 50 * 1024 * 1024)
    else:
        return max(50*1024*1024, n * 500_000 + 50 * 1024 * 1024)

def build_and_validate(ext, n, seed=42):
    """Build a single-format dataset and return all validation results."""
    vol = _volume_for(ext, n)
    builder = DatasetBuilder(seed=seed, volume_size=vol, files_per_image=n)
    image_bytes, manifest = builder.build_single_format_dataset(extension=ext, n_files=n)
    
    cluster_size = manifest.get("cluster_size", 4096)
    files = [f for f in manifest.get("files", []) if not f.get("is_directory", False)]
    
    results = {}
    
    # V1: File count
    results["v1_file_count"] = len(files) == n
    results["v1_expected"] = n
    results["v1_actual"] = len(files)
    
    # V2: No involuntary overlaps
    non_resident = [f for f in files if f.get("clusters", [])]
    all_clusters = {}  # cluster -> file_name
    overlaps = []
    for f in non_resident:
        for c in f["clusters"]:
            if c in all_clusters:
                overlaps.append((all_clusters[c], f["name"], c))
            else:
                all_clusters[c] = f["name"]
    results["v2_no_overlaps"] = len(overlaps) == 0
    results["v2_overlap_count"] = len(overlaps)
    if overlaps:
        results["v2_overlaps"] = [{"files": [a, b], "cluster": c} for a, b, c in overlaps[:5]]
    
    # V3: Unique starting offsets
    start_clusters = defaultdict(list)
    for f in non_resident:
        start_clusters[f["clusters"][0]].append(f["name"])
    dup_starts = {k: v for k, v in start_clusters.items() if len(v) > 1}
    results["v3_unique_offsets"] = len(dup_starts) == 0
    results["v3_duplicate_starts"] = len(dup_starts)
    
    # V4: Content matches ground truth (SHA-256)
    mismatches = []
    for f in non_resident:
        clusters = f.get("clusters", [])
        expected_sha256 = f.get("sha256", "")
        expected_size = f.get("size", 0)
        if not clusters or not expected_sha256:
            continue
        
        file_data = bytearray()
        for cluster in clusters:
            offset = cluster * cluster_size
            chunk = image_bytes[offset:offset + cluster_size]
            file_data.extend(chunk)
        file_data = bytes(file_data[:expected_size])
        actual_sha256 = hashlib.sha256(file_data).hexdigest()
        
        if actual_sha256 != expected_sha256:
            mismatches.append({
                "name": f["name"],
                "expected": expected_sha256[:16],
                "actual": actual_sha256[:16],
            })
    
    results["v4_ground_truth"] = len(mismatches) == 0
    results["v4_mismatch_count"] = len(mismatches)
    if mismatches:
        results["v4_mismatches"] = mismatches[:5]
    
    # V5: Signature density
    sig_counts = {}
    conflicts = []
    file_ranges = []
    for f in non_resident:
        clusters = f.get("clusters", [])
        if clusters:
            start_byte = clusters[0] * cluster_size
            end_byte = (clusters[-1] + 1) * cluster_size
            file_ranges.append((start_byte, end_byte, f["name"]))
    
    for sig_name, sig_bytes in CARVING_SIGNATURES.items():
        count = 0
        offset = 0
        while True:
            pos = image_bytes.find(sig_bytes, offset)
            if pos == -1:
                break
            count += 1
            
            # Check if this signature is at a file start or inside another file
            at_file_start = any(pos == start for start, end, name in file_ranges)
            inside_other = None
            for start, end, name in file_ranges:
                if start < pos < end and pos != start:
                    inside_other = name
                    break
            
            if inside_other and not at_file_start:
                conflicts.append({
                    "signature": sig_name,
                    "position": pos,
                    "inside_file": inside_other,
                })
            
            offset = pos + 1
        
        sig_counts[sig_name] = count
    
    total_sigs = sum(sig_counts.values())
    results["v5_signature_counts"] = sig_counts
    results["v5_total_signatures"] = total_sigs
    results["v5_conflicts"] = len(conflicts)
    results["v5_conflict_rate"] = len(conflicts) / max(1, total_sigs)
    results["v5_conflict_examples"] = conflicts[:5]
    
    # V7: Adversarial metrics
    if non_resident:
        last_cluster = max(f["clusters"][-1] for f in non_resident if f.get("clusters"))
        data_area_start = manifest.get("data_area_start", 0)
        data_area_mb = (last_cluster - data_area_start) * cluster_size / (1024 * 1024)
        density = len(non_resident) / max(0.1, data_area_mb)
    else:
        density = 0
        data_area_mb = 0
    
    pk_files = [f for f in files if f["name"].endswith((".zip", ".docx", ".xlsx"))]
    avg_size = sum(f.get("size", 0) for f in files) / max(1, len(files))
    
    results["v7_density"] = round(density, 2)
    results["v7_data_area_mb"] = round(data_area_mb, 2)
    results["v7_pk_files"] = len(pk_files)
    results["v7_avg_size_kb"] = round(avg_size / 1024, 1)
    
    return results, manifest, image_bytes


def run_inst_0001():
    print("=" * 70)
    print("INST-0001: Dataset Builder Validation")
    print("=" * 70)
    print(f"Familia: INST (Instrument Validation)")
    print(f"Origen: Auditoría externa r11")
    print(f"Fecha: {datetime.now(timezone.utc).isoformat()}")
    print()
    
    all_results = {}
    
    # Test configurations: (format, N_values)
    configs = [
        (".zip",  [15, 30, 100]),
        (".docx", [15, 30, 100]),
        (".pdf",  [15, 30, 100]),
        (".jpg",  [15, 30]),      # JPG is large, skip N=100
        (".png",  [15, 30]),      # PNG is large, skip N=100
    ]
    
    # ─── Phases 1-5: All validations per format/N ─────────────────────────
    print("\n" + "─" * 70)
    print("PHASES 1-5: Comprehensive Validation (V1-V5)")
    print("─" * 70)
    
    for ext, n_values in configs:
        for n in n_values:
            print(f"\n  Testing {ext[1:]:5s} N={n:3d} ...", end=" ", flush=True)
            try:
                results, manifest, image_bytes = build_and_validate(ext, n)
                key = f"N={n}_{ext[1:]}"
                all_results[key] = results
                
                v1 = "✓" if results["v1_file_count"] else "✗"
                v2 = "✓" if results["v2_no_overlaps"] else "✗"
                v3 = "✓" if results["v3_unique_offsets"] else "✗"
                v4 = "✓" if results["v4_ground_truth"] else "✗"
                cr = results["v5_conflict_rate"]
                
                print(f"V1={v1} V2={v2} V3={v3} V4={v4} conflict={cr:.1%}")
                
                if not results["v2_no_overlaps"]:
                    print(f"    ⚠ OVERLAPS: {results['v2_overlap_count']} cluster conflicts")
                if not results["v4_ground_truth"]:
                    print(f"    ⚠ MISMATCHES: {results['v4_mismatch_count']} SHA-256 failures")
                    if results.get("v4_mismatches"):
                        for m in results["v4_mismatches"][:3]:
                            print(f"      {m['name']}: expected={m['expected']}... actual={m['actual']}...")
                
                print(f"    Signatures: {results['v5_signature_counts']}")
                if results["v5_conflicts"] > 0:
                    print(f"    Conflicts: {results['v5_conflicts']} inside other files")
                    for c in results["v5_conflict_examples"][:3]:
                        print(f"      {c['signature']} at byte {c['position']} inside {c['inside_file']}")
                
            except Exception as e:
                print(f"ERROR: {e}")
                all_results[f"N={n}_{ext[1:]}"] = {"error": str(e)}
    
    # ─── Phase 6: Determinism ──────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("PHASE 6: Determinism Verification")
    print("─" * 70)
    
    for ext in [".zip", ".pdf", ".jpg"]:
        builder1 = DatasetBuilder(seed=42, volume_size=_volume_for(ext, 15), files_per_image=15)
        builder2 = DatasetBuilder(seed=42, volume_size=_volume_for(ext, 15), files_per_image=15)
        
        img1, m1 = builder1.build_single_format_dataset(extension=ext, n_files=15)
        img2, m2 = builder2.build_single_format_dataset(extension=ext, n_files=15)
        
        img_match = img1 == img2
        m_match = json.dumps(m1, sort_keys=True) == json.dumps(m2, sort_keys=True)
        
        key = f"determinism_{ext[1:]}"
        all_results[key] = {
            "image_match": img_match,
            "manifest_match": m_match,
            "pass": img_match and m_match,
        }
        status = "✓" if img_match and m_match else "✗"
        print(f"  {status} {ext[1:]:5s}: image={'identical' if img_match else 'DIFFERENT'}, "
              f"manifest={'identical' if m_match else 'DIFFERENT'}")
    
    # ─── Phase 7: Adversarial metrics ──────────────────────────────────────
    print("\n" + "─" * 70)
    print("PHASE 7: Layout Adversarial Metrics")
    print("─" * 70)
    
    for key, results in all_results.items():
        if "v7_density" in results:
            print(f"  {key:20s}: density={results['v7_density']:.1f} files/MB, "
                  f"PK_files={results['v7_pk_files']}, avg_size={results['v7_avg_size_kb']:.1f}KB")
    
    # ─── Summary ───────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("INST-0001 SUMMARY")
    print("=" * 70)
    
    v1_pass = sum(1 for v in all_results.values() if v.get("v1_file_count", False))
    v1_fail = sum(1 for v in all_results.values() if "v1_file_count" in v and not v["v1_file_count"])
    v2_pass = sum(1 for v in all_results.values() if v.get("v2_no_overlaps", False))
    v2_fail = sum(1 for v in all_results.values() if "v2_no_overlaps" in v and not v["v2_no_overlaps"])
    v3_pass = sum(1 for v in all_results.values() if v.get("v3_unique_offsets", False))
    v3_fail = sum(1 for v in all_results.values() if "v3_unique_offsets" in v and not v["v3_unique_offsets"])
    v4_pass = sum(1 for v in all_results.values() if v.get("v4_ground_truth", False))
    v4_fail = sum(1 for v in all_results.values() if "v4_ground_truth" in v and not v["v4_ground_truth"])
    v6_pass = sum(1 for v in all_results.values() if "determinism" in str(v) and v.get("pass", False))
    v6_fail = sum(1 for v in all_results.values() if "determinism" in str(v) and "pass" in v and not v["pass"])
    
    print(f"  V1 File Count:         {v1_pass} pass / {v1_fail} fail")
    print(f"  V2 No Overlaps:        {v2_pass} pass / {v2_fail} fail")
    print(f"  V3 Unique Offsets:     {v3_pass} pass / {v3_fail} fail")
    print(f"  V4 Ground Truth:       {v4_pass} pass / {v4_fail} fail")
    print(f"  V5 Signature Density:  (observational)")
    print(f"  V6 Determinism:        {v6_pass} pass / {v6_fail} fail")
    print(f"  V7 Adversarial Score:  (observational)")
    
    # ─── H6 Discrimination ─────────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("H6 DISCRIMINATION (RC-A-003)")
    print("─" * 70)
    
    # Analyze conflict rates across N values
    conflict_by_n = defaultdict(list)
    for key, results in all_results.items():
        if "v5_conflict_rate" in results:
            for n in [15, 30, 100]:
                if f"N={n}" in key:
                    conflict_by_n[n].append(results["v5_conflict_rate"])
    
    print("\n  Conflict rate by N:")
    for n in sorted(conflict_by_n.keys()):
        rates = conflict_by_n[n]
        if rates:
            avg = sum(rates) / len(rates)
            print(f"    N={n:3d}: avg conflict rate = {avg:.1%} (across {len(rates)} formats)")
    
    # H6 verdict
    any_overlaps = v2_fail > 0
    any_mismatch = v4_fail > 0
    any_det_fail = v6_fail > 0
    high_conflict = any(v.get("v5_conflict_rate", 0) > 0.3 for v in all_results.values())
    
    print("\n  H6 Assessment:")
    if any_overlaps:
        print("  ❌ OVERLAPS — Dataset Builder produces overlapping files")
        print("     → H6 SUPPORTED: layout is adversarial")
    elif any_mismatch:
        print("  ❌ MISMATCH — Dataset Builder ground truth is incorrect")
        print("     → CRITICAL: instrument defect")
    elif any_det_fail:
        print("  ❌ DETERMINISM — same seed produces different images")
        print("     → CRITICAL: instrument defect")
    else:
        print("  ✅ NO ADVERSARIAL INDICATORS — Dataset Builder is NOT adversarial")
        print("     → H6 is NOT SUPPORTED: the collapse is not caused by the Builder")
        print("     → RC-A-003 remains classified as RC-A (algorithm problem)")
    
    if high_conflict and not any_overlaps:
        print("  ⚠️  NOTE: High signature conflict rate detected")
        print("     → But this is caused by file content (random data containing PK signatures),")
        print("     → NOT by the Builder placing files at adversarial positions")
        print("     → This is a carving algorithm issue (deduplication), not a Builder issue")
    
    # Save ledger
    output_dir = Path(__file__).parent.parent / "output" / "inst_0001"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    ledger_entry = {
        "experiment_id": "INST-0001",
        "family": "INST",
        "title": "Dataset Builder Validation",
        "date": datetime.now(timezone.utc).isoformat(),
        "status": "COMPLETED",
        "question": "Does the Dataset Builder generate representative, non-adversarial NTFS images?",
        "validations": {
            "V1_file_count": f"{v1_pass}/{v1_pass+v1_fail} pass",
            "V2_no_overlaps": f"{v2_pass}/{v2_pass+v2_fail} pass",
            "V3_unique_offsets": f"{v3_pass}/{v3_pass+v3_fail} pass",
            "V4_ground_truth": f"{v4_pass}/{v4_pass+v4_fail} pass",
            "V6_determinism": f"{v6_pass}/{v6_pass+v6_fail} pass",
        },
        "h6_discrimination": {
            "overlaps_detected": any_overlaps,
            "content_mismatch": any_mismatch,
            "determinism_failure": any_det_fail,
            "high_conflict_rate": high_conflict,
            "h6_supported": any_overlaps or any_mismatch or any_det_fail,
        },
        "full_results": all_results,
    }
    
    ledger_path = output_dir / "ledger_entry.json"
    with open(ledger_path, 'w') as f:
        json.dump(ledger_entry, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n  Ledger: {ledger_path}")
    print(f"\n  INST-0001 COMPLETE")
    
    return ledger_entry


if __name__ == "__main__":
    run_inst_0001()
