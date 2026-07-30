"""
RecoveryLab — RVS Calibration Experiment (EXP-RVS-CAL)
=======================================================
The most important human experiment in the project.

This is NOT a software experiment. It is a MODEL VALIDATION experiment.
It tests whether the RVS value weights assigned by the laboratory
correspond to the actual preferences of real users.

Question: "Si solo pudieras recuperar uno de estos archivos, cual elegirias?"

Method: Bradley-Terry pairwise comparison
Population: 5 groups x 30+ respondents
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import json
import os
import random


# ─── File Pairs for the Survey ───────────────────────────────────────────────
# Each pair forces a choice between two file types.
# The pairs are designed to test the key assumptions of the RVS model.

SURVEY_PAIRS = [
    # ── Core assumption: thesis > thumbnails ──
    {
        "id": "P01",
        "pair": ("tesis_final.docx", "thumbnail_cache.db"),
        "tests": "RVS core assumption: thesis >> thumbnail",
        "expected_winner": "A",
        "rvs_weight_A": 100,
        "rvs_weight_B": 1,
    },
    {
        "id": "P02",
        "pair": ("familia_navidad.jpg", "thumbnail_001.jpg"),
        "tests": "Family photo vs thumbnail (same format, different value)",
        "expected_winner": "A",
        "rvs_weight_A": 90,
        "rvs_weight_B": 1,
    },
    # ── Value vs replaceability ──
    {
        "id": "P03",
        "pair": ("tesis_final.docx", "ubuntu-22.04.iso"),
        "tests": "Irreplaceable vs downloadable (high value, low replaceability)",
        "expected_winner": "A",
        "rvs_weight_A": 100,
        "rvs_weight_B": 2,
    },
    {
        "id": "P04",
        "pair": ("pelicula_descargada.mp4", "video_vacaciones.mov"),
        "tests": "Downloadable vs irreplaceable video (same format, different replaceability)",
        "expected_winner": "B",
        "rvs_weight_A": 20,
        "rvs_weight_B": 70,
    },
    # ── RAW vs processed ──
    {
        "id": "P05",
        "pair": ("foto_RAW.cr2", "foto_editada.jpg"),
        "tests": "RAW source vs processed version (photographers may differ)",
        "expected_winner": "A",
        "rvs_weight_A": 60,
        "rvs_weight_B": 90,
        "note": "This is a critical test: if photographers choose RAW but non-photographers choose JPG, RVS needs population-specific weights.",
    },
    # ── Database vs documents ──
    {
        "id": "P06",
        "pair": ("clientes.sqlite", "contrato_firmado.pdf"),
        "tests": "Database vs legal document (businesses may differ from home users)",
        "expected_winner": "A",
        "rvs_weight_A": 95,
        "rvs_weight_B": 65,
        "note": "Population-dependent: businesses value databases, home users value documents.",
    },
    # ── Emotional vs economic value ──
    {
        "id": "P07",
        "pair": ("foto_familia.jpg", "proyecto_psd.psd"),
        "tests": "Emotional value vs economic value",
        "expected_winner": "A",
        "rvs_weight_A": 90,
        "rvs_weight_B": 65,
        "note": "This tests whether emotional impact (family photo) outweighs economic value (work project).",
    },
    # ── Size vs value ──
    {
        "id": "P08",
        "pair": ("base_datos_grande.sqlite", "tesis_final.docx"),
        "tests": "Large file vs small but irreplaceable file",
        "expected_winner": "B",
        "rvs_weight_A": 95,
        "rvs_weight_B": 100,
        "note": "Both high value. Tests whether size matters when value is similar.",
    },
    # ── MP4 vs DOCX ──
    {
        "id": "P09",
        "pair": ("video_importante.mp4", "informe_anual.docx"),
        "tests": "Video vs document (different media, different value systems)",
        "expected_winner": "B",
        "rvs_weight_A": 70,
        "rvs_weight_B": 65,
        "note": "Close call. This tests the boundary between medium-value categories.",
    },
    # ── SQLite vs DOCX ──
    {
        "id": "P10",
        "pair": ("clientes.sqlite", "tesis_final.docx"),
        "tests": "Database vs thesis (both high value, different type)",
        "expected_winner": "B",
        "rvs_weight_A": 95,
        "rvs_weight_B": 100,
        "note": "Near-tie. This tests the top of the value hierarchy.",
    },
    # ── Thumbnails vs contract ──
    {
        "id": "P11",
        "pair": ("200_thumbnails/", "contrato_firmado.pdf"),
        "tests": "Many low-value files vs one high-value file",
        "expected_winner": "B",
        "rvs_weight_A": 1,
        "rvs_weight_B": 65,
        "note": "Quantity vs quality. Tests whether the RVS model correctly discounts quantity.",
    },
    # ── Family photo vs MP4 ──
    {
        "id": "P12",
        "pair": ("foto_familia.jpg", "pelicula_descargada.mp4"),
        "tests": "Irreplaceable photo vs downloadable movie",
        "expected_winner": "A",
        "rvs_weight_A": 90,
        "rvs_weight_B": 20,
    },
]


# ─── Population Definitions ──────────────────────────────────────────────────

POPULATIONS = {
    "photographers": {
        "name": "Fotografos profesionales",
        "description": "Valoran RAW y fotos familiares, desprecian ISO y thumbnails",
        "expected_bias": "Will choose RAW over processed, family photos over everything else",
        "min_responses": 30,
    },
    "legal": {
        "name": "Estudios juridicos",
        "description": "Valoran documentos y bases de datos, desprecian thumbnails",
        "expected_bias": "Will choose contracts and databases over photos and videos",
        "min_responses": 30,
    },
    "tech": {
        "name": "Empresas de tecnologia",
        "description": "Valoran bases de datos y codigo, desprecian ISO",
        "expected_bias": "Will choose databases over documents, code over photos",
        "min_responses": 30,
    },
    "home": {
        "name": "Usuarios domesticos",
        "description": "Valoran fotos y videos familiares, desprecian archivos de sistema",
        "expected_bias": "Will choose family photos and videos over everything else",
        "min_responses": 30,
    },
    "students": {
        "name": "Estudiantes",
        "description": "Valoran tesis y documentos, desprecian thumbnails",
        "expected_bias": "Will choose thesis and documents over everything else",
        "min_responses": 30,
    },
}


@dataclass
class SurveyResponse:
    """A single response to the survey."""
    respondent_id: str
    population: str
    pair_id: str
    choice: str          # "A" or "B"
    confidence: float = 0.0  # 0.0-1.0 how confident the respondent was
    timestamp: str = ""


@dataclass
class BradleyTerryModel:
    """
    Bradley-Terry model for pairwise comparison data.

    Given a set of pairwise comparisons, estimates the merit (worth) of
    each item. The probability that item i is preferred over item j is:

        P(i > j) = merit_i / (merit_i + merit_j)

    This produces a continuous ranking that can be used to calibrate RVS weights.

    Uses the standard MM algorithm where:
      merit_i = W_i / sum_j( n_ij / (merit_i + merit_j) )

    where W_i = total wins of item i, n_ij = total comparisons between i and j.
    """
    items: List[str] = field(default_factory=list)
    merits: Dict[str, float] = field(default_factory=dict)
    # Stores (i, j) -> (i_wins, j_wins) — always ordered by first appearance
    pair_counts: Dict[Tuple[str, str], Tuple[int, int]] = field(default_factory=dict)

    def _get_pair_key(self, a: str, b: str) -> Tuple[str, str]:
        """Get canonical key for a pair (always same order)."""
        return (a, b) if a <= b else (b, a)

    def add_comparison(self, winner: str, loser: str):
        """Record that winner was preferred over loser."""
        key = self._get_pair_key(winner, loser)
        if key not in self.pair_counts:
            self.pair_counts[key] = (0, 0)

        a_wins, b_wins = self.pair_counts[key]
        # key = (a, b) where a <= b lexicographically
        if winner == key[0]:
            self.pair_counts[key] = (a_wins + 1, b_wins)
        else:
            self.pair_counts[key] = (a_wins, b_wins + 1)

        if winner not in self.items:
            self.items.append(winner)
        if loser not in self.items:
            self.items.append(loser)

    def fit(self, iterations: int = 200):
        """
        Fit the Bradley-Terry model using iterative MM algorithm.

        Returns a dict of item -> merit score.
        """
        # Initialize all merits to 1.0
        for item in self.items:
            self.merits[item] = 1.0

        for _ in range(iterations):
            new_merits = {}
            for item in self.items:
                # W_i = total wins of item i
                total_wins = 0.0
                denominator = 0.0

                for (a, b), (a_wins, b_wins) in self.pair_counts.items():
                    if item not in (a, b):
                        continue

                    n_ij = a_wins + b_wins  # total comparisons in this pair
                    other = b if item == a else a

                    if item == a:
                        total_wins += a_wins
                    else:
                        total_wins += b_wins

                    # n_ij / (merit_i + merit_j)
                    denom_contribution = n_ij / (self.merits[item] + self.merits[other])
                    denominator += denom_contribution

                if denominator > 0:
                    new_merits[item] = total_wins / denominator
                else:
                    new_merits[item] = self.merits[item]

            # Normalize so the minimum merit is 1.0
            min_merit = min(new_merits.values())
            if min_merit > 0:
                for item in new_merits:
                    new_merits[item] /= min_merit

            self.merits = new_merits

        return self.merits

    def predict(self, item_a: str, item_b: str) -> float:
        """Predict probability that item_a is preferred over item_b."""
        ma = self.merits.get(item_a, 1.0)
        mb = self.merits.get(item_b, 1.0)
        return ma / (ma + mb)

    def to_rvs_weights(self, scale: float = 100.0) -> Dict[str, float]:
        """
        Convert Bradley-Terry merits to RVS-style weights (0-100 scale).

        The highest merit item gets weight 100. Others are scaled proportionally.
        """
        if not self.merits:
            return {}

        max_merit = max(self.merits.values())
        if max_merit == 0:
            return {k: 0.0 for k in self.merits}

        return {
            item: round(merit / max_merit * scale, 1)
            for item, merit in self.merits.items()
        }


@dataclass
class RVSExperiment:
    """
    The complete RVS calibration experiment.

    This is the experiment that validates whether the RVS model
    reflects real user preferences.
    """
    responses: List[SurveyResponse] = field(default_factory=list)
    model: BradleyTerryModel = field(default_factory=BradleyTerryModel)

    def add_response(self, response: SurveyResponse):
        """Add a survey response and update the Bradley-Terry model."""
        self.responses.append(response)

        # Find the pair
        pair = next((p for p in SURVEY_PAIRS if p["id"] == response.pair_id), None)
        if pair is None:
            return

        file_a, file_b = pair["pair"]
        winner = file_a if response.choice == "A" else file_b
        loser = file_b if response.choice == "A" else file_a

        self.model.add_comparison(winner, loser)

    def analyze(self) -> Dict:
        """Run the full analysis and return results."""
        merits = self.model.fit()

        # Compare with current RVS weights
        current_rvs = {
            "tesis_final.docx": 100,
            "clientes.sqlite": 95,
            "familia_navidad.jpg": 90,
            "video_vacaciones.mov": 70,
            "proyecto_psd.psd": 65,
            "foto_RAW.cr2": 60,
            "pelicula_descargada.mp4": 20,
            "ubuntu-22.04.iso": 2,
            "thumbnail_001.jpg": 1,
            "thumbnail_cache.db": 1,
            "contrato_firmado.pdf": 65,
            "foto_editada.jpg": 90,
            "foto_familia.jpg": 90,
            "informe_anual.docx": 65,
            "base_datos_grande.sqlite": 95,
            "200_thumbnails/": 1,
        }

        calibrated = self.model.to_rvs_weights()

        # Calculate discrepancy
        discrepancies = {}
        for item in calibrated:
            current = current_rvs.get(item, 50)
            cal = calibrated[item]
            discrepancies[item] = {
                "current_rvs": current,
                "calibrated_rvs": cal,
                "difference": cal - current,
                "pct_change": round((cal - current) / max(current, 1) * 100, 1),
            }

        return {
            "total_responses": len(self.responses),
            "populations": len(set(r.population for r in self.responses)),
            "merits": merits,
            "calibrated_weights": calibrated,
            "discrepancies": discrepancies,
            "needs_recalibration": any(
                abs(d["pct_change"]) > 20 for d in discrepancies.values()
            ),
        }

    def generate_survey_markdown(self) -> str:
        """Generate a markdown version of the survey for distribution."""
        lines = [
            "# RecoveryLab — RVS Calibration Survey",
            "",
            "## Instrucciones",
            "",
            "Para cada par de archivos, elige cual preferirias recuperar",
            "si solo pudieras recuperar UNO de los dos.",
            "",
            "No hay respuesta correcta o incorrecta.",
            "Tu respuesta nos ayuda a calibrar un modelo de valor",
            "para herramientas de recuperacion de datos.",
            "",
            "---",
            "",
        ]

        for i, pair in enumerate(SURVEY_PAIRS, 1):
            file_a, file_b = pair["pair"]
            lines.extend([
                f"## Pregunta {i} ({pair['id']})",
                "",
                f"**A:** `{file_a}`",
                "",
                f"**B:** `{file_b}`",
                "",
                f"Tu eleccion: [ ] A  [ ] B",
                "",
                f"Confianza: [ ] Muy seguro  [ ] Seguro  [ ] Dudo",
                "",
                "---",
                "",
            ])

        lines.extend([
            "## Datos demograficos (opcional)",
            "",
            "Perfil: [ ] Fotografo  [ ] Juridico  [ ] Tecnologia  [ ] Hogar  [ ] Estudiante  [ ] Otro",
            "",
            "---",
            "",
            "Gracias por participar.",
        ])

        return "\n".join(lines)


if __name__ == "__main__":
    # Generate the survey
    exp = RVSExperiment()

    # Save survey as markdown
    survey_path = "/home/z/my-project/RecoveryLab/data/rvs_calibration_survey.md"
    os.makedirs(os.path.dirname(survey_path), exist_ok=True)
    with open(survey_path, "w", encoding="utf-8") as f:
        f.write(exp.generate_survey_markdown())
    print(f"Survey saved to: {survey_path}")

    # Simulate with synthetic data to verify the pipeline works
    print("\n--- Synthetic Simulation (verifying pipeline) ---\n")

    random.seed(42)
    for pop_id, pop in POPULATIONS.items():
        for _ in range(30):  # 30 respondents per population
            for pair in SURVEY_PAIRS:
                # Use RVS weights to simulate "expected" choices with some noise
                weight_a = pair["rvs_weight_A"]
                weight_b = pair["rvs_weight_B"]
                prob_a = weight_a / (weight_a + weight_b)

                # Add noise (10% chance of choosing the "wrong" option)
                noise = random.gauss(0, 0.05)
                prob_a = max(0.05, min(0.95, prob_a + noise))

                choice = "A" if random.random() < prob_a else "B"

                response = SurveyResponse(
                    respondent_id=f"{pop_id}_{random.randint(1000, 9999)}",
                    population=pop_id,
                    pair_id=pair["id"],
                    choice=choice,
                    confidence=random.uniform(0.5, 1.0),
                )
                exp.add_response(response)

    # Analyze
    results = exp.analyze()
    print(f"Total responses: {results['total_responses']}")
    print(f"Populations: {results['populations']}")
    print(f"\nCalibrated RVS weights (0-100 scale):")
    for item, weight in sorted(results['calibrated_weights'].items(), key=lambda x: -x[1]):
        disc = results['discrepancies'].get(item, {})
        current = disc.get('current_rvs', '?')
        diff = disc.get('pct_change', 0)
        print(f"  {item:35s} | Calibrated: {weight:5.1f} | Current: {current:5} | Diff: {diff:+.1f}%")

    print(f"\nNeeds recalibration: {results['needs_recalibration']}")

    # Save experiment design as JSON
    design_path = "/home/z/my-project/RecoveryLab/data/rvs_experiment_design.json"
    design = {
        "experiment_id": "EXP-RVS-CAL",
        "type": "HUMAN",
        "title": "RVS Calibration Experiment — Bradley-Terry Pairwise Comparison",
        "purpose": "Validate whether the RVS value weights reflect real user preferences",
        "method": "Bradley-Terry pairwise comparison",
        "pairs": SURVEY_PAIRS,
        "populations": POPULATIONS,
        "min_total_responses": 150,
        "current_rvs_weights": {
            "tesis_final.docx": 100,
            "clientes.sqlite": 95,
            "familia_navidad.jpg": 90,
            "video_vacaciones.mov": 70,
            "proyecto_psd.psd": 65,
            "foto_RAW.cr2": 60,
            "pelicula_descargada.mp4": 20,
            "ubuntu-22.04.iso": 2,
            "thumbnail_001.jpg": 1,
        },
        "status": "DESIGNED",
        "next_step": "Distribute survey to 5 target populations",
    }
    with open(design_path, "w", encoding="utf-8") as f:
        json.dump(design, f, indent=2, ensure_ascii=False)
    print(f"\nExperiment design saved to: {design_path}")
