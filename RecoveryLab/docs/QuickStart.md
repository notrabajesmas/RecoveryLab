# Quick Start

Recover files from an NTFS disk image in 3 commands.

## 1. Scan

```bash
recoverylab scan disk.img
```

This shows all recoverable files with their status:

```
Scanning disk.img... done (0.53s)

  #  Name                Size     Source   Confidence
  1  report.pdf          245 KB   mft      █████ 1.00
  2  photo.jpg           1.2 MB   mft      █████ 1.00
  3  budget.xlsx         89 KB    mft      █████ 1.00

20/20 files recovered (RR=100.0%, RFS=0.815)
```

## 2. Recover

```bash
recoverylab recover disk.img output/
```

This writes recovered files to the `output/` directory:

```
Recovering to output/...
  ✓ report.pdf       (245 KB, █████ 1.00)
  ✓ photo.jpg        (1.2 MB, █████ 1.00)
  ✓ budget.xlsx      (89 KB,  █████ 1.00)

20/20 files written to output/
```

## 3. Filter (optional)

Recover only specific file types:

```bash
recoverylab recover disk.img output/ --filter .jpg,.png,.pdf
```

Or only high-confidence files:

```bash
recoverylab recover disk.img output/ --min-confidence 0.8
```

## That's it

For more options, see [CLI.md](CLI.md) and [Recovery Profiles.md](RecoveryProfiles.md).
