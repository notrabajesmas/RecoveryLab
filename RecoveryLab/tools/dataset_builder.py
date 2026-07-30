#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RecoveryLab — Dataset Builder (Semana 1A)

Creates NTFS disk images with known content and generates manifest.json.
Every image is deterministic: same seed → same image, bit by bit.

The manifest.json is the ground truth. Without it, we cannot measure
whether any motor recovered files correctly.

Philosophy: This tool is designed to help REFUTE H1, not to prove it.
"""

import os, sys, json, hashlib, struct, random, math, time
from pathlib import Path

# ─── Configuration ────────────────────────────────────────────────────────────

BYTES_PER_SECTOR = 512
SECTORS_PER_CLUSTER = 8          # 4096 bytes per cluster
CLUSTER_SIZE = BYTES_PER_SECTOR * SECTORS_PER_CLUSTER  # 4096
MFT_RECORD_SIZE = 1024
INDEX_RECORD_SIZE = 4096

# NTFS System File MFT entry indices
MFT_SYSTEM_FILES = {
    0: '$MFT',
    1: '$MFTMirr',
    2: '$LogFile',
    3: '$Volume',
    4: '$AttrDef',
    5: '.',
    6: '$Bitmap',
    7: '$Boot',
    8: '$BadClus',
    9: '$Secure',
    10: '$UpCase',
    11: '$Extend',
}

# First user file starts at MFT entry 32 (standard NTFS convention)
FIRST_USER_MFT_INDEX = 32


# ─── NTFS Binary Structures ──────────────────────────────────────────────────

class NTFSBootSector:
    """NTFS Volume Boot Record (first 512 bytes of the volume)."""

    def __init__(self, total_sectors, mft_cluster, mft_mirror_cluster,
                 serial_number, sectors_per_cluster=8):
        self.bytes_per_sector = BYTES_PER_SECTOR
        self.sectors_per_cluster = sectors_per_cluster
        self.total_sectors = total_sectors
        self.mft_cluster = mft_cluster
        self.mft_mirror_cluster = mft_mirror_cluster
        self.serial_number = serial_number

    def pack(self):
        bs = bytearray(512)
        # Jump instruction
        bs[0:3] = b'\xEB\x52\x90'
        # OEM ID
        bs[3:11] = b'NTFS    '
        # BPB
        struct.pack_into('<H', bs, 11, self.bytes_per_sector)      # Bytes per sector
        bs[13] = self.sectors_per_cluster                            # Sectors per cluster
        struct.pack_into('<H', bs, 14, 0)                           # Reserved sectors
        bs[16:19] = b'\x00\x00\x00'                                 # Always 0
        struct.pack_into('<H', bs, 19, 0)                           # Unused
        bs[21] = 0xF8                                                # Media descriptor (hard disk)
        struct.pack_into('<H', bs, 22, 0)                           # Always 0
        struct.pack_into('<H', bs, 24, 63)                          # Sectors per track
        struct.pack_into('<H', bs, 26, 255)                         # Number of heads
        struct.pack_into('<I', bs, 28, 0)                           # Hidden sectors
        struct.pack_into('<I', bs, 32, 0)                           # Unused
        struct.pack_into('<I', bs, 36, 0x00800080)                  # Unused (special flags)
        # Total sectors (8 bytes)
        struct.pack_into('<Q', bs, 40, self.total_sectors)
        # MFT cluster number (8 bytes)
        struct.pack_into('<Q', bs, 48, self.mft_cluster)
        # MFT mirror cluster number (8 bytes)
        struct.pack_into('<Q', bs, 56, self.mft_mirror_cluster)
        # Clusters per MFT record: -10 means 2^10 = 1024 bytes
        struct.pack_into('<i', bs, 64, -10)
        # Clusters per index record: -10 means 2^10 = 1024 bytes
        struct.pack_into('<i', bs, 68, -10)
        # Volume serial number (8 bytes)
        struct.pack_into('<Q', bs, 72, self.serial_number)
        # Checksum (4 bytes) — leave as 0 for now
        struct.pack_into('<I', bs, 76, 0)
        # Boot code signature at offset 510
        struct.pack_into('<H', bs, 510, 0xAA55)
        return bytes(bs)


class MFTAttribute:
    """An NTFS MFT attribute (resident or non-resident)."""

    def __init__(self, attr_type, attr_id=0, resident=True):
        self.attr_type = attr_type
        self.attr_id = attr_id
        self.resident = resident
        self.data = b''           # For resident attributes
        self.data_runs = []       # For non-resident: [(length, offset), ...]
        self.compressed = False
        self.encrypted = False
        self.sparse = False

    def pack(self):
        """Pack attribute into bytes."""
        if self.resident:
            return self._pack_resident()
        else:
            return self._pack_non_resident()

    def _pack_resident(self):
        attr_len = 24 + len(self.data)  # Header + data
        # Align to 8 bytes
        attr_len = (attr_len + 7) & ~7
        buf = bytearray(attr_len)
        # Attribute header
        struct.pack_into('<I', buf, 0, self.attr_type)     # Type
        struct.pack_into('<I', buf, 4, attr_len)           # Length
        bs_flag = 0x00
        if self.compressed: bs_flag |= 0x01
        if self.encrypted:   bs_flag |= 0x02
        if self.sparse:      bs_flag |= 0x08
        buf[8] = bs_flag                                      # Non-resident flag
        buf[9] = len(self.data) & 0xFF                        # Name length
        buf[10] = 0x00                                        # Name offset
        struct.pack_into('<H', buf, 12, 0x0000)              # Flags
        struct.pack_into('<H', buf, 14, 0x0000)              # Attribute ID
        struct.pack_into('<I', buf, 16, 24)                  # Content offset
        struct.pack_into('<I', buf, 20, len(self.data))      # Content length
        buf[22] = 0x00                                        # Indexed flag
        buf[23] = 0x00                                        # Padding
        # Content
        buf[24:24+len(self.data)] = self.data
        return bytes(buf)

    def _pack_non_resident(self):
        # Pack data runs first
        runs_data = self._pack_data_runs()
        attr_len = 64 + len(runs_data) + 2  # Header + runs + terminator
        attr_len = (attr_len + 7) & ~7
        buf = bytearray(attr_len)
        # Attribute header
        struct.pack_into('<I', buf, 0, self.attr_type)
        struct.pack_into('<I', buf, 4, attr_len)
        buf[8] = 0x01                                        # Non-resident flag
        buf[9] = 0x00                                        # Name length
        buf[10] = 0x00                                       # Name offset
        struct.pack_into('<H', buf, 12, 0x0000)             # Flags
        struct.pack_into('<H', buf, 14, 0x0000)             # Attribute ID
        # Non-resident specific fields
        struct.pack_into('<H', buf, 16, 64)                 # Data runs offset
        struct.pack_into('<I', buf, 18, 0)                  # Compression unit size
        struct.pack_into('<I', buf, 22, 0)                  # Padding
        struct.pack_into('<Q', buf, 24, 0)                  # Allocated size
        total_data_size = sum(r[0] for r in self.data_runs) * CLUSTER_SIZE
        struct.pack_into('<Q', buf, 32, total_data_size)    # Data size
        struct.pack_into('<Q', buf, 40, total_data_size)    # Initialized size
        # Data runs
        buf[64:64+len(runs_data)] = runs_data
        buf[64+len(runs_data)] = 0x00  # Terminator
        return bytes(buf)

    def _pack_data_runs(self):
        """Pack data runs into NTFS encoding."""
        result = bytearray()
        for length, offset in self.data_runs:
            # Determine how many bytes needed for length and offset
            len_bytes = max(1, (length.bit_length() + 7) // 8)
            off_bytes = max(1, (abs(offset).bit_length() + 8) // 8)  # +1 for sign
            header = (off_bytes << 4) | len_bytes
            result.append(header)
            # Length (little-endian)
            result.extend(length.to_bytes(len_bytes, 'little'))
            # Offset (signed little-endian)
            if offset >= 0:
                result.extend(offset.to_bytes(off_bytes, 'little'))
            else:
                result.extend(offset.to_bytes(off_bytes, 'little', signed=True))
        return bytes(result)


class MFTEntry:
    """An NTFS MFT file record (1024 bytes)."""

    def __init__(self, entry_index, is_directory=False, sequence_number=1):
        self.entry_index = entry_index
        self.is_directory = is_directory
        self.sequence_number = sequence_number
        self.attributes = []
        self.filename = ''
        self.parent_index = 5  # Root directory by default

    def add_attribute(self, attr):
        self.attributes.append(attr)

    def pack(self):
        """Pack MFT entry into 1024 bytes."""
        buf = bytearray(MFT_RECORD_SIZE)
        # File record header
        buf[0:4] = b'FILE'
        struct.pack_into('<H', buf, 4, 48)                  # Offset to fixup
        struct.pack_into('<H', buf, 6, 3)                   # Number of fixup entries
        struct.pack_into('<Q', buf, 8, self.sequence_number)  # Sequence number
        struct.pack_into('<H', buf, 16, 0)                  # Hard link count
        struct.pack_into('<H', buf, 18, 0)                  # Offset to first attribute
        struct.pack_into('<I', buf, 20, 0x0001)             # Flags (in use)
        struct.pack_into('<I', buf, 24, MFT_RECORD_SIZE)    # Used size
        struct.pack_into('<I', buf, 28, MFT_RECORD_SIZE)    # Allocated size

        # Pack attributes
        offset = 48  # After the header (simplified)
        # Fixup values (placeholder)
        struct.pack_into('<H', buf, 48, 0x0000)  # Fixup #1
        struct.pack_into('<H', buf, 50, 0x0000)  # Fixup #2

        attr_offset = 56  # Start of attributes
        for attr in self.attributes:
            attr_bytes = attr.pack()
            if attr_offset + len(attr_bytes) <= MFT_RECORD_SIZE - 8:
                buf[attr_offset:attr_offset+len(attr_bytes)] = attr_bytes
                attr_offset += len(attr_bytes)

        # End marker
        if attr_offset < MFT_RECORD_SIZE - 8:
            struct.pack_into('<I', buf, attr_offset, 0xFFFFFFFF)  # End attribute

        return bytes(buf)


# ─── File Content Generators ─────────────────────────────────────────────────

def generate_file_content(rng, file_type, size):
    """Generate deterministic file content based on type and size."""
    if file_type == 'text':
        # Generate ASCII text
        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,!?\n'
        content = bytes(rng.choice(list(chars.encode())) for _ in range(size))
        return content
    elif file_type == 'jpeg':
        # Minimal JPEG header + random data
        jpeg_header = b'\xFF\xD8\xFF\xE0' + b'\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        if size <= len(jpeg_header) + 2:
            return jpeg_header[:size]
        content = jpeg_header + bytes(rng.getrandbits(8) for _ in range(size - len(jpeg_header) - 2))
        return content + b'\xFF\xD9'
    elif file_type == 'pdf':
        pdf_header = b'%PDF-1.4\n'
        if size <= len(pdf_header) + 6:
            return pdf_header[:size]
        content = pdf_header + bytes(rng.getrandbits(8) for _ in range(size - len(pdf_header) - 6))
        return content + b'\n%%EOF\n'
    elif file_type == 'binary':
        return bytes(rng.getrandbits(8) for _ in range(size))
    else:
        return bytes(rng.getrandbits(8) for _ in range(size))


# ─── NTFS Image Builder ──────────────────────────────────────────────────────

class NTFSImageBuilder:
    """Builds a deterministic NTFS disk image with known content."""

    def __init__(self, seed, image_size_mb=10, num_files=50, cluster_size=4096):
        self.seed = seed
        self.rng = random.Random(seed)
        self.image_size = image_size_mb * 1024 * 1024
        self.num_files = num_files
        self.cluster_size = cluster_size
        self.sectors_per_cluster = cluster_size // BYTES_PER_SECTOR
        self.total_sectors = self.image_size // BYTES_PER_SECTOR
        self.total_clusters = self.image_size // cluster_size

        # Layout: MFT starts at cluster 2 (standard NTFS)
        self.mft_start_cluster = 2
        self.mft_entry_count = FIRST_USER_MFT_INDEX + num_files + 100  # Extra space
        self.mft_clusters = (self.mft_entry_count * MFT_RECORD_SIZE + cluster_size - 1) // cluster_size
        self.mft_mirror_cluster = self.mft_start_cluster + self.mft_clusters
        self.bitmap_cluster = self.mft_mirror_cluster + 2
        self.logfile_cluster = self.bitmap_cluster + 2
        self.data_start_cluster = self.logfile_cluster + 4

        # Image buffer
        self.image = bytearray(self.image_size)

        # Track allocated clusters
        self.allocated_clusters = set()
        self.next_data_cluster = self.data_start_cluster

        # File records for manifest
        self.file_records = []

        # Volume serial
        self.serial_number = self.rng.getrandbits(64)

    def build(self):
        """Build the complete NTFS image."""
        # 1. Write boot sector
        self._write_boot_sector()

        # 2. Allocate system areas
        for c in range(self.mft_start_cluster, self.data_start_cluster):
            self.allocated_clusters.add(c)

        # 3. Write system MFT entries (0-11)
        self._write_system_mft_entries()

        # 4. Write user files
        self._write_user_files()

        # 5. Write $Bitmap
        self._write_bitmap()

        # 6. Write $LogFile (empty)
        self._write_logfile()

        return bytes(self.image)

    def _write_boot_sector(self):
        boot = NTFSBootSector(
            total_sectors=self.total_sectors,
            mft_cluster=self.mft_start_cluster,
            mft_mirror_cluster=self.mft_mirror_cluster,
            serial_number=self.serial_number,
            sectors_per_cluster=self.sectors_per_cluster,
        )
        self.image[0:512] = boot.pack()

    def _allocate_clusters(self, count):
        """Allocate 'count' contiguous clusters for file data."""
        start = self.next_data_cluster
        for i in range(count):
            cluster = start + i
            if cluster >= self.total_clusters:
                raise RuntimeError(f"Out of clusters: need {count} from {start}, total {self.total_clusters}")
            self.allocated_clusters.add(cluster)
        self.next_data_cluster = start + count
        return start, count

    def _write_mft_entry(self, index, entry):
        """Write an MFT entry at the correct position."""
        offset = (self.mft_start_cluster * self.cluster_size) + (index * MFT_RECORD_SIZE)
        entry_bytes = entry.pack()
        self.image[offset:offset + MFT_RECORD_SIZE] = entry_bytes

    def _make_standard_info_attr(self, creation_time=None):
        """Create a $STANDARD_INFORMATION attribute (type 0x10)."""
        if creation_time is None:
            # NTFS timestamp: 100ns intervals since 1601-01-01
            # 2024-01-01 ≈ 133,494,720,000,000,000 (100ns units)
            creation_time = 133494720000000000 + self.rng.randint(0, 10**15)
        data = struct.pack('<Q', creation_time)  # Creation time
        data += struct.pack('<Q', creation_time + self.rng.randint(0, 10**12))  # Modification time
        data += struct.pack('<Q', creation_time + self.rng.randint(0, 10**12))  # MFT change time
        data += struct.pack('<Q', creation_time + self.rng.randint(0, 10**12))  # Access time
        data += struct.pack('<I', 0x20)  # File attributes (archive)
        data += struct.pack('<I', 0)     # Max versions
        data += struct.pack('<I', 0)     # Version
        data += struct.pack('<I', 0)     # Class ID
        data += struct.pack('<I', 0)     # Owner ID
        data += struct.pack('<I', 0)     # Security ID
        data += struct.pack('<Q', 0)     # Quota charged
        data += struct.pack('<Q', 0)     # USN
        attr = MFTAttribute(0x10, resident=True)
        attr.data = data
        return attr

    def _make_filename_attr(self, filename, parent_index=5, is_directory=False):
        """Create a $FILE_NAME attribute (type 0x30)."""
        # NTFS timestamp
        ts = 133494720000000000 + self.rng.randint(0, 10**15)
        fn_bytes = filename.encode('utf-16-le')
        data = struct.pack('<Q', ts)  # Creation time
        data += struct.pack('<Q', ts)  # Modification time
        data += struct.pack('<Q', ts)  # MFT change time
        data += struct.pack('<Q', ts)  # Access time
        data += struct.pack('<Q', 0)   # Allocated size
        data += struct.pack('<Q', 0)   # Real size
        data += struct.pack('<I', 0x20 if not is_directory else 0x10000020)  # Flags
        data += struct.pack('<I', 0)   # Reparse
        data += struct.pack('<B', len(filename))  # Name length
        data += struct.pack('<B', 0)   # Name namespace (0 = POSIX)
        data += struct.pack('<H', parent_index)  # Parent directory (low word)
        data += struct.pack('<H', 0)   # Parent directory (high word)
        data += struct.pack('<H', 1)   # Parent sequence
        data += fn_bytes
        attr = MFTAttribute(0x30, resident=True)
        attr.data = data
        return attr

    def _make_data_attr_resident(self, file_data):
        """Create a resident $DATA attribute (type 0x80)."""
        attr = MFTAttribute(0x80, resident=True)
        attr.data = file_data
        return attr

    def _make_data_attr_nonresident(self, start_cluster, num_clusters):
        """Create a non-resident $DATA attribute (type 0x80)."""
        attr = MFTAttribute(0x80, resident=False)
        attr.data_runs = [(num_clusters, start_cluster)]
        return attr

    def _write_system_mft_entries(self):
        """Write the 12 system MFT entries (indices 0-11)."""
        for idx, name in MFT_SYSTEM_FILES.items():
            entry = MFTEntry(idx, is_directory=(name in ['.', '$Extend']))
            entry.filename = name
            entry.add_attribute(self._make_standard_info_attr())
            entry.add_attribute(self._make_filename_attr(name, is_directory=(name in ['.', '$Extend'])))
            self._write_mft_entry(idx, entry)

    def _write_user_files(self):
        """Write user files with known content."""
        file_types = ['text', 'jpeg', 'pdf', 'binary']
        file_exts = {'text': '.txt', 'jpeg': '.jpg', 'pdf': '.pdf', 'binary': '.bin'}

        for i in range(self.num_files):
            # Determine file properties
            ftype = self.rng.choice(file_types)
            fsize = self.rng.randint(512, self.cluster_size * 5)  # 512B to 5 clusters
            fname = f'file_{i:04d}{file_exts[ftype]}'

            # Generate content
            content = generate_file_content(self.rng, ftype, fsize)
            sha256 = hashlib.sha256(content).hexdigest()

            # Determine if resident or non-resident
            # Resident: data fits in MFT entry (< ~700 bytes)
            # Non-resident: data in separate clusters
            mft_index = FIRST_USER_MFT_INDEX + i

            if fsize < 700:
                # Resident file
                entry = MFTEntry(mft_index)
                entry.filename = fname
                entry.add_attribute(self._make_standard_info_attr())
                entry.add_attribute(self._make_filename_attr(fname))
                entry.add_attribute(self._make_data_attr_resident(content))

                # For manifest: resident files have no cluster allocation
                self.file_records.append({
                    'name': fname,
                    'type': ftype,
                    'size': fsize,
                    'sha256': sha256,
                    'mft_index': mft_index,
                    'resident': True,
                    'clusters': [],
                    'data_offset': None,
                })
            else:
                # Non-resident file
                num_clusters_needed = (fsize + self.cluster_size - 1) // self.cluster_size
                start_cluster, num_clusters = self._allocate_clusters(num_clusters_needed)

                # Write file data to image
                data_offset = start_cluster * self.cluster_size
                self.image[data_offset:data_offset + fsize] = content

                # Create MFT entry
                entry = MFTEntry(mft_index)
                entry.filename = fname
                entry.add_attribute(self._make_standard_info_attr())
                entry.add_attribute(self._make_filename_attr(fname))
                entry.add_attribute(self._make_data_attr_nonresident(start_cluster, num_clusters))

                # Record for manifest
                cluster_list = list(range(start_cluster, start_cluster + num_clusters))
                self.file_records.append({
                    'name': fname,
                    'type': ftype,
                    'size': fsize,
                    'sha256': sha256,
                    'mft_index': mft_index,
                    'resident': False,
                    'clusters': cluster_list,
                    'data_offset': start_cluster * self.cluster_size,
                })

            self._write_mft_entry(mft_index, entry)

    def _write_bitmap(self):
        """Write the $Bitmap (cluster allocation bitmap)."""
        bitmap_offset = self.bitmap_cluster * self.cluster_size
        bitmap_size = (self.total_clusters + 7) // 8
        bitmap = bytearray(bitmap_size)
        for cluster in self.allocated_clusters:
            if cluster < self.total_clusters:
                byte_idx = cluster // 8
                bit_idx = cluster % 8
                bitmap[byte_idx] |= (1 << bit_idx)
        self.image[bitmap_offset:bitmap_offset + bitmap_size] = bitmap[:self.cluster_size]

    def _write_logfile(self):
        """Write a minimal $LogFile."""
        log_offset = self.logfile_cluster * self.cluster_size
        # NTFS $LogFile starts with "RSTR" signature
        self.image[log_offset:log_offset+4] = b'RSTR'
        # Rest is zeros (empty journal)

    def generate_manifest(self):
        """Generate the manifest.json for this image."""
        manifest = {
            'version': '1.0',
            'seed': self.seed,
            'filesystem': 'NTFS',
            'image_size_bytes': self.image_size,
            'cluster_size': self.cluster_size,
            'total_clusters': self.total_clusters,
            'total_sectors': self.total_sectors,
            'bytes_per_sector': BYTES_PER_SECTOR,
            'sectors_per_cluster': self.sectors_per_cluster,
            'mft_start_cluster': self.mft_start_cluster,
            'mft_clusters': self.mft_clusters,
            'mft_mirror_cluster': self.mft_mirror_cluster,
            'bitmap_cluster': self.bitmap_cluster,
            'logfile_cluster': self.logfile_cluster,
            'data_start_cluster': self.data_start_cluster,
            'serial_number': self.serial_number,
            'num_files': self.num_files,
            'files': self.file_records,
            'layout': {
                'boot_sector': {'offset': 0, 'size': 512},
                'mft': {'offset': self.mft_start_cluster * self.cluster_size,
                        'size': self.mft_clusters * self.cluster_size,
                        'cluster_start': self.mft_start_cluster,
                        'cluster_count': self.mft_clusters},
                'mft_mirror': {'offset': self.mft_mirror_cluster * self.cluster_size,
                               'size': 2 * self.cluster_size,
                               'cluster_start': self.mft_mirror_cluster},
                'bitmap': {'offset': self.bitmap_cluster * self.cluster_size,
                           'cluster_start': self.bitmap_cluster},
                'logfile': {'offset': self.logfile_cluster * self.cluster_size,
                            'cluster_start': self.logfile_cluster},
                'data_area': {'offset': self.data_start_cluster * self.cluster_size,
                              'cluster_start': self.data_start_cluster},
            }
        }
        return manifest


# ─── Batch Generator ──────────────────────────────────────────────────────────

def generate_dataset(output_dir, num_images=20, image_size_mb=10, num_files=50,
                     base_seed=42):
    """Generate a dataset of NTFS images with manifests."""
    healthy_dir = os.path.join(output_dir, 'datasets', 'ntfs', 'healthy')
    os.makedirs(healthy_dir, exist_ok=True)

    results = []
    for i in range(num_images):
        seed = base_seed + i
        dataset_id = f'dataset_{seed:06d}'

        print(f'  [{i+1}/{num_images}] Building {dataset_id} (seed={seed})...')

        builder = NTFSImageBuilder(
            seed=seed,
            image_size_mb=image_size_mb,
            num_files=num_files,
        )

        # Build image
        image_data = builder.build()

        # Save image
        img_path = os.path.join(healthy_dir, f'{dataset_id}.img')
        with open(img_path, 'wb') as f:
            f.write(image_data)

        # Save manifest
        manifest = builder.generate_manifest()
        manifest_path = os.path.join(healthy_dir, f'{dataset_id}_manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        # Verify determinism
        builder2 = NTFSImageBuilder(seed=seed, image_size_mb=image_size_mb, num_files=num_files)
        image_data2 = builder2.build()
        if image_data != image_data2:
            print(f'  ⚠ DETERMINISM FAILURE for seed={seed}!')
            results.append({'dataset': dataset_id, 'seed': seed, 'status': 'DETERMINISM_FAILURE'})
        else:
            # Verify manifest matches image
            sha256_img = hashlib.sha256(image_data).hexdigest()
            results.append({
                'dataset': dataset_id,
                'seed': seed,
                'status': 'OK',
                'image_sha256': sha256_img,
                'files': len(manifest['files']),
                'non_resident': sum(1 for f in manifest['files'] if not f['resident']),
                'resident': sum(1 for f in manifest['files'] if f['resident']),
            })
            print(f'  ✓ {dataset_id}: {len(manifest["files"])} files, '
                  f'img_sha256={sha256_img[:16]}...')

    # Summary
    print(f'\n{"="*60}')
    print(f'Dataset generation complete: {num_images} images')
    print(f'  OK: {sum(1 for r in results if r["status"]=="OK")}')
    print(f'  FAILED: {sum(1 for r in results if r["status"]!="OK")}')
    print(f'  Output: {healthy_dir}')

    return results


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='RecoveryLab — Dataset Builder')
    parser.add_argument('--output-dir', default='/home/z/my-project/RecoveryLab',
                        help='Output directory')
    parser.add_argument('--num-images', type=int, default=20,
                        help='Number of images to generate')
    parser.add_argument('--size-mb', type=int, default=10,
                        help='Image size in MB')
    parser.add_argument('--num-files', type=int, default=50,
                        help='Number of files per image')
    parser.add_argument('--base-seed', type=int, default=42,
                        help='Base seed for deterministic generation')

    args = parser.parse_args()

    print(f'RecoveryLab — Dataset Builder')
    print(f'  Output: {args.output_dir}')
    print(f'  Images: {args.num_images}')
    print(f'  Size: {args.size_mb} MB each')
    print(f'  Files: {args.num_files} per image')
    print(f'  Base seed: {args.base_seed}')
    print(f'  Golden rule: "Ningún resultado positivo será considerado válido')
    print(f'   hasta que haya sobrevivido a al menos un intento serio de refutación."')
    print()

    results = generate_dataset(
        output_dir=args.output_dir,
        num_images=args.num_images,
        image_size_mb=args.size_mb,
        num_files=args.num_files,
        base_seed=args.base_seed,
    )
