"""
digitalsoma/veddra/veddra_rules.py
Species-aware VeDDRA adverse event rule sets for DigitalSoma v3.0.0.

Each rule is a dict with:
    pt_code  : VeDDRA PT code (str) — key into VEDDRA_TERMS
    key      : canonical state key to evaluate
    op       : comparison operator — 'gt' | 'lt'
    ref      : ATR parameter key for the species baseline value (optional)
    factor   : multiply ref by this (for relative thresholds)
    offset   : add/subtract from ref (for absolute offsets)
    absolute : fixed threshold value (used when no species ref exists)

Threshold logic:
    If 'ref' given:
        gt → state[key] > params[ref] * factor + offset
        lt → state[key] < params[ref] * factor - offset
    If 'absolute' given:
        gt → state[key] > absolute
        lt → state[key] < absolute

Author: Dr. ir. Ali Youssef (ORCID: 0000-0002-9986-5324)
        Digital Agroecosystems Laboratory, University of Manitoba &
        BioTwinR Ltd., Leuven, Belgium
"""

from typing import Dict, List, Any

# ---------------------------------------------------------------------------
# Rule builder helpers — keep rule definitions readable
# ---------------------------------------------------------------------------

def _gt_ref(pt_code, key, ref, factor=1.0, offset=0.0):
    """Fires when state[key] > params[ref] * factor + offset."""
    return {"pt_code": pt_code, "key": key, "op": "gt",
            "ref": ref, "factor": factor, "offset": offset}

def _lt_ref(pt_code, key, ref, factor=1.0, offset=0.0):
    """Fires when state[key] < params[ref] * factor - offset."""
    return {"pt_code": pt_code, "key": key, "op": "lt",
            "ref": ref, "factor": factor, "offset": offset}

def _gt_abs(pt_code, key, absolute):
    """Fires when state[key] > absolute."""
    return {"pt_code": pt_code, "key": key, "op": "gt", "absolute": absolute}

def _lt_abs(pt_code, key, absolute):
    """Fires when state[key] < absolute."""
    return {"pt_code": pt_code, "key": key, "op": "lt", "absolute": absolute}

# ---------------------------------------------------------------------------
# Universal rules — apply to all endotherm species
# These 6 existed in v2.x but with incorrect codes; now corrected.
# ---------------------------------------------------------------------------

_UNIVERSAL_ENDOTHERM: List[Dict[str, Any]] = [
    # Hyperthermia  — T_core > T_base + 1.5°C
    _gt_ref("604", "core_temp_C",     "core_temp_normal_C", factor=1.0, offset=1.5),
    # Hypothermia   — T_core < T_base − 2.0°C
    _lt_ref("605", "core_temp_C",     "core_temp_normal_C", factor=1.0, offset=2.0),
    # Tachycardia   — HR > HR_base × 1.5
    _gt_ref("122", "heart_rate_bpm",  "hr_normal_bpm",      factor=1.5),
    # Bradycardia   — HR < HR_base × 0.6
    _lt_ref("120", "heart_rate_bpm",  "hr_normal_bpm",      factor=0.6),
    # Hypoxia       — SpO₂ < 90%
    _lt_abs("501", "spo2_pct",        90.0),
    # Tachypnoea    — RR > RR_base × 1.5
    _gt_ref("515", "respiratory_rate_bpm", "rr_normal_bpm", factor=1.5),
    # Bradypnoea    — RR < RR_base × 0.5
    _lt_ref("504", "respiratory_rate_bpm", "rr_normal_bpm", factor=0.5),
    # Dyspnoea      — PSI > 0.70 (composite stress + respiratory failure)
    _gt_abs("506", "physiological_stress_index", 0.70),
]

# ---------------------------------------------------------------------------
# Species-specific rule sets
# Each set = universal endotherm rules + species-specific additions
# ---------------------------------------------------------------------------

# ── Sus scrofa domesticus (pig) ──────────────────────────────────────────────
# Pigs have very few sweat glands — thermal stress escalates rapidly.
# Heat stress is the dominant welfare risk in commercial porcine production.
# Glucose dysregulation is common under HPA activation.

_PORCINE_EXTRA: List[Dict[str, Any]] = [
    # Hypoglycaemia — glucose < 3.0 mmol/L (stress/neonatal hypoglycaemia)
    _lt_abs("904", "blood_glucose_mmol_L", 3.0),
    # Hyperglycaemia — glucose > 8.0 mmol/L (stress hyperglycaemia)
    _gt_abs("903", "blood_glucose_mmol_L", 8.0),
    # Dehydration — haematocrit > 48% (haemoconcentration in heat stress)
    _gt_abs("657", "haematocrit_pct",     48.0),
    # Anaemia — haemoglobin < 8.0 g/dL
    _lt_abs("85",  "haemoglobin_g_dL",    8.0),
    # Cyanosis — SpO₂ < 86% (severe hypoxaemia beyond Hypoxia threshold)
    _lt_abs("601", "spo2_pct",            86.0),
]

# ── Equus caballus (horse) ───────────────────────────────────────────────────
# High-performance sport animal. Post-exercise rhabdomyolysis risk.
# Haemoconcentration common after prolonged exertion.

_EQUINE_EXTRA: List[Dict[str, Any]] = [
    # Hypoglycaemia — glucose < 3.5 mmol/L
    _lt_abs("904", "blood_glucose_mmol_L", 3.5),
    # Dehydration — haematocrit > 52%
    _gt_abs("657", "haematocrit_pct",     52.0),
    # Anaemia — haemoglobin < 8.0 g/dL
    _lt_abs("85",  "haemoglobin_g_dL",    8.0),
    # Cyanosis — SpO₂ < 88%
    _lt_abs("601", "spo2_pct",            88.0),
]

# ── Bos taurus (cattle) ──────────────────────────────────────────────────────
# Ruminant. Heat stress risk in intensive dairy. Lower glucose threshold.

_BOVINE_EXTRA: List[Dict[str, Any]] = [
    # Hypoglycaemia — glucose < 2.5 mmol/L (bovine baseline is lower)
    _lt_abs("904", "blood_glucose_mmol_L", 2.5),
    # Hyperglycaemia — glucose > 7.0 mmol/L
    _gt_abs("903", "blood_glucose_mmol_L", 7.0),
    # Dehydration — haematocrit > 45%
    _gt_abs("657", "haematocrit_pct",     45.0),
    # Anaemia — haemoglobin < 7.0 g/dL
    _lt_abs("85",  "haemoglobin_g_dL",    7.0),
]

# ── Ovis aries (sheep) ───────────────────────────────────────────────────────
# Similar to bovine; more susceptible to anaemia.

_OVINE_EXTRA: List[Dict[str, Any]] = [
    # Hypoglycaemia — glucose < 2.8 mmol/L
    _lt_abs("904", "blood_glucose_mmol_L", 2.8),
    # Dehydration — haematocrit > 46%
    _gt_abs("657", "haematocrit_pct",     46.0),
    # Anaemia — haemoglobin < 7.0 g/dL
    _lt_abs("85",  "haemoglobin_g_dL",    7.0),
    # Cyanosis — SpO₂ < 88%
    _lt_abs("601", "spo2_pct",            88.0),
]

# ── Canis lupus familiaris (dog) ─────────────────────────────────────────────
# Companion animal. Panting is primary thermal regulation — monitor carefully.

_CANINE_EXTRA: List[Dict[str, Any]] = [
    # Hypoglycaemia — glucose < 3.3 mmol/L
    _lt_abs("904", "blood_glucose_mmol_L", 3.3),
    # Hyperglycaemia — glucose > 8.0 mmol/L (diabetes mellitus risk)
    _gt_abs("903", "blood_glucose_mmol_L", 8.0),
    # Dehydration — haematocrit > 55%
    _gt_abs("657", "haematocrit_pct",     55.0),
    # Anaemia — haemoglobin < 7.0 g/dL
    _lt_abs("85",  "haemoglobin_g_dL",    7.0),
    # Cyanosis — SpO₂ < 88%
    _lt_abs("601", "spo2_pct",            88.0),
]

# ── Salmo salar (Atlantic salmon) ────────────────────────────────────────────
# Ectotherm — no body temperature thresholds.
# Oxygen saturation critical in aquaculture (dissolved O₂ proxy via SpO₂).
# Limited sensor coverage — minimal rule set.

_SALMONID_RULES: List[Dict[str, Any]] = [
    # Tachycardia — HR > HR_base × 1.5
    _gt_ref("122", "heart_rate_bpm", "hr_normal_bpm", factor=1.5),
    # Bradycardia — HR < HR_base × 0.6
    _lt_ref("120", "heart_rate_bpm", "hr_normal_bpm", factor=0.6),
    # Hypoxia — SpO₂ < 80% (lower threshold for fish)
    _lt_abs("501", "spo2_pct", 80.0),
    # Dyspnoea (gill distress) — PSI > 0.70
    _gt_abs("506", "physiological_stress_index", 0.70),
]

# ---------------------------------------------------------------------------
# Assembled species rule sets
# ---------------------------------------------------------------------------

SPECIES_RULES: Dict[str, List[Dict[str, Any]]] = {
    "porcine_adult":  _UNIVERSAL_ENDOTHERM + _PORCINE_EXTRA,
    "equine_adult":   _UNIVERSAL_ENDOTHERM + _EQUINE_EXTRA,
    "bovine_adult":   _UNIVERSAL_ENDOTHERM + _BOVINE_EXTRA,
    "ovine_adult":    _UNIVERSAL_ENDOTHERM + _OVINE_EXTRA,
    "canine_adult":   _UNIVERSAL_ENDOTHERM + _CANINE_EXTRA,
    "salmonid_adult": _SALMONID_RULES,
}


def get_rules_for_species(animal_type: str) -> List[Dict[str, Any]]:
    """
    Return the VeDDRA rule set for a given ATR animal_type key.

    Falls back to universal endotherm rules if the species is not
    explicitly listed — so custom ATR species still get basic screening.

    Parameters
    ----------
    animal_type : str — ATR key (e.g. 'porcine_adult')

    Returns
    -------
    list of rule dicts
    """
    return SPECIES_RULES.get(animal_type, _UNIVERSAL_ENDOTHERM)


def rule_count(animal_type: str) -> int:
    """Return the number of VeDDRA rules for a given species."""
    return len(get_rules_for_species(animal_type))
