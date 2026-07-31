# EXP-0005 — External Tool Test Dataset Package
==============================================
Generated: 2026-07-30 21:59
Commit: c2cc5af
Seed: 42

## Files
- healthy_10mb.img / _manifest.json — Healthy NTFS image (0% corruption)
- mft20_10mb.img / _manifest.json — 20% MFT entries zeroed
- mft60_10mb.img / _manifest.json — 60% MFT entries zeroed

## How to Test an External Tool
1. Run the tool on each .img file
2. Record:
   - Total files recovered
   - Files with correct content (compare with manifest SHA-256)
   - Total runtime
   - Read count (if available)
3. Compute OU = RVS × FQS using the manifest values
4. Add results to the comparison table in external_validation_report.md

## Expected Results (RecoveryLab)
See external_validation_summary.json for RecoveryLab's results on these datasets.

## Important
- The manifest.json contains the GROUND TRUTH (what's in the image)
- Compare the tool's output against the manifest to compute recovery metrics
- Use the same Judge API (or equivalent) for fair comparison
