"""
RecoveryLab — Base Motor
=========================
Abstract base class for all recovery motors.

Every motor must implement:
  - recover(): The main recovery algorithm
  - name: Human-readable name
  - description: What strategy this motor uses

The motor receives:
  - A corrupted NTFS image
  - A read budget (0 = unlimited)
  - Optional metadata (slow sectors, timeouts, etc.)

The motor returns:
  - A MotorResult with recovered files and metrics
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from pathlib import Path


@dataclass
class RecoveredFile:
    """A file recovered by a motor."""
    name: str
    sha256: str
    size: int
    data: bytes = b""
    is_directory: bool = False
    source: str = ""  # How it was found: "mft", "journal", "indx", "bitmap", "carving"
    confidence: float = 1.0  # 0.0-1.0 confidence in the recovery
    read_count: int = 0  # Reads used to recover this file


@dataclass
class MotorResult:
    """Complete result from a recovery motor."""
    motor_name: str
    recovered_files: List[RecoveredFile] = field(default_factory=list)
    read_count: int = 0
    sectors_wasted: int = 0
    time_to_first_file: int = 0
    mft_entries_parsed: int = 0
    directories_rebuilt: int = 0
    total_time_seconds: float = 0.0
    false_positive_files: List[str] = field(default_factory=list)
    duplicate_files: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


class BaseMotor(ABC):
    """Abstract base class for recovery motors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable motor name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of the recovery strategy."""
        pass

    @abstractmethod
    def recover(self, image: bytes, manifest: Dict,
                read_budget: int = 0,
                corruption_metadata: Optional[Dict] = None) -> MotorResult:
        """
        Run the recovery algorithm on a corrupted image.

        Args:
            image: Raw NTFS image bytes (possibly corrupted)
            manifest: Ground truth manifest (for the motor to know the structure)
            read_budget: Maximum sector reads allowed (0 = unlimited)
            corruption_metadata: Optional metadata about slow sectors, timeouts, etc.

        Returns:
            MotorResult with recovered files and metrics
        """
        pass

    def _read_sector(self, image: bytes, sector: int,
                     read_count: int, read_budget: int,
                     corruption_metadata: Optional[Dict] = None) -> Optional[bytes]:
        """
        Read a sector from the image with budget enforcement.

        Returns None if:
          - Budget exceeded
          - Sector is out of range
          - Sector times out (simulated)
        """
        # Check budget
        if read_budget > 0 and read_count >= read_budget:
            return None

        # Check bounds
        offset = sector * 512
        if offset + 512 > len(image):
            return None

        # Check timeout metadata
        if corruption_metadata:
            timeout_sectors = corruption_metadata.get("timeout_sector_list", [])
            if sector in timeout_sectors:
                # Simulate timeout — skip this sector
                return None

        # Read the sector
        return image[offset:offset + 512]

    def _read_cluster(self, image: bytes, cluster: int,
                      cluster_size: int,
                      read_count: int, read_budget: int,
                      corruption_metadata: Optional[Dict] = None) -> Optional[bytes]:
        """Read a complete cluster from the image."""
        sectors_per_cluster = cluster_size // 512
        start_sector = cluster * sectors_per_cluster
        data = bytearray()

        for s in range(start_sector, start_sector + sectors_per_cluster):
            sector_data = self._read_sector(image, s, read_count, read_budget,
                                           corruption_metadata)
            if sector_data is None:
                return None  # Budget or timeout
            data.extend(sector_data)
            read_count += 1

        return bytes(data)

    def _parse_mft_record(self, image: bytes, offset: int) -> Optional[Dict]:
        """
        Parse a single MFT record at the given byte offset.

        Returns a dict with:
          - signature: "FILE" or None
          - in_use: bool
          - is_directory: bool
          - attributes: list of parsed attributes
          - file_name: str (if $FILE_NAME attribute found)
          - data_runs: list of DataRun (if non-resident $DATA found)
          - resident_data: bytes (if resident $DATA found)
        """
        if offset + 1024 > len(image):
            return None

        record = image[offset:offset + 1024]

        # Check signature
        sig = record[0:4]
        if sig != b'FILE':
            return None

        # Parse header
        import struct
        flags = struct.unpack_from('<H', record, 22)[0]
        in_use = bool(flags & 0x0001)
        is_directory = bool(flags & 0x0002)
        first_attr_offset = struct.unpack_from('<H', record, 20)[0]

        # Parse attributes
        attrs = []
        attr_offset = first_attr_offset
        file_names = []
        data_runs = []
        resident_data = b""
        data_real_size = 0

        while attr_offset + 4 < 1024:
            attr_type = struct.unpack_from('<I', record, attr_offset)[0]

            if attr_type == 0xFFFFFFFF:
                break

            attr_length = struct.unpack_from('<I', record, attr_offset + 4)[0]
            if attr_length == 0:
                break

            non_resident = record[attr_offset + 8]

            if attr_type == 0x30:  # $FILE_NAME
                # Extract filename
                name_offset = struct.unpack_from('<H', record, attr_offset + 20)[0]
                name_length = record[attr_offset + 88]  # Name length in chars
                name_start = attr_offset + 90
                name_bytes = record[name_start:name_start + name_length * 2]
                try:
                    file_name = name_bytes.decode('utf-16-le')
                except:
                    file_name = ""
                file_names.append(file_name)

            elif attr_type == 0x80:  # $DATA
                if non_resident:
                    # Non-resident: parse data runs
                    run_offset = struct.unpack_from('<H', record, attr_offset + 32)[0]
                    data_size = struct.unpack_from('<Q', record, attr_offset + 48)[0]
                    runs = self._parse_run_list(record, attr_offset + run_offset)
                    data_runs.extend(runs)
                    # Store the actual file size for trimming
                    data_real_size = data_size
                else:
                    # Resident: data is in the attribute
                    data_len = struct.unpack_from('<I', record, attr_offset + 16)[0]
                    data_off = struct.unpack_from('<H', record, attr_offset + 20)[0]
                    resident_data = record[attr_offset + data_off:attr_offset + data_off + data_len]
                    data_real_size = data_len

            attr_offset += attr_length

        return {
            "signature": "FILE",
            "in_use": in_use,
            "is_directory": is_directory,
            "file_names": file_names,
            "data_runs": data_runs,
            "resident_data": resident_data,
            "data_size": data_real_size,
            "offset": offset,
        }

    def _parse_run_list(self, record: bytes, offset: int) -> List[Dict]:
        """
        Parse NTFS data run list at the given offset.

        Returns list of dicts with 'length' and 'offset' (absolute cluster numbers).
        """
        import struct
        runs = []
        current_offset = 0

        while offset < len(record) - 1:
            header = record[offset]
            if header == 0:
                break

            length_size = header & 0x0F
            offset_size = (header >> 4) & 0x0F

            if length_size == 0 or offset_size == 0:
                break

            offset += 1

            # Read length
            length = int.from_bytes(
                record[offset:offset + length_size], 'little')
            offset += length_size

            # Read offset (signed)
            rel_offset = int.from_bytes(
                record[offset:offset + offset_size], 'little', signed=True)
            offset += offset_size

            current_offset += rel_offset

            runs.append({
                "length": length,
                "offset": current_offset,
            })

        return runs
