# CLI Reference

## Commands

### `recoverylab scan`

Scan a disk image and list recoverable files.

```bash
recoverylab scan disk.img
```

**Options:**

| Flag | Description |
|------|-------------|
| `--json` | Output results as JSON (for scripts) |
| `--profile NAME` | Use a recovery profile (default: mft_first) |
| `--no-carving` | Skip signature carving (faster) |
| `--no-journal` | Skip USN Journal fallback |
| `--filter EXT` | Show only specific extensions (comma-separated) |
| `--min-confidence N` | Show only files with confidence ≥ N |

**Examples:**

```bash
# Fast scan (MFT only, no carving)
recoverylab scan disk.img --profile fast

# JSON output for scripting
recoverylab scan disk.img --json > results.json

# Show only images
recoverylab scan disk.img --filter .jpg,.png,.gif
```

### `recoverylab recover`

Recover files to a directory.

```bash
recoverylab recover disk.img output/
```

**Options:**

| Flag | Description |
|------|-------------|
| `--filter EXT` | Recover only specific extensions |
| `--min-confidence N` | Recover only files with confidence ≥ N |
| `--profile NAME` | Use a recovery profile |

**Examples:**

```bash
# Recover only PDFs
recoverylab recover disk.img output/ --filter .pdf

# Recover only high-confidence files
recoverylab recover disk.img output/ --min-confidence 0.8
```

### `recoverylab info`

Quick image metadata without a full scan.

```bash
recoverylab info disk.img
```

Shows filesystem type, cluster size, and MFT location.

### `recoverylab --version`

Show version number.

### `recoverylab --help`

Show help with examples and supported formats.

## Output format

The scan output shows:

- **Name**: Original filename (from MFT when available)
- **Size**: File size
- **Source**: How the file was found (mft, journal, carving)
- **Confidence**: Recovery confidence (0.0 - 1.0) shown as bars

The confidence bar uses 5 blocks:

```
█████ 1.00  — Perfect recovery
████░ 0.80  — High confidence
███░░ 0.60  — Good confidence
██░░░ 0.40  — Low confidence
█░░░░ 0.20  — Very low confidence
```
