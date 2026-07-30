"""
RecoveryLab — Disk Layout Visualizer
======================================
Shows the layout of the disk: MFT, bitmap, files, journal.

This accelerates debugging — you can SEE where things are
instead of guessing from hex dumps.

Usage:
    from visualizer import DiskLayoutVisualizer
    viz = DiskLayoutVisualizer(manifest)
    viz.render_ascii()     # ASCII art to terminal
    viz.render_png(path)   # PNG image
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class DiskLayoutVisualizer:
    """
    Visualizes the layout of an NTFS disk image.

    Shows:
      - MFT zone (system files)
      - Bitmap
      - MFT Mirror
      - Journal
      - User files (color-coded by type)
      - Free space
      - Corruption zones (if applicable)
    """

    def __init__(self, manifest: Dict, corruption_log: Optional[List[Dict]] = None):
        self.manifest = manifest
        self.corruption_log = corruption_log or []
        self.cluster_size = manifest.get("cluster_size", 4096)
        self.total_clusters = manifest.get("total_clusters", 0)

    def render_ascii(self, width: int = 80, height: int = 20) -> str:
        """
        Render an ASCII art visualization of the disk layout.

        Each character represents a range of clusters.
        """
        total = self.total_clusters
        if total == 0:
            return "No clusters to visualize"

        # Map clusters to characters
        chars_per_row = width - 4  # Margin for line numbers
        total_chars = chars_per_row * height
        clusters_per_char = max(1, total // total_chars)

        # Build cluster map
        cluster_map = {}  # cluster -> type

        # MFT
        mft_info = self.manifest.get("mft", {})
        for c in mft_info.get("clusters", []):
            cluster_map[c] = "M"  # MFT

        # Bitmap
        bitmap_info = self.manifest.get("bitmap", {})
        for c in bitmap_info.get("clusters", []):
            cluster_map[c] = "B"  # Bitmap

        # MFT Mirror
        mftmirr_info = self.manifest.get("mftmirr", {})
        for c in mftmirr_info.get("clusters", []):
            cluster_map[c] = "R"  # Mirror

        # LogFile
        logfile_info = self.manifest.get("logfile", {})
        for c in logfile_info.get("clusters", []):
            cluster_map[c] = "J"  # Journal

        # User files
        file_colors = {}
        for f in self.manifest.get("files", []):
            if f.get("is_directory", False):
                for c in f.get("clusters", []):
                    cluster_map[c] = "D"  # Directory
            else:
                for c in f.get("clusters", []):
                    cluster_map[c] = "F"  # File

        # Corruption zones
        corrupted_clusters = set()
        for entry in self.corruption_log:
            for c in entry.get("clusters_affected", []):
                corrupted_clusters.add(c)
                cluster_map[c] = "X"  # Corrupted

        # Build the grid
        lines = []
        lines.append(f"Disk Layout: {total:,} clusters × {self.cluster_size} bytes = "
                     f"{total * self.cluster_size:,} bytes")
        lines.append(f"{'─' * width}")
        lines.append("Legend: M=MFT  B=Bitmap  R=Mirror  J=Journal  "
                      "F=File  D=Dir  X=Corrupted  ·=Free")
        lines.append(f"{'─' * width}")

        for row in range(height):
            start_cluster = row * chars_per_row * clusters_per_char
            line = ""
            for col in range(chars_per_row):
                cluster = start_cluster + col * clusters_per_char
                # Determine the dominant type in this range
                types = {}
                for c in range(cluster, min(cluster + clusters_per_char, total)):
                    t = cluster_map.get(c, ".")
                    types[t] = types.get(t, 0) + 1

                if types:
                    dominant = max(types, key=types.get)
                    line += dominant
                else:
                    line += "."

            cluster_start = start_cluster
            cluster_end = min(start_cluster + chars_per_row * clusters_per_char, total)
            lines.append(f"{cluster_start:>6} │{line}│ {cluster_end:>6}")

        lines.append(f"{'─' * width}")

        # Statistics
        mft_count = sum(1 for v in cluster_map.values() if v == "M")
        file_count = sum(1 for v in cluster_map.values() if v == "F")
        dir_count = sum(1 for v in cluster_map.values() if v == "D")
        corrupted_count = len(corrupted_clusters)
        used_count = len(cluster_map)
        free_count = total - used_count

        lines.append(f"  MFT: {mft_count:,} clusters | "
                     f"Files: {file_count:,} | Dirs: {dir_count:,} | "
                     f"Corrupted: {corrupted_count:,}")
        lines.append(f"  Used: {used_count:,} ({used_count/total:.1%}) | "
                     f"Free: {free_count:,} ({free_count/total:.1%})")

        return "\n".join(lines)

    def render_png(self, output_path: Path, width: int = 1200, height: int = 600):
        """
        Render a PNG visualization of the disk layout.

        Uses matplotlib for the visualization.
        """
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            import matplotlib.patches as patches
            import numpy as np
        except ImportError:
            print("matplotlib not available for PNG rendering")
            return

        total = self.total_clusters
        if total == 0:
            return

        # Build cluster type array
        cluster_types = np.zeros(total, dtype=int)
        # 0=free, 1=MFT, 2=bitmap, 3=mirror, 4=journal, 5=file, 6=directory, 7=corrupted

        # MFT
        mft_info = self.manifest.get("mft", {})
        for c in mft_info.get("clusters", []):
            if c < total:
                cluster_types[c] = 1

        # Bitmap
        bitmap_info = self.manifest.get("bitmap", {})
        for c in bitmap_info.get("clusters", []):
            if c < total:
                cluster_types[c] = 2

        # MFT Mirror
        mftmirr_info = self.manifest.get("mftmirr", {})
        for c in mftmirr_info.get("clusters", []):
            if c < total:
                cluster_types[c] = 3

        # LogFile
        logfile_info = self.manifest.get("logfile", {})
        for c in logfile_info.get("clusters", []):
            if c < total:
                cluster_types[c] = 4

        # User files
        for f in self.manifest.get("files", []):
            if f.get("is_directory", False):
                for c in f.get("clusters", []):
                    if c < total:
                        cluster_types[c] = 6
            else:
                for c in f.get("clusters", []):
                    if c < total:
                        cluster_types[c] = 5

        # Corruption
        for entry in self.corruption_log:
            for c in entry.get("clusters_affected", []):
                if c < total:
                    cluster_types[c] = 7

        # Color map
        colors = {
            0: '#2d2d2d',   # Free (dark)
            1: '#e74c3c',   # MFT (red)
            2: '#f39c12',   # Bitmap (orange)
            3: '#9b59b6',   # Mirror (purple)
            4: '#3498db',   # Journal (blue)
            5: '#2ecc71',   # Files (green)
            6: '#1abc9c',   # Directories (teal)
            7: '#e74c3c',   # Corrupted (bright red)
        }

        # Create figure
        fig, ax = plt.subplots(1, 1, figsize=(width/100, height/100), dpi=100)

        # Render as a horizontal strip
        rows = 20
        cols = (total + rows - 1) // rows

        data = np.zeros((rows, cols, 3))
        for i in range(total):
            row = i // cols
            col = i % cols
            if row < rows and col < cols:
                color = colors.get(cluster_types[i], '#2d2d2d')
                # Convert hex to RGB
                r = int(color[1:3], 16) / 255
                g = int(color[3:5], 16) / 255
                b = int(color[5:7], 16) / 255
                data[row, col] = [r, g, b]

        ax.imshow(data, aspect='auto', interpolation='nearest')
        ax.set_title(f"Disk Layout — {total:,} clusters × {self.cluster_size} bytes",
                     fontsize=12, color='white')
        ax.set_xlabel("Cluster offset", fontsize=10)
        ax.set_ylabel("Row", fontsize=10)

        # Legend
        legend_items = [
            patches.Patch(color=colors[1], label='MFT'),
            patches.Patch(color=colors[2], label='Bitmap'),
            patches.Patch(color=colors[3], label='Mirror'),
            patches.Patch(color=colors[4], label='Journal'),
            patches.Patch(color=colors[5], label='Files'),
            patches.Patch(color=colors[6], label='Directories'),
            patches.Patch(color=colors[7], label='Corrupted'),
            patches.Patch(color=colors[0], label='Free'),
        ]
        ax.legend(handles=legend_items, loc='upper right', fontsize=8,
                  facecolor='#1a1a1a', edgecolor='#444', labelcolor='white')

        fig.patch.set_facecolor('#1a1a1a')
        ax.set_facecolor('#1a1a1a')
        ax.tick_params(colors='white')

        plt.tight_layout()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=100, bbox_inches='tight',
                    facecolor='#1a1a1a', edgecolor='none')
        plt.close()

        print(f"  Disk layout saved: {output_path}")

    def render_file_map(self) -> str:
        """Render a text-based file-to-cluster map."""
        lines = []
        lines.append("File → Cluster Map")
        lines.append(f"{'─' * 60}")

        for f in self.manifest.get("files", []):
            name = f.get("name", "?")
            clusters = f.get("clusters", [])
            is_frag = f.get("is_fragmented", False)
            is_dir = f.get("is_directory", False)
            is_res = f.get("is_resident", False)

            if is_dir:
                lines.append(f"  📁 {name:40s} [directory]")
            elif is_res:
                lines.append(f"  📄 {name:40s} [resident in MFT]")
            elif clusters:
                frag = " [FRAGMENTED]" if is_frag else ""
                cluster_str = ",".join(str(c) for c in clusters[:10])
                if len(clusters) > 10:
                    cluster_str += f"... ({len(clusters)} total)"
                lines.append(f"  📄 {name:40s} clusters:[{cluster_str}]{frag}")
            else:
                lines.append(f"  📄 {name:40s} [no clusters]")

        return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="RecoveryLab Disk Layout Visualizer")
    parser.add_argument("--manifest", required=True, help="Path to manifest.json")
    parser.add_argument("--corruption-log", default=None, help="Path to corruption log")
    parser.add_argument("--png", default=None, help="Output PNG path")
    parser.add_argument("--width", type=int, default=80, help="ASCII width")

    args = parser.parse_args()

    with open(args.manifest) as f:
        manifest = json.load(f)

    corruption_log = []
    if args.corruption_log:
        with open(args.corruption_log) as f:
            log_data = json.load(f)
            corruption_log = log_data.get("entries", [])

    viz = DiskLayoutVisualizer(manifest, corruption_log)

    # ASCII output
    print(viz.render_ascii(width=args.width))
    print()
    print(viz.render_file_map())

    # PNG output
    if args.png:
        viz.render_png(Path(args.png))
