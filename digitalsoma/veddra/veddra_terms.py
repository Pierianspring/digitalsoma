"""
digitalsoma/veddra/veddra_terms.py
VeDDRA clinical sign vocabulary for DigitalSoma.

Derived from:
    Combined Veterinary Dictionary for Drug Regulatory Activities (VeDDRA)
    EMA/CVMP/PhVWP/10418/2009 Rev.16
    Effective: 1 October 2025
    Source: https://www.ema.europa.eu/en/veterinary-regulatory-overview/
            post-authorisation-veterinary-medicines/pharmacovigilance-veterinary-medicines/
            eudravigilance-veterinary

This file contains the subset of VeDDRA Preferred Terms (PT) selected for
computational implementation in DigitalSoma v3.0.0 — terms whose trigger
conditions can be derived from physiological sensor data and solver outputs.

Full VeDDRA vocabulary (4,623 terms across SOC/HLT/PT/LLT levels) is
available from the EMA website as the "dataload friendly file".

Structure:
    VEDDRA_TERMS[pt_code] = {
        "preferred_term": str,      PT-level clinical sign name
        "hlt":            str,      High Level Term (parent)
        "soc":            str,      System Organ Class (grandparent)
        "snomed":         str|None, SNOMED CT concept ID (if mapped)
        "deprecated":     bool,     False for all active terms
        "llt_codes":      list,     Low Level Term codes that map to this PT
        "llt_names":      list,     LLT display names for reporting
    }

Note on code format:
    VeDDRA uses short integer codes (1–3343) at all levels.
    The same integer may appear at different levels (SOC/HLT/PT/LLT) —
    terms are identified by BOTH their code AND their level.
    This dictionary stores PT-level codes only.

Note on previously used codes:
    DigitalSoma v2.x used 8-digit codes (e.g. 10020557) which were incorrect
    and did not exist in the official EMA VeDDRA file. v3.0.0 corrects all
    codes to the official EMA Rev.16 PT codes.

Author: Dr. ir. Ali Youssef (ORCID: 0000-0002-9986-5324)
        Digital Agroecosystems Laboratory, University of Manitoba &
        BioTwinR Ltd., Leuven, Belgium
"""

from typing import Dict, Any

# ---------------------------------------------------------------------------
# VeDDRA Preferred Term dictionary
# Key: PT code (string) from EMA Rev.16
# ---------------------------------------------------------------------------

VEDDRA_TERMS: Dict[str, Dict[str, Any]] = {

    # ── Cardiovascular ───────────────────────────────────────────────────────
    "122": {
        "preferred_term": "Tachycardia",
        "hlt":            "Cardiac rhythm disorders",
        "soc":            "Cardio-vascular system disorders",
        "snomed":         "3424008",
        "deprecated":     False,
        "llt_codes":      ["192", "193", "1514", "1670", "1719", "2522"],
        "llt_names":      ["Tachycardia", "Increased heart rate", "Heart pounding",
                           "Palpitation", "Rapid pulse rate", "Bounding pulse"],
    },
    "120": {
        "preferred_term": "Bradycardia",
        "hlt":            "Cardiac rhythm disorders",
        "soc":            "Cardio-vascular system disorders",
        "snomed":         "48867003",
        "deprecated":     False,
        "llt_codes":      ["188", "189", "190", "1060"],
        "llt_names":      ["Bradycardia", "Decreased heart rate",
                           "Slow heart rate", "Cardiac depression"],
    },

    # ── Respiratory ──────────────────────────────────────────────────────────
    "501": {
        "preferred_term": "Hypoxia",
        "hlt":            "Bronchial and lung disorders",
        "soc":            "Respiratory tract disorders",
        "snomed":         "389086002",
        "deprecated":     False,
        "llt_codes":      ["829", "2186", "2486"],
        "llt_names":      ["Anoxia", "Hypoxia", "Decreased pulse oxygenation"],
    },
    "515": {
        "preferred_term": "Tachypnoea",
        "hlt":            "Bronchial and lung disorders",
        "soc":            "Respiratory tract disorders",
        "snomed":         "271823003",
        "deprecated":     False,
        "llt_codes":      ["854", "855", "856", "857", "1177"],
        "llt_names":      ["Tachypnoea", "Panting", "Increased respiratory rate",
                           "Polypnoea", "Hyperventilation"],
    },
    "504": {
        "preferred_term": "Bradypnoea",
        "hlt":            "Bronchial and lung disorders",
        "soc":            "Respiratory tract disorders",
        "snomed":         "86290005",
        "deprecated":     False,
        "llt_codes":      ["833", "834", "1168", "2058"],
        "llt_names":      ["Bradypnoea", "Decreased respiratory rate",
                           "Respiratory depression", "Hypoventilation"],
    },
    "506": {
        "preferred_term": "Dyspnoea",
        "hlt":            "Bronchial and lung disorders",
        "soc":            "Respiratory tract disorders",
        "snomed":         "267036007",
        "deprecated":     False,
        "llt_codes":      ["837", "838", "839", "840", "841",
                           "1170", "1171", "1172", "1173",
                           "1258", "1915", "2138", "2481",
                           "2641", "2776", "2777"],
        "llt_names":      ["Abnormal breathing", "Irregular breathing", "Dyspnoea",
                           "Respiratory distress", "Cheyne-Stokes respiration",
                           "Breathing difficulty", "Laboured breathing",
                           "Open mouth breathing", "Paradoxical breathing",
                           "Respiratory discomfort", "Breathlessness",
                           "Hyperpnoea", "Shallow breathing",
                           "Orthopnoea", "Heavy breathing", "Agonal breathing"],
    },
    "502": {
        "preferred_term": "Apnoea",
        "hlt":            "Bronchial and lung disorders",
        "soc":            "Respiratory tract disorders",
        "snomed":         "1023001",
        "deprecated":     False,
        "llt_codes":      ["830", "831", "1167"],
        "llt_names":      ["Apnoea", "Respiratory arrest", "Respiratory failure"],
    },

    # ── Systemic / Temperature ───────────────────────────────────────────────
    "604": {
        "preferred_term": "Hyperthermia",
        "hlt":            "General signs or symptoms",
        "soc":            "Systemic disorders",
        "snomed":         "386689009",
        "deprecated":     False,
        "llt_codes":      ["1013", "1014", "1031", "1032",
                           "1033", "1034", "1930", "2504"],
        "llt_names":      ["Malignant hyperthermia", "Hyperthermia", "Pyrexia",
                           "Fever", "Elevated temperature", "Febrile",
                           "Influenza-like symptoms", "Heat stroke"],
    },
    "605": {
        "preferred_term": "Hypothermia",
        "hlt":            "General signs or symptoms",
        "soc":            "Systemic disorders",
        "snomed":         "386692006",
        "deprecated":     False,
        "llt_codes":      ["1015", "1016"],
        "llt_names":      ["Hypothermia", "Decreased body temperature"],
    },
    "601": {
        "preferred_term": "Cyanosis",
        "hlt":            "General signs or symptoms",
        "soc":            "Systemic disorders",
        "snomed":         "3415004",
        "deprecated":     False,
        "llt_codes":      ["1009", "2988"],
        "llt_names":      ["Cyanosis", "Cyanotic mucous membranes"],
    },
    "657": {
        "preferred_term": "Dehydration",
        "hlt":            "General signs or symptoms",
        "soc":            "Systemic disorders",
        "snomed":         "34095006",
        "deprecated":     False,
        "llt_codes":      ["1208", "1209", "1210", "2272", "2273", "2549"],
        "llt_names":      ["Dehydration", "Exsiccosis", "Dry mucous membrane",
                           "Haemoconcentration", "Sunken eyes", "Decreased skin turgor"],
    },
    "946": {
        "preferred_term": "Weight loss",
        "hlt":            "General signs or symptoms",
        "soc":            "Systemic disorders",
        "snomed":         "89362005",
        "deprecated":     False,
        "llt_codes":      ["1043"],
        "llt_names":      ["Weight loss"],
    },
    "598": {
        "preferred_term": "Anorexia",
        "hlt":            "General signs or symptoms",
        "soc":            "Systemic disorders",
        "snomed":         "79890006",
        "deprecated":     False,
        "llt_codes":      ["996", "997", "998", "999", "1207",
                           "2401", "2548", "2591", "2740", "2783"],
        "llt_names":      ["Anorexia", "Appetite loss", "Decreased appetite",
                           "Inappetence", "Not eating", "Food refusal",
                           "Not sucking", "Partial anorexia",
                           "Off food", "Reduced food intake"],
    },

    # ── Investigations (Laboratory) ──────────────────────────────────────────
    "904": {
        "preferred_term": "Hypoglycaemia",
        "hlt":            "Metabolic investigations",
        "soc":            "Investigations",
        "snomed":         "271327008",
        "deprecated":     False,
        "llt_codes":      ["1947", "3282"],
        "llt_names":      ["Hypoglycaemia", "Low fructosamine"],
    },
    "903": {
        "preferred_term": "Hyperglycaemia",
        "hlt":            "Metabolic investigations",
        "soc":            "Investigations",
        "snomed":         "80394007",
        "deprecated":     False,
        "llt_codes":      ["1946", "3192"],
        "llt_names":      ["Hyperglycaemia", "Elevated fructosamine"],
    },
    "85": {
        "preferred_term": "Anaemia",
        "hlt":            "Red blood cell investigations",
        "soc":            "Investigations",
        "snomed":         "271737000",
        "deprecated":     False,
        "llt_codes":      ["142", "144", "145", "1056",
                           "2157", "2214", "2215", "2216", "2853"],
        "llt_names":      ["Anaemia NOS", "Iron deficiency anaemia",
                           "Non-regenerative anaemia", "Regenerative anaemia",
                           "Decreased red blood cell count", "Decreased haemoglobin",
                           "Decreased packed cell volume (PCV)",
                           "Heinz body anaemia", "Decreased haematocrit"],
    },
}

# ---------------------------------------------------------------------------
# Quick lookup helpers
# ---------------------------------------------------------------------------

def get_term(pt_code: str) -> dict:
    """Return the VeDDRA term dict for a PT code, or empty dict if not found."""
    return VEDDRA_TERMS.get(str(pt_code), {})


def get_preferred_term(pt_code: str) -> str:
    """Return the preferred term name for a PT code."""
    return VEDDRA_TERMS.get(str(pt_code), {}).get("preferred_term", f"Unknown [{pt_code}]")


def get_snomed(pt_code: str) -> str:
    """Return the SNOMED CT concept ID for a PT code, or empty string."""
    return VEDDRA_TERMS.get(str(pt_code), {}).get("snomed", "")


# Source reference
VEDDRA_SOURCE = {
    "document":   "Combined VeDDRA list of clinical terms",
    "reference":  "EMA/CVMP/PhVWP/10418/2009 Rev.16",
    "effective":  "2025-10-01",
    "url":        "https://www.ema.europa.eu/en/veterinary-regulatory-overview/"
                  "post-authorisation-veterinary-medicines/pharmacovigilance-veterinary-medicines/"
                  "eudravigilance-veterinary",
    "terms_used": len(VEDDRA_TERMS),
    "next_revision": "2026",
}
