"""
RecoveryLab — Deterministic File Generator
============================================
Generates realistic file content from a seed for reproducible datasets.

Every file is deterministic: same seed → same files → same SHA-256.
Uses a seeded PRNG to generate varied file types and sizes.
"""

import hashlib
import random
import struct
from dataclasses import dataclass
from typing import List, Tuple, Optional
from pathlib import Path

# ─── File Type Signatures ─────────────────────────────────────────────────────

# Common file headers for realistic file generation
FILE_SIGNATURES = {
    ".jpg":  b'\xFF\xD8\xFF\xE0',   # JPEG/JFIF
    ".png":  b'\x89PNG\r\n\x1a\n',   # PNG
    ".pdf":  b'%PDF-1.4\n',          # PDF
    ".zip":  b'PK\x03\x04',          # ZIP
    ".docx": b'PK\x03\x04',          # DOCX (ZIP-based)
    ".xlsx": b'PK\x03\x04',          # XLSX (ZIP-based)
    ".mp4":  b'\x00\x00\x00\x20ftypisom',  # MP4
    ".avi":  b'RIFF',                 # AVI
    ".exe":  b'MZ',                   # EXE
    ".dll":  b'MZ',                   # DLL
    ".sys":  b'MZ',                   # SYS
    ".txt":  b'',                     # Plain text (no signature)
    ".log":  b'',                     # Log (no signature)
    ".xml":  b'<?xml version="1.0"',  # XML
    ".json": b'{',                    # JSON
    ".cr2":  b'II\x2a\x00\x10\x00\x00\x00',  # Canon CR2
    ".nef":  b'MM\x00\x2a',          # Nikon NEF
    ".mov":  b'\x00\x00\x00\x1cftypqt',  # MOV
    ".dat":  b'',                     # Generic data
}

# File footers for carving — these are the end-of-file markers
# that a carving tool would search for to determine file boundaries.
# Without proper footers, carving becomes much harder.
FILE_FOOTERS = {
    ".jpg":  b'\xFF\xD9',              # JPEG EOI (End of Image)
    ".png":  b'IEND\xAE\x42\x60\x82',  # PNG IEND chunk + CRC
    ".pdf":  b'%%EOF\n',              # PDF end-of-file marker
    ".zip":  b'PK\x05\x06',            # ZIP End of Central Directory
    ".docx": b'PK\x05\x06',            # DOCX (same as ZIP)
    ".xlsx": b'PK\x05\x06',            # XLSX (same as ZIP)
    ".gif":  b';',                      # GIF trailer (semicolon)
    ".tiff": b'',                       # TIFF — no reliable footer
    ".cr2":  b'',                       # CR2 — no reliable footer (TIFF-based)
    ".nef":  b'',                       # NEF — no reliable footer (TIFF-based)
    ".mp4":  b'',                       # MP4 — no reliable footer
    ".mov":  b'',                       # MOV — no reliable footer
    ".avi":  b'',                       # AVI — no reliable footer
    ".sqlite": b'',                     # SQLite — no reliable footer
    ".bmp":  b'',                       # BMP — no reliable footer
    ".rar":  b'',                       # RAR — no reliable footer
    ".7z":   b'',                       # 7Z — no reliable footer
    ".psd":  b'',                       # PSD — no reliable footer
}


@dataclass
class GeneratedFile:
    """A single generated file with its content and metadata."""
    name: str
    data: bytes
    extension: str
    category: str
    size: int
    sha256: str
    created_offset: float   # Seconds offset from base time
    modified_offset: float


class FileGenerator:
    """
    Deterministic file generator.

    Usage:
        gen = FileGenerator(seed=42)
        files = gen.generate_file_set(count=50)
        for f in files:
            print(f.name, f.sha256, len(f.data))
    """

    def __init__(self, seed: int = 42, volume_size: int = 10*1024*1024,
                 cluster_size: int = 4096):
        self.seed = seed
        self.rng = random.Random(seed)
        self.volume_size = volume_size
        self.cluster_size = cluster_size

        # Import profiles from config
        from config import FILE_PROFILES
        self.profiles = FILE_PROFILES

    def generate_file_set(self, count: int = 50,
                          fragmentation_rate: float = 0.0,
                          max_total_bytes: Optional[int] = None) -> List[GeneratedFile]:
        """
        Generate a set of files with realistic distribution.

        Args:
            count: Number of files to generate
            fragmentation_rate: Fraction of files that should be fragmented
            max_total_bytes: Optional cap on total data size

        Returns:
            List of GeneratedFile objects
        """
        files = []
        total_bytes = 0
        counters = {}  # extension -> next number

        # Determine how many files per category
        category_counts = self._distribute_categories(count)

        for category, cat_count in category_counts.items():
            profile = self.profiles[category]
            extensions = profile["extensions"]
            size_min, size_max = profile["size_range"]

            for _ in range(cat_count):
                # Pick extension
                ext = self.rng.choice(extensions)
                counters[ext] = counters.get(ext, 0) + 1

                # Pick size
                # Use log-uniform distribution for more realistic sizes
                import math
                log_min = math.log(size_min)
                log_max = math.log(size_max)
                size = int(math.exp(self.rng.uniform(log_min, log_max)))

                # Check total size cap
                if max_total_bytes and total_bytes + size > max_total_bytes:
                    size = max(size_min, max_total_bytes - total_bytes)
                    if size < size_min:
                        break

                # Generate file name
                name = f"{ext[1:]}_{counters[ext]:04d}{ext}"

                # Generate content
                data = self._generate_content(ext, size)

                # Generate timestamps
                created_offset = self.rng.uniform(0, 365 * 24 * 3600)
                modified_offset = created_offset + self.rng.uniform(0, 30 * 24 * 3600)

                sha256 = hashlib.sha256(data).hexdigest()

                files.append(GeneratedFile(
                    name=name,
                    data=data,
                    extension=ext,
                    category=category,
                    size=len(data),
                    sha256=sha256,
                    created_offset=created_offset,
                    modified_offset=modified_offset,
                ))

                total_bytes += len(data)

        # Sort by creation time for more realistic ordering
        files.sort(key=lambda f: f.created_offset)

        return files

    def _distribute_categories(self, count: int) -> dict:
        """Distribute file count across categories based on weights."""
        result = {}
        remaining = count

        categories = list(self.profiles.keys())
        weights = [self.profiles[c]["weight"] for c in categories]

        # Normalize weights
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]

        for i, (cat, weight) in enumerate(zip(categories, weights)):
            if i == len(categories) - 1:
                result[cat] = remaining
            else:
                n = max(1, round(count * weight))
                n = min(n, remaining)
                result[cat] = n
                remaining -= n

        return result

    def _generate_content(self, ext: str, size: int) -> bytes:
        """
        Generate deterministic file content with realistic header AND footer.

        The content is seeded by (global_seed + extension + size) so that
        the same parameters always produce the same bytes.

        CRITICAL: Files now include proper footers (JPEG EOI, PNG IEND,
        PDF %%EOF, etc.) so that carving tools can detect file boundaries.
        Without footers, carving is practically impossible.
        """
        # Create a deterministic seed for this specific file
        content_seed = hashlib.md5(
            f"{self.seed}:{ext}:{size}:{self.rng.randint(0, 2**32)}".encode()
        ).hexdigest()
        content_rng = random.Random(content_seed)

        # Start with file signature (header)
        header = FILE_SIGNATURES.get(ext, b'')

        # Get footer for this file type
        footer = FILE_FOOTERS.get(ext, b'')

        # Calculate body size: total = header + body + footer
        total_fixed = len(header) + len(footer)
        body_size = size - total_fixed

        if body_size <= 0:
            # File too small for header + footer, just return header
            return header[:size]

        # Generate pseudo-random body
        # Use chunked generation for efficiency with large files
        body = bytearray()
        chunk_size = 65536
        while len(body) < body_size:
            # Generate a chunk of random data
            chunk = bytes(content_rng.getrandbits(8) for _ in
                         range(min(chunk_size, body_size - len(body))))
            body.extend(chunk)

        return header + bytes(body[:body_size]) + footer

    def generate_directories(self, files: List[GeneratedFile],
                             max_depth: int = 2) -> List[dict]:
        """
        Generate a directory structure for the given files.

        Returns a list of directory dicts with:
            - name: directory name
            - parent_record: parent directory MFT record number
            - files: list of GeneratedFile objects in this directory
        """
        dirs = []

        # Root directory (record 5) is always present
        # Create some common Windows-like directories
        dir_templates = [
            ("Users", 5),
            ("Users\\Alice", 5),
            ("Users\\Alice\\Documents", 5),
            ("Users\\Alice\\Pictures", 5),
            ("Users\\Alice\\Desktop", 5),
            ("Program Files", 5),
            ("Windows", 5),
            ("Windows\\System32", 5),
            ("Data", 5),
        ]

        # We'll assign record numbers later in the builder
        # For now, just return the structure
        return dir_templates
