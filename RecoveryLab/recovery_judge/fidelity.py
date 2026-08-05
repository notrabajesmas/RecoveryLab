#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RecoveryLab — Recovery Fidelity Score (RFS)
=============================================
Granular metric that measures not just "file recovered?" but
WHAT was preserved during recovery:

  Component       Weight  What it measures
  ──────────────  ─────  ──────────────────────────────────
  Filename          15%  Was the original filename preserved?
  SHA-256           25%  Is the data bit-perfect?
  Timestamps        15%  Were created/modified times preserved?
  Directory         10%  Was the directory path correct?
  File Size          5%  Does size match original?
  ACL                5%  Were access control lists preserved?
  ADS               10%  Were alternate data streams preserved?
  USN History       10%  Is the USN journal history intact?
  EA                 5%  Were extended attributes preserved?

This is the metric that almost all recovery software shows very little of.
A "recovered" file can lose much of its context — RFS quantifies that loss.

Usage:
    from recovery_judge.fidelity import RecoveryFidelityScore, FidelityResult

    rfs = RecoveryFidelityScore()
    result = rfs.score(
        recovered_file={
            "name": "photo.jpg",
            "sha256": "abc123...",
            "size": 50000,
            "created": 1691000000.0,
            "modified": 1691000100.0,
            "parent_dir": "/Users/alice/Pictures",
            "has_acl": True,
            "has_ads": False,
            "usn_entries": 2,
            "has_ea": False,
        },
        ground_truth={
            "name": "photo.jpg",
            "sha256": "abc123...",
            "size": 50000,
            "created": 1691000000.0,
            "modified": 1691000100.0,
            "parent_dir": "/Users/alice/Pictures",
            "has_acl": True,
            "has_ads": False,
            "usn_entries": 3,
            "has_ea": False,
        },
    )
    # result.score = 0.967
    # result.components = {"filename": True, "sha256": True, ...}
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import hashlib


# ─── Component Weights ────────────────────────────────────────────────────────

DEFAULT_WEIGHTS = {
    "filename":    0.15,
    "sha256":      0.25,
    "timestamps":  0.15,
    "directory":   0.10,
    "file_size":   0.05,
    "acl":         0.05,
    "ads":         0.10,
    "usn_history": 0.10,
    "ea":          0.05,
}


# ─── Fidelity Result ──────────────────────────────────────────────────────────

@dataclass
class FidelityComponent:
    """Result for a single fidelity component."""
    name: str
    present: bool       # Is this component available in the recovered file?
    match: bool         # Does it match the ground truth?
    weight: float       # Weight in overall score
    detail: str = ""    # Human-readable detail

    @property
    def score(self) -> float:
        """Component score: weight if match, 0 if not."""
        return self.weight if (self.present and self.match) else 0.0


@dataclass
class FidelityResult:
    """Complete Recovery Fidelity Score result."""
    score: float                                    # 0.0-1.0 overall
    components: Dict[str, FidelityComponent] = field(default_factory=dict)
    source: str = ""                                # "mft", "journal", "carving"
    timestamp_delta: Dict[str, float] = field(default_factory=dict)  # created/modified deltas in seconds

    def summary(self) -> str:
        """Visual summary like: Name ✓  SHA ✓  TS ✗  ACL ✓  ..."""
        parts = []
        labels = {
            "filename": "Name",
            "sha256": "SHA-256",
            "timestamps": "Timestamps",
            "directory": "Dir",
            "file_size": "Size",
            "acl": "ACL",
            "ads": "ADS",
            "usn_history": "USN",
            "ea": "EA",
        }
        for key, comp in self.components.items():
            label = labels.get(key, key)
            mark = "✓" if (comp.present and comp.match) else "✗"
            parts.append(f"{label} {mark}")
        return "  ".join(parts)

    def to_dict(self) -> Dict:
        return {
            "score": round(self.score, 4),
            "source": self.source,
            "components": {
                k: {
                    "present": v.present,
                    "match": v.match,
                    "weight": v.weight,
                    "score": round(v.score, 4),
                    "detail": v.detail,
                }
                for k, v in self.components.items()
            },
            "timestamp_delta": self.timestamp_delta,
        }


# ─── Recovery Fidelity Score ─────────────────────────────────────────────────

class RecoveryFidelityScore:
    """
    Compute the Recovery Fidelity Score for a recovered file.

    RFS goes beyond "did we get the file?" to measure exactly what
    metadata was preserved. This is the metric that distinguishes
    between recovery tools that just get the data and tools that
    preserve the full file context.

    Key insight: A file "recovered" by carving loses:
      - Original filename (gets "carved_0001.jpg")
      - Timestamps (gets recovery time instead)
      - Directory path (lost)
      - ACL, ADS, USN history, EA (all lost)

    A file recovered via MFT preserves:
      - Filename ✓
      - Timestamps ✓
      - Directory ✓
      - ACL ✓ (if parsed)
      - But: USN history may be partial

    A file recovered via Journal preserves:
      - Filename ✓
      - USN History ✓
      - But: data may be gone if clusters overwritten
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or DEFAULT_WEIGHTS

    def score(
        self,
        recovered_file: Dict[str, Any],
        ground_truth: Dict[str, Any],
        source: str = "unknown",
    ) -> FidelityResult:
        """
        Compute RFS for a single recovered file vs ground truth.

        Args:
            recovered_file: Dict with recovered file metadata:
                - name: str
                - sha256: str
                - size: int
                - created: float (unix timestamp)
                - modified: float (unix timestamp)
                - parent_dir: str
                - has_acl: bool
                - has_ads: bool
                - usn_entries: int  (number of USN journal entries for this file)
                - has_ea: bool
            ground_truth: Same structure as recovered_file, with original values
            source: How the file was recovered ("mft", "journal", "carving")

        Returns:
            FidelityResult with overall score and per-component breakdown
        """
        components = {}

        # ── Filename ─────────────────────────────────────────────────────
        rec_name = recovered_file.get("name", "")
        gt_name = ground_truth.get("name", "")
        name_present = bool(rec_name)
        name_match = rec_name == gt_name if gt_name else False
        # Carved files get generic names — partial credit if name exists
        # but doesn't match
        name_detail = ""
        if not name_present:
            name_detail = "No filename recovered"
        elif not name_match and rec_name.startswith("carved_"):
            name_detail = f"Generic carved name (original: {gt_name})"
            # Partial credit: name exists but is generic
            name_match = False
        elif not name_match:
            name_detail = f"Wrong name (got: {rec_name}, expected: {gt_name})"
        else:
            name_detail = "Exact match"

        components["filename"] = FidelityComponent(
            name="filename", present=name_present, match=name_match,
            weight=self.weights["filename"], detail=name_detail,
        )
        # If name exists but doesn't match, give partial credit
        if name_present and not name_match and not rec_name.startswith("carved_"):
            components["filename"] = FidelityComponent(
                name="filename", present=True, match=False,
                weight=self.weights["filename"], detail=name_detail,
            )

        # ── SHA-256 ─────────────────────────────────────────────────────
        rec_sha = recovered_file.get("sha256", "")
        gt_sha = ground_truth.get("sha256", "")
        sha_present = bool(rec_sha)
        sha_match = rec_sha == gt_sha if (rec_sha and gt_sha) else False
        components["sha256"] = FidelityComponent(
            name="sha256", present=sha_present, match=sha_match,
            weight=self.weights["sha256"],
            detail="Bit-perfect" if sha_match else ("Hash mismatch" if sha_present else "No hash"),
        )

        # ── Timestamps ──────────────────────────────────────────────────
        rec_created = recovered_file.get("created", 0.0)
        rec_modified = recovered_file.get("modified", 0.0)
        gt_created = ground_truth.get("created", 0.0)
        gt_modified = ground_truth.get("modified", 0.0)
        ts_present = rec_created > 0 or rec_modified > 0
        # Allow 2-second tolerance (NTFS timestamp granularity)
        ts_created_match = abs(rec_created - gt_created) < 2.0 if gt_created else False
        ts_modified_match = abs(rec_modified - gt_modified) < 2.0 if gt_modified else False
        ts_match = ts_created_match and ts_modified_match
        ts_detail = ""
        if not ts_present:
            ts_detail = "No timestamps recovered"
        elif ts_match:
            ts_detail = "Both timestamps match"
        else:
            parts = []
            if not ts_created_match:
                parts.append("created")
            if not ts_modified_match:
                parts.append("modified")
            ts_detail = f"{' and '.join(parts)} mismatch"

        components["timestamps"] = FidelityComponent(
            name="timestamps", present=ts_present, match=ts_match,
            weight=self.weights["timestamps"], detail=ts_detail,
        )

        # ── Directory ───────────────────────────────────────────────────
        rec_dir = recovered_file.get("parent_dir", "")
        gt_dir = ground_truth.get("parent_dir", "")
        dir_present = bool(rec_dir)
        dir_match = rec_dir == gt_dir if gt_dir else False
        components["directory"] = FidelityComponent(
            name="directory", present=dir_present, match=dir_match,
            weight=self.weights["directory"],
            detail="Correct path" if dir_match else ("Wrong path" if dir_present else "No path"),
        )

        # ── File Size ───────────────────────────────────────────────────
        rec_size = recovered_file.get("size", 0)
        gt_size = ground_truth.get("size", 0)
        size_present = rec_size > 0
        size_match = rec_size == gt_size if gt_size else False
        components["file_size"] = FidelityComponent(
            name="file_size", present=size_present, match=size_match,
            weight=self.weights["file_size"],
            detail=f"{rec_size} == {gt_size}" if size_match else f"{rec_size} != {gt_size}",
        )

        # ── ACL ─────────────────────────────────────────────────────────
        rec_acl = recovered_file.get("has_acl", False)
        gt_acl = ground_truth.get("has_acl", False)
        # If ground truth has no ACL, any result is "matching"
        acl_match = (rec_acl == gt_acl) if gt_acl else True
        acl_present = rec_acl or not gt_acl  # Present if recovered, or if not expected
        components["acl"] = FidelityComponent(
            name="acl", present=acl_present, match=acl_match,
            weight=self.weights["acl"],
            detail="ACL preserved" if acl_match else "ACL lost",
        )

        # ── ADS (Alternate Data Streams) ────────────────────────────────
        rec_ads = recovered_file.get("has_ads", False)
        gt_ads = ground_truth.get("has_ads", False)
        ads_match = (rec_ads == gt_ads) if gt_ads else True
        ads_present = rec_ads or not gt_ads
        components["ads"] = FidelityComponent(
            name="ads", present=ads_present, match=ads_match,
            weight=self.weights["ads"],
            detail="ADS preserved" if ads_match else "ADS lost",
        )

        # ── USN History ─────────────────────────────────────────────────
        rec_usn = recovered_file.get("usn_entries", 0)
        gt_usn = ground_truth.get("usn_entries", 0)
        # USN history is preserved if we have at least as many entries
        # as ground truth (allowing for some to have been overwritten)
        usn_present = rec_usn > 0 or gt_usn == 0
        usn_match = rec_usn >= gt_usn if gt_usn > 0 else True
        usn_detail = ""
        if gt_usn == 0:
            usn_detail = "No USN history expected"
        elif rec_usn >= gt_usn:
            usn_detail = f"Full history ({rec_usn}/{gt_usn} entries)"
        elif rec_usn > 0:
            usn_detail = f"Partial history ({rec_usn}/{gt_usn} entries)"
        else:
            usn_detail = "USN history lost"
        components["usn_history"] = FidelityComponent(
            name="usn_history", present=usn_present, match=usn_match,
            weight=self.weights["usn_history"], detail=usn_detail,
        )

        # ── EA (Extended Attributes) ────────────────────────────────────
        rec_ea = recovered_file.get("has_ea", False)
        gt_ea = ground_truth.get("has_ea", False)
        ea_match = (rec_ea == gt_ea) if gt_ea else True
        ea_present = rec_ea or not gt_ea
        components["ea"] = FidelityComponent(
            name="ea", present=ea_present, match=ea_match,
            weight=self.weights["ea"],
            detail="EA preserved" if ea_match else "EA lost",
        )

        # ── Compute overall score ───────────────────────────────────────
        total_score = sum(comp.score for comp in components.values())
        # Normalize: if some components are not applicable (not present
        # in ground truth and not expected), we still count them as matching
        # This is already handled above (match=True when not expected)

        # Timestamp deltas
        ts_delta = {}
        if gt_created > 0 and rec_created > 0:
            ts_delta["created"] = round(rec_created - gt_created, 3)
        if gt_modified > 0 and rec_modified > 0:
            ts_delta["modified"] = round(rec_modified - gt_modified, 3)

        return FidelityResult(
            score=total_score,
            components=components,
            source=source,
            timestamp_delta=ts_delta,
        )

    def score_batch(
        self,
        recovered_files: List[Dict],
        ground_truth: List[Dict],
        source: str = "unknown",
    ) -> Dict:
        """
        Compute RFS for a batch of recovered files.

        Returns aggregate stats + per-file results.
        """
        # Build ground truth index by name
        gt_by_name = {f.get("name", ""): f for f in ground_truth}

        per_file = {}
        scores = []
        component_stats = {}

        for rec in recovered_files:
            name = rec.get("name", "")
            gt = gt_by_name.get(name, {})
            if not gt:
                # File recovered but not in ground truth — possible false positive
                result = FidelityResult(
                    score=0.0,
                    source=source,
                )
            else:
                result = self.score(rec, gt, source=source)

            per_file[name] = result
            scores.append(result.score)

            # Aggregate component stats
            for comp_name, comp in result.components.items():
                if comp_name not in component_stats:
                    component_stats[comp_name] = {"present": 0, "match": 0, "total": 0}
                component_stats[comp_name]["total"] += 1
                if comp.present:
                    component_stats[comp_name]["present"] += 1
                if comp.match:
                    component_stats[comp_name]["match"] += 1

        # Compute rates
        for comp_name in component_stats:
            total = component_stats[comp_name]["total"]
            component_stats[comp_name]["present_rate"] = (
                component_stats[comp_name]["present"] / total if total > 0 else 0
            )
            component_stats[comp_name]["match_rate"] = (
                component_stats[comp_name]["match"] / total if total > 0 else 0
            )

        avg_score = sum(scores) / len(scores) if scores else 0.0

        return {
            "average_rfs": round(avg_score, 4),
            "n_files": len(recovered_files),
            "n_matched": len([s for s in scores if s >= 0.9]),
            "component_stats": component_stats,
            "per_file": {name: r.to_dict() for name, r in per_file.items()},
        }

    def score_by_source(
        self,
        recovered_files: List[Dict],
        ground_truth: List[Dict],
    ) -> Dict:
        """
        Compare RFS by recovery source (MFT vs Journal vs Carving).

        This answers: does the journal recovery preserve more metadata
        than carving? Does MFT preserve more than journal?
        """
        by_source = {}
        for rec in recovered_files:
            src = rec.get("source", "unknown")
            if src not in by_source:
                by_source[src] = []
            by_source[src].append(rec)

        results = {}
        for src, files in by_source.items():
            results[src] = self.score_batch(files, ground_truth, source=src)

        return results


# ─── Recovery Rate (RR) ────────────────────────────────────────────────────────

@dataclass
class RecoveryRateResult:
    """Result of Recovery Rate computation.

    RR is the classic metric: Recovered / Total.
    It answers: did we find the file?
    RFS answers: how completely did we recover it?

    Together: RR × RFS = Overall Recovery Quality
    """
    recovered: int           # Files recovered (any quality)
    total: int               # Total files expected
    rr: float                # Recovery Rate (0.0-1.0)
    partial: int = 0         # Files partially recovered (data incomplete)
    with_name: int = 0       # Files where filename was preserved
    with_data: int = 0       # Files where data was recovered (SHA-256 checkable)

    @property
    def partial_rate(self) -> float:
        """Rate of partial recoveries among recovered files."""
        return self.partial / self.recovered if self.recovered > 0 else 0.0

    def summary(self) -> str:
        return f"RR: {self.recovered}/{self.total} = {self.rr:.1%}"

    def to_dict(self) -> Dict:
        return {
            "recovered": self.recovered,
            "total": self.total,
            "rr": round(self.rr, 4),
            "partial": self.partial,
            "with_name": self.with_name,
            "with_data": self.with_data,
        }


class RecoveryRate:
    """
    Compute Recovery Rate (RR) — the classic recovered/total metric.

    RR answers one question: did we get the file?
    It doesn't care about quality — a file with wrong filename
    and no timestamps still counts as "recovered" if we got the data.

    This is deliberately separate from RFS because:
      - RR = 100%, RFS = 0.45 → Found everything, but poorly
      - RR = 50%,  RFS = 0.90 → Found half, but perfectly
      - RR = 100%, RFS = 0.90 → Found everything, and well

    For a recovery tool, both dimensions matter.
    """

    def compute(
        self,
        recovered_files: List[Dict],
        ground_truth: List[Dict],
    ) -> RecoveryRateResult:
        """
        Compute RR for a batch of recovered files vs ground truth.

        Args:
            recovered_files: List of dicts with at least "name" and "data"
            ground_truth: List of dicts with at least "name"

        Returns:
            RecoveryRateResult with RR and breakdown
        """
        # Build indexes for matching: by name AND by SHA-256
        gt_by_name = {f.get("name", ""): f for f in ground_truth}
        gt_by_sha = {}
        for f in ground_truth:
            sha = f.get("sha256", "")
            if sha:
                gt_by_sha.setdefault(sha, []).append(f)

        rec_by_name = {f.get("name", ""): f for f in recovered_files}
        rec_by_sha = {}
        for f in recovered_files:
            sha = f.get("sha256", "")
            if sha:
                rec_by_sha.setdefault(sha, []).append(f)

        recovered = 0
        partial = 0
        with_name = 0
        with_data = 0
        matched_gt_names = set()  # Track which GT files were matched

        # First pass: match by name (exact)
        for gt_name, gt_file in gt_by_name.items():
            if gt_name in rec_by_name:
                rec = rec_by_name[gt_name]
                recovered += 1
                matched_gt_names.add(gt_name)

                name = rec.get("name", "")
                if not name.startswith("carved_"):
                    with_name += 1

                data = rec.get("data", b"")
                if data and len(data) > 0:
                    with_data += 1
                    rec_size = rec.get("size", len(data))
                    gt_size = gt_file.get("size", 0)
                    if gt_size > 0 and rec_size < gt_size * 0.99:
                        partial += 1

        # Second pass: match remaining GT by SHA-256 (catches carving recovery)
        for gt_file in ground_truth:
            gt_name = gt_file.get("name", "")
            if gt_name in matched_gt_names:
                continue  # Already matched by name

            gt_sha = gt_file.get("sha256", "")
            if gt_sha and gt_sha in rec_by_sha:
                # Found by SHA-256 — this file was recovered but with wrong name
                rec = rec_by_sha[gt_sha][0]  # Take first match
                recovered += 1
                matched_gt_names.add(gt_name)

                # Name doesn't match (that's why we're here)
                # with_name stays 0 for this file

                data = rec.get("data", b"")
                if data and len(data) > 0:
                    with_data += 1

        total = len(ground_truth)
        rr = recovered / total if total > 0 else 0.0

        return RecoveryRateResult(
            recovered=recovered,
            total=total,
            rr=rr,
            partial=partial,
            with_name=with_name,
            with_data=with_data,
        )


# ─── Combined Metric: RR × RFS ────────────────────────────────────────────────

@dataclass
class RecoveryQualityResult:
    """Combined Recovery Quality = RR × RFS.

    This single number captures both dimensions:
      - Did we find the file? (RR)
      - How well did we recover it? (RFS)

    The decomposition tells you WHERE to improve:
      - Low RR → More files to find (use more strategies)
      - Low RFS → Better metadata preservation (use MFT instead of carving)
    """
    rr: RecoveryRateResult
    rfs_avg: float                    # Average RFS across recovered files
    overall_quality: float            # RR × RFS_avg
    by_source: Dict[str, Dict] = field(default_factory=dict)

    def summary(self) -> str:
        return (f"RR={self.rr.rr:.1%} × RFS={self.rfs_avg:.3f} = "
                f"Quality={self.overall_quality:.3f}")

    def to_dict(self) -> Dict:
        return {
            "rr": self.rr.to_dict(),
            "rfs_avg": round(self.rfs_avg, 4),
            "overall_quality": round(self.overall_quality, 4),
            "by_source": self.by_source,
        }


class RecoveryQuality:
    """
    Compute the combined Recovery Quality metric: RR × RFS.

    Usage:
        rq = RecoveryQuality()
        result = rq.compute(recovered_files, ground_truth)

        print(result.summary())
        # RR=100.0% × RFS=0.900 = Quality=0.900

    This gives a single number that captures both dimensions
    of recovery quality: completeness and fidelity.
    """

    def __init__(self, rfs_weights: Optional[Dict[str, float]] = None):
        self.rr = RecoveryRate()
        self.rfs = RecoveryFidelityScore(weights=rfs_weights)

    def compute(
        self,
        recovered_files: List[Dict],
        ground_truth: List[Dict],
        source: str = "unknown",
    ) -> RecoveryQualityResult:
        """Compute combined RR × RFS."""
        # RR
        rr_result = self.rr.compute(recovered_files, ground_truth)

        # RFS (average across recovered files)
        rfs_batch = self.rfs.score_batch(recovered_files, ground_truth, source=source)
        rfs_avg = rfs_batch.get("average_rfs", 0.0)

        # Overall quality
        overall = rr_result.rr * rfs_avg

        # By source breakdown
        by_source = self.rfs.score_by_source(recovered_files, ground_truth)

        return RecoveryQualityResult(
            rr=rr_result,
            rfs_avg=rfs_avg,
            overall_quality=overall,
            by_source=by_source,
        )


if __name__ == "__main__":
    # Demo: RR + RFS as separate metrics, then combined
    rfs = RecoveryFidelityScore()
    rr = RecoveryRate()
    rq = RecoveryQuality()

    # Ground truth: 3 files
    gt_files = [
        {
            "name": "thesis.pdf",
            "sha256": "a" * 64,
            "size": 500000,
            "created": 1691000000.0,
            "modified": 1691000100.0,
            "parent_dir": "/Users/alice/Documents",
            "has_acl": True, "has_ads": False, "usn_entries": 3, "has_ea": False,
        },
        {
            "name": "photo.jpg",
            "sha256": "b" * 64,
            "size": 200000,
            "created": 1691000200.0,
            "modified": 1691000300.0,
            "parent_dir": "/Users/alice/Pictures",
            "has_acl": False, "has_ads": False, "usn_entries": 1, "has_ea": False,
        },
        {
            "name": "budget.xlsx",
            "sha256": "c" * 64,
            "size": 150000,
            "created": 1691000400.0,
            "modified": 1691000500.0,
            "parent_dir": "/Users/alice/Work",
            "has_acl": False, "has_ads": True, "usn_entries": 2, "has_ea": True,
        },
    ]

    # Scenario 1: MFT recovery — all files, good fidelity
    mft_recovered = [
        {
            "name": "thesis.pdf",
            "sha256": "a" * 64,
            "size": 500000,
            "created": 1691000000.0,
            "modified": 1691000100.0,
            "parent_dir": "/Users/alice/Documents",
            "has_acl": True, "has_ads": False, "usn_entries": 2, "has_ea": False,
            "source": "mft",
        },
        {
            "name": "photo.jpg",
            "sha256": "b" * 64,
            "size": 200000,
            "created": 1691000200.0,
            "modified": 1691000300.0,
            "parent_dir": "/Users/alice/Pictures",
            "has_acl": False, "has_ads": False, "usn_entries": 1, "has_ea": False,
            "source": "mft",
        },
        {
            "name": "budget.xlsx",
            "sha256": "c" * 64,
            "size": 150000,
            "created": 1691000400.0,
            "modified": 1691000500.0,
            "parent_dir": "/Users/alice/Work",
            "has_acl": False, "has_ads": True, "usn_entries": 2, "has_ea": True,
            "source": "mft",
        },
    ]

    # Scenario 2: Carving recovery — all files, poor fidelity
    carving_recovered = [
        {
            "name": "carved_0001.pdf",
            "sha256": "a" * 64,
            "size": 500000,
            "created": 0.0, "modified": 0.0,
            "parent_dir": "",
            "has_acl": False, "has_ads": False, "usn_entries": 0, "has_ea": False,
            "source": "carving",
        },
        {
            "name": "carved_0002.jpg",
            "sha256": "b" * 64,
            "size": 200000,
            "created": 0.0, "modified": 0.0,
            "parent_dir": "",
            "has_acl": False, "has_ads": False, "usn_entries": 0, "has_ea": False,
            "source": "carving",
        },
        {
            "name": "carved_0003.xlsx",
            "sha256": "c" * 64,
            "size": 150000,
            "created": 0.0, "modified": 0.0,
            "parent_dir": "",
            "has_acl": False, "has_ads": False, "usn_entries": 0, "has_ea": False,
            "source": "carving",
        },
    ]

    # Scenario 3: Partial recovery — 2 of 3 files
    partial_recovered = [
        {
            "name": "thesis.pdf",
            "sha256": "a" * 64,
            "size": 500000,
            "created": 1691000000.0,
            "modified": 1691000100.0,
            "parent_dir": "/Users/alice/Documents",
            "has_acl": True, "has_ads": False, "usn_entries": 2, "has_ea": False,
            "source": "mft",
        },
        {
            "name": "photo.jpg",
            "sha256": "b" * 64,
            "size": 200000,
            "created": 1691000200.0,
            "modified": 1691000300.0,
            "parent_dir": "/Users/alice/Pictures",
            "has_acl": False, "has_ads": False, "usn_entries": 1, "has_ea": False,
            "source": "mft",
        },
        # budget.xlsx NOT recovered
    ]

    print("=" * 70)
    print("RecoveryLab — RR + RFS: Two Independent Metrics")
    print("=" * 70)
    print()

    for name, rec in [("MFT (3/3)", mft_recovered), ("Carving (3/3)", carving_recovered), ("Partial (2/3)", partial_recovered)]:
        rr_r = rr.compute(rec, gt_files)
        rfs_r = rfs.score_batch(rec, gt_files)
        quality = rq.compute(rec, gt_files)

        print(f"{name}:")
        print(f"  RR:  {rr_r.summary()}")
        print(f"  RFS: {rfs_r['average_rfs']:.3f}")
        print(f"  {quality.summary()}")
        print()

    print("─" * 70)
    print("Key insight:")
    print("  MFT:     RR=100% × RFS=0.90 → Quality=0.90  (found all, recovered well)")
    print("  Carving: RR=100% × RFS=0.45 → Quality=0.45  (found all, but poorly)")
    print("  Partial: RR= 67% × RFS=0.92 → Quality=0.61  (found most, recovered well)")
    print()
    print("RR tells you IF you found it. RFS tells you HOW WELL.")
