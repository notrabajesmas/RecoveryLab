#!/usr/bin/env python3
"""
RecoveryLab — Main Entry Point
=================================
The complete framework for objectively testing recovery strategies.

  RecoveryLab/
  ├── Dataset Builder     — Creates perfectly known NTFS images
  ├── Corruptor           — Applies real failure patterns
  ├── Gold Images         — Fixed benchmark set (never changes)
  ├── Recovery Judge      — Measures EVERYTHING
  ├── Experiment Runner   — Automated pipeline
  ├── Visualizer          — See disk layout
  └── Experimental Motors — Motor A (sequential) vs Motor B (MFT-first)

Usage:
  python run_experiment.py build          # Build 20 datasets
  python run_experiment.py gold           # Build 10 gold images
  python run_experiment.py run            # Run full experiment
  python run_experiment.py run --attack A01  # Run specific attack
  python run_experiment.py viz --manifest path/to/manifest.json  # Visualize
  python run_experiment.py verify         # Verify all manifests
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def cmd_build(args):
    """Build dataset images."""
    from dataset_builder.builder import DatasetBuilder

    builder = DatasetBuilder(
        seed=args.seed,
        num_images=args.num_images,
        volume_size=args.volume_size,
        cluster_size=args.cluster_size,
        files_per_image=args.files_per_image,
    )
    builder.build_all()


def cmd_gold(args):
    """Build gold images (immutable benchmark set)."""
    import json
    from dataset_builder.builder import DatasetBuilder

    gold_config_path = PROJECT_ROOT / "gold_images" / "gold_config.json"
    with open(gold_config_path) as f:
        gold_config = json.load(f)

    output_dir = PROJECT_ROOT / "output" / "gold"

    for i, seed in enumerate(gold_config["seeds"], 1):
        print(f"\n{'='*60}")
        print(f"Gold Image {i}/{len(gold_config['seeds'])} (seed={seed})")
        print(f"{'='*60}")

        builder = DatasetBuilder(
            seed=seed,
            num_images=1,
            volume_size=gold_config["volume_size"],
            cluster_size=gold_config["cluster_size"],
            files_per_image=gold_config["files_per_image"],
            output_dir=output_dir,
        )
        # Override the image naming for gold
        builder.build_image(index=i)

    print(f"\n✓ Gold images complete: {len(gold_config['seeds'])} images")
    print(f"  These images are LOCKED and must never change.")


def cmd_run(args):
    """Run the full experiment."""
    from experiment_runner.runner import ExperimentRunner
    from corruptor.corruptor import ATTACK_MATRIX

    dataset_dir = PROJECT_ROOT / args.dataset_dir
    output_dir = PROJECT_ROOT / args.output_dir

    runner = ExperimentRunner(
        dataset_dir=dataset_dir,
        output_dir=output_dir,
        seed=args.seed,
    )

    attacks = ATTACK_MATRIX
    if args.attack:
        attacks = [a for a in ATTACK_MATRIX if a["id"] == args.attack]

    runner.run_all(attacks=attacks, read_budget=args.read_budget)


def cmd_viz(args):
    """Visualize a disk layout."""
    import json
    from visualizer.disk_layout import DiskLayoutVisualizer

    with open(args.manifest) as f:
        manifest = json.load(f)

    corruption_log = []
    if args.corruption_log:
        with open(args.corruption_log) as f:
            log_data = json.load(f)
            corruption_log = log_data.get("entries", [])

    viz = DiskLayoutVisualizer(manifest, corruption_log)

    print(viz.render_ascii(width=args.width))
    print()
    print(viz.render_file_map())

    if args.png:
        viz.render_png(Path(args.png))


def cmd_verify(args):
    """Verify all manifests in the dataset directory."""
    from dataset_builder.manifest import load_manifest, verify_manifest

    dataset_dir = PROJECT_ROOT / args.dataset_dir
    manifests = sorted(dataset_dir.glob("*_manifest.json"))

    if not manifests:
        print(f"No manifests found in {dataset_dir}")
        return

    total = len(manifests)
    ok = 0
    issues = []

    for path in manifests:
        manifest = load_manifest(path)
        problems = verify_manifest(manifest)
        if problems:
            issues.append((path.name, problems))
        else:
            ok += 1

    print(f"\nManifest Verification: {ok}/{total} OK")
    if issues:
        for name, probs in issues:
            print(f"  ⚠ {name}: {probs}")
    else:
        print("  ✓ All manifests are valid")


def cmd_judge(args):
    """Run the judge on a single image."""
    import json
    from dataset_builder.manifest import load_manifest
    from recovery_judge.judge import RecoveryJudge
    from motors.motor_a_sequential import MotorASequential
    from motors.motor_b_mft_first import MotorBMFTFirst

    with open(args.manifest) as f:
        manifest = load_manifest(Path(args.manifest))

    image_path = Path(args.image)
    with open(image_path, 'rb') as f:
        image = f.read()

    judge = RecoveryJudge(manifest)
    motor_a = MotorASequential()
    motor_b = MotorBMFTFirst()

    # Run Motor A
    result_a = motor_a.recover(image, manifest, read_budget=args.read_budget)
    metrics_a = judge.judge(
        recovered_files=[{"name": f.name, "sha256": f.sha256, "size": f.size,
                          "is_directory": f.is_directory}
                         for f in result_a.recovered_files],
        read_count=result_a.read_count,
        sectors_wasted=result_a.sectors_wasted,
        time_to_first_file=result_a.time_to_first_file,
        mft_entries_parsed=result_a.mft_entries_parsed,
    )

    # Run Motor B
    result_b = motor_b.recover(image, manifest, read_budget=args.read_budget)
    metrics_b = judge.judge(
        recovered_files=[{"name": f.name, "sha256": f.sha256, "size": f.size,
                          "is_directory": f.is_directory}
                         for f in result_b.recovered_files],
        read_count=result_b.read_count,
        sectors_wasted=result_b.sectors_wasted,
        time_to_first_file=result_b.time_to_first_file,
        mft_entries_parsed=result_b.mft_entries_parsed,
    )

    # Compare
    comparison = judge.compare(metrics_a, metrics_b)

    print(f"\n{'='*60}")
    print(f"Motor A: {metrics_a.summary()}")
    print(f"Motor B: {metrics_b.summary()}")
    print(f"\nΔ Recovery: {comparison.delta_recovery_rate():+.2%}")
    print(f"Δ Reads: {comparison.delta_reads():+d}")
    print(f"H1: {comparison.h1_strength()}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="RecoveryLab — Framework for objectively testing recovery strategies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  build     Build dataset images
  gold      Build gold images (immutable benchmark)
  run       Run the full experiment
  viz       Visualize disk layout
  verify    Verify all manifests
  judge     Run judge on a single image

Examples:
  python run_experiment.py build --seed 42 --num-images 20
  python run_experiment.py gold
  python run_experiment.py run --attack A01
  python run_experiment.py viz --manifest output/datasets/dataset_001_manifest.json
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ─── Build ─────────────────────────────────────────────────────────
    p_build = subparsers.add_parser("build", help="Build dataset images")
    p_build.add_argument("--seed", type=int, default=42)
    p_build.add_argument("--num-images", type=int, default=20)
    p_build.add_argument("--volume-size", type=int, default=10*1024*1024)
    p_build.add_argument("--cluster-size", type=int, default=4096)
    p_build.add_argument("--files-per-image", type=int, default=30)

    # ─── Gold ──────────────────────────────────────────────────────────
    p_gold = subparsers.add_parser("gold", help="Build gold images")

    # ─── Run ───────────────────────────────────────────────────────────
    p_run = subparsers.add_parser("run", help="Run the full experiment")
    p_run.add_argument("--dataset-dir", default="output/datasets")
    p_run.add_argument("--output-dir", default="output/results")
    p_run.add_argument("--seed", type=int, default=42)
    p_run.add_argument("--read-budget", type=int, default=0)
    p_run.add_argument("--attack", default=None, help="Run only specific attack")

    # ─── Visualize ─────────────────────────────────────────────────────
    p_viz = subparsers.add_parser("viz", help="Visualize disk layout")
    p_viz.add_argument("--manifest", required=True)
    p_viz.add_argument("--corruption-log", default=None)
    p_viz.add_argument("--png", default=None)
    p_viz.add_argument("--width", type=int, default=80)

    # ─── Verify ────────────────────────────────────────────────────────
    p_verify = subparsers.add_parser("verify", help="Verify manifests")
    p_verify.add_argument("--dataset-dir", default="output/datasets")

    # ─── Judge ─────────────────────────────────────────────────────────
    p_judge = subparsers.add_parser("judge", help="Run judge on single image")
    p_judge.add_argument("--image", required=True)
    p_judge.add_argument("--manifest", required=True)
    p_judge.add_argument("--read-budget", type=int, default=0)

    args = parser.parse_args()

    if args.command == "build":
        cmd_build(args)
    elif args.command == "gold":
        cmd_gold(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "viz":
        cmd_viz(args)
    elif args.command == "verify":
        cmd_verify(args)
    elif args.command == "judge":
        cmd_judge(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
