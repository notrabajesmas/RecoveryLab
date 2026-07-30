"""
RecoveryLab — Read Classification Instrumentation
====================================================
Formalizes what counts as a "useful read" (Objeción 2 / formalización).

Every sector read is classified into exactly one category:
  1. DATA_READ       — Contains file data (ground truth)
  2. METADATA_READ   — Contains MFT, bitmap, journal, INDX
  3. DIAGNOSTIC_READ — Read to determine disk state
  4. REDUNDANT_READ  — Already read (duplicate)
  5. WASTED_READ     — No useful information (free space, zeros)

This module provides:
  - A SectorClassifier that maps sectors to categories using the manifest
  - A ReadTracker that tracks reads in real-time as motors execute
  - Integration helpers for Motor A and Motor B
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
from pathlib import Path


@dataclass
class ReadClassification:
    """Classification of all reads performed during recovery."""
    data_reads: int = 0       # Sectors containing file data
    metadata_reads: int = 0   # Sectors containing MFT, bitmap, journal, INDX
    diagnostic_reads: int = 0 # Sectors read to determine disk state
    redundant_reads: int = 0  # Sectors already read (duplicate)
    wasted_reads: int = 0     # Sectors with no useful information

    @property
    def total_reads(self) -> int:
        return (self.data_reads + self.metadata_reads +
                self.diagnostic_reads + self.redundant_reads + self.wasted_reads)

    def useful_reads_v1(self) -> int:
        """Useful = data + metadata + diagnostic (anything that provides information)."""
        return self.data_reads + self.metadata_reads + self.diagnostic_reads

    def useful_reads_v2(self) -> int:
        """Useful = data + metadata (only reads that directly contribute to recovery)."""
        return self.data_reads + self.metadata_reads

    def efficiency_v1(self) -> float:
        """Fraction of reads that provide any information."""
        total = self.total_reads
        return self.useful_reads_v1() / total if total > 0 else 0.0

    def efficiency_v2(self) -> float:
        """Fraction of reads that directly contribute to recovery."""
        total = self.total_reads
        return self.useful_reads_v2() / total if total > 0 else 0.0

    def to_dict(self) -> Dict:
        return {
            "data_reads": self.data_reads,
            "metadata_reads": self.metadata_reads,
            "diagnostic_reads": self.diagnostic_reads,
            "redundant_reads": self.redundant_reads,
            "wasted_reads": self.wasted_reads,
            "total_reads": self.total_reads,
            "efficiency_v1": round(self.efficiency_v1(), 4),
            "efficiency_v2": round(self.efficiency_v2(), 4),
        }


class SectorClassifier:
    """
    Maps sectors to read categories using the manifest.

    This is the key piece: given a manifest (ground truth), we can
    determine EXACTLY what each sector contains. This lets us classify
    every read into one of the 5 categories.

    Note: This uses the manifest (ground truth) for classification.
    In a real recovery scenario, we wouldn't have this. But for
    measuring and comparing motors, it's essential.
    """

    def __init__(self, manifest: Dict, cluster_size: int = 4096,
                 sector_size: int = 512):
        self.manifest = manifest
        self.cluster_size = cluster_size
        self.sector_size = sector_size
        self.sectors_per_cluster = cluster_size // sector_size

        # Build sector maps
        self._data_sectors: Set[int] = set()
        self._metadata_sectors: Set[int] = set()
        self._allocated_sectors: Set[int] = set()

        self._build_maps()

    def _build_maps(self):
        """Build sets of sector numbers for each category."""
        mft_info = self.manifest.get("mft", {})
        bitmap_info = self.manifest.get("bitmap", {})
        logfile_info = self.manifest.get("logfile", {})
        mftmirr_info = self.manifest.get("mftmirr", {})

        # Metadata sectors: MFT, Bitmap, Journal, MFT Mirror
        self._add_clusters_to_set(self._metadata_sectors,
                                  mft_info.get("start_cluster", 0),
                                  mft_info.get("clusters", []))
        self._add_clusters_to_set(self._metadata_sectors,
                                  bitmap_info.get("start_cluster", 0),
                                  bitmap_info.get("clusters", []))
        self._add_clusters_to_set(self._metadata_sectors,
                                  logfile_info.get("start_cluster", 0),
                                  logfile_info.get("clusters", []))
        self._add_clusters_to_set(self._metadata_sectors,
                                  mftmirr_info.get("start_cluster", 0),
                                  mftmirr_info.get("clusters", []))

        # Data sectors: file data clusters
        for f in self.manifest.get("files", []):
            if f.get("is_directory", False):
                continue
            if f.get("is_resident", False):
                continue  # Resident data is in MFT (metadata)
            for cluster in f.get("clusters", []):
                for s in range(cluster * self.sectors_per_cluster,
                              (cluster + 1) * self.sectors_per_cluster):
                    self._data_sectors.add(s)

        # Allocated sectors: all sectors that have useful data
        self._allocated_sectors = self._data_sectors | self._metadata_sectors

        # VBR is metadata
        for s in range(0, self.sectors_per_cluster):
            self._metadata_sectors.add(s)

    def _add_clusters_to_set(self, sector_set: Set[int],
                              start_cluster: int,
                              cluster_list: List[int]):
        """Add all sectors in the given clusters to the set."""
        for cluster in cluster_list:
            for s in range(cluster * self.sectors_per_cluster,
                          (cluster + 1) * self.sectors_per_cluster):
                sector_set.add(s)

    def classify(self, sector: int) -> str:
        """Classify a single sector read."""
        if sector in self._data_sectors:
            return "DATA_READ"
        elif sector in self._metadata_sectors:
            return "METADATA_READ"
        else:
            return "WASTED_READ"

    def classify_cluster(self, cluster: int) -> str:
        """Classify all sectors in a cluster. Returns the dominant category."""
        start_sector = cluster * self.sectors_per_cluster
        categories = {}
        for s in range(start_sector, start_sector + self.sectors_per_cluster):
            cat = self.classify(s)
            categories[cat] = categories.get(cat, 0) + 1

        # Return the dominant category
        if categories.get("DATA_READ", 0) > 0:
            return "DATA_READ"
        elif categories.get("METADATA_READ", 0) > 0:
            return "METADATA_READ"
        else:
            return "WASTED_READ"


class ReadTracker:
    """
    Tracks reads in real-time as motors execute.

    Usage:
        tracker = ReadTracker(classifier)
        tracker.mark_read(sector)
        tracker.mark_cluster_read(cluster)
        classification = tracker.get_classification()
    """

    def __init__(self, classifier: SectorClassifier):
        self.classifier = classifier
        self.read_sectors: Set[int] = set()
        self.classification = ReadClassification()

    def mark_read(self, sector: int, override_category: str = None):
        """Record a sector read and classify it."""
        if sector in self.read_sectors:
            self.classification.redundant_reads += 1
            return

        self.read_sectors.add(sector)

        if override_category:
            cat = override_category
        else:
            cat = self.classifier.classify(sector)

        if cat == "DATA_READ":
            self.classification.data_reads += 1
        elif cat == "METADATA_READ":
            self.classification.metadata_reads += 1
        elif cat == "DIAGNOSTIC_READ":
            self.classification.diagnostic_reads += 1
        elif cat == "WASTED_READ":
            self.classification.wasted_reads += 1

    def mark_cluster_read(self, cluster: int, override_category: str = None):
        """Record all sectors in a cluster as read."""
        spc = self.classifier.sectors_per_cluster
        start = cluster * spc
        for s in range(start, start + spc):
            self.mark_read(s, override_category)

    def mark_diagnostic(self, sector: int):
        """Record a sector read as diagnostic (motor chose to read it for diagnosis)."""
        if sector in self.read_sectors:
            self.classification.redundant_reads += 1
            return
        self.read_sectors.add(sector)
        self.classification.diagnostic_reads += 1

    def get_classification(self) -> ReadClassification:
        """Get the current read classification."""
        return self.classification

    def reset(self):
        """Reset the tracker for a new run."""
        self.read_sectors.clear()
        self.classification = ReadClassification()
