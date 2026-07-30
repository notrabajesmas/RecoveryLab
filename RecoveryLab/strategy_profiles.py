"""
RecoveryLab — Strategy Profiles (Ficha Técnica)
=================================================
Each strategy has a formal spec sheet that defines EXACTLY what data sources
it uses. This prevents ambiguous comparisons.

The user's insight: "Cada estrategia tendría una ficha técnica."
If two strategies share the same data sources, they're not really different.

Strategy           | Uses MFT | Uses Signatures | Uses Journal | Uses Bitmap
-------------------|----------|-----------------|--------------|------------
Carving            | NO       | YES             | NO           | NO
MFT-Only           | YES      | NO              | NO           | NO
Hybrid             | YES      | YES             | NO           | NO
Motor C            | Adaptive | Adaptive        | Adaptive     | Adaptive
"""

from dataclasses import dataclass, field
from typing import Set, Dict, Optional


@dataclass
class StrategyProfile:
    """Ficha técnica de una estrategia de recuperación."""
    name: str
    description: str

    # Data sources used
    uses_mft: bool = False
    uses_signatures: bool = False
    uses_journal: bool = False
    uses_bitmap: bool = False
    uses_indx: bool = False
    uses_vbr: bool = False

    # Recovery characteristics
    supports_filenames: bool = False
    supports_directories: bool = False
    supports_fragmentation: bool = False
    supports_resident_files: bool = False

    # Risk profile
    false_positive_risk: str = "LOW"    # LOW / MEDIUM / HIGH
    read_cost: str = "VARIABLE"          # LOW / MEDIUM / HIGH / VARIABLE
    metadata_dependency: str = "NONE"    # NONE / PARTIAL / FULL

    def data_sources(self) -> Set[str]:
        """Return the set of data sources this strategy uses."""
        sources = set()
        if self.uses_mft:
            sources.add("MFT")
        if self.uses_signatures:
            sources.add("Signatures")
        if self.uses_journal:
            sources.add("Journal")
        if self.uses_bitmap:
            sources.add("Bitmap")
        if self.uses_indx:
            sources.add("INDX")
        if self.uses_vbr:
            sources.add("VBR")
        return sources

    def is_truly_different_from(self, other: "StrategyProfile") -> bool:
        """
        Two strategies are truly different if their data source sets differ.

        If strategy A uses {MFT} and strategy B uses {MFT, VBR},
        they're NOT truly different — B is just A with one extra source.
        Both depend on MFT.

        Truly different strategies have DISJOINT data source sets,
        or at minimum, their PRIMARY data source is different.
        """
        my_sources = self.data_sources()
        other_sources = other.data_sources()

        # If they share the same primary source, they're not truly different
        if my_sources == other_sources:
            return False

        # Check if primary data source is different
        my_primary = self._primary_source()
        other_primary = other._primary_source()

        return my_primary != other_primary

    def _primary_source(self) -> str:
        """Return the primary data source this strategy depends on."""
        if self.uses_mft:
            return "MFT"
        if self.uses_signatures:
            return "Signatures"
        if self.uses_journal:
            return "Journal"
        if self.uses_bitmap:
            return "Bitmap"
        return "None"

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "data_sources": sorted(self.data_sources()),
            "primary_source": self._primary_source(),
            "uses_mft": self.uses_mft,
            "uses_signatures": self.uses_signatures,
            "uses_journal": self.uses_journal,
            "uses_bitmap": self.uses_bitmap,
            "uses_indx": self.uses_indx,
            "uses_vbr": self.uses_vbr,
            "supports_filenames": self.supports_filenames,
            "supports_directories": self.supports_directories,
            "supports_fragmentation": self.supports_fragmentation,
            "supports_resident_files": self.supports_resident_files,
            "false_positive_risk": self.false_positive_risk,
            "read_cost": self.read_cost,
            "metadata_dependency": self.metadata_dependency,
        }

    def to_markdown_row(self) -> str:
        """Format as a markdown table row."""
        def check(v: bool) -> str:
            return "YES" if v else "NO"

        return (
            f"| {self.name:20s} | {check(self.uses_mft):3s} | "
            f"{check(self.uses_signatures):3s} | {check(self.uses_journal):3s} | "
            f"{check(self.uses_bitmap):3s} | {check(self.uses_vbr):3s} | "
            f"{self._primary_source():12s} |"
        )


# ─── Registered Strategy Profiles ─────────────────────────────────────────────

STRATEGY_CARVING = StrategyProfile(
    name="Carving",
    description="Signature-based recovery. Scans raw bytes for file headers. Never reads filesystem metadata.",
    uses_mft=False,
    uses_signatures=True,
    uses_journal=False,
    uses_bitmap=False,
    uses_indx=False,
    uses_vbr=False,
    supports_filenames=False,
    supports_directories=False,
    supports_fragmentation=False,
    supports_resident_files=False,
    false_positive_risk="MEDIUM",
    read_cost="HIGH",
    metadata_dependency="NONE",
)

STRATEGY_MFT_ONLY = StrategyProfile(
    name="MFT-Only",
    description="MFT-guided recovery. Reads VBR to find MFT, then reads only MFT-referenced clusters. No carving.",
    uses_mft=True,
    uses_signatures=False,
    uses_journal=False,
    uses_bitmap=False,
    uses_indx=False,
    uses_vbr=True,
    supports_filenames=True,
    supports_directories=True,
    supports_fragmentation=True,
    supports_resident_files=True,
    false_positive_risk="LOW",
    read_cost="LOW",
    metadata_dependency="FULL",
)

STRATEGY_MFT_SEQUENTIAL = StrategyProfile(
    name="MFT-Sequential",
    description="Reads all clusters sequentially, then parses MFT. Same data source as MFT-Only, different read order.",
    uses_mft=True,
    uses_signatures=False,
    uses_journal=False,
    uses_bitmap=False,
    uses_indx=False,
    uses_vbr=True,
    supports_filenames=True,
    supports_directories=True,
    supports_fragmentation=True,
    supports_resident_files=True,
    false_positive_risk="LOW",
    read_cost="HIGH",
    metadata_dependency="FULL",
)

STRATEGY_HYBRID = StrategyProfile(
    name="Hybrid",
    description="MFT-guided recovery with carving fallback. Uses MFT when available, falls back to signatures.",
    uses_mft=True,
    uses_signatures=True,
    uses_journal=False,
    uses_bitmap=False,
    uses_indx=False,
    uses_vbr=True,
    supports_filenames=True,
    supports_directories=True,
    supports_fragmentation=True,
    supports_resident_files=True,
    false_positive_risk="LOW",
    read_cost="VARIABLE",
    metadata_dependency="PARTIAL",
)

STRATEGY_MOTOR_C = StrategyProfile(
    name="Motor C",
    description="Adaptive orchestrator. Diagnoses disk state, selects optimal strategy based on confidence.",
    uses_mft=True,   # Adaptive
    uses_signatures=True,  # Adaptive
    uses_journal=True,     # Adaptive
    uses_bitmap=True,      # Adaptive
    uses_indx=True,        # Adaptive
    uses_vbr=True,
    supports_filenames=True,
    supports_directories=True,
    supports_fragmentation=True,
    supports_resident_files=True,
    false_positive_risk="LOW",
    read_cost="VARIABLE",
    metadata_dependency="ADAPTIVE",
)


# ─── All registered strategies ─────────────────────────────────────────────────

ALL_STRATEGIES = {
    "carving": STRATEGY_CARVING,
    "mft_only": STRATEGY_MFT_ONLY,
    "mft_sequential": STRATEGY_MFT_SEQUENTIAL,
    "hybrid": STRATEGY_HYBRID,
    "motor_c": STRATEGY_MOTOR_C,
}


def validate_comparison(profile_a: StrategyProfile, profile_b: StrategyProfile) -> Dict:
    """
    Validate that two strategies are genuinely different enough to compare.

    Returns a dict with:
      - valid: bool — whether the comparison is scientifically valid
      - reason: str — explanation
      - shared_sources: Set[str] — data sources both use
      - unique_a: Set[str] — sources only A uses
      - unique_b: Set[str] — sources only B uses
    """
    sources_a = profile_a.data_sources()
    sources_b = profile_b.data_sources()

    shared = sources_a & sources_b
    unique_a = sources_a - sources_b
    unique_b = sources_b - sources_a

    is_valid = profile_a.is_truly_different_from(profile_b)

    if not is_valid:
        reason = (
            f"NOT VALID: Both strategies share the same primary data source "
            f"({profile_a._primary_source()}). They differ only in read order "
            f"or implementation details, not in fundamental approach."
        )
    else:
        reason = (
            f"VALID: Strategies have different primary data sources "
            f"({profile_a._primary_source()} vs {profile_b._primary_source()}). "
            f"This is a genuine comparison of different recovery philosophies."
        )

    return {
        "valid": is_valid,
        "reason": reason,
        "shared_sources": sorted(shared),
        "unique_a": sorted(unique_a),
        "unique_b": sorted(unique_b),
    }


def print_strategy_comparison_table():
    """Print the strategy comparison table in markdown format."""
    print("| Strategy             | MFT | Sig | Jnl | Bmp | VBR | Primary      |")
    print("|----------------------|-----|-----|-----|-----|-----|--------------|")
    for s in ALL_STRATEGIES.values():
        print(s.to_markdown_row())

    print()
    print("## Comparison Validation")
    print()

    # Check all pairwise comparisons
    strategy_list = list(ALL_STRATEGIES.items())
    for i in range(len(strategy_list)):
        for j in range(i + 1, len(strategy_list)):
            name_a, prof_a = strategy_list[i]
            name_b, prof_b = strategy_list[j]
            result = validate_comparison(prof_a, prof_b)
            status = "VALID" if result["valid"] else "NOT VALID"
            print(f"  {name_a} vs {name_b}: {status}")
            if not result["valid"]:
                print(f"    → {result['reason']}")


if __name__ == "__main__":
    print_strategy_comparison_table()
