"""
RecoveryLab — Pipeline Stages
================================
Concrete implementations of each pipeline stage.

Image → Detect → NTFS → MFT → Journal → Fragment → Carving → Merge → Score
"""

import hashlib
import time
from typing import Dict, List, Optional, Any

from .pipeline import PipelineStage, PipelineContext


class DetectStage(PipelineStage):
    """Detect filesystem type from the image."""
    
    @property
    def name(self) -> str:
        return "detect"
    
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        # Check for NTFS signature
        if len(ctx.image) >= 11 and ctx.image[3:11] == b'NTFS    ':
            ctx.filesystem_type = "NTFS"
            ctx.is_valid_image = True
        elif len(ctx.image) >= 54 and ctx.image[54:62] == b'FAT32   ':
            ctx.filesystem_type = "FAT32"
            ctx.is_valid_image = True
        else:
            ctx.filesystem_type = "UNKNOWN"
            ctx.is_valid_image = False
            ctx.errors.append("Unknown filesystem type")
        
        return ctx


class NTFSParseStage(PipelineStage):
    """Parse NTFS metadata (VBR, MFT entries, Journal)."""
    
    @property
    def name(self) -> str:
        return "ntfs_parse"
    
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.filesystem_type != "NTFS":
            return ctx
        
        from ntfs_parser.parser import parse_ntfs_image
        ctx.ntfs_metadata = parse_ntfs_image(ctx.image, cluster_size=ctx.cluster_size)
        ctx.mft_entries = ctx.ntfs_metadata.mft_entries
        ctx.journal_entries = ctx.ntfs_metadata.journal_entries
        
        return ctx


class MFTStage(PipelineStage):
    """Recover files using MFT entries (Strategy A)."""
    
    @property
    def name(self) -> str:
        return "mft"
    
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.ntfs_metadata:
            return ctx
        
        from ntfs_parser.parser import recover_file_data
        
        for entry in ctx.mft_entries:
            if not entry.in_use or entry.is_directory or entry.record_number < 12:
                continue
            if not entry.filename:
                continue
            
            file_data = recover_file_data(ctx.image, entry, cluster_size=ctx.cluster_size)
            if file_data is None:
                continue
            
            # Trim to actual size
            actual_size = entry.data_size if entry.data_size > 0 else len(file_data)
            if len(file_data) > actual_size:
                file_data = file_data[:actual_size]
            
            sha256 = hashlib.sha256(file_data).hexdigest()
            num_runs = len(entry.data_runs)
            
            ctx.recovered_from_mft.append({
                "id": f"mft_{entry.record_number}",
                "name": entry.filename,
                "size": len(file_data),
                "sha256": sha256,
                "source": "mft",
                "confidence": 1.0,
                "num_runs": num_runs,
                "is_fragmented": num_runs > 1,
                "is_sparse": entry.is_sparse if hasattr(entry, 'is_sparse') else False,
                "data": file_data,
                "entry": entry,
            })
        
        return ctx


class JournalStage(PipelineStage):
    """Recover files using USN Journal (Strategy B)."""
    
    @property
    def name(self) -> str:
        return "journal"
    
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.ntfs_metadata:
            return ctx
        
        from ntfs_parser.parser import recover_from_journal, recover_file_data
        
        candidates = recover_from_journal(ctx.ntfs_metadata, ctx.image, 
                                          cluster_size=ctx.cluster_size)
        
        # Skip files already found by MFT
        mft_names = {r["name"].lower() for r in ctx.recovered_from_mft}
        
        for candidate in candidates:
            filename = candidate.get("filename", "")
            if not filename or filename.lower() in mft_names:
                continue
            
            mft_rec = candidate.get("mft_record", 0)
            file_data = None
            if mft_rec in ctx.ntfs_metadata.files_by_record:
                entry = ctx.ntfs_metadata.files_by_record[mft_rec]
                file_data = recover_file_data(ctx.image, entry, 
                                             cluster_size=ctx.cluster_size)
            
            sha256 = hashlib.sha256(file_data).hexdigest() if file_data else ""
            size = len(file_data) if file_data else 0
            confidence = 0.8 if file_data else 0.3
            if candidate.get("is_delete"):
                confidence *= 0.7
            
            ctx.recovered_from_journal.append({
                "id": f"journal_{mft_rec}",
                "name": filename,
                "size": size,
                "sha256": sha256,
                "source": "journal",
                "confidence": confidence,
                "num_runs": 1,
                "is_fragmented": False,
                "data": file_data or b"",
            })
        
        return ctx


class FragmentStage(PipelineStage):
    """Reconstruct fragmented and sparse files (Strategy D)."""
    
    @property
    def name(self) -> str:
        return "fragment"
    
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        # Fragment/sparse recovery is already done by MFT stage
        # (it follows all data runs including sparse ones).
        # This stage enriches the results with sparse metadata
        # and adjusts confidence for sparse files.
        
        # Mark sparse files and adjust confidence
        for item in ctx.recovered_from_mft:
            entry = item.get("entry")
            if entry and hasattr(entry, 'is_sparse') and entry.is_sparse:
                item["is_sparse"] = True
                # Sparse files: slight confidence reduction because
                # we fill gaps with zeros (correct for NTFS sparse,
                # but might not match original if file was corrupted)
                if item.get("confidence", 0) >= 0.9:
                    item["confidence"] = 0.95
        
        return ctx


class CarvingStage(PipelineStage):
    """Recover files by signature carving (Strategy C)."""
    
    @property
    def name(self) -> str:
        return "carving"
    
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        # Only run carving for files not already found by MFT/Journal
        # (carving is expensive — reads entire image)
        already_found = {r["name"].lower() for r in ctx.recovered_from_mft}
        already_found.update(r["name"].lower() for r in ctx.recovered_from_journal)
        
        # Also match by SHA-256 (carving finds files even with wrong names)
        already_sha = {r["sha256"] for r in ctx.recovered_from_mft 
                       if r["sha256"]}
        already_sha.update(r["sha256"] for r in ctx.recovered_from_journal 
                          if r["sha256"])
        
        from motors.motor_carving import MotorCarving
        motor = MotorCarving()
        
        # Carving needs a manifest-like dict
        carving_manifest = {
            "cluster_size": ctx.cluster_size,
            "total_clusters": len(ctx.image) // ctx.cluster_size,
        }
        
        result = motor.recover(ctx.image, carving_manifest)
        
        for rf in result.recovered_files:
            # Skip if already found (by name or SHA)
            if rf.name.lower() in already_found:
                continue
            if rf.sha256 and rf.sha256 in already_sha:
                continue
            
            ctx.recovered_from_carving.append({
                "id": f"carved_{len(ctx.recovered_from_carving)}",
                "name": rf.name,
                "size": rf.size,
                "sha256": rf.sha256,
                "source": "carving",
                "confidence": rf.confidence,
                "num_runs": 1,
                "is_fragmented": False,
                "data": rf.data,
            })
        
        return ctx


class MergeStage(PipelineStage):
    """Merge results from all strategies, deduplicating."""
    
    @property
    def name(self) -> str:
        return "merge"
    
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        # Priority order: MFT > Journal > Fragment > Carving
        all_results = (
            ctx.recovered_from_mft +
            ctx.recovered_from_journal +
            ctx.recovered_from_fragment +
            ctx.recovered_from_carving
        )
        
        # Dedup by filename (first occurrence wins — priority order)
        seen_names = set()
        seen_sha = set()
        
        for item in all_results:
            name_lower = item["name"].lower()
            sha = item.get("sha256", "")
            
            if name_lower in seen_names:
                continue
            if sha and sha in seen_sha:
                continue
            
            seen_names.add(name_lower)
            if sha:
                seen_sha.add(sha)
            
            ctx.all_recovered.append(item)
        
        return ctx


class ScoringStage(PipelineStage):
    """Compute RR and RFS metrics."""
    
    @property
    def name(self) -> str:
        return "scoring"
    
    def execute(self, ctx: PipelineContext) -> PipelineContext:
        # Compute RR based on what we found vs what we recovered
        total_found = len(ctx.all_recovered)
        recovered_with_data = sum(1 for item in ctx.all_recovered 
                                  if item.get("data") and len(item.get("data", b"")) > 0)
        
        if total_found > 0:
            ctx.recovery_rate = recovered_with_data / total_found
        else:
            ctx.recovery_rate = 0.0
        
        # If we have a manifest, also verify SHA-256 matches
        if ctx.manifest:
            manifest_files = [f for f in ctx.manifest.get("files", []) 
                             if not f.get("is_directory", False)]
            manifest_sha = {f.get("name", ""): f.get("sha256", "") 
                           for f in manifest_files if "sha256" in f}
            
            verified = 0
            for item in ctx.all_recovered:
                expected = manifest_sha.get(item["name"])
                if expected and item.get("sha256") == expected:
                    verified += 1
            
            total = len(manifest_files)
            if total > 0:
                # Use manifest-based RR (more accurate)
                ctx.recovery_rate = verified / total
        
        # Compute RFS (simplified — full 9-component needs per-file comparison)
        # For now, estimate based on sources
        mft_count = len(ctx.recovered_from_mft)
        carving_count = len(ctx.recovered_from_carving)
        journal_count = len(ctx.recovered_from_journal)
        
        rfs_total = total_found  # Use total found, not manifest total
        if rfs_total > 0:
            # MFT gives ~0.85 RFS, journal ~0.70, carving ~0.45
            mft_in_total = min(mft_count, rfs_total)
            journal_in_total = min(journal_count, rfs_total - mft_in_total)
            carving_in_total = min(carving_count, rfs_total - mft_in_total - journal_in_total)
            rfs_sum = (mft_in_total * 0.85 + journal_in_total * 0.70 + carving_in_total * 0.45)
            ctx.fidelity_score = min(rfs_sum / rfs_total, 1.0)
        
        return ctx
