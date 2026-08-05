# API Reference

RecoveryLab's public API is frozen. These classes and methods will not change
without a major version bump.

## Quick example

```python
from core import RecoveryEngine

engine = RecoveryEngine()
result = engine.scan("disk.img")

# Browse results
for f in result.files:
    print(f.name, f.size, f.confidence, f.status.value)

# Recover specific file
result.recover("mft_42", output_dir="recovered/")

# Recover all
result.recover_all(output_dir="recovered/")

# Statistics
print(result.statistics.summary)
```

## RecoveryEngine

The single entry point for all recovery operations.

```python
engine = RecoveryEngine(
    profile="mft_first",    # Strategy profile
    cluster_size=4096,       # NTFS cluster size
    enable_carving=True,     # Run signature carving
    enable_journal=True,     # Use USN Journal fallback
)
```

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `scan(path)` | `ScanResult` | Scan a disk image file |
| `scan_bytes(data)` | `ScanResult` | Scan from bytes (for testing) |
| `recover(item, output_dir)` | `str` or `None` | Recover one file to disk |
| `recover_all(result, output_dir)` | `Dict[str,str]` | Recover all files |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `version` | `str` | Engine version |
| `pipeline_stages` | `List[str]` | Active pipeline stages |

## ScanResult

The result of a scan operation. Contains all found files and statistics.

| Method/Property | Returns | Description |
|-----------------|---------|-------------|
| `files` | `List[RecoveredItem]` | All found files |
| `statistics` | `RecoveryStatistics` | RR, RFS, RC, timing |
| `errors` | `List[str]` | Any errors encountered |
| `recover(file_id, output_dir)` | `str` or `None` | Recover one file by ID |
| `recover_all(output_dir)` | `Dict[str,str]` | Recover all files |
| `get_file(file_id)` | `RecoveredItem` or `None` | Lookup by ID |
| `by_source()` | `Dict[str, List]` | Group by source (mft/journal/carving) |
| `by_status()` | `Dict[str, List]` | Group by status |
| `by_extension()` | `Dict[str, List]` | Group by file extension |

## RecoveredItem

A single recovered file.

| Property | Type | Description |
|----------|------|-------------|
| `id` | `str` | Unique identifier (e.g. "mft_42") |
| `name` | `str` | Original filename |
| `size` | `int` | File size in bytes |
| `status` | `FileStatus` | Recovery status |
| `source` | `FileSource` | How it was found |
| `confidence` | `float` | 0.0-1.0 confidence |
| `sha256` | `str` | SHA-256 hash |
| `is_fragmented` | `bool` | Split across multiple runs |
| `fragment_count` | `int` | Number of data runs |
| `is_recovered` | `bool` | True if data is available |

## RecoveryStatistics

| Property | Type | Description |
|----------|------|-------------|
| `recovery_rate` | `float` | RR (0.0-1.0) |
| `fidelity_score` | `float` | RFS (0.0-1.0) |
| `quality` | `float` | RR × RFS |
| `cost` | `RecoveryCost` | CPU, RAM, I/O metrics |
| `scan_time_seconds` | `float` | Total scan time |
| `peak_ram_mb` | `float` | Peak memory usage |
| `summary` | `str` | Human-readable summary |

## RecoveryCost

| Property | Type | Description |
|----------|------|-------------|
| `cpu_time_seconds` | `float` | CPU time |
| `peak_ram_mb` | `float` | Peak RAM |
| `bytes_scanned` | `int` | Bytes read from image |
| `strategy_cost_total` | `float` | Sum of strategy cost multipliers |
| `strategies_run` | `List[str]` | Which stages ran |
| `read_efficiency` | `float` | Fraction of useful reads (0.0-1.0) |

## Enums

### FileStatus
`RECOVERED` | `PARTIAL` | `METADATA_ONLY` | `DAMAGED` | `NOT_RECOVERED`

### FileSource
`MFT` | `JOURNAL` | `CARVING` | `FRAGMENT` | `HYBRID`
