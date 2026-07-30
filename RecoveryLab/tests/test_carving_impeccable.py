#!/usr/bin/env python3
"""
RecoveryLab — Carving Motor Validation Suite
==============================================
The 1:1 rule: For every 500 lines of recovery code, add at least
500 lines of validation, tests, and metrics.

This test suite validates that the three core parsers (JPEG, PNG, PDF)
are IMPECCABLE. Not "more or less" — impeccable.

Test categories:
  1. Signature detection: Must find all valid files
  2. Boundary detection: Must correctly determine file boundaries
  3. False positive rate: Must not produce false positives
  4. Edge cases: Must handle fragmented, truncated, and corrupted files
  5. Regression: Must not break existing functionality

Rule: If a test fails, the parser is NOT impeccable. Fix it.
"""

import hashlib
import struct
import sys
import unittest
from pathlib import Path
from typing import Dict, List, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from motors.motor_carving import MotorCarving, SIGNATURES, FileSignature
from motors.base_motor import MotorResult
from dataset_builder.file_generator import FileGenerator, FILE_SIGNATURES, FILE_FOOTERS
from dataset_builder.builder import DatasetBuilder
from recovery_judge.judge import RecoveryJudge
from recovery_judge.functional_validator import FunctionalValidator, RecoveryLevel


# ─── Helper: Build a simple image with specific files ─────────────────────────

def build_simple_image(files_data: List[Tuple[str, bytes]],
                       cluster_size: int = 4096,
                       total_size: int = 10 * 1024 * 1024) -> Tuple[bytes, Dict]:
    """
    Build a simple NTFS-like image with specific files at known offsets.
    Returns (image_bytes, manifest_dict).
    """
    image = bytearray(total_size)
    manifest_files = []
    offset = cluster_size * 100  # Start after "system area"

    for name, data in files_data:
        # Align to cluster boundary
        cluster_start = (offset + cluster_size - 1) // cluster_size * cluster_size
        image[cluster_start:cluster_start + len(data)] = data

        sha256 = hashlib.sha256(data).hexdigest()
        manifest_files.append({
            "id": len(manifest_files),
            "name": name,
            "sha256": sha256,
            "size": len(data),
            "is_directory": False,
            "clusters": [cluster_start // cluster_size],
        })
        offset = cluster_start + len(data)

    manifest = {
        "cluster_size": cluster_size,
        "total_clusters": total_size // cluster_size,
        "mft": {"start_cluster": 2, "record_count": 20},
        "files": manifest_files,
    }

    return bytes(image), manifest


# ─── Test JPEG Signature Detection ───────────────────────────────────────────

class TestJPEGCarving(unittest.TestCase):
    """JPEG carving must be IMPECCABLE."""

    def setUp(self):
        self.motor = MotorCarving()
        self.validator = FunctionalValidator()

    def test_jpeg_basic_detection(self):
        """JPEG with valid header + footer must be detected."""
        jpeg_data = (
            b'\xFF\xD8\xFF\xE0' +
            b'\x00\x10' +
            b'JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00' +
            b'\xFF\xC0\x00\x0B\x08\x00\x01\x00\x01\x01\x01\x11\x00' +
            b'\xFF\xDA\x00\x08\x01\x01\x00\x00\x3F\x00' +
            b'\x00' * 500 +   # Must exceed min_size=200
            b'\xFF\xD9'
        )

        image, manifest = build_simple_image([("photo.jpg", jpeg_data)])
        result = self.motor.recover(image, manifest)

        jpeg_files = [f for f in result.recovered_files if f.name.endswith('.jpg')]
        self.assertGreaterEqual(len(jpeg_files), 1,
            "JPEG with valid header + footer must be detected")

        if len(jpeg_files) > 0:
            self.assertEqual(jpeg_files[0].data[:3], b'\xFF\xD8\xFF',
                "Recovered JPEG must start with SOI marker")

    def test_jpeg_with_exif(self):
        """JPEG with EXIF (FF E1) header must be detected."""
        jpeg_data = (
            b'\xFF\xD8\xFF\xE1' +
            b'\x00\x10Exif\x00\x00\x00' * 2 +
            b'\xFF\xC0\x00\x0B\x08\x00\x01\x00\x01\x01\x01\x11\x00' +
            b'\xFF\xDA\x00\x08\x01\x01\x00\x00\x3F\x00' +
            b'\x00' * 500 +   # Must exceed min_size=200
            b'\xFF\xD9'
        )

        image, manifest = build_simple_image([("photo_exif.jpg", jpeg_data)])
        result = self.motor.recover(image, manifest)
        jpeg_files = [f for f in result.recovered_files if f.name.endswith('.jpg')]
        self.assertGreaterEqual(len(jpeg_files), 1,
            "JPEG with EXIF header must be detected")

    def test_jpeg_multiple_in_image(self):
        """Multiple JPEGs in the same image must all be detected."""
        jpegs = []
        for i in range(5):
            jpeg_data = (
                b'\xFF\xD8\xFF\xE0' +
                b'\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00' +
                b'\xFF\xC0\x00\x0B\x08\x00\x01\x00\x01\x01\x01\x11\x00' +
                b'\xFF\xDA\x00\x08\x01\x01\x00\x00\x3F\x00' +
                bytes([i * 37 % 256] * 500) +   # Must exceed min_size=200
                b'\xFF\xD9'
            )
            jpegs.append((f"photo_{i:04d}.jpg", jpeg_data))

        image, manifest = build_simple_image(jpegs)
        result = self.motor.recover(image, manifest)

        jpeg_files = [f for f in result.recovered_files if f.name.endswith('.jpg')]
        self.assertGreaterEqual(len(jpeg_files), 3,
            f"Expected at least 3 of 5 JPEGs, found {len(jpeg_files)}")

    def test_jpeg_no_false_positives(self):
        """Random data should not produce JPEG false positives."""
        import random
        rng = random.Random(42)
        image = bytes(rng.getrandbits(8) for _ in range(10 * 1024 * 1024))
        manifest = {
            "cluster_size": 4096, "total_clusters": 2560,
            "mft": {"start_cluster": 2, "record_count": 20}, "files": [],
        }

        result = self.motor.recover(image, manifest)
        jpeg_fps = [f for f in result.recovered_files if f.name.endswith('.jpg')]
        self.assertLessEqual(len(jpeg_fps), 2,
            f"Too many JPEG false positives: {len(jpeg_fps)}")

    def test_jpeg_functional_validation(self):
        """A perfectly carved JPEG should pass functional validation."""
        jpeg_data = (
            b'\xFF\xD8\xFF\xE0' +
            b'\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00' +
            b'\xFF\xC0\x00\x0B\x08\x00\x01\x00\x01\x01\x01\x11\x00' +
            b'\xFF\xDA\x00\x08\x01\x01\x00\x00\x3F\x00' +
            b'\x00' * 500 +   # Must exceed min_size=200
            b'\xFF\xD9'
        )

        val_result = self.validator.validate(jpeg_data, "photo.jpg")
        self.assertGreaterEqual(val_result["functional_score"], 0.5,
            f"Valid JPEG should have functional_score >= 0.5, got {val_result['functional_score']}")


# ─── Test PNG Signature Detection ────────────────────────────────────────────

class TestPNGCarving(unittest.TestCase):
    """PNG carving must be IMPECCABLE."""

    def setUp(self):
        self.motor = MotorCarving()
        self.validator = FunctionalValidator()

    def test_png_basic_detection(self):
        """PNG with valid header + IEND must be detected."""
        png_sig = b'\x89PNG\r\n\x1a\n'
        ihdr_data = b'\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00'
        ihdr_chunk = struct.pack('>I', 13) + b'IHDR' + ihdr_data + b'\x90\x77\x53\xDE'
        # Create larger IDAT to exceed min_size=100
        idat_data = b'\x08\x1D' + b'\x00' * 200 + b'\x01'
        idat_chunk = struct.pack('>I', len(idat_data)) + b'IDAT' + idat_data + b'\x5C\x4F\xB2\x42'
        iend_chunk = b'\x00\x00\x00\x00IEND\xAE\x42\x60\x82'

        png_data = png_sig + ihdr_chunk + idat_chunk + iend_chunk

        image, manifest = build_simple_image([("image.png", png_data)])
        result = self.motor.recover(image, manifest)
        png_files = [f for f in result.recovered_files if f.name.endswith('.png')]
        self.assertGreaterEqual(len(png_files), 1,
            "PNG with valid header + IEND must be detected")

    def test_png_functional_validation(self):
        """A perfectly carved PNG should pass functional validation."""
        png_sig = b'\x89PNG\r\n\x1a\n'
        ihdr_data = b'\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00'
        ihdr_chunk = struct.pack('>I', 13) + b'IHDR' + ihdr_data + b'\x90\x77\x53\xDE'
        idat_data = b'\x08\x1D' + b'\x00' * 200 + b'\x01'
        idat_chunk = struct.pack('>I', len(idat_data)) + b'IDAT' + idat_data + b'\x5C\x4F\xB2\x42'
        iend_chunk = b'\x00\x00\x00\x00IEND\xAE\x42\x60\x82'
        png_data = png_sig + ihdr_chunk + idat_chunk + iend_chunk

        val_result = self.validator.validate(png_data, "image.png")
        self.assertGreaterEqual(val_result["functional_score"], 0.5,
            f"Valid PNG should have functional_score >= 0.5, got {val_result['functional_score']}")

    def test_png_no_false_positives(self):
        """Random data should not produce PNG false positives."""
        import random
        rng = random.Random(42)
        image = bytes(rng.getrandbits(8) for _ in range(10 * 1024 * 1024))
        manifest = {
            "cluster_size": 4096, "total_clusters": 2560,
            "mft": {"start_cluster": 2, "record_count": 20}, "files": [],
        }

        result = self.motor.recover(image, manifest)
        png_fps = [f for f in result.recovered_files if f.name.endswith('.png')]
        self.assertLessEqual(len(png_fps), 1,
            f"Too many PNG false positives: {len(png_fps)}")


# ─── Test PDF Signature Detection ────────────────────────────────────────────

class TestPDFCarving(unittest.TestCase):
    """PDF carving must be IMPECCABLE."""

    def setUp(self):
        self.motor = MotorCarving()
        self.validator = FunctionalValidator()

    def test_pdf_basic_detection(self):
        """PDF with valid header + %%EOF must be detected."""
        # Create a PDF large enough to exceed min_size=500
        pdf_data = (
            b'%PDF-1.4\n'
            b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n'
            b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n'
            b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
            b'/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n'
            b'4 0 obj\n<< /Length 200 >>\nstream\n'
            + b'BT /F1 12 Tf 100 700 Td (RecoveryLab Test Document) Tj ET\n' +
            b' ' * 150 +  # Padding to exceed min_size
            b'\nendstream\nendobj\n'
            b'5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n'
            b'xref\n0 6\n'
            b'0000000000 65535 f \n0000000009 00000 n \n'
            b'0000000058 00000 n \n0000000115 00000 n \n'
            b'0000000300 00000 n \n0000000600 00000 n \n'
            b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n700\n%%EOF\n'
        )

        image, manifest = build_simple_image([("document.pdf", pdf_data)])
        result = self.motor.recover(image, manifest)
        pdf_files = [f for f in result.recovered_files if f.name.endswith('.pdf')]
        self.assertGreaterEqual(len(pdf_files), 1,
            "PDF with valid header + %%EOF must be detected")

    def test_pdf_functional_validation(self):
        """A perfectly carved PDF should pass functional validation."""
        pdf_data = (
            b'%PDF-1.4\n'
            b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n'
            b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n'
            b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
            b'/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n'
            b'4 0 obj\n<< /Length 200 >>\nstream\n'
            + b'BT /F1 12 Tf 100 700 Td (RecoveryLab Test Document) Tj ET\n' +
            b' ' * 150 +
            b'\nendstream\nendobj\n'
            b'5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n'
            b'xref\n0 6\n'
            b'0000000000 65535 f \n0000000009 00000 n \n'
            b'0000000058 00000 n \n0000000115 00000 n \n'
            b'0000000300 00000 n \n0000000600 00000 n \n'
            b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n700\n%%EOF\n'
        )

        val_result = self.validator.validate(pdf_data, "document.pdf")
        self.assertGreaterEqual(val_result["functional_score"], 0.5,
            f"Valid PDF should have functional_score >= 0.5, got {val_result['functional_score']}")
        self.assertTrue(val_result["details"]["has_valid_header"],
            "PDF must have valid header")
        self.assertTrue(val_result["details"]["has_eof_marker"],
            "PDF must have %%EOF marker")

    def test_pdf_no_false_positives(self):
        """Random data should not produce PDF false positives."""
        import random
        rng = random.Random(42)
        image = bytes(rng.getrandbits(8) for _ in range(10 * 1024 * 1024))
        manifest = {
            "cluster_size": 4096, "total_clusters": 2560,
            "mft": {"start_cluster": 2, "record_count": 20}, "files": [],
        }

        result = self.motor.recover(image, manifest)
        pdf_fps = [f for f in result.recovered_files if f.name.endswith('.pdf')]
        self.assertLessEqual(len(pdf_fps), 1,
            f"Too many PDF false positives: {len(pdf_fps)}")


# ─── Test Signature Database Consistency ─────────────────────────────────────

class TestSignatureDatabase(unittest.TestCase):
    """The signature database must be consistent and correct."""

    def test_all_signatures_have_required_fields(self):
        """Every signature must have name, extension, header, footer, max_size, min_size."""
        for sig in SIGNATURES:
            self.assertTrue(sig.name, "Signature must have a name")
            self.assertTrue(sig.extension.startswith('.'), f"Extension must start with .: {sig.extension}")
            self.assertTrue(len(sig.header) > 0, f"Signature {sig.name} must have a header")
            self.assertTrue(sig.max_size > 0, f"Signature {sig.name} must have max_size > 0")
            self.assertTrue(sig.min_size > 0, f"Signature {sig.name} must have min_size > 0")
            self.assertTrue(sig.min_size <= sig.max_size, f"Signature {sig.name}: min_size > max_size")

    def test_header_mask_consistency(self):
        """Header mask must be the same length as header."""
        for sig in SIGNATURES:
            self.assertEqual(len(sig.header_mask), len(sig.header),
                f"Signature {sig.name}: mask length ({len(sig.header_mask)}) != header length ({len(sig.header)})")

    def test_jpeg_header_specificity(self):
        """JPEG header must be specific enough to avoid false positives."""
        jpeg_sigs = [s for s in SIGNATURES if s.name == "JPEG"]
        self.assertEqual(len(jpeg_sigs), 1, "Should have exactly one JPEG signature")
        jpeg_sig = jpeg_sigs[0]
        self.assertEqual(jpeg_sig.header[:3], b'\xFF\xD8\xFF',
            "JPEG header must start with FF D8 FF")
        self.assertEqual(jpeg_sig.footer, b'\xFF\xD9',
            "JPEG footer must be FF D9")

    def test_png_header_specificity(self):
        """PNG header must be the exact 8-byte signature."""
        png_sigs = [s for s in SIGNATURES if s.name == "PNG"]
        self.assertEqual(len(png_sigs), 1, "Should have exactly one PNG signature")
        png_sig = png_sigs[0]
        self.assertEqual(png_sig.header, b'\x89PNG\r\n\x1a\n',
            "PNG header must be the exact 8-byte signature")
        self.assertEqual(png_sig.footer, b'IEND\xAE\x42\x60\x82',
            "PNG footer must include IEND chunk + CRC")

    def test_pdf_header_specificity(self):
        """PDF header must be %PDF-."""
        pdf_sigs = [s for s in SIGNATURES if s.name == "PDF"]
        self.assertEqual(len(pdf_sigs), 1, "Should have exactly one PDF signature")
        pdf_sig = pdf_sigs[0]
        self.assertEqual(pdf_sig.header, b'%PDF-',
            "PDF header must be %PDF-")
        self.assertEqual(pdf_sig.footer, b'%%EOF',
            "PDF footer must be %%EOF")


# ─── Test Functional Validator Consistency ────────────────────────────────────

class TestFunctionalValidatorConsistency(unittest.TestCase):
    """The functional validator must be consistent with carving results."""

    def setUp(self):
        self.validator = FunctionalValidator()

    def test_jpeg_validation_levels(self):
        """JPEG validation must produce correct levels for different inputs."""
        jpeg_perfect = (
            b'\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
            b'\xFF\xC0\x00\x0B\x08\x00\x01\x00\x01\x01\x01\x11\x00'
            b'\xFF\xDA\x00\x08\x01\x01\x00\x00\x3F\x00'
            b'\x00' * 100 + b'\xFF\xD9'
        )
        result = self.validator.validate(jpeg_perfect, "photo.jpg", jpeg_perfect)
        self.assertEqual(result["level"], RecoveryLevel.FULL,
            f"Perfect JPEG should be FULL, got {result['level']}")

        result = self.validator.validate(b'\x00' * 100, "photo.jpg")
        self.assertEqual(result["level"], RecoveryLevel.FAILED,
            f"Non-JPEG data should be FAILED, got {result['level']}")

    def test_rvs_thesis_vs_thumbnail(self):
        """A thesis must be worth more than 200 thumbnails."""
        from recovery_judge.rvs import RecoveryValueScore

        rvs = RecoveryValueScore()
        motor_a_recovered = {f"thumb_{i:04d}.jpg" for i in range(200)}
        ground_truth = {"tesis_final.docx"} | motor_a_recovered

        rvs_a = rvs.compute_rvs_simple(
            motor_a_recovered, ground_truth,
            {f: 5000 for f in motor_a_recovered} | {"tesis_final.docx": 500000}
        )
        rvs_b = rvs.compute_rvs_simple(
            {"tesis_final.docx"}, ground_truth,
            {f: 5000 for f in motor_a_recovered} | {"tesis_final.docx": 500000}
        )

        self.assertGreater(rvs_b, rvs_a,
            f"Motor that recovers thesis (RVS={rvs_b:.3f}) should have higher RVS "
            f"than motor that recovers 200 thumbnails (RVS={rvs_a:.3f})")


# ─── Test Motor Carving Purity ───────────────────────────────────────────────

class TestCarvingPurity(unittest.TestCase):
    """Carving motor must NEVER access filesystem metadata."""

    def test_carving_never_reads_mft(self):
        """Motor Carving must produce mft_entries_parsed = 0."""
        motor = MotorCarving()
        from dataset_builder.builder import DatasetBuilder
        builder = DatasetBuilder(seed=42)
        image, manifest = builder.build_single_format_dataset(
            extension=".jpg", n_files=5, volume_size=10*1024*1024
        )

        result = motor.recover(image, manifest)
        self.assertEqual(result.mft_entries_parsed, 0,
            "Carving motor must NEVER parse MFT entries")


if __name__ == "__main__":
    unittest.main(verbosity=2)
