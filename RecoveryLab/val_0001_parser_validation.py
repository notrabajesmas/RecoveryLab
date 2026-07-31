#!/usr/bin/env python3
"""
VAL-0001 — Validación Individual de Parsers
=============================================
Pregunta: ¿Los parsers individuales funcionan correctamente?

Diseño:
  - 100 archivos por formato (JPEG, PNG, PDF, ZIP, DOCX)
  - Sin MFT
  - Sin corrupción
  - Sin RVS
  - Sin Judge
  - Sin hipótesis

Solo: Entrada conocida → Salida conocida

Familia: VAL (Validación de instrumentos de medición)
Diferencia con DIAG: DIAG localiza problemas. VAL certifica que los
instrumentos funcionan correctamente. No hay hipótesis — solo verificación
de que un parser puede extraer archivos que él mismo debería poder extraer.

Metodología:
  1. Generar 100 archivos de un formato específico
  2. Crear una imagen de disco NTFS que contenga SOLO esos archivos
  3. Ejecutar el parser de carving SOLO para ese formato
  4. Comparar cada archivo extraído con el ground truth
  5. Reportar: match exacto, parcial, truncado, faltante, falso positivo

Observación pura (sin interpretación):
  - N archivos generados
  - M archivos extraídos
  - K archivos con SHA-256 exacto
  - T archivos truncados (falta N bytes al final)
  - F falsos positivos
  - P archivos faltantes (no extraídos)

El experimento NO interpreta los resultados. Solo reporta observaciones.
"""

import sys
import os
import json
import csv
import hashlib
import time
import datetime
import statistics
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# ─── Project root ─────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RECOVERYLAB_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(RECOVERYLAB_ROOT))

# ─── Imports ──────────────────────────────────────────────────────
from dataset_builder.builder import DatasetBuilder
from dataset_builder.manifest import load_manifest, save_manifest
from motors.motor_carving import MotorCarving
from motors.motor_b_mft_first import MotorBMFTFirst
from recovery_judge.judge import RecoveryJudge
from recovery_judge.fqs import compute_overall_utility

# ─── Experiment Metadata ─────────────────────────────────────────
EXPERIMENT_ID = "VAL-0001"
EXPERIMENT_NAME = "Validación Individual de Parsers"
PROTOCOL_VERSION = "v1.5"
JUDGE_VERSION = "N/A"  # No Judge — solo validación de parser

# ─── Configuration ────────────────────────────────────────────────
FILES_PER_FORMAT = 100
SEED = 42
VOLUME_SIZE = 100 * 1024 * 1024  # 100 MB per format

FORMATS = {
    "JPEG": {
        "extension": ".jpg",
        "volume_size": 500 * 1024 * 1024,  # 500 MB (JPEGs are large, need space for 100)
    },
    "PNG": {
        "extension": ".png",
        "volume_size": 500 * 1024 * 1024,  # 500 MB (PNGs are large, need space for 100)
    },
    "PDF": {
        "extension": ".pdf",
        "volume_size": 200 * 1024 * 1024,  # 200 MB (PDFs are smaller, but 100 files)
    },
    "ZIP": {
        "extension": ".zip",
        "volume_size": 200 * 1024 * 1024,  # 200 MB
    },
    "DOCX": {
        "extension": ".docx",
        "volume_size": 200 * 1024 * 1024,  # 200 MB
    },
}

# ─── Output ───────────────────────────────────────────────────────
OUTPUT_DIR = RECOVERYLAB_ROOT / "output" / "val_0001"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_single_format_dataset(format_name: str, format_config: Dict,
                                     num_files: int, seed: int) -> Tuple[bytes, Dict]:
    """
    Generate a disk image containing ONLY files of a single format.

    Uses DatasetBuilder.build_single_format_dataset() which is the same
    method used by DIAG-0001.

    Returns: (image_bytes, manifest)
    """
    ext = format_config["extension"]
    vol_size = format_config.get("volume_size", VOLUME_SIZE)

    builder = DatasetBuilder(
        seed=seed,
        num_images=1,
        volume_size=vol_size,
        cluster_size=4096,
        files_per_image=num_files,
    )

    image, manifest = builder.build_single_format_dataset(
        extension=ext,
        n_files=num_files,
        volume_size=vol_size,
    )

    return image, manifest


def run_carving_parser_on_image(image: bytes, manifest: Dict) -> Dict:
    """
    Run ONLY the carving parser on the image.

    No MFT, no corruption, no Judge. Just the parser.

    Returns: dict with parser results
    """
    motor = MotorCarving()

    result = motor.recover(
        image=image,
        manifest=manifest,
        read_budget=0,  # Unlimited reads
    )

    return {
        "motor_name": result.motor_name,
        "files_recovered": len(result.recovered_files),
        "recovered_files": [
            {
                "name": f.name,
                "sha256": f.sha256,
                "size": f.size,
                "source": f.source,
                "data": f.data,
            }
            for f in result.recovered_files
        ],
        "read_count": result.read_count,
        "carving_stats": getattr(result, 'carving_stats', {}),
    }


def compare_carved_to_ground_truth(carved_files: List[Dict],
                                    manifest: Dict,
                                    image: bytes) -> Dict:
    """
    Compare carved files to ground truth.

    This is the core of VAL-0001: pure comparison, no interpretation.

    Returns: dict with comparison results
    """
    # Build ground truth SHA-256 lookup
    gt_by_sha256 = {}
    gt_files = manifest.get("files", [])
    for gt_file in gt_files:
        gt_by_sha256[gt_file["sha256"]] = gt_file

    # Match carved files to ground truth
    matched = []
    false_positives = []
    matched_gt_shas = set()

    for cf in carved_files:
        if cf["sha256"] in gt_by_sha256:
            gt_file = gt_by_sha256[cf["sha256"]]
            matched.append({
                "carved_name": cf["name"],
                "carved_size": cf["size"],
                "gt_name": gt_file["name"],
                "gt_size": gt_file.get("size", cf["size"]),
                "match_type": "exact_sha256",
            })
            matched_gt_shas.add(cf["sha256"])
        else:
            # Check if it's a truncated version of a ground truth file
            truncated = False
            truncation_info = None

            for gt_sha, gt_file in gt_by_sha256.items():
                gt_size = gt_file.get("size", 0)
                cf_size = cf["size"]

                if gt_sha in matched_gt_shas:
                    continue  # Already matched

                if cf_size < gt_size and cf_size > 0 and cf["data"] is not None:
                    # Check if carved data is a prefix of ground truth
                    gt_clusters = gt_file.get("clusters", [])
                    if gt_clusters:
                        gt_start = gt_clusters[0] * 4096
                        gt_data = image[gt_start:gt_start + gt_size]
                        if cf["data"] == gt_data[:cf_size]:
                            missing_bytes = gt_size - cf_size
                            # Get the first missing byte
                            missing_byte = gt_data[cf_size:cf_size+1] if cf_size < len(gt_data) else b''
                            truncation_info = {
                                "carved_name": cf["name"],
                                "carved_size": cf_size,
                                "gt_name": gt_file["name"],
                                "gt_size": gt_size,
                                "missing_bytes": missing_bytes,
                                "missing_byte_hex": missing_byte.hex() if missing_byte else "",
                                "match_type": "truncated",
                            }
                            truncated = True
                            break

            if truncated and truncation_info:
                false_positives.append(truncation_info)
            else:
                false_positives.append({
                    "carved_name": cf["name"],
                    "carved_size": cf["size"],
                    "match_type": "false_positive",
                })

    # Count missing (ground truth files not carved)
    missing_count = len(gt_by_sha256) - len(matched_gt_shas)

    return {
        "matched": matched,
        "matched_count": len(matched),
        "false_positives": false_positives,
        "false_positive_count": len(false_positives),
        "missing_count": missing_count,
        "total_gt_files": len(gt_by_sha256),
        "total_carved_files": len(carved_files),
    }


def run_single_format_validation(format_name: str, format_config: Dict) -> Dict:
    """
    Run the full validation for a single format.

    Returns: dict with all results
    """
    print(f"\n{'='*60}")
    print(f"VAL-0001 — Validando parser: {format_name}")
    print(f"{'='*60}")

    # Step 1: Generate dataset
    print(f"  [1/4] Generando {FILES_PER_FORMAT} archivos {format_name}...")
    image, manifest = generate_single_format_dataset(
        format_name=format_name,
        format_config=format_config,
        num_files=FILES_PER_FORMAT,
        seed=SEED,
    )
    print(f"        Imagen generada: {len(image):,} bytes")
    gt_files = manifest.get("files", [])
    print(f"        Archivos en manifest: {len(gt_files)}")

    # Step 2: Run carving parser
    print(f"  [2/4] Ejecutando carving parser...")
    parser_result = run_carving_parser_on_image(image, manifest)
    print(f"        Archivos carved: {parser_result['files_recovered']}")
    print(f"        Firmas encontradas: {parser_result.get('carving_stats', {}).get('signatures_found', {})}")

    # Step 3: Compare to ground truth
    print(f"  [3/4] Comparando con ground truth...")
    comparison = compare_carved_to_ground_truth(
        parser_result["recovered_files"],
        manifest,
        image,
    )
    print(f"        Matched (SHA-256 exacto): {comparison['matched_count']}")
    print(f"        Falsos positivos: {comparison['false_positive_count']}")
    print(f"        Faltantes: {comparison['missing_count']}")

    # Truncation analysis
    truncation_details = []
    for fp in comparison["false_positives"]:
        if fp.get("match_type") == "truncated":
            truncation_details.append(fp)

    # Step 4: Build observation (pure — no interpretation)
    print(f"  [4/4] Construyendo observación pura...")

    observation = {
        "format": format_name,
        "files_generated": comparison["total_gt_files"],
        "files_carved": comparison["total_carved_files"],
        "files_matched_exact": comparison["matched_count"],
        "files_false_positive": comparison["false_positive_count"],
        "files_missing": comparison["missing_count"],
        "files_truncated": len(truncation_details),
        "exact_match_rate": round(comparison["matched_count"] / max(comparison["total_gt_files"], 1), 4),
        "carve_rate": round(comparison["total_carved_files"] / max(comparison["total_gt_files"], 1), 4),
        "signatures_found": parser_result.get("carving_stats", {}).get("signatures_found", {}),
    }

    print(f"\n  OBSERVACIÓN PURA:")
    print(f"    Archivos generados: {observation['files_generated']}")
    print(f"    Archivos carved: {observation['files_carved']}")
    print(f"    Match exacto (SHA-256): {observation['files_matched_exact']}")
    print(f"    Falsos positivos: {observation['files_false_positive']}")
    print(f"    Faltantes: {observation['files_missing']}")
    print(f"    Truncados: {observation['files_truncated']}")
    print(f"    Tasa de match exacto: {observation['exact_match_rate']:.2%}")
    print(f"    Tasa de carve: {observation['carve_rate']:.2%}")

    # Clean up data references before returning (they're large)
    for cf in parser_result["recovered_files"]:
        cf.pop("data", None)

    return {
        "format": format_name,
        "observation": observation,
        "comparison": comparison,
        "parser_result": {
            "files_recovered": parser_result["files_recovered"],
            "read_count": parser_result["read_count"],
            "carving_stats": parser_result.get("carving_stats", {}),
        },
        "manifest": {
            "num_files": len(gt_files),
            "volume_size": len(image),
        },
    }


def generate_report(results: Dict[str, Dict]) -> str:
    """
    Generate the VAL-0001 report.

    OBSERVATION ONLY. No interpretation.
    """
    lines = []
    lines.append(f"# VAL-0001 — Validación Individual de Parsers")
    lines.append("")
    lines.append(f"**Date**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Protocol**: {PROTOCOL_VERSION} | **Judge**: {JUDGE_VERSION}")
    lines.append(f"**Pregunta**: ¿Los parsers individuales funcionan correctamente?")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Summary table
    lines.append("## 1. Resumen por Formato")
    lines.append("")
    lines.append("| Formato | Generados | Carved | Match Exacto | Truncados | Faltantes | FP | Tasa Match | Tasa Carve |")
    lines.append("|---------|-----------|--------|-------------|-----------|-----------|-----|-----------|------------|")

    for fmt_name, fmt_result in results.items():
        obs = fmt_result["observation"]
        lines.append(
            f"| {fmt_name} | {obs['files_generated']} | {obs['files_carved']} | "
            f"{obs['files_matched_exact']} | {obs['files_truncated']} | "
            f"{obs['files_missing']} | {obs['files_false_positive']} | "
            f"{obs['exact_match_rate']:.2%} | {obs['carve_rate']:.2%} |"
        )

    lines.append("")

    # Per-format details
    lines.append("## 2. Detalle por Formato")
    lines.append("")

    for fmt_name, fmt_result in results.items():
        obs = fmt_result["observation"]
        lines.append(f"### {fmt_name}")
        lines.append("")
        lines.append(f"- Archivos generados: {obs['files_generated']}")
        lines.append(f"- Archivos carved: {obs['files_carved']}")
        lines.append(f"- Match exacto (SHA-256): {obs['files_matched_exact']}")
        lines.append(f"- Truncados: {obs['files_truncated']}")
        lines.append(f"- Faltantes: {obs['files_missing']}")
        lines.append(f"- Falsos positivos: {obs['files_false_positive']}")
        lines.append(f"- Firmas encontradas: {obs['signatures_found']}")
        lines.append(f"- Tasa de match exacto: {obs['exact_match_rate']:.2%}")
        lines.append(f"- Tasa de carve: {obs['carve_rate']:.2%}")
        lines.append("")

        # Truncation/false positive details
        fps = fmt_result.get("comparison", {}).get("false_positives", [])
        if fps:
            lines.append("**Detalle de falsos positivos/truncados:**")
            lines.append("")
            for fp in fps:
                if fp.get("match_type") == "truncated":
                    lines.append(
                        f"- `{fp['carved_name']}` (size={fp['carved_size']}): "
                        f"TRUNCATED — missing {fp['missing_bytes']} bytes "
                        f"(gt: `{fp['gt_name']}`, size={fp['gt_size']})"
                    )
                elif fp.get("match_type") == "false_positive":
                    lines.append(
                        f"- `{fp['carved_name']}` (size={fp['carved_size']}): "
                        f"FALSE POSITIVE — no ground truth match"
                    )
            lines.append("")

    # Pure observation
    lines.append("## 3. Observación Pura (para Evidence Ledger)")
    lines.append("")
    lines.append(f"> En VAL-0001, bajo las condiciones evaluadas ({FILES_PER_FORMAT} archivos por formato,")
    lines.append(f"> sin corrupción, sin Judge, Protocol {PROTOCOL_VERSION}),")
    lines.append(f"> los parsers de carving produjeron:")
    lines.append(">")
    for fmt_name, fmt_result in results.items():
        obs = fmt_result["observation"]
        lines.append(f"> - {fmt_name}: {obs['files_matched_exact']}/{obs['files_generated']} match exacto, "
                     f"{obs['files_carved']} carved, {obs['files_missing']} faltantes, "
                     f"{obs['files_false_positive']} FP")
    lines.append(">")
    lines.append(f"> Esta es una observación pura. No contiene interpretación.")
    lines.append("")

    # Cross-reference with DIAG-0001
    lines.append("## 4. Referencia Cruzada con DIAG-0001")
    lines.append("")
    lines.append("| Formato | DIAG-0001 OU | VAL-0001 Match Rate | Consistente? |")
    lines.append("|---------|-------------|--------------------:|:------------:|")

    diag_ou = {
        "JPEG": 0.0,
        "PNG": 0.8709,
        "PDF": 0.0,
        "ZIP": 1.0,
        "DOCX": 1.0,
    }

    for fmt_name, fmt_result in results.items():
        obs = fmt_result["observation"]
        d_ou = diag_ou.get(fmt_name, "N/A")
        v_rate = obs["exact_match_rate"]
        if d_ou == "N/A":
            consistent = "N/A"
        elif (d_ou > 0.5 and v_rate > 0.5) or (d_ou < 0.5 and v_rate < 0.5):
            consistent = "Si"
        else:
            consistent = "Verificar"
        lines.append(f"| {fmt_name} | {d_ou} | {v_rate:.2%} | {consistent} |")

    lines.append("")

    # Notes
    lines.append("## 5. Notas Metodológicas")
    lines.append("")
    lines.append("- **No se uso Judge**: Este experimento valida parsers, no motores.")
    lines.append("- **No se uso corrupcion**: Los archivos estan intactos en la imagen.")
    lines.append("- **No se uso MFT**: El parser de carving no accede al MFT por diseno.")
    lines.append("- **No se uso RVS/FQS**: No hay scoring de valor o calidad.")
    lines.append("- **No hay hipotesis**: Este experimento solo observa, no interpreta.")
    lines.append("- **Observacion pura**: Los resultados son hechos, no conclusiones.")
    lines.append("- **N=100 por formato**: Mas archivos que DIAG-0001 (N=15) para mayor confianza estadistica.")
    lines.append("")
    lines.append(f"*Experiment ID: {EXPERIMENT_ID} | Protocol: {PROTOCOL_VERSION} | Judge: {JUDGE_VERSION}*")

    return "\n".join(lines)


def main():
    """Run VAL-0001 — Validate individual parsers."""
    print(f"{'='*60}")
    print(f"VAL-0001 — Validación Individual de Parsers")
    print(f"{'='*60}")
    print(f"Archivos por formato: {FILES_PER_FORMAT}")
    print(f"Seed: {SEED}")
    print(f"Formatos: {list(FORMATS.keys())}")
    print()

    all_results = {}

    for fmt_name, fmt_config in FORMATS.items():
        try:
            result = run_single_format_validation(fmt_name, fmt_config)
            all_results[fmt_name] = result
        except Exception as e:
            print(f"\n  ERROR en {fmt_name}: {e}")
            import traceback
            traceback.print_exc()
            all_results[fmt_name] = {
                "format": fmt_name,
                "error": str(e),
                "observation": {
                    "format": fmt_name,
                    "files_generated": 0,
                    "files_carved": 0,
                    "files_matched_exact": 0,
                    "files_false_positive": 0,
                    "files_missing": 0,
                    "files_truncated": 0,
                    "exact_match_rate": 0.0,
                    "carve_rate": 0.0,
                    "signatures_found": {},
                    "error": str(e),
                },
                "comparison": {"false_positives": [], "matched": []},
            }

    # Generate report
    print(f"\n{'='*60}")
    print(f"Generando reporte VAL-0001...")
    print(f"{'='*60}")

    report = generate_report(all_results)

    # Save report
    report_path = OUTPUT_DIR / "val_0001_report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"Reporte guardado: {report_path}")

    # Save summary JSON
    summary = {
        "experiment_id": EXPERIMENT_ID,
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "versions": {
            "protocol": PROTOCOL_VERSION,
            "judge": JUDGE_VERSION,
        },
        "config": {
            "files_per_format": FILES_PER_FORMAT,
            "seed": SEED,
            "formats": list(FORMATS.keys()),
        },
        "format_results": {
            fmt_name: fmt_result["observation"]
            for fmt_name, fmt_result in all_results.items()
        },
    }

    summary_path = OUTPUT_DIR / "val_0001_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Summary guardado: {summary_path}")

    # Save per-file CSV
    csv_path = OUTPUT_DIR / "val_0001_per_file.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "format", "carved_name", "carved_size",
            "match_type", "gt_name", "gt_size", "missing_bytes"
        ])
        for fmt_name, fmt_result in all_results.items():
            for fp in fmt_result.get("comparison", {}).get("false_positives", []):
                writer.writerow([
                    fmt_name,
                    fp.get("carved_name", ""),
                    fp.get("carved_size", 0),
                    fp.get("match_type", "unknown"),
                    fp.get("gt_name", ""),
                    fp.get("gt_size", 0),
                    fp.get("missing_bytes", 0),
                ])
            for m in fmt_result.get("comparison", {}).get("matched", []):
                writer.writerow([
                    fmt_name,
                    m.get("carved_name", ""),
                    m.get("carved_size", 0),
                    m.get("match_type", "exact"),
                    m.get("gt_name", ""),
                    m.get("gt_size", 0),
                    0,
                ])

    print(f"CSV guardado: {csv_path}")

    # Save ledger entry
    ledger_entry = {
        "experiment_id": EXPERIMENT_ID,
        "experiment_type": "VALIDATION",
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "protocol_version": PROTOCOL_VERSION,
        "judge_version": JUDGE_VERSION,
        "question": "¿Los parsers individuales funcionan correctamente?",
        "design": "100 archivos por formato, sin corrupción, sin Judge, sin hipótesis",
        "formats_tested": list(FORMATS.keys()),
        "observation_pure": {
            fmt_name: {
                "files_generated": fmt_result["observation"]["files_generated"],
                "files_matched_exact": fmt_result["observation"]["files_matched_exact"],
                "files_carved": fmt_result["observation"]["files_carved"],
                "files_missing": fmt_result["observation"]["files_missing"],
                "files_false_positive": fmt_result["observation"]["files_false_positive"],
                "exact_match_rate": fmt_result["observation"]["exact_match_rate"],
            }
            for fmt_name, fmt_result in all_results.items()
        },
        "no_interpretation": True,
        "notes": "Observación pura. No se modificó código. No se interpretan resultados.",
    }

    ledger_path = OUTPUT_DIR / "ledger_entry.json"
    ledger_path.write_text(json.dumps(ledger_entry, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Ledger guardado: {ledger_path}")

    # Print summary
    print(f"\n{'='*60}")
    print(f"VAL-0001 — RESUMEN")
    print(f"{'='*60}")
    print(f"{'Formato':<8} {'Generados':>10} {'Carved':>8} {'Match':>8} {'FP':>5} {'Faltantes':>10} {'Tasa':>8}")
    print(f"{'-'*8} {'-'*10} {'-'*8} {'-'*8} {'-'*5} {'-'*10} {'-'*8}")
    for fmt_name, fmt_result in all_results.items():
        obs = fmt_result["observation"]
        print(f"{fmt_name:<8} {obs['files_generated']:>10} {obs['files_carved']:>8} "
              f"{obs['files_matched_exact']:>8} {obs['files_false_positive']:>5} "
              f"{obs['files_missing']:>10} {obs['exact_match_rate']:>8.2%}")

    print(f"\nVAL-0001 completado.")


if __name__ == "__main__":
    main()
