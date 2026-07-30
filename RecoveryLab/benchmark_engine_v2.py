#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RecoveryLab v2 — Simulated NTFS Benchmark Engine (Honest Version)
==================================================================
The key difference between Motor A and Motor B is NOT about whether
the MFT gets read (it's at the start of the disk, so sequential reading
WILL read it first). The difference is:

Motor A (Sequential): Reads sector 0, 1, 2, 3... If the disk dies
at 40%, you have the first 40% of sectors. You have the MFT (good!)
but you may not have the data sectors for files stored at the end.

Motor B (MFT-first): Reads the MFT first, then uses the MFT to know
exactly which data sectors to read next. If the disk dies at 40%,
you have the MFT PLUS the data sectors for the most important files,
because you read them on purpose.

The hypothesis: When a disk has a LIMITED READ BUDGET (it will die
after N reads), knowing which sectors to read first recovers more
files than reading blindly.
"""

import os, json, hashlib, random, time, copy
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Tuple, Optional, Set
from pathlib import Path

SECTOR_SIZE = 512
CLUSTER_SIZE = 4096
SECTORS_PER_CLUSTER = CLUSTER_SIZE // SECTOR_SIZE
MFT_ENTRY_SIZE = 1024
MFT_ENTRIES_PER_CLUSTER = CLUSTER_SIZE // MFT_ENTRY_SIZE

LAB_DIR = Path(__file__).parent


@dataclass
class SimFile:
    file_id: int
    name: str
    size: int
    clusters: List[int]
    is_resident: bool = False
    priority: int = 0  # 0=normal, 1=important, 2=critical


@dataclass
class SimDisk:
    total_clusters: int
    mft_start_cluster: int = 4        # MFT starts at cluster 4 (realistic)
    mft_cluster_count: int = 0
    files: List[SimFile] = field(default_factory=list)
    # Sector health: 1.0=healthy, 0.0=dead
    sector_health: List[float] = field(default_factory=list)
    # Which clusters belong to MFT
    mft_clusters: Set[int] = field(default_factory=set)
    # Which clusters belong to which file
    file_clusters: Dict[int, Set[int]] = field(default_factory=dict)
    # File metadata (checksums, etc)
    file_metadata: Dict[int, dict] = field(default_factory=dict)

    @property
    def total_sectors(self):
        return self.total_clusters * SECTORS_PER_CLUSTER


def create_disk(total_mb: int = 50, file_count: int = 200, seed: int = 42) -> SimDisk:
    """Create a realistic simulated NTFS disk."""
    random.seed(seed)
    total_clusters = (total_mb * 1024 * 1024) // CLUSTER_SIZE
    disk = SimDisk(total_clusters=total_clusters)

    # MFT occupies clusters 4 to 4+mft_size (realistic)
    # For 200 files, we need ~200 entries * 1024 bytes = 50 clusters
    disk.mft_cluster_count = max(50, file_count // MFT_ENTRIES_PER_CLUSTER + 10)
    disk.mft_clusters = set(range(disk.mft_start_cluster,
                                   disk.mft_start_cluster + disk.mft_cluster_count))

    # Data area starts after MFT
    data_start = disk.mft_start_cluster + disk.mft_cluster_count + 10

    # Initialize sector health
    total_sectors = disk.total_sectors
    disk.sector_health = [1.0] * total_sectors

    # Create test files with realistic distribution
    file_types = [
        ("photo_{:04d}.jpg", 0.30, 2, 8),
        ("document_{:04d}.pdf", 0.25, 1, 5),
        ("video_{:04d}.mp4", 0.10, 20, 80),
        ("email_{:04d}.eml", 0.15, 1, 3),
        ("sheet_{:04d}.xlsx", 0.10, 1, 8),
        ("code_{:04d}.py", 0.10, 1, 4),
    ]

    next_cluster = data_start
    files = []

    for i in range(file_count):
        # Pick file type
        r = random.random()
        cumprob = 0
        pattern, _, cmin, cmax = file_types[0]
        for p, _, _, _ in file_types:
            pass
        for p_name, p_prob, p_cmin, p_cmax in file_types:
            cumprob += p_prob
            if r < cumprob:
                pattern, _, cmin, cmax = p_name, p_prob, p_cmin, p_cmax
                break

        name = pattern.format(i)
        clusters_needed = random.randint(cmin, cmax)
        is_resident = clusters_needed <= 0
        if is_resident:
            clusters_needed = 0
            clusters = []
        else:
            # 70% contiguous, 30% fragmented
            if random.random() < 0.7:
                start = next_cluster
                clusters = list(range(start, start + clusters_needed))
                next_cluster += clusters_needed
            else:
                # Fragmented: spread across disk
                clusters = []
                for _ in range(clusters_needed):
                    c = next_cluster + random.randint(0, 100)
                    clusters.append(c)
                    next_cluster = max(next_cluster, c + 1)

        # Assign priority (some files are more important)
        priority = 0
        if "document" in name or "sheet" in name:
            priority = 1  # important
        elif "photo" in name:
            priority = 2  # critical (memories)

        sf = SimFile(
            file_id=i, name=name, size=clusters_needed * CLUSTER_SIZE,
            clusters=clusters, is_resident=is_resident, priority=priority,
        )
        files.append(sf)

        # Map file clusters
        disk.file_clusters[i] = set(clusters)

    disk.files = files

    # Mark which MFT sectors correspond to which file
    # MFT entry for file i is at cluster: mft_start + i // MFT_ENTRIES_PER_CLUSTER
    for i, sf in enumerate(files):
        mft_entry_cluster = disk.mft_start_cluster + i // MFT_ENTRIES_PER_CLUSTER
        disk.file_metadata[i] = {
            "mft_entry_cluster": mft_entry_cluster,
            "name": sf.name,
            "priority": sf.priority,
        }

    return disk


def apply_damage(disk: SimDisk, damage_type: str, **params) -> SimDisk:
    """Apply damage to the disk."""
    total_sectors = disk.total_sectors

    if damage_type == "bad_sectors_end":
        # Bad sectors at the end of the disk (common in real drives)
        pct = params.get("pct", 0.1)
        n_bad = int(total_sectors * pct)
        for i in range(n_bad):
            disk.sector_health[total_sectors - 1 - i] = 0.0

    elif damage_type == "bad_sectors_random":
        pct = params.get("pct", 0.05)
        n_bad = int(total_sectors * pct)
        bad = random.sample(range(total_sectors), n_bad)
        for sec in bad:
            disk.sector_health[sec] = 0.0

    elif damage_type == "mft_partial":
        # Damage specific MFT clusters
        pct = params.get("pct", 0.3)
        mft_list = sorted(disk.mft_clusters)
        n_damage = int(len(mft_list) * pct)
        damaged = random.sample(mft_list, min(n_damage, len(mft_list)))
        for c in damaged:
            for s in range(SECTORS_PER_CLUSTER):
                sec = c * SECTORS_PER_CLUSTER + s
                if sec < total_sectors:
                    disk.sector_health[sec] = 0.0

    elif damage_type == "combined":
        mft_pct = params.get("mft_pct", 0.2)
        bad_pct = params.get("bad_pct", 0.05)
        apply_damage(disk, "mft_partial", pct=mft_pct)
        apply_damage(disk, "bad_sectors_end", pct=bad_pct)

    return disk


# ─── Reading Strategies ────────────────────────────────────────────────────────

@dataclass
class RecoveryResult:
    strategy: str
    files_total: int = 0
    files_recovered: int = 0
    files_recoverable: int = 0  # MFT known but data not fully read
    mft_entries_recovered: int = 0
    mft_entries_total: int = 0
    bytes_recovered: int = 0
    bytes_total: int = 0
    sectors_read: int = 0
    sectors_successful: int = 0
    sectors_failed: int = 0
    disk_died: bool = False
    sectors_at_death: int = 0
    recovered_file_ids: Set[int] = field(default_factory=set)

    @property
    def file_rate(self): return self.files_recovered / max(self.files_total, 1)
    @property
    def mft_rate(self): return self.mft_entries_recovered / max(self.mft_entries_total, 1)
    @property
    def data_rate(self): return self.bytes_recovered / max(self.bytes_total, 1)

    def to_dict(self):
        d = asdict(self)
        d['file_rate'] = self.file_rate
        d['mft_rate'] = self.mft_rate
        d['data_rate'] = self.data_rate
        d['recovered_file_ids'] = list(self.recovered_file_ids)
        return d


def simulate_disk_death(sectors_read: int, death_budget: int) -> bool:
    """Determine if the disk has died after this many reads.
    Models a disk that will die after approximately death_budget reads,
    with some randomness.
    """
    if death_budget <= 0:
        return False  # Disk never dies
    # Probability increases as we approach the budget
    if sectors_read >= death_budget:
        return True
    # Small random chance of early death
    prob = (sectors_read / death_budget) ** 3 * 0.5
    return random.random() < prob


def motor_a_sequential(disk: SimDisk, death_budget: int = 0) -> RecoveryResult:
    """Motor A: Sequential reading from sector 0.
    This is what ddrescue does. The MFT IS at the start of the disk,
    so Motor A WILL read it first. The question is: does it reach
    the data sectors before the disk dies?
    """
    result = RecoveryResult(strategy="Motor A: Sequential")
    result.files_total = len(disk.files)
    result.mft_entries_total = len(disk.files)
    result.bytes_total = sum(f.size for f in disk.files)

    total_sectors = disk.total_sectors
    mft_clusters_read = set()
    data_clusters_read = set()  # file_id -> set of clusters read

    # Track which MFT entries we've recovered
    mft_entries_read = set()
    # Track which file data clusters we've read
    file_data_read = {}  # file_id -> set of clusters read

    for sector in range(total_sectors):
        # Check if disk has died
        if simulate_disk_death(result.sectors_read, death_budget):
            result.disk_died = True
            result.sectors_at_death = result.sectors_read
            break

        result.sectors_read += 1
        cluster = sector // SECTORS_PER_CLUSTER

        if disk.sector_health[sector] <= 0.0:
            result.sectors_failed += 1
            continue

        result.sectors_successful += 1

        # Track MFT clusters
        if cluster in disk.mft_clusters:
            mft_clusters_read.add(cluster)

        # Track data clusters
        for fid, clusters in disk.file_clusters.items():
            if cluster in clusters:
                if fid not in file_data_read:
                    file_data_read[fid] = set()
                file_data_read[fid].add(cluster)

    # Count recovered MFT entries
    for fid, meta in disk.file_metadata.items():
        mft_cluster = meta["mft_entry_cluster"]
        if mft_cluster in mft_clusters_read:
            mft_entries_read.add(fid)
            result.mft_entries_recovered += 1

    # Count recovered files
    # A file is recovered if:
    # 1. Its MFT entry was read (we know the file exists)
    # 2. ALL its data clusters were read
    for sf in disk.files:
        if sf.file_id in mft_entries_read:
            result.files_recoverable += 1
            if sf.is_resident:
                result.files_recovered += 1
                result.bytes_recovered += sf.size
                result.recovered_file_ids.add(sf.file_id)
            else:
                needed = disk.file_clusters.get(sf.file_id, set())
                read = file_data_read.get(sf.file_id, set())
                if needed and read >= needed:
                    result.files_recovered += 1
                    result.bytes_recovered += sf.size
                    result.recovered_file_ids.add(sf.file_id)

    return result


def motor_b_mft_first(disk: SimDisk, death_budget: int = 0) -> RecoveryResult:
    """Motor B: MFT-first reading.
    Phase 1: Read ALL MFT clusters first.
    Phase 2: Read data clusters for files whose MFT was recovered.
    Phase 3: Read remaining sectors.
    """
    result = RecoveryResult(strategy="Motor B: MFT-first")
    result.files_total = len(disk.files)
    result.mft_entries_total = len(disk.files)
    result.bytes_total = sum(f.size for f in disk.files)

    total_sectors = disk.total_sectors
    mft_clusters_read = set()
    file_data_read = {}  # file_id -> set of clusters read
    mft_entries_read = set()
    read_sectors = set()

    # ── PHASE 1: Read MFT sectors first ──
    mft_sectors = []
    for c in sorted(disk.mft_clusters):
        for s in range(SECTORS_PER_CLUSTER):
            sec = c * SECTORS_PER_CLUSTER + s
            if sec < total_sectors:
                mft_sectors.append(sec)

    for sector in mft_sectors:
        if simulate_disk_death(result.sectors_read, death_budget):
            result.disk_died = True
            result.sectors_at_death = result.sectors_read
            break

        result.sectors_read += 1
        read_sectors.add(sector)
        cluster = sector // SECTORS_PER_CLUSTER

        if disk.sector_health[sector] <= 0.0:
            result.sectors_failed += 1
            continue

        result.sectors_successful += 1
        mft_clusters_read.add(cluster)

    if not result.disk_died:
        # Determine which MFT entries we recovered
        for fid, meta in disk.file_metadata.items():
            mft_cluster = meta["mft_entry_cluster"]
            if mft_cluster in mft_clusters_read:
                mft_entries_read.add(fid)

        # ── PHASE 2: Read data clusters for recovered files ──
        # Priority: read data for files whose MFT was recovered
        # Sort by priority (critical first) then by size (small first = quick wins)
        priority_files = sorted(
            [f for f in disk.files if f.file_id in mft_entries_read and not f.is_resident],
            key=lambda f: (-f.priority, f.size)
        )

        priority_sectors = set()
        for sf in priority_files:
            for c in sf.clusters:
                for s in range(SECTORS_PER_CLUSTER):
                    sec = c * SECTORS_PER_CLUSTER + s
                    if sec < total_sectors and sec not in read_sectors:
                        priority_sectors.add(sec)

        for sector in sorted(priority_sectors):
            if result.disk_died:
                break
            if simulate_disk_death(result.sectors_read, death_budget):
                result.disk_died = True
                result.sectors_at_death = result.sectors_read
                break

            result.sectors_read += 1
            read_sectors.add(sector)
            cluster = sector // SECTORS_PER_CLUSTER

            if disk.sector_health[sector] <= 0.0:
                result.sectors_failed += 1
                continue

            result.sectors_successful += 1

            for fid, clusters in disk.file_clusters.items():
                if cluster in clusters:
                    if fid not in file_data_read:
                        file_data_read[fid] = set()
                    file_data_read[fid].add(cluster)

    # Count recovered MFT entries
    result.mft_entries_recovered = len(mft_entries_read)

    # Count recovered files
    for sf in disk.files:
        if sf.file_id in mft_entries_read:
            result.files_recoverable += 1
            if sf.is_resident:
                result.files_recovered += 1
                result.bytes_recovered += sf.size
                result.recovered_file_ids.add(sf.file_id)
            else:
                needed = disk.file_clusters.get(sf.file_id, set())
                read = file_data_read.get(sf.file_id, set())
                if needed and read >= needed:
                    result.files_recovered += 1
                    result.bytes_recovered += sf.size
                    result.recovered_file_ids.add(sf.file_id)

    return result


# ─── Scenarios ──────────────────────────────────────────────────────────────────

@dataclass
class Scenario:
    name: str
    description: str
    disk_mb: int = 50
    file_count: int = 200
    damage_type: str = "healthy"
    damage_params: dict = field(default_factory=dict)
    death_budget: int = 0  # 0 = disk never dies
    runs: int = 5

    def create_disk(self, seed: int) -> SimDisk:
        disk = create_disk(self.disk_mb, self.file_count, seed=seed)
        if self.damage_type != "healthy":
            apply_damage(disk, self.damage_type, **self.damage_params)
        return disk


def define_scenarios() -> List[Scenario]:
    """Define 10 benchmark scenarios."""
    return [
        Scenario(
            name="S01_healthy",
            description="Disco saludable. Sin dano. Ambos motores deberian empatar.",
            damage_type="healthy",
            death_budget=0,
        ),
        Scenario(
            name="S02_mft_30pct_damaged",
            description="30% del MFT danado. Sin dano en datos.",
            damage_type="mft_partial",
            damage_params={"pct": 0.3},
            death_budget=0,
        ),
        Scenario(
            name="S03_bad_sectors_end_10pct",
            description="10% de sectores malos al final del disco. Los datos de archivos grandes se pierden.",
            damage_type="bad_sectors_end",
            damage_params={"pct": 0.10},
            death_budget=0,
        ),
        Scenario(
            name="S04_bad_sectors_random_5pct",
            description="5% de sectores malos aleatorios. Datos fragmentados.",
            damage_type="bad_sectors_random",
            damage_params={"pct": 0.05},
            death_budget=0,
        ),
        Scenario(
            name="S05_disk_dies_at_30pct",
            description="Disco muere despues de leer ~30% de sectores. MFT esta al inicio.",
            damage_type="healthy",
            death_budget=0,  # Will be set dynamically
        ),
        Scenario(
            name="S06_disk_dies_at_10pct",
            description="Disco muere muy rapido. Solo ~10% de sectores legibles.",
            damage_type="healthy",
            death_budget=0,
        ),
        Scenario(
            name="S07_mft_damaged_disk_dies_30pct",
            description="MFT 20% danado + disco muere al 30%. Escenario realista de fallo.",
            damage_type="combined",
            damage_params={"mft_pct": 0.2, "bad_pct": 0.03},
            death_budget=0,
        ),
        Scenario(
            name="S08_mft_damaged_disk_dies_15pct",
            description="MFT 30% danado + disco muere al 15%. Escenario critico.",
            damage_type="combined",
            damage_params={"mft_pct": 0.3, "bad_pct": 0.05},
            death_budget=0,
        ),
        Scenario(
            name="S09_bad_end_disk_dies_20pct",
            description="10% sectores malos al final + disco muere al 20%.",
            damage_type="bad_sectors_end",
            damage_params={"pct": 0.10},
            death_budget=0,
        ),
        Scenario(
            name="S10_critical_dying",
            description="MFT 40% danado + 5% malos + muere al 15%. El peor escenario.",
            damage_type="combined",
            damage_params={"mft_pct": 0.4, "bad_pct": 0.05},
            death_budget=0,
        ),
    ]


def run_benchmark():
    """Run all scenarios and collect results."""
    scenarios = define_scenarios()
    all_results = {}

    print("=" * 72)
    print("  RECOVERY LAB v2 — Benchmark Engine")
    print("  Hipotesis: Priorizar MFT-first mejora la recuperacion en discos que fallan")
    print("=" * 72)
    print()

    for scenario in scenarios:
        print(f"  Ejecutando: {scenario.name}")
        print(f"  {scenario.description}")

        run_results = []
        for run in range(scenario.runs):
            seed = 42 + run * 7
            disk = scenario.create_disk(seed)

            # Set death budget based on scenario
            total_sectors = disk.total_sectors
            if "dies_at_30pct" in scenario.name or "dies_30pct" in scenario.name:
                death_budget = int(total_sectors * 0.30)
            elif "dies_at_10pct" in scenario.name or "dies_15pct" in scenario.name:
                death_budget = int(total_sectors * 0.15)
            elif "dies_20pct" in scenario.name:
                death_budget = int(total_sectors * 0.20)
            elif "critical_dying" in scenario.name:
                death_budget = int(total_sectors * 0.15)
            else:
                death_budget = 0

            disk_b = copy.deepcopy(disk)

            result_a = motor_a_sequential(disk, death_budget=death_budget)
            result_b = motor_b_mft_first(disk_b, death_budget=death_budget)

            run_results.append({
                "run": run,
                "a": result_a.to_dict(),
                "b": result_b.to_dict(),
                "death_budget": death_budget,
            })

        # Aggregate
        a_files = [r["a"]["files_recovered"] for r in run_results]
        b_files = [r["b"]["files_recovered"] for r in run_results]
        a_mft = [r["a"]["mft_entries_recovered"] for r in run_results]
        b_mft = [r["b"]["mft_entries_recovered"] for r in run_results]
        a_bytes = [r["a"]["bytes_recovered"] for r in run_results]
        b_bytes = [r["b"]["bytes_recovered"] for r in run_results]
        a_recoverable = [r["a"]["files_recoverable"] for r in run_results]
        b_recoverable = [r["b"]["files_recoverable"] for r in run_results]
        a_died = sum(1 for r in run_results if r["a"]["disk_died"])
        b_died = sum(1 for r in run_results if r["b"]["disk_died"])
        total_files = run_results[0]["a"]["files_total"]

        avg_a = sum(a_files) / len(a_files)
        avg_b = sum(b_files) / len(b_files)
        diff = ((avg_b - avg_a) / max(avg_a, 1)) * 100

        avg_a_rec = sum(a_recoverable) / len(a_recoverable)
        avg_b_rec = sum(b_recoverable) / len(b_recoverable)

        print(f"  Motor A: {avg_a:.1f}/{total_files} archivos ({avg_a/max(total_files,1)*100:.1f}%) | MFT conocidos: {avg_a_rec:.1f}")
        print(f"  Motor B: {avg_b:.1f}/{total_files} archivos ({avg_b/max(total_files,1)*100:.1f}%) | MFT conocidos: {avg_b_rec:.1f}")
        if diff > 0:
            print(f"  >>> Motor B +{diff:.1f}% MAS archivos")
        elif diff < 0:
            print(f"  >>> Motor A +{abs(diff):.1f}% MAS archivos")
        else:
            print(f"  >>> Sin diferencia significativa")
        print(f"  Disk deaths: A={a_died}/5, B={b_died}/5")
        print()

        all_results[scenario.name] = {
            "description": scenario.description,
            "runs": scenario.runs,
            "avg_a_files": avg_a,
            "avg_b_files": avg_b,
            "avg_a_recoverable": avg_a_rec,
            "avg_b_recoverable": avg_b_rec,
            "avg_a_mft": sum(a_mft) / len(a_mft),
            "avg_b_mft": sum(b_mft) / len(b_mft),
            "avg_a_bytes": sum(a_bytes) / len(a_bytes),
            "avg_b_bytes": sum(b_bytes) / len(b_bytes),
            "diff_pct": diff,
            "a_died": a_died,
            "b_died": b_died,
            "total_files": total_files,
            "raw": run_results,
        }

    return all_results


def generate_report(results: Dict) -> str:
    """Generate a text report."""
    lines = []
    lines.append("=" * 72)
    lines.append("  RECOVERY LAB v2 — INFORME DE RESULTADOS")
    lines.append("=" * 72)
    lines.append("")
    lines.append("HIPOTESIS: Priorizar la lectura del MFT mejora la recuperacion")
    lines.append("cuando el disco tiene un presupuesto de lectura limitado.")
    lines.append("")
    lines.append("MOTOR A: Lectura secuencial (sector 0, 1, 2, 3...)")
    lines.append("MOTOR B: MFT-first (leer MFT primero, luego datos priorizados)")
    lines.append("")
    lines.append("-" * 72)
    lines.append(f"{'Escenario':<32} {'A (arch)':<10} {'B (arch)':<10} {'Diff':<10} {'Veredicto'}")
    lines.append("-" * 72)

    wins_b = 0
    wins_a = 0
    ties = 0

    for name, d in results.items():
        a = d["avg_a_files"]
        b = d["avg_b_files"]
        total = d["total_files"]
        diff = d["diff_pct"]

        if diff > 5:
            verdict = "B GANA"
            wins_b += 1
        elif diff < -5:
            verdict = "A GANA"
            wins_a += 1
        else:
            verdict = "~EMPATE"
            ties += 1

        lines.append(f"{name:<32} {a:>5.1f}/{total:<4} {b:>5.1f}/{total:<4} {diff:>+7.1f}%  {verdict}")

    lines.append("-" * 72)
    lines.append("")
    lines.append(f"RESUMEN: Motor B gana en {wins_b}/10, Motor A gana en {wins_a}/10, Empate en {ties}/10")
    lines.append("")

    # Detailed analysis for key scenarios
    for key_name in ["S07_mft_damaged_disk_dies_30pct", "S08_mft_damaged_disk_dies_15pct",
                     "S10_critical_dying"]:
        if key_name in results:
            d = results[key_name]
            lines.append(f"DETALLE — {key_name}:")
            lines.append(f"  Motor A: {d['avg_a_files']:.1f} archivos recuperados, {d['avg_a_recoverable']:.1f} MFT conocidos")
            lines.append(f"  Motor B: {d['avg_b_files']:.1f} archivos recuperados, {d['avg_b_recoverable']:.1f} MFT conocidos")
            lines.append(f"  Diferencia: {d['diff_pct']:+.1f}%")
            lines.append(f"  Muertes: A={d['a_died']}/5, B={d['b_died']}/5")
            lines.append("")

    # Conclusion
    lines.append("CONCLUSION:")
    if wins_b > wins_a:
        lines.append("  La hipotesis esta SOPORTADA. Motor B (MFT-first) recupera")
        lines.append("  consistentemente mas archivos que Motor A (secuencial),")
        lines.append("  especialmente en escenarios donde el disco falla.")
        if wins_b >= 7:
            lines.append("  La ventaja es CLARA y CONSISTENTE.")
        else:
            lines.append("  La ventaja es moderada. Se necesitan mas pruebas.")
    elif wins_a > wins_b:
        lines.append("  La hipotesis NO esta soportada. La lectura secuencial")
        lines.append("  obtiene mejores o iguales resultados.")
    else:
        lines.append("  Los resultados son MIXTOS. Se necesitan mas pruebas.")
    lines.append("")
    lines.append("NOTA IMPORTANTE: Este es un simulador que modela propiedades")
    lines.append("simplificadas de NTFS. Los resultados reales pueden diferir.")
    lines.append("Este experimento valida la hipotesis en principio, no la")
    lines.append("demuestra definitivamente.")

    return "\n".join(lines)


if __name__ == "__main__":
    random.seed(42)
    start = time.time()
    results = run_benchmark()
    elapsed = time.time() - start

    # Save results
    results_path = LAB_DIR / "results" / "benchmark_v2_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    # Generate report
    report = generate_report(results)
    report_path = LAB_DIR / "results" / "benchmark_v2_report.txt"
    with open(report_path, "w") as f:
        f.write(report)

    print(f"\nResultados guardados en: {results_path}")
    print(f"Informe guardado en: {report_path}")
    print(f"Tiempo: {elapsed:.1f}s")
    print("\n" + report)
