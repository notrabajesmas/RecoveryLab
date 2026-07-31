#!/usr/bin/env python3
"""
INST-0002 — Pipeline Loss Localization
========================================
Familia: INST (Instrument Validation)
Origen: Auditoría externa r12

Pregunta: ¿En qué etapa exacta del pipeline desaparece cada archivo?

Pipeline instrumentado:
  Scanner → Firma encontrada → Delimitación → Candidato → Dedup → Carved → Judge

Para cada archivo del ground truth, se registra:
  - stage_1_scan: ¿Se encontró la firma del archivo en el scanner?
  - stage_2_delimitation: ¿Se extrajo el archivo del imagen?
  - stage_3_dedup: ¿Sobrevivió a la deduplicación?
  - stage_4_judge: ¿El SHA-256 coincide con el ground truth?

El resultado es una cadena causal completa por archivo, que permite
discriminar entre las hipótesis H1-H5 de RC-A-003.
"""

import sys
import os
import json
import csv
import hashlib
import struct
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any, Optional, Set
from collections import defaultdict
from dataclasses import dataclass, field, asdict

# ─── Project root ─────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# ─── Imports ──────────────────────────────────────────────────────────────
from dataset_builder.builder import DatasetBuilder
from dataset_builder.manifest import load_manifest, save_manifest
from motors.motor_carving import MotorCarving, SIGNATURES, FileSignature
from motors.motor_b_mft_first import MotorBMFTFirst
from recovery_judge.judge import RecoveryJudge
from recovery_judge.fqs import compute_overall_utility


# ═══════════════════════════════════════════════════════════════════════════
# STAGE 1: Instrumented Scanner
# ═══════════════════════════════════════════════════════════════════════════

def run_instrumented_scan(image: bytes, cluster_size: int, total_clusters: int) -> List[Dict]:
    """
    Run the carving scanner and return ALL signature matches found,
    with their offsets and format names.
    
    This is Stage 1 of the pipeline: detection.
    """
    image_len = len(image)
    all_matches = []
    
    for cluster_num in range(total_clusters):
        cluster_start = cluster_num * cluster_size
        if cluster_start + cluster_size > image_len:
            break
        
        for sig in SIGNATURES:
            # Check at start of cluster
            check_offsets = [0]
            for sector_offset in range(512, min(cluster_size, 4096), 512):
                check_offsets.append(sector_offset)
            
            for offset_in_cluster in check_offsets:
                abs_offset = cluster_start + offset_in_cluster
                if abs_offset + sig.header_len > image_len:
                    continue
                
                candidate = image[abs_offset:abs_offset + sig.header_len]
                if _matches_with_mask(candidate, sig.header, sig.header_mask):
                    all_matches.append({
                        "offset": abs_offset,
                        "cluster": cluster_num,
                        "format_name": sig.name,
                        "extension": sig.extension,
                        "header": sig.header.hex(),
                    })
    
    return all_matches


def _matches_with_mask(candidate: bytes, header: bytes, mask: bytes) -> bool:
    """Check if candidate bytes match the header pattern with mask."""
    if len(candidate) < len(header):
        return False
    for i in range(len(header)):
        if mask[i] == 0xFF:
            if candidate[i] != header[i]:
                return False
    return True


# ═══════════════════════════════════════════════════════════════════════════
# STAGE 2: Instrumented Delimitation
# ═══════════════════════════════════════════════════════════════════════════

def run_instrumented_delimitation(image: bytes, scan_matches: List[Dict],
                                   cluster_size: int, total_clusters: int) -> List[Dict]:
    """
    For each signature match found in Stage 1, try to carve the file.
    
    This is Stage 2: delimitation/extraction.
    
    Returns the list of carved candidates with their data.
    """
    image_len = len(image)
    carved_candidates = []
    
    # Build a lookup from format name to signature
    sig_by_name = {s.name: s for s in SIGNATURES}
    
    for match in scan_matches:
        sig = sig_by_name.get(match["format_name"])
        if sig is None:
            continue
        
        start_offset = match["offset"]
        
        # Try to carve the file using the same logic as MotorCarving
        carved = _carve_file_instrumented(
            image, start_offset, sig, image_len, cluster_size
        )
        
        if carved is not None:
            carved_candidates.append({
                **carved,
                "format_name": match["format_name"],
                "extension": match["extension"],
                "from_scan_match": match,
            })
    
    return carved_candidates


def _carve_file_instrumented(image: bytes, start_offset: int,
                              sig: FileSignature, image_len: int,
                              cluster_size: int) -> Optional[Dict]:
    """Extract a file from the image starting at the given offset (instrumented)."""
    remaining = image_len - start_offset
    if remaining < sig.min_size:
        return None
    
    file_data = None
    footer_found = False
    
    if sig.name == "JPEG":
        # JPEG-specific carving: parse structure to find the real EOI.
        # RC-002 fix: structural parsing correctly identifies EOI by skipping
        # entropy-coded data (byte stuffing FF 00).
        carved = _carve_jpeg_instrumented(
            image, start_offset, image_len, sig, cluster_size
        )
        if carved is not None:
            return carved
        # Fallback: if structural parsing fails, use max-size heuristic
        heuristic_size = min(sig.max_size, remaining)
        file_data = image[start_offset:start_offset + heuristic_size]
        if len(file_data) < sig.min_size:
            return None
        return {
            "data": file_data,
            "start_offset": start_offset,
            "start_cluster": start_offset // cluster_size,
            "size": len(file_data),
            "footer_found": False,
            "sha256": hashlib.sha256(file_data).hexdigest(),
        }
    elif sig.footer:
        footer_search_start = start_offset + sig.header_len
        max_search_end = min(start_offset + sig.max_size, image_len)
        
        footer_offset = _find_footer_instrumented(
            image, footer_search_start, max_search_end, sig.footer
        )
        
        if footer_offset is not None:
            file_end = footer_offset + len(sig.footer)
            file_data = image[start_offset:file_end]
            footer_found = True
        else:
            heuristic_size = min(sig.max_size, remaining)
            file_data = image[start_offset:start_offset + heuristic_size]
    else:
        heuristic_size = min(sig.max_size, remaining)
        file_data = image[start_offset:start_offset + heuristic_size]
    
    if file_data is None or len(file_data) < sig.min_size:
        return None
    
    if len(file_data) > sig.max_size:
        file_data = file_data[:sig.max_size]
    
    return {
        "data": file_data,
        "start_offset": start_offset,
        "start_cluster": start_offset // cluster_size,
        "size": len(file_data),
        "footer_found": footer_found,
        "sha256": hashlib.sha256(file_data).hexdigest(),
    }


def _carve_jpeg_instrumented(image: bytes, start_offset: int,
                              image_len: int, sig: FileSignature,
                              cluster_size: int) -> Optional[Dict]:
    """
    Carve a JPEG file by parsing its structure to find the real EOI.
    
    RC-002 fix: three-tier strategy:
      1. Structural parsing (for real JPEGs with SOS marker)
      2. Last FFD9 before next JPEG signature (for synthetic/partial JPEGs)
      3. Last FFD9 within max_size (fallback)
    """
    max_end = min(start_offset + sig.max_size, image_len)
    
    if start_offset + 2 > image_len:
        return None
    if image[start_offset:start_offset + 2] != b'\xFF\xD8':
        return None
    
    # Tier 1: Last FFD9 before next JPEG signature (most reliable for multi-JPEG images)
    next_jpeg = _find_next_jpeg_sig(image, start_offset + 4, max_end)
    if next_jpeg is not None:
        last_ffd9 = _find_footer_last_instrumented(
            image, start_offset + 4, next_jpeg, b'\xFF\xD9'
        )
        if last_ffd9 is not None:
            file_end = last_ffd9 + 2
            file_data = image[start_offset:file_end]
            if len(file_data) >= sig.min_size:
                return {
                    "data": file_data,
                    "start_offset": start_offset,
                    "start_cluster": start_offset // cluster_size,
                    "size": len(file_data),
                    "footer_found": True,
                    "sha256": hashlib.sha256(file_data).hexdigest(),
                }
    
    # Tier 2: Structural parsing (for real JPEGs with SOS, when no next JPEG boundary)
    eoi_offset = _find_jpeg_eoi_structured(image, start_offset, max_end)
    if eoi_offset is not None:
        file_end = eoi_offset + 2
        file_data = image[start_offset:file_end]
        if len(file_data) >= sig.min_size:
            return {
                "data": file_data,
                "start_offset": start_offset,
                "start_cluster": start_offset // cluster_size,
                "size": len(file_data),
                "footer_found": True,
                "sha256": hashlib.sha256(file_data).hexdigest(),
            }
    
    # Tier 3: Last FFD9 within max_size
    last_ffd9 = _find_footer_last_instrumented(
        image, start_offset + 4, max_end, b'\xFF\xD9'
    )
    if last_ffd9 is not None:
        file_end = last_ffd9 + 2
        file_data = image[start_offset:file_end]
        if len(file_data) >= sig.min_size:
            return {
                "data": file_data,
                "start_offset": start_offset,
                "start_cluster": start_offset // cluster_size,
                "size": len(file_data),
                "footer_found": True,
                "sha256": hashlib.sha256(file_data).hexdigest(),
            }
    
    return None  # Structural parsing failed


def _find_jpeg_eoi_structured(image: bytes, start_offset: int,
                               max_end: int) -> Optional[int]:
    """Find the real EOI of a JPEG by parsing its structure."""
    pos = start_offset + 2  # Skip SOI
    
    while pos < max_end - 1:
        if image[pos] != 0xFF:
            pos += 1
            continue
        marker_byte = image[pos + 1]
        if marker_byte == 0x00 or marker_byte == 0xFF:
            pos += 1
            continue
        if marker_byte == 0xDA:  # SOS
            if pos + 4 > max_end:
                return None
            sos_length = struct.unpack('>H', image[pos + 2:pos + 4])[0]
            pos += 2 + sos_length
            while pos < max_end - 1:
                if image[pos] == 0xFF:
                    next_byte = image[pos + 1]
                    if next_byte == 0x00:
                        pos += 2
                        continue
                    if next_byte == 0xFF:
                        pos += 1
                        continue
                    if next_byte == 0xD9:
                        return pos
                    if 0xD0 <= next_byte <= 0xD7:
                        pos += 2
                        continue
                    pos += 1
                    continue
                else:
                    pos += 1
            return None
        if marker_byte == 0xD9:  # EOI before SOS
            return pos
        if marker_byte in (0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7):
            pos += 2
            continue
        if pos + 4 > max_end:
            return None
        marker_length = struct.unpack('>H', image[pos + 2:pos + 4])[0]
        pos += 2 + marker_length
    return None


def _find_next_jpeg_sig(image: bytes, start: int, end: int,
                        cluster_size: int = 4096) -> Optional[int]:
    """Find the next JPEG signature (FFD8FF) at a cluster boundary after the given offset."""
    jpeg_sig = b'\xFF\xD8\xFF'
    pos = start
    
    while pos < end - len(jpeg_sig):
        idx = image.find(jpeg_sig, pos, end)
        if idx == -1:
            return None
        if idx % cluster_size == 0:
            return idx
        next_cluster = ((idx // cluster_size) + 1) * cluster_size
        pos = next_cluster
    
    return None


def _find_footer_instrumented(image: bytes, start: int, end: int,
                               footer: bytes) -> Optional[int]:
    """Find the first occurrence of footer bytes in the image."""
    footer_len = len(footer)
    if footer_len == 0:
        return None
    
    chunk_size = 1024 * 1024
    pos = start
    
    while pos < end:
        chunk_end = min(pos + chunk_size + footer_len, end + footer_len)
        chunk = image[pos:chunk_end]
        idx = chunk.find(footer)
        if idx != -1:
            return pos + idx
        pos += chunk_size
    
    return None


def _find_footer_last_instrumented(image: bytes, start: int, end: int,
                                    footer: bytes) -> Optional[int]:
    """Find the LAST occurrence of footer bytes in the image.
    
    RC-002 fix: JPEG body may contain spurious FFD9 bytes. The real EOI
    is the last FFD9, not the first one.
    """
    footer_len = len(footer)
    if footer_len == 0:
        return None
    
    last_found = None
    chunk_size = 1024 * 1024
    pos = start
    
    while pos < end:
        chunk_end = min(pos + chunk_size + footer_len, end + footer_len)
        chunk = image[pos:chunk_end]
        
        search_pos = 0
        while search_pos < len(chunk):
            idx = chunk.find(footer, search_pos)
            if idx == -1:
                break
            last_found = pos + idx
            search_pos = idx + 1
        
        pos += chunk_size
    
    return last_found


# ═══════════════════════════════════════════════════════════════════════════
# STAGE 3: Instrumented Deduplication
# ═══════════════════════════════════════════════════════════════════════════

def run_instrumented_dedup(carved_candidates: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    Apply the same deduplication logic as MotorCarving, but track
    which files were eliminated and why.
    
    Returns (survived, eliminated) where eliminated contains the reason.
    """
    # First, resolve ZIP/DOCX/XLSX ambiguity
    resolved = _resolve_zip_docx_instrumented(carved_candidates)
    
    if len(resolved) <= 1:
        return resolved, []
    
    # Apply deduplication
    sorted_files = sorted(resolved, key=lambda f: f["start_offset"])
    
    survived = []
    eliminated = []
    
    for cf in sorted_files:
        is_duplicate = False
        eliminated_by = None
        overlap_amount = 0
        
        for existing in survived:
            overlap_start = max(cf["start_offset"], existing["start_offset"])
            overlap_end = min(
                cf["start_offset"] + cf["size"],
                existing["start_offset"] + existing["size"]
            )
            
            if overlap_start < overlap_end:
                overlap_size = overlap_end - overlap_start
                smaller_size = min(cf["size"], existing["size"])
                
                if overlap_size > smaller_size * 0.5:
                    # Significant overlap
                    if cf["size"] > existing["size"]:
                        # New file is larger — remove existing
                        eliminated.append({
                            **existing,
                            "eliminated_by": "dedup_overlap",
                            "eliminated_by_file_offset": cf["start_offset"],
                            "eliminated_by_file_format": cf.get("format_name", "?"),
                            "eliminated_by_file_size": cf["size"],
                            "overlap_amount": overlap_size,
                        })
                        survived.remove(existing)
                        survived.append(cf)
                    else:
                        # Existing is larger — remove new file
                        eliminated_by = existing
                        overlap_amount = overlap_size
                    is_duplicate = True
                    break
        
        if is_duplicate and eliminated_by is not None:
            eliminated.append({
                **cf,
                "eliminated_by": "dedup_overlap",
                "eliminated_by_file_offset": eliminated_by["start_offset"],
                "eliminated_by_file_format": eliminated_by.get("format_name", "?"),
                "eliminated_by_file_size": eliminated_by["size"],
                "overlap_amount": overlap_amount,
            })
        elif not is_duplicate:
            survived.append(cf)
    
    return survived, eliminated


def _resolve_zip_docx_instrumented(carved_files: List[Dict]) -> List[Dict]:
    """Resolve ZIP/DOCX/XLSX ambiguity (same logic as MotorCarving)."""
    by_offset: Dict[int, List[Dict]] = {}
    for cf in carved_files:
        offset = cf["start_offset"]
        if offset not in by_offset:
            by_offset[offset] = []
        by_offset[offset].append(cf)
    
    resolved = []
    for offset, files in by_offset.items():
        if len(files) == 1:
            resolved.append(files[0])
            continue
        
        data = files[0]["data"]
        
        has_docx_markers = (
            b'word/' in data or
            b'word/document.xml' in data or
            b'Content_Types.xml' in data
        )
        
        has_xlsx_markers = (
            b'xl/' in data or
            b'xl/workbook.xml' in data or
            b'xl/worksheets/' in data
        )
        
        if has_xlsx_markers:
            for f in files:
                if f["format_name"] == "XLSX":
                    resolved.append(f)
                    break
            else:
                files[0]["extension"] = ".xlsx"
                files[0]["format_name"] = "XLSX"
                resolved.append(files[0])
        elif has_docx_markers:
            for f in files:
                if f["format_name"] == "DOCX":
                    resolved.append(f)
                    break
            else:
                files[0]["extension"] = ".docx"
                files[0]["format_name"] = "DOCX"
                resolved.append(files[0])
        else:
            for f in files:
                if f["format_name"] == "ZIP":
                    resolved.append(f)
                    break
            else:
                resolved.append(files[0])
    
    return resolved


# ═══════════════════════════════════════════════════════════════════════════
# STAGE 4: Instrumented Judge
# ═══════════════════════════════════════════════════════════════════════════

def run_instrumented_judge(carved_files: List[Dict], manifest: Dict) -> List[Dict]:
    """
    For each carved file, check if it matches ground truth by SHA-256.
    
    This is Stage 4: matching.
    
    Returns the carved files with judge results appended.
    """
    # Build ground truth lookup by SHA-256
    gt_by_sha = {}
    gt_by_offset = {}
    gt_files = [f for f in manifest.get("files", []) if not f.get("is_directory", False)]
    
    cluster_size = manifest.get("cluster_size", 4096)
    
    for f in gt_files:
        if f.get("sha256"):
            gt_by_sha[f["sha256"]] = f
        # Also build offset lookup from clusters
        clusters = f.get("clusters", [])
        if clusters:
            start_byte = clusters[0] * cluster_size
            gt_by_offset[start_byte] = f
    
    results = []
    for cf in carved_files:
        sha256 = cf.get("sha256", "")
        gt_match = gt_by_sha.get(sha256)
        
        # If no SHA match, check if the carved file is at the same offset
        # as a ground truth file (then it's a near-miss)
        offset_match = gt_by_offset.get(cf["start_offset"])
        
        judge_result = {
            **cf,
            "sha256_match": gt_match is not None,
            "matched_gt_name": gt_match.get("name", "") if gt_match else "",
            "offset_match_name": offset_match.get("name", "") if offset_match else "",
        }
        
        # If no SHA match but offset matches, check size difference
        if not gt_match and offset_match:
            gt_size = offset_match.get("size", 0)
            carved_size = cf.get("size", 0)
            size_diff = carved_size - gt_size
            judge_result["size_diff"] = size_diff
            judge_result["gt_size"] = gt_size
            judge_result["carved_size"] = carved_size
            
            # Check if adding missing bytes fixes SHA
            if size_diff < 0:
                # Carved file is shorter than ground truth
                gt_sha = offset_match.get("sha256", "")
                # Try to check if the carved data matches the beginning of the GT file
                # by checking if the carved SHA matches the first carved_size bytes
                # We need the actual GT data for this
                pass
        
        results.append(judge_result)
    
    return results


# ═══════════════════════════════════════════════════════════════════════════
# PER-FILE TRACE: Build the causal chain for each ground truth file
# ═══════════════════════════════════════════════════════════════════════════

def build_per_file_trace(
    manifest: Dict,
    scan_matches: List[Dict],
    carved_candidates: List[Dict],
    dedup_survived: List[Dict],
    dedup_eliminated: List[Dict],
    judge_results: List[Dict],
    image: bytes,
) -> List[Dict]:
    """
    For each ground truth file, determine its fate at each pipeline stage.
    
    Returns a list of per-file traces, one per ground truth file.
    """
    cluster_size = manifest.get("cluster_size", 4096)
    gt_files = [f for f in manifest.get("files", []) if not f.get("is_directory", False)]
    
    # Build lookup structures
    # Scan matches by offset
    scan_by_offset = defaultdict(list)
    for m in scan_matches:
        scan_by_offset[m["offset"]].append(m)
    
    # Carved candidates by offset
    carved_by_offset = defaultdict(list)
    for c in carved_candidates:
        carved_by_offset[c["start_offset"]].append(c)
    
    # Dedup survived by offset
    survived_by_offset = defaultdict(list)
    for s in dedup_survived:
        survived_by_offset[s["start_offset"]].append(s)
    
    # Dedup eliminated by offset
    eliminated_by_offset = defaultdict(list)
    for e in dedup_eliminated:
        eliminated_by_offset[e["start_offset"]].append(e)
    
    # Judge results by offset
    judge_by_offset = defaultdict(list)
    for j in judge_results:
        judge_by_offset[j["start_offset"]].append(j)
    
    traces = []
    
    for gt_file in gt_files:
        clusters = gt_file.get("clusters", [])
        if not clusters:
            # Resident file (data in MFT) — carving can't find these
            trace = {
                "gt_name": gt_file.get("name", ""),
                "gt_sha256": gt_file.get("sha256", ""),
                "gt_size": gt_file.get("size", 0),
                "gt_start_offset": None,
                "stage_1_scan": "SKIP",
                "stage_1_scan_detail": "Resident file — no clusters to scan",
                "stage_2_delimitation": "SKIP",
                "stage_2_delimitation_detail": "Resident file — carving inapplicable",
                "stage_3_dedup": "SKIP",
                "stage_3_dedup_detail": "Resident file — never reached",
                "stage_4_judge": "FAIL",
                "stage_4_judge_detail": "Resident file — carving cannot recover",
                "loss_stage": "N/A_RESIDENT",
                "loss_detail": "File is resident (stored in MFT, not in data area)",
            }
            traces.append(trace)
            continue
        
        start_byte = clusters[0] * cluster_size
        gt_sha256 = gt_file.get("sha256", "")
        gt_size = gt_file.get("size", 0)
        gt_name = gt_file.get("name", "")
        
        trace = {
            "gt_name": gt_name,
            "gt_sha256": gt_sha256[:16] + "..." if gt_sha256 else "",
            "gt_size": gt_size,
            "gt_start_offset": start_byte,
        }
        
        # ─── Stage 1: Scan ──────────────────────────────────────────
        scan_matches_at_offset = scan_by_offset.get(start_byte, [])
        # Also check nearby offsets (within cluster)
        nearby_matches = []
        for offset in range(max(0, start_byte - cluster_size), start_byte + cluster_size):
            nearby_matches.extend(scan_by_offset.get(offset, []))
        
        if scan_matches_at_offset:
            trace["stage_1_scan"] = "PASS"
            sig_names = [m["format_name"] for m in scan_matches_at_offset]
            trace["stage_1_scan_detail"] = f"Signature found: {', '.join(sig_names)}"
        elif nearby_matches:
            trace["stage_1_scan"] = "PASS_NEARBY"
            trace["stage_1_scan_detail"] = f"Signature found nearby: {nearby_matches[0]['format_name']} at offset {nearby_matches[0]['offset']}"
        else:
            trace["stage_1_scan"] = "FAIL"
            trace["stage_1_scan_detail"] = "No signature found at this file's start offset"
            # Check if the file has a signature that should be detectable
            # Read the first few bytes of the file from the image
            if start_byte + 16 <= len(image):
                file_header = image[start_byte:start_byte + 16]
                trace["stage_1_scan_detail"] += f" | File header: {file_header[:8].hex()}"
        
        # ─── Stage 2: Delimitation ──────────────────────────────────
        carved_at_offset = carved_by_offset.get(start_byte, [])
        # Also check nearby carved
        nearby_carved = []
        for offset in range(max(0, start_byte - cluster_size), start_byte + cluster_size):
            nearby_carved.extend(carved_by_offset.get(offset, []))
        
        if carved_at_offset:
            trace["stage_2_delimitation"] = "PASS"
            c = carved_at_offset[0]
            trace["stage_2_delimitation_detail"] = (
                f"Carved: {c.get('format_name', '?')} size={c.get('size', 0)} "
                f"footer={'found' if c.get('footer_found') else 'not found'}"
            )
        elif nearby_carved:
            trace["stage_2_delimitation"] = "PASS_NEARBY"
            c = nearby_carved[0]
            trace["stage_2_delimitation_detail"] = f"Carved nearby: offset={c['start_offset']}"
        else:
            trace["stage_2_delimitation"] = "FAIL"
            trace["stage_2_delimitation_detail"] = "File not extracted from image"
            if trace["stage_1_scan"] == "FAIL":
                trace["stage_2_delimitation_detail"] += " (upstream: no signature found)"
        
        # ─── Stage 3: Dedup ─────────────────────────────────────────
        survived_at_offset = survived_by_offset.get(start_byte, [])
        eliminated_at_offset = eliminated_by_offset.get(start_byte, [])
        
        if survived_at_offset:
            trace["stage_3_dedup"] = "PASS"
            s = survived_at_offset[0]
            trace["stage_3_dedup_detail"] = f"Survived: {s.get('format_name', '?')} size={s.get('size', 0)}"
        elif eliminated_at_offset:
            trace["stage_3_dedup"] = "FAIL"
            e = eliminated_at_offset[0]
            trace["stage_3_dedup_detail"] = (
                f"Eliminated by overlap with {e.get('eliminated_by_file_format', '?')} "
                f"at offset {e.get('eliminated_by_file_offset', '?')} "
                f"(overlap: {e.get('overlap_amount', 0)} bytes)"
            )
        else:
            trace["stage_3_dedup"] = "N/A"
            trace["stage_3_dedup_detail"] = "File not found in either survived or eliminated"
            if trace["stage_2_delimitation"] == "FAIL":
                trace["stage_3_dedup_detail"] += " (upstream: not carved)"
        
        # ─── Stage 4: Judge ─────────────────────────────────────────
        judge_at_offset = judge_by_offset.get(start_byte, [])
        nearby_judge = []
        for offset in range(max(0, start_byte - cluster_size), start_byte + cluster_size):
            nearby_judge.extend(judge_by_offset.get(offset, []))
        
        # Also check by SHA-256 match
        sha_match = None
        for j in judge_results:
            if j.get("sha256_match") and j.get("matched_gt_name") == gt_name:
                sha_match = j
                break
        
        if sha_match:
            trace["stage_4_judge"] = "PASS"
            trace["stage_4_judge_detail"] = f"SHA-256 match: {sha_match.get('matched_gt_name', '')}"
        elif judge_at_offset:
            j = judge_at_offset[0]
            if j.get("sha256_match"):
                trace["stage_4_judge"] = "PASS"
                trace["stage_4_judge_detail"] = f"SHA-256 match (different GT file)"
            else:
                trace["stage_4_judge"] = "FAIL"
                size_diff = j.get("size_diff", j.get("size", 0) - gt_size)
                trace["stage_4_judge_detail"] = (
                    f"SHA-256 mismatch: carved_size={j.get('size', 0)} gt_size={gt_size} "
                    f"diff={size_diff}"
                )
                # Check if it's a truncation fixable
                if size_diff == -1:
                    trace["stage_4_judge_detail"] += " [TRUNCATION FIXABLE: 1 byte short]"
                elif size_diff < 0:
                    trace["stage_4_judge_detail"] += f" [TRUNCATION: {abs(size_diff)} bytes short]"
        elif nearby_judge:
            j = nearby_judge[0]
            if j.get("sha256_match"):
                trace["stage_4_judge"] = "PASS"
                trace["stage_4_judge_detail"] = f"SHA-256 match at nearby offset"
            else:
                trace["stage_4_judge"] = "FAIL"
                trace["stage_4_judge_detail"] = f"SHA-256 mismatch at nearby offset"
        else:
            trace["stage_4_judge"] = "N/A"
            trace["stage_4_judge_detail"] = "File not in judge results"
            if trace["stage_3_dedup"] == "FAIL":
                trace["stage_4_judge_detail"] += " (upstream: eliminated by dedup)"
            elif trace["stage_2_delimitation"] == "FAIL":
                trace["stage_4_judge_detail"] += " (upstream: not carved)"
        
        # ─── Determine loss stage ────────────────────────────────────
        loss_stage = "NONE"  # File survived all stages
        loss_detail = ""
        
        if trace["stage_4_judge"] == "PASS":
            loss_stage = "NONE"
            loss_detail = "File fully recovered through all stages"
        elif trace["stage_4_judge"] == "FAIL":
            loss_stage = "STAGE_4_JUDGE"
            loss_detail = trace["stage_4_judge_detail"]
        elif trace["stage_3_dedup"] == "FAIL":
            loss_stage = "STAGE_3_DEDUP"
            loss_detail = trace["stage_3_dedup_detail"]
        elif trace["stage_2_delimitation"] == "FAIL":
            loss_stage = "STAGE_2_DELIMITATION"
            loss_detail = trace["stage_2_delimitation_detail"]
        elif trace["stage_1_scan"] == "FAIL":
            loss_stage = "STAGE_1_SCAN"
            loss_detail = trace["stage_1_scan_detail"]
        elif trace["stage_3_dedup"] == "N/A" and trace["stage_2_delimitation"] == "FAIL":
            loss_stage = "STAGE_2_DELIMITATION"
            loss_detail = trace["stage_2_delimitation_detail"]
        else:
            loss_stage = "UNKNOWN"
            loss_detail = f"Scan={trace['stage_1_scan']} Delim={trace['stage_2_delimitation']} Dedup={trace['stage_3_dedup']} Judge={trace['stage_4_judge']}"
        
        trace["loss_stage"] = loss_stage
        trace["loss_detail"] = loss_detail
        
        traces.append(trace)
    
    return traces


# ═══════════════════════════════════════════════════════════════════════════
# MAIN EXPERIMENT RUNNER
# ═══════════════════════════════════════════════════════════════════════════

def _volume_for(ext, n):
    """Calculate appropriate volume size for a given format and file count."""
    if ext in (".jpg", ".png"):
        return max(50*1024*1024, n * 3 * 1024 * 1024 + 50 * 1024 * 1024)
    else:
        return max(50*1024*1024, n * 500_000 + 50 * 1024 * 1024)


def run_single_format(ext: str, n: int, seed: int = 42) -> Dict:
    """
    Run the full instrumented pipeline for a single format and file count.
    
    Returns a comprehensive result dict with per-file traces and aggregate metrics.
    """
    print(f"\n  {'─' * 60}")
    print(f"  Format: {ext} | N={n}")
    print(f"  {'─' * 60}")
    
    # ─── Build dataset ────────────────────────────────────────────────
    vol = _volume_for(ext, n)
    builder = DatasetBuilder(seed=seed, volume_size=vol, files_per_image=n)
    image_bytes, manifest = builder.build_single_format_dataset(extension=ext, n_files=n)
    
    cluster_size = manifest.get("cluster_size", 4096)
    total_clusters = manifest.get("total_clusters", len(image_bytes) // cluster_size)
    
    gt_files = [f for f in manifest.get("files", []) if not f.get("is_directory", False)]
    non_resident = [f for f in gt_files if f.get("clusters", [])]
    
    print(f"  Built: {len(gt_files)} files ({len(non_resident)} non-resident), "
          f"image={len(image_bytes)/(1024*1024):.1f}MB")
    
    # ─── Stage 1: Scan ────────────────────────────────────────────────
    t0 = time.time()
    scan_matches = run_instrumented_scan(image_bytes, cluster_size, total_clusters)
    t_scan = time.time() - t0
    
    sig_counts = defaultdict(int)
    for m in scan_matches:
        sig_counts[m["format_name"]] += 1
    
    print(f"  Stage 1 (Scan): {len(scan_matches)} matches in {t_scan:.2f}s")
    for name, count in sorted(sig_counts.items()):
        print(f"    {name}: {count}")
    
    # ─── Stage 2: Delimitation ────────────────────────────────────────
    t0 = time.time()
    carved_candidates = run_instrumented_delimitation(
        image_bytes, scan_matches, cluster_size, total_clusters
    )
    t_delim = time.time() - t0
    
    # Count how many have footer found
    footer_found_count = sum(1 for c in carved_candidates if c.get("footer_found"))
    
    print(f"  Stage 2 (Delimitation): {len(carved_candidates)} carved "
          f"({footer_found_count} with footer) in {t_delim:.2f}s")
    
    # ─── Stage 3: Dedup ───────────────────────────────────────────────
    t0 = time.time()
    survived, eliminated = run_instrumented_dedup(carved_candidates)
    t_dedup = time.time() - t0
    
    print(f"  Stage 3 (Dedup): {len(survived)} survived, {len(eliminated)} eliminated in {t_dedup:.2f}s")
    
    # Show elimination details
    elim_by_format = defaultdict(int)
    elim_reasons = defaultdict(list)
    for e in eliminated:
        fmt = e.get("format_name", "?")
        elim_by_format[fmt] += 1
        elim_reasons[fmt].append({
            "offset": e["start_offset"],
            "size": e.get("size", 0),
            "eliminated_by": e.get("eliminated_by_file_format", "?"),
            "eliminated_by_size": e.get("eliminated_by_file_size", 0),
            "overlap": e.get("overlap_amount", 0),
        })
    
    for fmt, count in sorted(elim_by_format.items()):
        print(f"    {fmt}: {count} eliminated")
        for r in elim_reasons[fmt][:3]:
            print(f"      offset={r['offset']} size={r['size']} "
                  f"→ eliminated by {r['eliminated_by']} (size={r['eliminated_by_size']}, "
                  f"overlap={r['overlap']})")
    
    # ─── Stage 4: Judge ───────────────────────────────────────────────
    t0 = time.time()
    judge_results = run_instrumented_judge(survived, manifest)
    t_judge = time.time() - t0
    
    sha_matches = sum(1 for j in judge_results if j.get("sha256_match"))
    sha_mismatches = sum(1 for j in judge_results if not j.get("sha256_match"))
    
    print(f"  Stage 4 (Judge): {sha_matches} SHA-256 matches, {sha_mismatches} mismatches in {t_judge:.2f}s")
    
    # ─── Build per-file trace ─────────────────────────────────────────
    traces = build_per_file_trace(
        manifest, scan_matches, carved_candidates, survived, eliminated,
        judge_results, image_bytes
    )
    
    # ─── Aggregate loss analysis ──────────────────────────────────────
    loss_by_stage = defaultdict(int)
    for t in traces:
        loss_by_stage[t["loss_stage"]] += 1
    
    print(f"\n  Per-file trace summary:")
    for stage, count in sorted(loss_by_stage.items()):
        print(f"    {stage}: {count} files")
    
    # ─── Build result ─────────────────────────────────────────────────
    result = {
        "format": ext,
        "n_files": n,
        "seed": seed,
        "image_size_mb": round(len(image_bytes) / (1024*1024), 1),
        "cluster_size": cluster_size,
        "total_clusters": total_clusters,
        "gt_files": len(gt_files),
        "non_resident_files": len(non_resident),
        
        # Stage counts
        "stage_1_scan_matches": len(scan_matches),
        "stage_1_sig_counts": dict(sig_counts),
        "stage_2_carved_candidates": len(carved_candidates),
        "stage_2_footer_found": footer_found_count,
        "stage_3_survived": len(survived),
        "stage_3_eliminated": len(eliminated),
        "stage_4_sha_matches": sha_matches,
        "stage_4_sha_mismatches": sha_mismatches,
        
        # Timing
        "timing": {
            "scan": round(t_scan, 3),
            "delimitation": round(t_delim, 3),
            "dedup": round(t_dedup, 3),
            "judge": round(t_judge, 3),
        },
        
        # Loss analysis
        "loss_by_stage": dict(loss_by_stage),
        
        # Per-file traces
        "per_file_traces": traces,
        
        # Elimination details
        "elimination_details": {fmt: reasons for fmt, reasons in elim_reasons.items()},
    }
    
    return result


def run_inst_0002():
    """Run the full INST-0002 experiment."""
    print("=" * 70)
    print("INST-0002: Pipeline Loss Localization")
    print("=" * 70)
    print(f"Familia: INST (Instrument Validation)")
    print(f"Origen: Auditoría externa r12")
    print(f"Fecha: {datetime.now(timezone.utc).isoformat()}")
    print()
    print("Pregunta: ¿En qué etapa exacta del pipeline desaparece cada archivo?")
    print()
    print("Pipeline instrumentado:")
    print("  Scanner → Firma encontrada → Delimitación → Candidato → Dedup → Carved → Judge")
    print()
    
    all_results = {}
    
    # ─── Test configurations ──────────────────────────────────────────
    configs = [
        (".zip",  [15, 30, 100]),
        (".docx", [15, 30, 100]),
        (".pdf",  [15, 30, 100]),
        (".jpg",  [15, 30]),
        (".png",  [15, 30]),
    ]
    
    # ─── Run all configurations ───────────────────────────────────────
    for ext, n_values in configs:
        for n in n_values:
            key = f"N={n}_{ext[1:]}"
            print(f"\n{'═' * 70}")
            print(f"  Running: {key}")
            print(f"{'═' * 70}")
            
            try:
                result = run_single_format(ext, n)
                all_results[key] = result
            except Exception as e:
                print(f"  ERROR: {e}")
                import traceback
                traceback.print_exc()
                all_results[key] = {"error": str(e)}
    
    # ─── Cross-format analysis ────────────────────────────────────────
    print("\n" + "=" * 70)
    print("CROSS-FORMAT ANALYSIS")
    print("=" * 70)
    
    # Aggregate loss by stage across all formats
    total_loss_by_stage = defaultdict(int)
    format_loss_by_stage = defaultdict(lambda: defaultdict(int))
    
    for key, result in all_results.items():
        if "error" in result:
            continue
        fmt = result.get("format", "?")
        for stage, count in result.get("loss_by_stage", {}).items():
            total_loss_by_stage[stage] += count
            format_loss_by_stage[fmt][stage] += count
    
    print("\nTotal loss by stage (across all formats and N values):")
    for stage, count in sorted(total_loss_by_stage.items()):
        print(f"  {stage:30s}: {count:4d} files")
    
    print("\nLoss by stage per format (aggregated across N):")
    for fmt in sorted(format_loss_by_stage.keys()):
        stages = format_loss_by_stage[fmt]
        total = sum(stages.values())
        print(f"\n  {fmt}:")
        for stage, count in sorted(stages.items()):
            pct = count / total * 100 if total > 0 else 0
            print(f"    {stage:30s}: {count:4d} ({pct:5.1f}%)")
    
    # ─── H1-H5 discrimination ────────────────────────────────────────
    print("\n" + "=" * 70)
    print("HYPOTHESIS DISCRIMINATION (H1-H5 from RC-A-003)")
    print("=" * 70)
    
    # Count losses at each stage
    scan_losses = total_loss_by_stage.get("STAGE_1_SCAN", 0)
    delim_losses = total_loss_by_stage.get("STAGE_2_DELIMITATION", 0)
    dedup_losses = total_loss_by_stage.get("STAGE_3_DEDUP", 0)
    judge_losses = total_loss_by_stage.get("STAGE_4_JUDGE", 0)
    no_losses = total_loss_by_stage.get("NONE", 0)
    total_files = sum(total_loss_by_stage.values())
    
    print(f"\n  Total files across all experiments: {total_files}")
    print(f"  Files fully recovered (NONE): {no_losses} ({no_losses/total_files*100:.1f}%)")
    print(f"  Loss at Stage 1 (Scan): {scan_losses} ({scan_losses/total_files*100:.1f}%)")
    print(f"  Loss at Stage 2 (Delimitation): {delim_losses} ({delim_losses/total_files*100:.1f}%)")
    print(f"  Loss at Stage 3 (Dedup): {dedup_losses} ({dedup_losses/total_files*100:.1f}%)")
    print(f"  Loss at Stage 4 (Judge): {judge_losses} ({judge_losses/total_files*100:.1f}%)")
    
    print("\n  Hypothesis assessment:")
    
    # H1: Loss during scanning (signatures not found)
    if scan_losses > 0:
        print(f"  H1 (Scanner loss): SUPPORTED — {scan_losses} files lost at scan stage")
    else:
        print(f"  H1 (Scanner loss): NOT SUPPORTED — scanner finds all signatures")
    
    # H2: Loss during delimitation (footer issues)
    if delim_losses > 0:
        print(f"  H2 (Delimitation loss): SUPPORTED — {delim_losses} files lost at delimitation")
    else:
        print(f"  H2 (Delimitation loss): NOT SUPPORTED — all signatures lead to valid carves")
    
    # H3: Loss during deduplication
    if dedup_losses > 0:
        print(f"  H3 (Dedup loss): SUPPORTED — {dedup_losses} files eliminated by dedup")
    else:
        print(f"  H3 (Dedup loss): NOT SUPPORTED — dedup doesn't eliminate valid files")
    
    # H4: Loss during Judge matching (SHA-256 mismatch)
    if judge_losses > 0:
        print(f"  H4 (Judge loss): SUPPORTED — {judge_losses} files have SHA-256 mismatch")
    else:
        print(f"  H4 (Judge loss): NOT SUPPORTED — all carved files match ground truth")
    
    # H5: Multiple stages
    multi_stage = sum(1 for stage, count in total_loss_by_stage.items() 
                      if count > 0 and stage.startswith("STAGE_"))
    if multi_stage > 1:
        print(f"  H5 (Multi-stage loss): SUPPORTED — losses occur at {multi_stage} different stages")
    else:
        print(f"  H5 (Multi-stage loss): NOT SUPPORTED — losses concentrated at single stage")
    
    # ─── Format-specific diagnosis ────────────────────────────────────
    print("\n" + "=" * 70)
    print("FORMAT-SPECIFIC DIAGNOSIS")
    print("=" * 70)
    
    for ext in [".pdf", ".jpg", ".png", ".zip", ".docx"]:
        # Find the N=15 result for this format
        key = f"N=15_{ext[1:]}"
        result = all_results.get(key, {})
        if "error" in result or not result:
            continue
        
        loss = result.get("loss_by_stage", {})
        total = sum(loss.values())
        if total == 0:
            continue
        
        print(f"\n  {ext[1:].upper()} (N=15):")
        for stage, count in sorted(loss.items()):
            pct = count / total * 100 if total > 0 else 0
            print(f"    {stage:30s}: {count:3d} ({pct:5.1f}%)")
        
        # Show sample traces for lost files
        lost_traces = [t for t in result.get("per_file_traces", []) 
                       if t.get("loss_stage", "NONE") != "NONE"]
        if lost_traces:
            print(f"    Sample loss traces (first 3):")
            for t in lost_traces[:3]:
                print(f"      {t['gt_name']:30s}: loss at {t['loss_stage']}")
                print(f"        {t['loss_detail']}")
    
    # ─── Save output ──────────────────────────────────────────────────
    output_dir = PROJECT_ROOT / "output" / "inst_0002"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save full results
    ledger_entry = {
        "experiment_id": "INST-0002",
        "family": "INST",
        "title": "Pipeline Loss Localization",
        "date": datetime.now(timezone.utc).isoformat(),
        "status": "COMPLETED",
        "question": "¿En qué etapa exacta del pipeline desaparece cada archivo?",
        "pipeline_stages": [
            "STAGE_1_SCAN: Signature detection",
            "STAGE_2_DELIMITATION: File extraction with footer",
            "STAGE_3_DEDUP: Overlap removal",
            "STAGE_4_JUDGE: SHA-256 matching against ground truth",
        ],
        "aggregate_loss_by_stage": dict(total_loss_by_stage),
        "format_loss_by_stage": {k: dict(v) for k, v in format_loss_by_stage.items()},
        "hypothesis_assessment": {
            "H1_scanner_loss": scan_losses,
            "H2_delimitation_loss": delim_losses,
            "H3_dedup_loss": dedup_losses,
            "H4_judge_loss": judge_losses,
            "H5_multi_stage": multi_stage > 1,
        },
        "full_results": all_results,
    }
    
    ledger_path = output_dir / "ledger_entry.json"
    with open(ledger_path, 'w') as f:
        json.dump(ledger_entry, f, indent=2, ensure_ascii=False, default=str)
    
    # Save per-file trace CSV
    csv_path = output_dir / "inst_0002_per_file_trace.csv"
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "format", "n_files", "gt_name", "gt_size", "gt_start_offset",
            "stage_1_scan", "stage_2_delimitation", "stage_3_dedup", "stage_4_judge",
            "loss_stage", "loss_detail"
        ])
        for key, result in all_results.items():
            if "error" in result:
                continue
            fmt = result.get("format", "?")
            n = result.get("n_files", 0)
            for t in result.get("per_file_traces", []):
                writer.writerow([
                    fmt, n, t.get("gt_name", ""), t.get("gt_size", 0),
                    t.get("gt_start_offset", ""),
                    t.get("stage_1_scan", ""), t.get("stage_2_delimitation", ""),
                    t.get("stage_3_dedup", ""), t.get("stage_4_judge", ""),
                    t.get("loss_stage", ""), t.get("loss_detail", ""),
                ])
    
    # Save summary
    summary = {
        "experiment_id": "INST-0002",
        "date": datetime.now(timezone.utc).isoformat(),
        "total_files_traced": total_files,
        "fully_recovered": no_losses,
        "loss_at_scan": scan_losses,
        "loss_at_delimitation": delim_losses,
        "loss_at_dedup": dedup_losses,
        "loss_at_judge": judge_losses,
        "formats_tested": [ext for ext, _ in configs],
        "n_values_tested": list(set(n for _, ns in configs for n in ns)),
    }
    
    summary_path = output_dir / "inst_0002_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n  Output directory: {output_dir}")
    print(f"  Ledger: {ledger_path}")
    print(f"  Per-file trace: {csv_path}")
    print(f"  Summary: {summary_path}")
    
    print(f"\n  INST-0002 COMPLETE")
    
    return ledger_entry


if __name__ == "__main__":
    run_inst_0002()
