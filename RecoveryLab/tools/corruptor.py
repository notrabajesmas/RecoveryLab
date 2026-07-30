#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RecoveryLab — Corruptor (Semana 1B)

Takes a healthy NTFS image and applies perfectly known corruption.
Every corruption is recorded in a corruption log.

Philosophy: We don't want a "broken" disk.
We want a disk whose corruption is completely known.

Corruption patterns (C01-C14):
  C01: MFT 20% deleted
  C02: MFT 40% deleted
  C03: MFT 60% deleted
  C04: MFT fragmented
  C05: MFT partially unreadable
  C06: Journal corrupt
  C07: Directory entries destroyed
  C08: Data sectors damaged
  C09: Combined: MFT + journal
  C10: Combined: everything
  C11: SMR behavior (simulated)
  C12: SSD wear leveling (simulated)
  C13: Encrypted (simulated)
  C14: Virtualization (simulated)
"""

import os, sys, json, hashlib, struct, random, copy
from pathlib import Path

CLUSTER_SIZE = 4096
BYTES_PER_SECTOR = 512
MFT_RECORD_SIZE = 1024
FIRST_USER_MFT_INDEX = 32


class NTFSImageCorruptor:
    """Applies controlled corruption to an NTFS image."""

    def __init__(self, image_path, manifest_path, seed=0):
        self.image_path = image_path
        self.manifest_path = manifest_path
        self.seed = seed
        self.rng = random.Random(seed)

        # Load image
        with open(image_path, 'rb') as f:
            self.image = bytearray(f.read())

        # Load manifest
        with open(manifest_path, 'r') as f:
            self.manifest = json.load(f)

        # Corruption log
        self.corruption_log = []

    def _get_mft_offset(self, mft_index):
        """Get byte offset of an MFT entry."""
        mft_start = self.manifest['mft_start_cluster'] * self.manifest['cluster_size']
        return mft_start + mft_index * MFT_RECORD_SIZE

    def _zero_mft_entry(self, mft_index):
        """Zero out an MFT entry (simulate deletion)."""
        offset = self._get_mft_offset(mft_index)
        self.image[offset:offset + MFT_RECORD_SIZE] = b'\x00' * MFT_RECORD_SIZE
        return offset

    def _corrupt_mft_entry(self, mft_index, mode='random'):
        """Corrupt an MFT entry (simulate partial damage)."""
        offset = self._get_mft_offset(mft_index)
        if mode == 'random':
            # Overwrite random bytes within the entry
            for _ in range(self.rng.randint(10, 100)):
                pos = offset + self.rng.randint(0, MFT_RECORD_SIZE - 1)
                self.image[pos] = self.rng.randint(0, 255)
        elif mode == 'header':
            # Corrupt the entry header (signature, offsets)
            for i in range(4, 48):
                self.image[offset + i] = self.rng.randint(0, 255)
        elif mode == 'data_runs':
            # Corrupt data run entries (offset 56+)
            for i in range(56, MFT_RECORD_SIZE):
                self.image[offset + i] = self.rng.randint(0, 255)
        return offset

    def _corrupt_sectors(self, start_sector, count):
        """Make sectors unreadable (fill with 0xFF pattern)."""
        for i in range(count):
            offset = (start_sector + i) * BYTES_PER_SECTOR
            if offset + BYTES_PER_SECTOR <= len(self.image):
                # Write a distinctive pattern (not just zeros)
                self.image[offset:offset + BYTES_PER_SECTOR] = b'\xFF' * BYTES_PER_SECTOR

    def _get_user_file_indices(self):
        """Get all user file MFT indices."""
        return [f['mft_index'] for f in self.manifest['files']]

    # ─── Corruption Patterns ──────────────────────────────────────────────

    def apply_c01_mft_20pct(self):
        """C01: Delete 20% of MFT entries."""
        indices = self._get_user_file_indices()
        count = max(1, len(indices) // 5)
        targets = self.rng.sample(indices, count)
        for idx in targets:
            self._zero_mft_entry(idx)
        self.corruption_log.append({
            'pattern': 'C01',
            'description': 'MFT 20% deleted',
            'mft_entries_deleted': sorted(targets),
            'count': count,
        })
        return self

    def apply_c02_mft_40pct(self):
        """C02: Delete 40% of MFT entries."""
        indices = self._get_user_file_indices()
        count = max(1, len(indices) * 2 // 5)
        targets = self.rng.sample(indices, count)
        for idx in targets:
            self._zero_mft_entry(idx)
        self.corruption_log.append({
            'pattern': 'C02',
            'description': 'MFT 40% deleted',
            'mft_entries_deleted': sorted(targets),
            'count': count,
        })
        return self

    def apply_c03_mft_60pct(self):
        """C03: Delete 60% of MFT entries."""
        indices = self._get_user_file_indices()
        count = max(1, len(indices) * 3 // 5)
        targets = self.rng.sample(indices, count)
        for idx in targets:
            self._zero_mft_entry(idx)
        self.corruption_log.append({
            'pattern': 'C03',
            'description': 'MFT 60% deleted',
            'mft_entries_deleted': sorted(targets),
            'count': count,
        })
        return self

    def apply_c05_mft_unreadable(self):
        """C05: Make parts of MFT area unreadable."""
        mft_start = self.manifest['mft_start_cluster']
        mft_clusters = self.manifest['mft_clusters']
        # Corrupt 30% of MFT clusters
        target_clusters = self.rng.sample(
            range(mft_start, mft_start + mft_clusters),
            max(1, mft_clusters * 3 // 10)
        )
        for cluster in target_clusters:
            offset = cluster * self.manifest['cluster_size']
            self.image[offset:offset + self.manifest['cluster_size']] = b'\xFF' * self.manifest['cluster_size']
        self.corruption_log.append({
            'pattern': 'C05',
            'description': 'MFT partially unreadable',
            'clusters_corrupted': sorted(target_clusters),
            'count': len(target_clusters),
        })
        return self

    def apply_c06_journal_corrupt(self):
        """C06: Corrupt the journal ($LogFile)."""
        log_cluster = self.manifest['logfile_cluster']
        offset = log_cluster * self.manifest['cluster_size']
        # Overwrite journal with random data
        for i in range(4 * self.manifest['cluster_size']):
            self.image[offset + i] = self.rng.randint(0, 255)
        self.corruption_log.append({
            'pattern': 'C06',
            'description': 'Journal corrupt',
            'clusters_corrupted': list(range(log_cluster, log_cluster + 4)),
        })
        return self

    def apply_c08_data_sectors_damaged(self):
        """C08: Damage random data sectors."""
        files = [f for f in self.manifest['files'] if not f['resident'] and f['clusters']]
        if not files:
            return self
        # Damage 20% of data files
        targets = self.rng.sample(files, max(1, len(files) // 5))
        damaged_clusters = []
        for f in targets:
            # Damage 1-2 clusters from each file
            num_damaged = min(len(f['clusters']), self.rng.randint(1, 2))
            for c in self.rng.sample(f['clusters'], num_damaged):
                offset = c * self.manifest['cluster_size']
                self.image[offset:offset + self.manifest['cluster_size']] = b'\xDE\xAD' * (self.manifest['cluster_size'] // 2)
                damaged_clusters.append(c)
        self.corruption_log.append({
            'pattern': 'C08',
            'description': 'Data sectors damaged',
            'clusters_damaged': sorted(damaged_clusters),
            'files_affected': [f['name'] for f in targets],
        })
        return self

    def apply_c09_combined_mft_journal(self):
        """C09: Combined: MFT damage + journal corruption."""
        self.apply_c05_mft_unreadable()
        self.apply_c06_journal_corrupt()
        self.corruption_log.append({
            'pattern': 'C09',
            'description': 'Combined: MFT + journal',
        })
        return self

    def apply_c10_combined_all(self):
        """C10: Combined: everything."""
        self.apply_c02_mft_40pct()
        self.apply_c06_journal_corrupt()
        self.apply_c08_data_sectors_damaged()
        self.corruption_log.append({
            'pattern': 'C10',
            'description': 'Combined: everything',
        })
        return self

    def apply_custom(self, pattern, description, corruption_fn):
        """Apply a custom corruption pattern."""
        corruption_fn(self)
        self.corruption_log.append({
            'pattern': pattern,
            'description': description,
        })
        return self

    # ─── Save ─────────────────────────────────────────────────────────────

    def save(self, output_dir, dataset_id, corruption_suffix):
        """Save corrupted image and corruption log."""
        os.makedirs(output_dir, exist_ok=True)

        img_path = os.path.join(output_dir, f'{dataset_id}_{corruption_suffix}.img')
        log_path = os.path.join(output_dir, f'{dataset_id}_{corruption_suffix}_corruption.json')

        with open(img_path, 'wb') as f:
            f.write(self.image)

        corruption_record = {
            'version': '1.0',
            'source_dataset': dataset_id,
            'corruption_suffix': corruption_suffix,
            'seed': self.seed,
            'timestamp': __import__('time').strftime('%Y-%m-%dT%H:%M:%S'),
            'source_manifest': self.manifest_path,
            'corruption_log': self.corruption_log,
            'image_sha256': hashlib.sha256(self.image).hexdigest(),
        }

        with open(log_path, 'w') as f:
            json.dump(corruption_record, f, indent=2)

        return img_path, log_path


# ─── Batch Corruptor ─────────────────────────────────────────────────────────

PATTERNS = {
    'c01': ('C01', 'apply_c01_mft_20pct'),
    'c02': ('C02', 'apply_c02_mft_40pct'),
    'c03': ('C03', 'apply_c03_mft_60pct'),
    'c05': ('C05', 'apply_c05_mft_unreadable'),
    'c06': ('C06', 'apply_c06_journal_corrupt'),
    'c08': ('C08', 'apply_c08_data_sectors_damaged'),
    'c09': ('C09', 'apply_c09_combined_mft_journal'),
    'c10': ('C10', 'apply_c10_combined_all'),
}


def corrupt_dataset(lab_dir, dataset_id, patterns=None, base_seed=1000):
    """Apply corruption patterns to a healthy image."""
    healthy_dir = os.path.join(lab_dir, 'datasets', 'ntfs', 'healthy')
    damaged_dir = os.path.join(lab_dir, 'datasets', 'ntfs', 'damaged')
    os.makedirs(damaged_dir, exist_ok=True)

    img_path = os.path.join(healthy_dir, f'{dataset_id}.img')
    manifest_path = os.path.join(healthy_dir, f'{dataset_id}_manifest.json')

    if not os.path.exists(img_path):
        print(f'  ⚠ Image not found: {img_path}')
        return []

    if patterns is None:
        patterns = list(PATTERNS.keys())

    results = []
    for i, pattern_key in enumerate(patterns):
        if pattern_key not in PATTERNS:
            print(f'  ⚠ Unknown pattern: {pattern_key}')
            continue

        pattern_code, method_name = PATTERNS[pattern_key]
        seed = base_seed + i
        print(f'  Applying {pattern_code} to {dataset_id} (seed={seed})...')

        corruptor = NTFSImageCorruptor(img_path, manifest_path, seed=seed)
        method = getattr(corruptor, method_name)
        method()

        img_out, log_out = corruptor.save(damaged_dir, dataset_id, pattern_key)

        results.append({
            'pattern': pattern_code,
            'dataset': dataset_id,
            'seed': seed,
            'image': img_out,
            'log': log_out,
            'corruptions': len(corruptor.corruption_log),
        })
        print(f'  ✓ {pattern_code}: {len(corruptor.corruption_log)} corruptions applied')

    return results


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='RecoveryLab — Corruptor')
    parser.add_argument('--lab-dir', default='/home/z/my-project/RecoveryLab',
                        help='RecoveryLab directory')
    parser.add_argument('--dataset-id', default='dataset_000042',
                        help='Dataset ID to corrupt')
    parser.add_argument('--patterns', nargs='+', default=None,
                        help='Corruption patterns to apply (c01-c10)')
    parser.add_argument('--all', action='store_true',
                        help='Apply all patterns')

    args = parser.parse_args()

    if args.all:
        patterns = list(PATTERNS.keys())
    elif args.patterns:
        patterns = args.patterns
    else:
        patterns = ['c01', 'c02', 'c05', 'c06', 'c08']

    print(f'RecoveryLab — Corruptor')
    print(f'  Dataset: {args.dataset_id}')
    print(f'  Patterns: {patterns}')
    print()

    results = corrupt_dataset(args.lab_dir, args.dataset_id, patterns)

    print(f'\nCorruption complete: {len(results)} corrupted images generated')
