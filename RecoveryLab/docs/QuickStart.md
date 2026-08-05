# Quick Start

Recover files from an NTFS disk image in 3 commands.

## 1. Install

```bash
pip install recoverylab
```

Or from source:

```bash
git clone https://github.com/notrabajesmas/RecoveryLab.git
cd RecoveryLab
pip install .
```

Verify:

```bash
recoverylab --version
# v0.6.0
```

## 2. Scan

```bash
recoverylab scan disk.img
```

This shows all recoverable files with their status:

```
Scanning disk.img... done (0.53s)

  #  Name                Size     Source   Confidence
  1  report.pdf          245 KB   mft      1.00
  2  photo.jpg           1.2 MB   mft      1.00
  3  budget.xlsx         89 KB    mft      1.00

20/20 files recovered (RR=100.0%, RFS=0.815)
```

## 3. Recover

```bash
recoverylab recover disk.img output/
```

This writes recovered files to the `output/` directory:

```
Recovering to output/...
  report.pdf       (245 KB, confidence 1.00)
  photo.jpg        (1.2 MB, confidence 1.00)
  budget.xlsx      (89 KB,  confidence 1.00)

20/20 files written to output/
```

## 4. Filter (optional)

Recover only specific file types:

```bash
recoverylab recover disk.img output/ --filter .jpg,.png,.pdf
```

Or only high-confidence files:

```bash
recoverylab recover disk.img output/ --min-confidence 0.8
```

## Recovery Profiles

```bash
recoverylab scan disk.img --profile fast         # MFT only — fastest
recoverylab scan disk.img --profile balanced     # MFT + Journal
recoverylab scan disk.img --profile mft_first    # MFT → Journal → Carving (default)
recoverylab scan disk.img --profile full         # All strategies — most thorough
```

## What RecoveryLab Recovers

| File type | How | Confidence |
|-----------|-----|-----------|
| Normal NTFS files | MFT metadata | 1.0 |
| Fragmented files | Multi-run reconstruction | 1.0 |
| Deleted files | USN journal | 0.8 |
| Sparse files | Sparse run zero-fill | 0.95 |
| Carved files | Signature matching | 0.5–0.9 |

For more options, see [CLI.md](CLI.md) and [Recovery Profiles.md](RecoveryProfiles.md).
