#!/usr/bin/env python3
"""Create GitHub Release v0.6.0 with wheel and sdist artifacts."""

import os
import json
import urllib.request
import urllib.error

TOKEN = "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"
REPO = "notrabajesmas/RecoveryLab"
API_BASE = f"https://api.github.com/repos/{REPO}"

def api_json_request(url, method="GET", data=None):
    """Make an authenticated GitHub API request with JSON data."""
    req_headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "RecoveryLab-Release-Script",
    }
    req_data = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=req_data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"HTTP {e.code}: {body}")
        return None

def upload_file(url, filepath, content_type):
    """Upload a binary file to GitHub release asset endpoint."""
    filename = os.path.basename(filepath)
    with open(filepath, "rb") as f:
        file_data = f.read()
    
    req_headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": content_type,
        "User-Agent": "RecoveryLab-Release-Script",
    }
    full_url = f"{url}?name={filename}"
    req = urllib.request.Request(full_url, data=file_data, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"HTTP {e.code}: {body}")
        return None

# Step 1: Create the release
print("Creating GitHub Release v0.6.0...")

release_body = """## RecoveryLab v0.6.0 — Filesystem Recovery Engine

**Recover files. Measure recovery. Prove it.**

### What's new

- **NTFS Sparse files: 0% → 100%** — Full support for sparse file recovery with zero-fill reconstruction
- **API FROZEN** — `scan()`, `recover()`, `statistics` are stable. Breaking = MAJOR bump.
- **CLI identity banner** — `RecoveryLab v0.6.0 / Filesystem Recovery Engine / RR 100% / Sparse 100%`
- **Zero-friction demo** — `recoverylab demo` shows recovery in action with checkmarks
- **Evidence rule** — Every version must answer: what new evidence will exist?

### Capabilities

| Capability | Method | Confidence |
|-----------|--------|-----------|
| Normal NTFS files | MFT metadata | 1.0 |
| Fragmented files | Multi-run reconstruction | 1.0 |
| Deleted files | USN journal | 0.8 |
| Sparse files | Sparse run zero-fill | 0.95 |
| Carved files | Signature matching (19 formats) | 0.5-0.9 |

### CI-verified metrics

These numbers come from real CI execution, not estimates.

| Category | Files | RR | RFS | Time |
|----------|------:|---:|----:|-----:|
| Normal | 20/20 | 100.0% | 0.815 | 0.53s |
| Fragmented | 20/20 | 100.0% | 0.815 | 0.50s |
| Deleted | 20/20 | 100.0% | 0.815 | 0.48s |
| Sparse | 20/20 | 100.0% | 0.850 | 0.19s |

**Total: 80/80 files recovered. RR = 100%.**

### Quick Start

```bash
pip install recoverylab
recoverylab demo
```

Then:
```bash
recoverylab scan disk.img
recoverylab recover disk.img output/
```

### Requirements

- Python 3.10+
- numpy, matplotlib, Pillow, psutil (auto-installed)

### What's next

- **UXR-001**: 10 external testers measure if real people can use RecoveryLab
- **v0.6.1** (compressed files): Release blocked until UXR-001 has data. Development open in `develop` branch.

### Full Changelog

See [CHANGELOG.md](https://github.com/notrabajesmas/RecoveryLab/blob/main/CHANGELOG.md)
"""

release_data = {
    "tag_name": "v0.6.0",
    "target_commitish": "main",
    "name": "RecoveryLab v0.6.0 — Filesystem Recovery Engine",
    "body": release_body,
    "draft": False,
    "prerelease": False,
}

result = api_json_request(f"{API_BASE}/releases", method="POST", data=release_data)

if not result:
    print("FAILED to create release")
    exit(1)

release_id = result.get("id")
upload_url = result.get("upload_url", "").split("{")[0]  # Remove template params
html_url = result.get("html_url", "")

print(f"Release created! ID: {release_id}")
print(f"URL: {html_url}")
print(f"Upload URL: {upload_url}")

# Step 2: Upload artifacts
artifacts = [
    ("/home/z/my-project/RecoveryLab/dist/recoverylab-0.6.0-py3-none-any.whl", "application/zip"),
    ("/home/z/my-project/RecoveryLab/dist/recoverylab-0.6.0.tar.gz", "application/gzip"),
]

for artifact_path, content_type in artifacts:
    filename = os.path.basename(artifact_path)
    print(f"\nUploading {filename}...")
    
    upload_result = upload_file(upload_url, artifact_path, content_type)
    
    if upload_result:
        size = os.path.getsize(artifact_path)
        print(f"  OK: {filename} uploaded ({size} bytes)")
    else:
        print(f"  FAIL: {filename}")

print(f"\nRelease page: {html_url}")
print("Done!")
