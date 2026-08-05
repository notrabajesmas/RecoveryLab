# Recovery Profiles

A recovery profile controls which strategies run and in what order. This affects
the trade-off between recovery completeness (RR) and cost (RC).

## Available profiles

| Profile | Strategies | Speed | Recovery | Use when |
|---------|-----------|-------|----------|----------|
| `fast` | MFT only | Fastest | Good for intact MFT | You need speed over completeness |
| `balanced` | MFT + Journal | Fast | Good + deleted files | Typical use |
| `mft_first` | MFT → Journal → Carving | Moderate | Best general | **Default** |
| `journal_first` | Journal → MFT → Carving | Moderate | Best for deleted | Many recently deleted files |
| `carving_first` | Carving → MFT → Journal | Slow | Most thorough | Heavy corruption, MFT damaged |
| `full` | All strategies | Slowest | Maximum recovery | Maximum recovery regardless of cost |

## Usage

```bash
# Use the default profile
recoverylab scan disk.img

# Use a specific profile
recoverylab scan disk.img --profile fast
recoverylab scan disk.img --profile full
```

## How strategies work

### Strategy A: MFT (cost 1.0x)
Reads the Master File Table to find files by their metadata entries. Fast and
precise — provides real filenames, timestamps, and directory structure.

### Strategy B: Journal (cost 1.5x)
Reads the USN Change Journal to find files that were recently deleted, renamed,
or moved. Falls back when MFT entries are damaged.

### Strategy C: Carving (cost 10.0x)
Scans the entire image byte-by-byte looking for file signatures (JPEG, PNG,
PDF, ZIP, DOCX, etc.). Slow but finds files even when all metadata is lost.
Does NOT recover filenames.

### Strategy D: Fragment (cost 2.0x)
Reconstructs files that are split across multiple non-contiguous data runs
(fragments). Handles sparse and partially lost files.

### Strategy E: Hybrid (cost 5.0x)
Adaptive delegation — automatically picks the best strategy for each file
based on its characteristics.

## What each strategy recovers

| Info | MFT | Journal | Carving | Fragment |
|------|-----|---------|---------|----------|
| Filename | ✅ | ✅ | ❌ | ✅ |
| SHA-256 | ✅ | ❌ | ✅ | ✅ |
| Timestamps | ✅ | ✅ | ❌ | ✅ |
| Directory | ✅ | ✅ | ❌ | ✅ |
| Deleted files | ✅ | ✅ | ✅ | ❌ |
| Without MFT | ❌ | ✅ | ✅ | ❌ |
