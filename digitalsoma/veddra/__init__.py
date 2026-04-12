"""digitalsoma.veddra — VeDDRA v2.2 vocabulary and species-aware rule engine."""

from digitalsoma.veddra.veddra_terms import VEDDRA_TERMS
from digitalsoma.veddra.veddra_rules import SPECIES_RULES, get_rules_for_species

__all__ = ["VEDDRA_TERMS", "SPECIES_RULES", "get_rules_for_species"]
