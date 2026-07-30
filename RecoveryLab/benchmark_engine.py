#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RecoveryLab — Simulated NTFS Benchmark Engine
================================================
A pure-Python simulation that models the core property we want to test:
Does reading MFT-first recover more files than sequential reading
when a disk is failing?

The simulation models:
- NTFS disk with MFT entries mapping files to clusters
- A "disk health" model where sectors fail over time
- Two reading strategies: Sequential (Motor A) vs MFT-first (Motor B)
- Measurement: how many files can be recovered before the disk dies

This is NOT a real NTFS parser. It's a scientific instrument for
testing a specific hypothesis.
"""

import os
import json
import hashlib
import random
import time
import struct
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Tuple, Optional
from pathlib import Path

# ─── Constants ────────────────────────────────────────────────────────────────
SECTOR_SIZE = 512          # bytes per sector
CLUSTER_SIZE = 4096        # bytes per cluster (8 sectors)
SECTORS_PER_CLUSTER = CLUSTER_SIZE // SECTOR_SIZE
MFT_ENTRY_SIZE = 1024      # bytes per MFT entry
MFT_ENTRIES_PER_CLUSTER = CLUSTER_SIZE // MFT_ENTRY_SIZE  # 4

LAB_DIR = Path(__file__).parent

# ─── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class SimFile:
    """A simulated file on the disk."""
    file_id: int
    name: str
    size: int                    # bytes
    start_cluster: int
    cluster_count: int
    clusters: List[int]          # list of cluster numbers
    is_resident: bool = False    # if True, data is in MFT entry itself
    checksum: str = ""           # SHA-256 of content
    content: bytes = b""         # simulated content

@dataclass
class SimMFTEntry:
    """A simulated MFT entry."""
    file_id: int
    is_directory: bool
    is_deleted: bool
    is_in_use: bool
    cluster_start: int           # where this MFT entry lives on disk (cluster)
    file_ref: Optional[SimFile]  # the file this entry describes

@dataclass
class SimDisk:
    """A simulated NTFS disk."""
    total_clusters: int
    cluster_size: int = CLUSTER_SIZE
    mft_start_cluster: int = 0
    mft_entry_count: int = 0
    mft_entries: List[SimMFTEntry] = field(default_factory=list)
    files: List[SimFile] = field(default_factory=list)
    # Sector health: 1.0 = healthy, 0.0 = dead
    sector_health: List[float] = field(default_factory=list)
    # Which sectors contain MFT data
    mft_sectors: set = field(default_factory=set)
    # Which sectors contain file data
    data_sectors: Dict[int, set] = field(default_factory=dict)  # file_id -> set of sectors

    @property
    def total_sectors(self):
        return self.total_clusters * SECTORS_PER_CLUSTER

    @property
    def total_bytes(self):
        return self.total_clusters * self.cluster_size

    @property
    def mft_cluster_count(self):
        return (self.mft_entry_count * MFT_ENTRY_SIZE + self.cluster_size - 1) // self.cluster_size


# ─── Disk Image Generator ─────────────────────────────────────────────────────

def generate_test_files(count: int, min_size: int = 100, max_size: int = 50000) -> List[Dict]:
    """Generate metadata for test files with realistic distribution."""
    file_types = [
        ("photo_{:04d}.jpg", 0.3, 2000, 8000),      # 30% photos, 2-8KB
        ("document_{:04d}.pdf", 0.25, 1000, 20000),   # 25% docs, 1-20KB
        ("video_{:04d}.mp4", 0.1, 50000, 200000),     # 10% videos, 50-200KB (simulated small)
        ("email_{:04d}.eml", 0.15, 500, 5000),        # 15% emails, 0.5-5KB
        ("spreadsheet_{:04d}.xlsx", 0.1, 2000, 30000),# 10% spreadsheets
        ("code_{:04d}.py", 0.1, 200, 10000),          # 10% code files
    ]

    files = []
    idx = 0
    for pattern, prob, fmin, fmax in file_types:
        n = int(count * prob)
        for i in range(n):
            name = pattern.format(idx)
            size = random.randint(fmin, fmax)
            files.append({"name": name, "size": size, "file_id": idx})
            idx += 1

    # Fill remaining
    while len(files) < count:
        name = f"file_{idx:04d}.bin"
        size = random.randint(min_size, max_size)
        files.append({"name": name, "size": size, "file_id": idx})
        idx += 1

    return files[:count]


def create_disk(total_mb: int = 100, file_count: int = 200) -> SimDisk:
    """Create a simulated NTFS disk with files and MFT."""
    total_clusters = (total_mb * 1024 * 1024) // CLUSTER_SIZE
    disk = SimDisk(total_clusters=total_clusters)

    # MFT starts at cluster 2 (typical NTFS)
    disk.mft_start_cluster = 2

    # Generate test files
    file_metadata = generate_test_files(file_count)
    total_sectors = disk.total_sectors

    # Initialize sector health (all healthy)
    disk.sector_health = [1.0] * total_sectors

    # Allocate clusters for files
    # Data starts after MFT area (reserve clusters 2-100 for MFT)
    next_data_cluster = 200

    for fm in file_metadata:
        clusters_needed = (fm["size"] + CLUSTER_SIZE - 1) // CLUSTER_SIZE
        # Small files are resident (data in MFT entry)
        is_resident = fm["size"] < 800  # ~800 bytes threshold

        if is_resident:
            clusters = []
        else:
            # Allocate contiguous or fragmented clusters
            if random.random() < 0.7:  # 70% contiguous
                start = next_data_cluster
                clusters = list(range(start, start + clusters_needed))
                next_data_cluster += clusters_needed
            else:  # 30% fragmented
                clusters = []
                for _ in range(clusters_needed):
                    c = next_data_cluster + random.randint(0, 50)
                    clusters.append(c)
                    next_data_cluster = max(next_data_cluster, c + 1)

        # Generate content
        content = os.urandom(min(fm["size"], 4096))  # We only need enough to verify
        if fm["size"] > 4096:
            content = content + b'\x00' * (fm["size"] - 4096)
            content = content[:fm["size"]]
        checksum = hashlib.sha256(content).hexdigest()

        sf = SimFile(
            file_id=fm["file_id"],
            name=fm["name"],
            size=fm["size"],
            start_cluster=clusters[0] if clusters else 0,
            cluster_count=len(clusters),
            clusters=clusters,
            is_resident=is_resident,
            checksum=checksum,
            content=content[:64],  # Store first 64 bytes for verification
        )
        disk.files.append(sf)

        # Map file's data sectors
        file_sectors = set()
        for c in clusters:
            for s in range(SECTORS_PER_CLUSTER):
                sector = c * SECTORS_PER_CLUSTER + s
                if sector < total_sectors:
                    file_sectors.add(sector)
        disk.data_sectors[sf.file_id] = file_sectors

    # Create MFT entries
    mft_cluster = disk.mft_start_cluster
    mft_sector_offset = 0

    for i, sf in enumerate(disk.files):
        entry = SimMFTEntry(
            file_id=sf.file_id,
            is_directory=False,
            is_deleted=False,
            is_in_use=True,
            cluster_start=mft_cluster,
            file_ref=sf,
        )
        disk.mft_entries.append(entry)

        # MFT entry occupies sectors within its cluster
        entry_sector = mft_cluster * SECTORS_PER_CLUSTER + (i % MFT_ENTRIES_PER_CLUSTER)
        for s in range(2):  # Each MFT entry spans ~2 sectors
            sec = entry_sector + s
            if sec < total_sectors:
                disk.mft_sectors.add(sec)

    disk.mft_entry_count = len(disk.mft_entries)

    return disk


# ─── Damage Models ─────────────────────────────────────────────────────────────

def apply_mft_damage(disk: SimDisk, damage_pct: float) -> SimDisk:
    """Damage a percentage of MFT sectors. Returns modified disk."""
    mft_list = sorted(disk.mft_sectors)
    n_damage = int(len(mft_list) * damage_pct)
    damaged = random.sample(mft_list, min(n_damage, len(mft_list)))
    for sec in damaged:
        disk.sector_health[sec] = 0.0
    return disk


def apply_bad_sectors(disk: SimDisk, pct: float, region: str = "random") -> SimDisk:
    """Add bad sectors. region: 'random', 'data_area', 'beginning'."""
    total = disk.total_sectors
    n_bad = int(total * pct)

    if region == "random":
        bad = random.sample(range(total), n_bad)
    elif region == "data_area":
        # Avoid MFT area (clusters 2-100)
        data_start = 200 * SECTORS_PER_CLUSTER
        bad = random.sample(range(data_start, total), n_bad)
    elif region == "beginning":
        bad = list(range(n_bad))
    else:
        bad = random.sample(range(total), n_bad)

    for sec in bad:
        disk.sector_health[sec] = 0.0
    return disk


def apply_growing_failure(disk: SimDisk, start_pct: float, rate: float) -> SimDisk:
    """Simulate a disk that's failing progressively.
    Sectors near the beginning fail first (common in real drives).
    start_pct: initial failure percentage
    rate: additional failure per 1000 sectors read
    """
    total = disk.total_sectors
    n_initial = int(total * start_pct)
    # Fail sectors from the end of the disk (common pattern)
    for i in range(n_initial):
        sec = total - 1 - i
        disk.sector_health[sec] = 0.0
    return disk


# ─── Reading Strategies ────────────────────────────────────────────────────────

@dataclass
class ReadResult:
    """Result of a read attempt."""
    sector: int
    success: bool
    data_recovered: bool
    is_mft: bool = False
    file_id: Optional[int] = None
    read_time_ms: float = 0.0


@dataclass
class RecoveryResult:
    """Result of a complete recovery session."""
    strategy: str
    total_sectors_read: int = 0
    successful_reads: int = 0
    failed_reads: int = 0
    mft_entries_recovered: int = 0
    mft_entries_total: int = 0
    files_recovered: int = 0
    files_total: int = 0
    files_recoverable: int = 0  # files whose MFT entry was read
    bytes_recovered: int = 0
    bytes_total: int = 0
    disk_died: bool = False
    sectors_before_death: int = 0
    time_elapsed_ms: float = 0.0
    # For tracking what was recovered
    recovered_file_ids: set = field(default_factory=set)
    recovered_mft_ids: set = field(default_factory=set)

    @property
    def file_recovery_rate(self) -> float:
        return self.files_recovered / max(self.files_total, 1)

    @property
    def mft_recovery_rate(self) -> float:
        return self.mft_entries_recovered / max(self.mft_entries_total, 1)

    @property
    def data_recovery_rate(self) -> float:
        return self.bytes_recovered / max(self.bytes_total, 1)

    def to_dict(self) -> dict:
        d = asdict(self)
        d['file_recovery_rate'] = self.file_recovery_rate
        d['mft_recovery_rate'] = self.mft_recovery_rate
        d['data_recovery_rate'] = self.data_recovery_rate
        return d


def read_sector(disk: SimDisk, sector: int, fail_probability_growth: float = 0.0,
                sectors_read_so_far: int = 0) -> Tuple[bool, bool]:
    """Try to read a sector. Returns (success, data_recovered).
    
    fail_probability_growth: if > 0, simulates growing failure as more sectors are read.
    Each read has a small chance of killing the disk.
    """
    if sector >= len(disk.sector_health):
        return False, False

    # Base health
    health = disk.sector_health[sector]

    # Growing failure: each read has a small chance of damaging nearby sectors
    if fail_probability_growth > 0:
        # Probability of disk dying increases with reads
        death_prob = fail_probability_growth * (sectors_read_so_far / 1000.0)
        if random.random() < death_prob:
            # Disk dies! Kill a bunch of remaining sectors
            return False, True  # (read failed, disk died)

    return health > 0.0, False


def motor_a_sequential(disk: SimDisk, max_reads: int = None,
                       fail_growth: float = 0.0) -> RecoveryResult:
    """Motor A: Sequential reading. Read sectors 0, 1, 2, 3...
    This is how ddrescue works by default.
    """
    result = RecoveryResult(strategy="Motor A: Sequential")
    result.files_total = len(disk.files)
    result.mft_entries_total = len(disk.mft_entries)
    result.bytes_total = sum(f.size for f in disk.files)

    total_sectors = len(disk.sector_health)
    max_reads = max_reads or total_sectors
    disk_died = False

    # Build sector -> file mapping for data sectors
    sector_to_file = {}
    for fid, sectors in disk.data_sectors.items():
        for sec in sectors:
            sector_to_file[sec] = fid

    # Build sector -> MFT entry mapping
    sector_to_mft = {}
    for entry in disk.mft_entries:
        entry_sectors = set()
        base = entry.cluster_start * SECTORS_PER_CLUSTER
        for s in range(2):
            sec = base + s
            if sec in disk.mft_sectors:
                entry_sectors.add(sec)
        for sec in entry_sectors:
            sector_to_mft[sec] = entry.file_id

    # Track which MFT entries are fully read (need all their sectors)
    mft_sectors_needed = {}  # file_id -> set of sectors
    for entry in disk.mft_entries:
        entry_sectors = set()
        base = entry.cluster_start * SECTORS_PER_CLUSTER
        for s in range(2):
            sec = base + s
            if sec in disk.mft_sectors:
                entry_sectors.add(sec)
        if entry_sectors:
            mft_sectors_needed[entry.file_id] = entry_sectors

    mft_sectors_read = {}  # file_id -> set of sectors read

    # Track which file sectors have been read
    file_sectors_read = {}  # file_id -> set of sectors read

    # Read sequentially
    for sector in range(min(total_sectors, max_reads)):
        success, died = read_sector(disk, sector, fail_growth, result.total_sectors_read)
        result.total_sectors_read += 1

        if died:
            disk_died = True
            break

        if success:
            result.successful_reads += 1

            # Check if this is an MFT sector
            if sector in sector_to_mft:
                fid = sector_to_mft[sector]
                if fid not in mft_sectors_read:
                    mft_sectors_read[fid] = set()
                mft_sectors_read[fid].add(sector)

            # Check if this is a data sector
            if sector in sector_to_file:
                fid = sector_to_file[sector]
                if fid not in file_sectors_read:
                    file_sectors_read[fid] = set()
                file_sectors_read[fid].add(sector)
        else:
            result.failed_reads += 1

    # Count recovered MFT entries
    for fid, needed in mft_sectors_needed.items():
        if fid in mft_sectors_read and mft_sectors_read[fid] >= needed:
            result.mft_entries_recovered += 1
            result.recovered_mft_ids.add(fid)

    # Count recovered files
    # A file is "recovered" if:
    # 1. Its MFT entry was read (we know the file exists and where its clusters are)
    # 2. All its data sectors were read
    # For resident files, only MFT entry is needed
    for sf in disk.files:
        if sf.file_id in result.recovered_mft_ids:
            result.files_recoverable += 1
            if sf.is_resident:
                # Resident file: MFT entry contains the data
                result.files_recovered += 1
                result.bytes_recovered += sf.size
                result.recovered_file_ids.add(sf.file_id)
            else:
                # Non-resident: need all data sectors
                needed = disk.data_sectors.get(sf.file_id, set())
                read = file_sectors_read.get(sf.file_id, set())
                if needed and read >= needed:
                    result.files_recovered += 1
                    result.bytes_recovered += sf.size
                    result.recovered_file_ids.add(sf.file_id)

    result.disk_died = disk_died
    result.sectors_before_death = result.total_sectors_read if disk_died else 0

    return result


def motor_b_mft_first(disk: SimDisk, max_reads: int = None,
                      fail_growth: float = 0.0) -> RecoveryResult:
    """Motor B: MFT-first reading. Read MFT sectors first, then data.
    After reading MFT, prioritize data sectors for files whose MFT was recovered.
    """
    result = RecoveryResult(strategy="Motor B: MFT-first")
    result.files_total = len(disk.files)
    result.mft_entries_total = len(disk.mft_entries)
    result.bytes_total = sum(f.size for f in disk.files)

    total_sectors = len(disk.sector_health)
    max_reads = max_reads or total_sectors
    disk_died = False

    # Build sector -> file mapping
    sector_to_file = {}
    for fid, sectors in disk.data_sectors.items():
        for sec in sectors:
            sector_to_file[sec] = fid

    # Build MFT entry -> sectors mapping
    mft_sectors_needed = {}
    for entry in disk.mft_entries:
        entry_sectors = set()
        base = entry.cluster_start * SECTORS_PER_CLUSTER
        for s in range(2):
            sec = base + s
            if sec in disk.mft_sectors:
                entry_sectors.add(sec)
        if entry_sectors:
            mft_sectors_needed[entry.file_id] = entry_sectors

    mft_sectors_read = {}
    file_sectors_read = {}

    # ── PHASE 1: Read MFT sectors first ──
    mft_sector_list = sorted(disk.mft_sectors)
    for sector in mft_sector_list:
        if result.total_sectors_read >= max_reads:
            break

        success, died = read_sector(disk, sector, fail_growth, result.total_sectors_read)
        result.total_sectors_read += 1

        if died:
            disk_died = True
            break

        if success:
            result.successful_reads += 1
            # Check which MFT entry this belongs to
            for fid, needed in mft_sectors_needed.items():
                if sector in needed:
                    if fid not in mft_sectors_read:
                        mft_sectors_read[fid] = set()
                    mft_sectors_read[fid].add(sector)
        else:
            result.failed_reads += 1

    # Count recovered MFT entries after Phase 1
    recovered_mft_ids = set()
    for fid, needed in mft_sectors_needed.items():
        if fid in mft_sectors_read and mft_sectors_read[fid] >= needed:
            recovered_mft_ids.add(fid)

    # ── PHASE 2: Read data sectors for files whose MFT was recovered ──
    # Prioritize data sectors belonging to recovered files
    priority_data_sectors = set()
    for sf in disk.files:
        if sf.file_id in recovered_mft_ids and not sf.is_resident:
            for sec in disk.data_sectors.get(sf.file_id, set()):
                priority_data_sectors.add(sec)

    # Also read MFT sectors we haven't read yet (in case some were missed)
    # But prioritize data sectors first
    read_sectors = set(mft_sector_list)  # Already read in Phase 1

    # Sort priority sectors (prefer smaller files first for quick wins)
    priority_list = sorted(priority_data_sectors - read_sectors)

    for sector in priority_list:
        if result.total_sectors_read >= max_reads:
            break
        if disk_died:
            break

        success, died = read_sector(disk, sector, fail_growth, result.total_sectors_read)
        result.total_sectors_read += 1
        read_sectors.add(sector)

        if died:
            disk_died = True
            break

        if success:
            result.successful_reads += 1
            if sector in sector_to_file:
                fid = sector_to_file[sector]
                if fid not in file_sectors_read:
                    file_sectors_read[fid] = set()
                file_sectors_read[fid].add(sector)
        else:
            result.failed_reads += 1

    # ── PHASE 3: Read remaining sectors sequentially ──
    for sector in range(total_sectors):
        if result.total_sectors_read >= max_reads:
            break
        if disk_died:
            break
        if sector in read_sectors:
            continue

        success, died = read_sector(disk, sector, fail_growth, result.total_sectors_read)
        result.total_sectors_read += 1
        read_sectors.add(sector)

        if died:
            disk_died = True
            break

        if success:
            result.successful_reads += 1
            if sector in sector_to_file:
                fid = sector_to_file[sector]
                if fid not in file_sectors_read:
                    file_sectors_read[fid] = set()
                file_sectors_read[fid].add(sector)
        else:
            result.failed_reads += 1

    # ── Count results ──
    result.mft_entries_recovered = len(recovered_mft_ids)
    result.recovered_mft_ids = recovered_mft_ids

    for sf in disk.files:
        if sf.file_id in recovered_mft_ids:
            result.files_recoverable += 1
            if sf.is_resident:
                result.files_recovered += 1
                result.bytes_recovered += sf.size
                result.recovered_file_ids.add(sf.file_id)
            else:
                needed = disk.data_sectors.get(sf.file_id, set())
                read = file_sectors_read.get(sf.file_id, set())
                if needed and read >= needed:
                    result.files_recovered += 1
                    result.bytes_recovered += sf.size
                    result.recovered_file_ids.add(sf.file_id)

    result.disk_died = disk_died
    result.sectors_before_death = result.total_sectors_read if disk_died else 0

    return result


# ─── Benchmark Runner ──────────────────────────────────────────────────────────

@dataclass
class Scenario:
    """A benchmark scenario."""
    name: str
    description: str
    disk_mb: int = 100
    file_count: int = 200
    damage_type: str = "mft"          # mft, bad_sectors, growing, combined
    damage_params: dict = field(default_factory=dict)
    fail_growth: float = 0.0          # probability of disk dying per 1000 reads
    max_reads: int = 0                # 0 = unlimited
    runs: int = 5                     # number of runs to average

    def create_disk(self) -> SimDisk:
        disk = create_disk(total_mb=self.disk_mb, file_count=self.file_count)
        if self.damage_type == "mft":
            apply_mft_damage(disk, self.damage_params.get("pct", 0.3))
        elif self.damage_type == "bad_sectors":
            apply_bad_sectors(disk, self.damage_params.get("pct", 0.01),
                            self.damage_params.get("region", "random"))
        elif self.damage_type == "growing":
            apply_growing_failure(disk, self.damage_params.get("start_pct", 0.0),
                                self.damage_params.get("rate", 0.0))
        elif self.damage_type == "combined":
            apply_mft_damage(disk, self.damage_params.get("mft_pct", 0.2))
            apply_bad_sectors(disk, self.damage_params.get("bad_pct", 0.005))
        elif self.damage_type == "healthy":
            pass  # No damage
        return disk


def run_scenario(scenario: Scenario) -> List[Dict]:
    """Run a scenario with both motors and return results."""
    results = []

    for run in range(scenario.runs):
        random.seed(42 + run)  # Reproducible but different per run

        disk = scenario.create_disk()

        # Create a copy of disk for Motor B (since reading modifies state)
        import copy
        disk_b = copy.deepcopy(disk)

        # Run Motor A
        max_reads = scenario.max_reads or disk.total_sectors
        result_a = motor_a_sequential(disk, max_reads=max_reads,
                                      fail_growth=scenario.fail_growth)

        # Run Motor B
        result_b = motor_b_mft_first(disk_b, max_reads=max_reads,
                                     fail_growth=scenario.fail_growth)

        results.append({
            "run": run,
            "scenario": scenario.name,
            "motor_a": result_a.to_dict(),
            "motor_b": result_b.to_dict(),
        })

    return results


def define_scenarios() -> List[Scenario]:
    """Define the 10 benchmark scenarios."""
    return [
        Scenario(
            name="S01_healthy_deleted",
            description="Disco saludable con archivos eliminados. Sin dano fisico.",
            damage_type="healthy",
            file_count=300,
            fail_growth=0.0,
        ),
        Scenario(
            name="S02_mft_20pct",
            description="20% del MFT danado. Disco fisicamente sano.",
            damage_type="mft",
            damage_params={"pct": 0.2},
            file_count=300,
            fail_growth=0.0,
        ),
        Scenario(
            name="S03_mft_40pct",
            description="40% del MFT danado. Disco fisicamente sano.",
            damage_type="mft",
            damage_params={"pct": 0.4},
            file_count=300,
            fail_growth=0.0,
        ),
        Scenario(
            name="S04_mft_60pct",
            description="60% del MFT danado. Disco fisicamente sano.",
            damage_type="mft",
            damage_params={"pct": 0.6},
            file_count=300,
            fail_growth=0.0,
        ),
        Scenario(
            name="S05_bad_sectors_1pct",
            description="1% de sectores malos distribuidos aleatoriamente.",
            damage_type="bad_sectors",
            damage_params={"pct": 0.01, "region": "random"},
            file_count=300,
            fail_growth=0.0,
        ),
        Scenario(
            name="S06_bad_sectors_5pct",
            description="5% de sectores malos distribuidos aleatoriamente.",
            damage_type="bad_sectors",
            damage_params={"pct": 0.05, "region": "random"},
            file_count=300,
            fail_growth=0.0,
        ),
        Scenario(
            name="S07_growing_failure_slow",
            description="Disco que falla lentamente. Probabilidad de muerte crece con cada lectura.",
            damage_type="growing",
            damage_params={"start_pct": 0.01, "rate": 0.0},
            fail_growth=0.0003,  # 0.03% chance per 1000 reads initially
            file_count=300,
        ),
        Scenario(
            name="S08_growing_failure_fast",
            description="Disco que falla rapidamente. Mayor probabilidad de muerte.",
            damage_type="growing",
            damage_params={"start_pct": 0.02, "rate": 0.0},
            fail_growth=0.001,  # 0.1% chance per 1000 reads initially
            file_count=300,
        ),
        Scenario(
            name="S09_combined_mft_bad",
            description="MFT danado 20% + sectores malos 2%. Combinacion realista.",
            damage_type="combined",
            damage_params={"mft_pct": 0.2, "bad_pct": 0.02},
            file_count=300,
            fail_growth=0.0,
        ),
        Scenario(
            name="S10_critical_dying_disk",
            description="Disco muriendo con MFT parcialmente danado. El escenario clave.",
            damage_type="combined",
            damage_params={"mft_pct": 0.3, "bad_pct": 0.05},
            fail_growth=0.0008,
            file_count=300,
        ),
    ]


def run_all_scenarios() -> Dict:
    """Run all scenarios and return combined results."""
    scenarios = define_scenarios()
    all_results = {}

    print("=" * 70)
    print("  RECOVERY LAB — Benchmark Engine")
    print("  Hipótesis: ¿Leer primero el MFT mejora la recuperación?")
    print("=" * 70)
    print()

    for scenario in scenarios:
        print(f"  Ejecutando: {scenario.name}")
        print(f"  Descripción: {scenario.description}")
        results = run_scenario(scenario)

        # Aggregate
        a_files = [r["motor_a"]["files_recovered"] for r in results]
        b_files = [r["motor_b"]["files_recovered"] for r in results]
        a_mft = [r["motor_a"]["mft_entries_recovered"] for r in results]
        b_mft = [r["motor_b"]["mft_entries_recovered"] for r in results]
        a_bytes = [r["motor_a"]["bytes_recovered"] for r in results]
        b_bytes = [r["motor_b"]["bytes_recovered"] for r in results]
        a_died = sum(1 for r in results if r["motor_a"]["disk_died"])
        b_died = sum(1 for r in results if r["motor_b"]["disk_died"])
        total_files = results[0]["motor_a"]["files_total"]

        avg_a = sum(a_files) / len(a_files)
        avg_b = sum(b_files) / len(b_files)
        diff_pct = ((avg_b - avg_a) / max(avg_a, 1)) * 100

        print(f"  Motor A (secuencial): {avg_a:.1f}/{total_files} archivos ({avg_a/max(total_files,1)*100:.1f}%)")
        print(f"  Motor B (MFT-first):  {avg_b:.1f}/{total_files} archivos ({avg_b/max(total_files,1)*100:.1f}%)")
        if diff_pct > 0:
            print(f"  ▶ Motor B recupera {diff_pct:+.1f}% MAS archivos")
        elif diff_pct < 0:
            print(f"  ▶ Motor B recupera {diff_pct:+.1f}% MENOS archivos")
        else:
            print(f"  ▶ Sin diferencia significativa")
        print(f"  Disk deaths: A={a_died}, B={b_died}")
        print()

        all_results[scenario.name] = {
            "description": scenario.description,
            "runs": scenario.runs,
            "motor_a_avg_files": avg_a,
            "motor_b_avg_files": avg_b,
            "motor_a_avg_mft": sum(a_mft) / len(a_mft),
            "motor_b_avg_mft": sum(b_mft) / len(b_mft),
            "motor_a_avg_bytes": sum(a_bytes) / len(a_bytes),
            "motor_b_avg_bytes": sum(b_bytes) / len(b_bytes),
            "motor_a_deaths": a_died,
            "motor_b_deaths": b_died,
            "diff_pct": diff_pct,
            "total_files": total_files,
            "raw_results": results,
        }

    return all_results


def generate_report(results: Dict) -> str:
    """Generate a text report of the benchmark results."""
    lines = []
    lines.append("=" * 70)
    lines.append("  RECOVERY LAB — INFORME DE RESULTADOS")
    lines.append("=" * 70)
    lines.append("")
    lines.append("HIPÓTESIS: Priorizar la lectura del MFT mejora la recuperación")
    lines.append("de archivos cuando un disco está fallando.")
    lines.append("")
    lines.append("MOTOR A: Lectura secuencial (como ddrescue por defecto)")
    lines.append("MOTOR B: Lectura MFT-first (priorizar metadatos primero)")
    lines.append("")
    lines.append("-" * 70)
    lines.append(f"{'Escenario':<30} {'A (archivos)':<15} {'B (archivos)':<15} {'Diferencia':<12}")
    lines.append("-" * 70)

    wins_b = 0
    wins_a = 0
    ties = 0

    for name, data in results.items():
        avg_a = data["motor_a_avg_files"]
        avg_b = data["motor_b_avg_files"]
        total = data["total_files"]
        diff = data["diff_pct"]

        if diff > 1:
            verdict = f"B +{diff:.1f}%"
            wins_b += 1
        elif diff < -1:
            verdict = f"A +{abs(diff):.1f}%"
            wins_a += 1
        else:
            verdict = "≈ igual"
            ties += 1

        lines.append(f"{name:<30} {avg_a:>6.1f}/{total:<7} {avg_b:>6.1f}/{total:<7} {verdict}")

    lines.append("-" * 70)
    lines.append("")
    lines.append("RESUMEN:")
    lines.append(f"  Escenarios donde Motor B gana: {wins_b}/{len(results)}")
    lines.append(f"  Escenarios donde Motor A gana: {wins_a}/{len(results)}")
    lines.append(f"  Escenarios sin diferencia:     {ties}/{len(results)}")
    lines.append("")

    # Key scenario analysis
    if "S10_critical_dying_disk" in results:
        s10 = results["S10_critical_dying_disk"]
        lines.append("ESCENARIO CLAVE (S10: Disco muriendo con MFT dañado):")
        lines.append(f"  Motor A: {s10['motor_a_avg_files']:.1f} archivos recuperados")
        lines.append(f"  Motor B: {s10['motor_b_avg_files']:.1f} archivos recuperados")
        lines.append(f"  Diferencia: {s10['diff_pct']:+.1f}%")
        lines.append(f"  Muertes de disco: A={s10['motor_a_deaths']}, B={s10['motor_b_deaths']}")
        lines.append("")

    if "S08_growing_failure_fast" in results:
        s08 = results["S08_growing_failure_fast"]
        lines.append("ESCENARIO CRÍTICO (S08: Fallo rápido creciente):")
        lines.append(f"  Motor A: {s08['motor_a_avg_files']:.1f} archivos recuperados")
        lines.append(f"  Motor B: {s08['motor_b_avg_files']:.1f} archivos recuperados")
        lines.append(f"  Diferencia: {s08['diff_pct']:+.1f}%")
        lines.append(f"  Muertes de disco: A={s08['motor_a_deaths']}, B={s08['motor_b_deaths']}")
        lines.append("")

    # Conclusion
    lines.append("CONCLUSIÓN:")
    if wins_b > wins_a:
        lines.append("  La hipótesis está SOPORTADA por los datos.")
        lines.append("  Priorizar MFT-first mejora consistentemente la recuperación,")
        lines.append("  especialmente en escenarios donde el disco está fallando.")
    elif wins_a > wins_b:
        lines.append("  La hipótesis NO está soportada por los datos.")
        lines.append("  La lectura secuencial obtiene mejores o iguales resultados.")
    else:
        lines.append("  Los resultados son MIXTOS.")
        lines.append("  Se necesitan más escenarios y mayor granularidad para decidir.")
    lines.append("")
    lines.append("NOTA: Estos resultados provienen de un simulador. Los resultados")
    lines.append("reales pueden diferir. Este experimento es un primer paso, no una")
    lines.append("conclusión definitiva.")

    return "\n".join(lines)


# ─── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    random.seed(42)
    start = time.time()
    results = run_all_scenarios()
    elapsed = time.time() - start

    # Save JSON results
    results_path = LAB_DIR / "results" / "benchmark_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Resultados JSON guardados en: {results_path}")

    # Generate and save report
    report = generate_report(results)
    report_path = LAB_DIR / "results" / "benchmark_report.txt"
    with open(report_path, "w") as f:
        f.write(report)
    print(f"Informe guardado en: {report_path}")

    print(f"\nTiempo total: {elapsed:.1f} segundos")
    print("\n" + report)
