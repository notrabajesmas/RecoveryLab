#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RecoveryLab — Visualizer

Shows disk layout as a cluster map. When a benchmark fails,
you want to see quickly what was actually on the disk.

Simple but invaluable for debugging.
"""

import os, sys, json, math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import ListedColormap

# ─── Color Map ────────────────────────────────────────────────────────────────

CLUSTER_COLORS = {
    'boot':       '#FF6B6B',   # Red - boot sector
    'mft':        '#4ECDC4',   # Teal - MFT
    'mft_mirror': '#45B7D1',   # Light blue - MFT mirror
    'bitmap':     '#96CEB4',   # Green - $Bitmap
    'journal':    '#FFEAA7',   # Yellow - $LogFile
    'data':       '#6C5CE7',   # Purple - file data
    'system':     '#DDA0DD',   # Plum - other system files
    'free':       '#F8F9FA',   # Light gray - free
    'corrupted':  '#E74C3C',   # Bright red - corrupted
    'unknown':    '#DFE6E9',   # Gray - unknown
}

# ─── Cluster Map Builder ─────────────────────────────────────────────────────

def build_cluster_map(manifest, corruption_log=None):
    """Build a cluster type map from manifest and corruption log."""
    total_clusters = manifest['total_clusters']
    cluster_types = ['free'] * total_clusters

    # Boot sector
    cluster_types[0] = 'boot'

    # MFT
    mft_start = manifest['mft_start_cluster']
    mft_end = mft_start + manifest['mft_clusters']
    for c in range(mft_start, min(mft_end, total_clusters)):
        cluster_types[c] = 'mft'

    # MFT mirror
    mirror_start = manifest['mft_mirror_cluster']
    for c in range(mirror_start, min(mirror_start + 2, total_clusters)):
        cluster_types[c] = 'mft_mirror'

    # Bitmap
    bitmap_start = manifest['bitmap_cluster']
    for c in range(bitmap_start, min(bitmap_start + 2, total_clusters)):
        cluster_types[c] = 'bitmap'

    # Journal
    log_start = manifest['logfile_cluster']
    for c in range(log_start, min(log_start + 4, total_clusters)):
        cluster_types[c] = 'journal'

    # File data
    for f in manifest['files']:
        for c in f['clusters']:
            if c < total_clusters:
                cluster_types[c] = 'data'

    # Apply corruption overlay
    if corruption_log:
        corrupted_clusters = set()
        for entry in corruption_log:
            if 'clusters_corrupted' in entry:
                corrupted_clusters.update(entry['clusters_corrupted'])
            if 'clusters_damaged' in entry:
                corrupted_clusters.update(entry['clusters_damaged'])
        for c in corrupted_clusters:
            if c < total_clusters:
                cluster_types[c] = 'corrupted'

    return cluster_types


def visualize_disk(manifest_path, corruption_log_path=None, output_path=None,
                   max_clusters=None, title=None):
    """Generate a disk layout visualization."""
    # Load manifest
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)

    # Load corruption log if available
    corruption_log = None
    if corruption_log_path and os.path.exists(corruption_log_path):
        with open(corruption_log_path, 'r') as f:
            corruption_data = json.load(f)
            corruption_log = corruption_data.get('corruption_log', [])

    # Build cluster map
    cluster_types = build_cluster_map(manifest, corruption_log)
    total_clusters = len(cluster_types)

    # Limit display if too many clusters
    if max_clusters and total_clusters > max_clusters:
        cluster_types = cluster_types[:max_clusters]

    # Set up the figure
    fig, ax = plt.subplots(1, 1, figsize=(16, 6))

    # Determine grid dimensions
    cols = 128
    rows = math.ceil(len(cluster_types) / cols)

    # Create a 2D array for the heatmap
    color_map = []
    for i in range(rows * cols):
        if i < len(cluster_types):
            ct = cluster_types[i]
            color_map.append(list(CLUSTER_COLORS.keys()).index(ct) if ct in CLUSTER_COLORS else len(CLUSTER_COLORS) - 1)
        else:
            color_map.append(list(CLUSTER_COLORS.keys()).index('free'))

    # Reshape into 2D
    grid = []
    for r in range(rows):
        row = color_map[r * cols:(r + 1) * cols]
        grid.append(row)

    # Create custom colormap
    colors_list = list(CLUSTER_COLORS.values())
    cmap = ListedColormap(colors_list)

    im = ax.imshow(grid, cmap=cmap, aspect='auto', interpolation='nearest')

    # Labels
    if title:
        ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
    else:
        dataset_id = os.path.basename(manifest_path).replace('_manifest.json', '')
        ax.set_title(f'Disk Layout: {dataset_id}', fontsize=14, fontweight='bold', pad=15)

    ax.set_xlabel('Cluster (offset in row)', fontsize=10)
    ax.set_ylabel('Row', fontsize=10)

    # Legend
    # Only show types that exist in the data
    present_types = set(cluster_types)
    legend_handles = []
    for ct, color in CLUSTER_COLORS.items():
        if ct in present_types:
            label = ct.replace('_', ' ').title()
            legend_handles.append(mpatches.Patch(color=color, label=label))

    ax.legend(handles=legend_handles, loc='upper right', fontsize=8,
              framealpha=0.9, ncol=min(len(legend_handles), 3))

    # Stats text
    stats = {}
    for ct in cluster_types:
        stats[ct] = stats.get(ct, 0) + 1
    stats_text = ' | '.join(f'{k}: {v}' for k, v in sorted(stats.items()) if k != 'free')
    fig.text(0.5, 0.02, stats_text, ha='center', fontsize=8, color='gray')

    plt.tight_layout()
    plt.subplots_adjust(bottom=0.1)

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        return output_path
    else:
        plt.close()
        return None


def visualize_ascii(manifest_path, corruption_log_path=None, width=80):
    """Generate an ASCII disk layout (for quick terminal debugging)."""
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)

    corruption_log = None
    if corruption_log_path and os.path.exists(corruption_log_path):
        with open(corruption_log_path, 'r') as f:
            corruption_data = json.load(f)
            corruption_log = corruption_data.get('corruption_log', [])

    cluster_types = build_cluster_map(manifest, corruption_log)

    symbols = {
        'boot': 'B',
        'mft': 'M',
        'mft_mirror': 'm',
        'bitmap': 'b',
        'journal': 'J',
        'data': 'D',
        'system': 'S',
        'free': '.',
        'corrupted': 'X',
        'unknown': '?',
    }

    lines = []
    for i in range(0, len(cluster_types), width):
        row = cluster_types[i:i+width]
        line = ''.join(symbols.get(ct, '?') for ct in row)
        lines.append(f'{i:6d} |{line}|')

    # Legend
    legend = '  '.join(f'{sym}={key}' for key, sym in symbols.items())
    lines.append('')
    lines.append(f'Legend: {legend}')

    return '\n'.join(lines)


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='RecoveryLab — Visualizer')
    parser.add_argument('--manifest', required=True,
                        help='Path to manifest.json')
    parser.add_argument('--corruption-log', default=None,
                        help='Path to corruption log JSON')
    parser.add_argument('--output', default=None,
                        help='Output PNG path')
    parser.add_argument('--ascii', action='store_true',
                        help='Output ASCII art instead of PNG')
    parser.add_argument('--max-clusters', type=int, default=2560,
                        help='Max clusters to display')

    args = parser.parse_args()

    if args.ascii:
        result = visualize_ascii(args.manifest, args.corruption_log)
        print(result)
    else:
        if args.output is None:
            base = os.path.basename(args.manifest).replace('_manifest.json', '')
            args.output = f'/home/z/my-project/RecoveryLab/datasets/ntfs/{base}_layout.png'

        visualize_disk(args.manifest, args.corruption_log, args.output,
                       max_clusters=args.max_clusters)
        print(f'Visualization saved: {args.output}')
