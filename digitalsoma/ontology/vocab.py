"""
ontology/vocab.py — DigitalSoma property vocabulary.

    canonical_key(alias)     → O(1) canonical key lookup
    normalise_dict(d)        → rewrite all keys in one pass
    to_jsonld(state)         → JSON-LD export with ontology URIs

Ontology namespaces used:
    Uberon   — cross-species anatomy and physiology  (http://purl.obolibrary.org/obo/UBERON_)
    SNOMED   — clinical findings and body structures  (http://snomed.info/id/)
    VeDDRA   — veterinary adverse event terminology   (https://www.ema.europa.eu/en/veterinary-regulatory/)
    NCBITaxon— species and taxon identifiers          (http://purl.obolibrary.org/obo/NCBITaxon_)
    UCUM     — units of measure                       (http://unitsofmeasure.org/)
    PATO     — phenotypic quality descriptors         (http://purl.obolibrary.org/obo/PATO_)
    HP/MP    — human/mammalian phenotype ontology     (http://purl.obolibrary.org/obo/HP_)

Each OntologyProperty carries:
    canonical   : the single authoritative key used internally
    uri         : primary ontology URI (Uberon preferred; SNOMED for clinical findings)
    unit        : UCUM unit string
    aliases     : all known vendor/device aliases → resolved to canonical in O(1)
    description : human-readable description
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

# ---------------------------------------------------------------------------
# OntologyProperty dataclass (identical interface to DP)
# ---------------------------------------------------------------------------

@dataclass
class OntologyProperty:
    canonical: str
    uri: str
    unit: str
    aliases: List[str] = field(default_factory=list)
    description: str = ""
    veddra_term: Optional[str] = None       # VeDDRA clinical sign term (if applicable)
    veddra_id: Optional[str] = None         # VeDDRA term ID


# ---------------------------------------------------------------------------
# Canonical property definitions
# 44 properties: 29 core in vocab.py + 15 sensor-specific
# (44 canonical properties: 26 core + 15 gait + 3 sensor)
# ---------------------------------------------------------------------------

PROPERTIES: List[OntologyProperty] = [

    # ── Cardiovascular ──────────────────────────────────────────────────────
    OntologyProperty(
        canonical="heart_rate_bpm",
        uri="http://purl.obolibrary.org/obo/CMO_0000052",
        unit="/min",
        aliases=["HR", "hr", "heart_rate", "HeartRate", "pulse_bpm",
                 "pulse", "Pulse", "ECG_HR", "PPG_HR"],
        description="Heart rate in beats per minute",
        veddra_term="Heart rate increased", veddra_id="10019302",
    ),
    OntologyProperty(
        canonical="systolic_bp_mmHg",
        uri="http://snomed.info/id/271649006",
        unit="mm[Hg]",
        aliases=["SBP", "sbp", "systolic_bp", "SystolicBP", "systolicBloodPressure"],
        description="Systolic blood pressure",
    ),
    OntologyProperty(
        canonical="diastolic_bp_mmHg",
        uri="http://snomed.info/id/271650006",
        unit="mm[Hg]",
        aliases=["DBP", "dbp", "diastolic_bp", "DiastolicBP"],
        description="Diastolic blood pressure",
    ),
    OntologyProperty(
        canonical="mean_arterial_pressure_mmHg",
        uri="http://snomed.info/id/251076008",
        unit="mm[Hg]",
        aliases=["MAP", "map_mmhg", "MeanArterialPressure"],
        description="Mean arterial pressure",
    ),
    OntologyProperty(
        canonical="cardiac_output_L_min",
        uri="http://purl.obolibrary.org/obo/CMO_0000230",
        unit="L/min",
        aliases=["CO", "cardiac_output", "CardiacOutput"],
        description="Cardiac output in litres per minute",
    ),
    OntologyProperty(
        canonical="stroke_volume_mL",
        uri="http://purl.obolibrary.org/obo/CMO_0000231",
        unit="mL",
        aliases=["SV", "stroke_volume", "StrokeVolume"],
        description="Stroke volume in millilitres",
    ),

    # ── Respiratory ─────────────────────────────────────────────────────────
    OntologyProperty(
        canonical="respiratory_rate_bpm",
        uri="http://purl.obolibrary.org/obo/CMO_0000136",
        unit="/min",
        aliases=["RR", "rr", "resp_rate", "RespiratoryRate", "BreathRate",
                 "breath_rate", "breaths_per_min"],
        description="Respiratory rate in breaths per minute",
        veddra_term="Respiratory rate increased", veddra_id="10038750",
    ),
    OntologyProperty(
        canonical="spo2_pct",
        uri="http://snomed.info/id/59408-5",
        unit="%",
        aliases=["SpO2", "spo2", "o2_sat", "O2Sat", "oxygen_saturation",
                 "OxygenSaturation", "pulse_ox"],
        description="Peripheral oxygen saturation",
        veddra_term="Hypoxia", veddra_id="10021143",
    ),
    OntologyProperty(
        canonical="vo2_L_min",
        uri="http://purl.obolibrary.org/obo/CMO_0001690",
        unit="L/min",
        aliases=["VO2", "vo2", "oxygen_consumption"],
        description="Oxygen consumption rate",
    ),
    OntologyProperty(
        canonical="vco2_L_min",
        uri="http://purl.obolibrary.org/obo/CMO_0001691",
        unit="L/min",
        aliases=["VCO2", "vco2", "co2_production"],
        description="Carbon dioxide production rate",
    ),
    OntologyProperty(
        canonical="minute_ventilation_L_min",
        uri="http://snomed.info/id/250811003",
        unit="L/min",
        aliases=["MV", "minute_vent", "MinuteVentilation"],
        description="Minute ventilation (RR × tidal volume)",
    ),

    # ── Thermal / thermoregulation ───────────────────────────────────────────
    OntologyProperty(
        canonical="core_temp_C",
        uri="http://purl.obolibrary.org/obo/CMO_0000015",
        unit="Cel",
        aliases=["Tb", "TB", "core_temp", "CoreTemp", "body_temp",
                 "BodyTemp", "rectal_temp", "T_core", "temp_C",
                 "temperature_C", "core_temperature"],
        description="Core body temperature in Celsius",
        veddra_term="Hyperthermia", veddra_id="10020557",
    ),
    OntologyProperty(
        canonical="ambient_temp_C",
        uri="http://snomed.info/id/364395008",
        unit="Cel",
        aliases=["T_ambient", "ambient_temp", "AmbientTemp",
                 "env_temp", "T_env", "temperature_ambient"],
        description="Ambient (environmental) temperature",
    ),
    OntologyProperty(
        canonical="skin_temp_C",
        uri="http://snomed.info/id/364395008",
        unit="Cel",
        aliases=["Ts", "skin_temp", "SkinTemp", "surface_temp"],
        description="Skin surface temperature",
    ),
    OntologyProperty(
        canonical="thermal_comfort_index",
        uri="http://purl.obolibrary.org/obo/PATO_0001334",
        unit="1",
        aliases=["TCI", "tci", "thermal_comfort"],
        description="Dimensionless thermal comfort index (0 = thermoneutral)",
    ),

    # ── Metabolic / endocrine ────────────────────────────────────────────────
    OntologyProperty(
        canonical="blood_glucose_mmol_L",
        uri="http://snomed.info/id/33747003",
        unit="mmol/L",
        aliases=["glucose", "Glucose", "BG", "BGlucose", "blood_glucose",
                 "BloodGlucose", "CGM", "glucose_mmol"],
        description="Blood glucose concentration",
        veddra_term="Hypoglycaemia", veddra_id="10020993",
    ),
    OntologyProperty(
        canonical="cortisol_nmol_L",
        uri="http://snomed.info/id/42798000",
        unit="nmol/L",
        aliases=["cortisol", "Cortisol", "CORT", "cortisol_plasma"],
        description="Plasma cortisol concentration",
        veddra_term="Increased cortisol level", veddra_id="10022476",
    ),
    OntologyProperty(
        canonical="insulin_pmol_L",
        uri="http://snomed.info/id/55550003",
        unit="pmol/L",
        aliases=["insulin", "Insulin", "INS"],
        description="Plasma insulin concentration",
    ),
    OntologyProperty(
        canonical="rmr_kcal_day",
        uri="http://purl.obolibrary.org/obo/CMO_0000649",
        unit="kcal/d",
        aliases=["RMR", "rmr", "RestingMetabolicRate", "BMR"],
        description="Resting metabolic rate",
    ),
    OntologyProperty(
        canonical="rmr_W",
        uri="http://purl.obolibrary.org/obo/CMO_0000649",
        unit="W",
        aliases=["rmr_watts", "metabolic_power_W"],
        description="Resting metabolic rate in Watts",
    ),

    # ── Musculoskeletal / locomotion ─────────────────────────────────────────
    OntologyProperty(
        canonical="acceleration_m_s2",
        uri="http://purl.obolibrary.org/obo/NCIT_C71253",
        unit="m/s2",
        aliases=["accel", "Accel", "accelerometer", "ACC", "acc_ms2"],
        description="Body acceleration magnitude",
    ),
    OntologyProperty(
        canonical="activity_counts",
        uri="http://snomed.info/id/48761009",
        unit="1",
        aliases=["activity", "Activity", "ActCounts", "steps"],
        description="Activity monitor counts (dimensionless)",
    ),
    OntologyProperty(
        canonical="lying_time_min",
        uri="http://snomed.info/id/39271001",
        unit="min",
        aliases=["LyingTime", "lying_time", "recumbency_min"],
        description="Time spent lying / recumbent in minutes",
    ),

    # ── Neuroendocrine / stress ──────────────────────────────────────────────
    OntologyProperty(
        canonical="physiological_stress_index",
        uri="http://purl.obolibrary.org/obo/PATO_0001455",
        unit="1",
        aliases=["stress_index", "StressIndex", "PSI", "psi"],
        description="Composite physiological stress index (0–1)",
        veddra_term="Distress", veddra_id="10013029",
    ),

    # ── Haematology / biochemistry ───────────────────────────────────────────
    OntologyProperty(
        canonical="haematocrit_pct",
        uri="http://snomed.info/id/28317006",
        unit="%",
        aliases=["HCT", "hct", "haematocrit", "hematocrit", "PCV"],
        description="Haematocrit (packed cell volume)",
    ),
    OntologyProperty(
        canonical="haemoglobin_g_dL",
        uri="http://snomed.info/id/59528000",
        unit="g/dL",
        aliases=["Hb", "HB", "haemoglobin", "hemoglobin", "HGB"],
        description="Haemoglobin concentration",
    ),
    OntologyProperty(
        canonical="wbc_10e9_L",
        uri="http://snomed.info/id/165507003",
        unit="10*9/L",
        aliases=["WBC", "wbc", "white_blood_cells", "leukocytes"],
        description="White blood cell count",
    ),
    OntologyProperty(
        canonical="creatinine_umol_L",
        uri="http://snomed.info/id/70901006",
        unit="umol/L",
        aliases=["creatinine", "Creatinine", "CREA"],
        description="Plasma creatinine",
    ),

    # ── Anthropometrics ──────────────────────────────────────────────────────
    OntologyProperty(
        canonical="body_mass_kg",
        uri="http://purl.obolibrary.org/obo/CMO_0000012",
        unit="kg",
        aliases=["weight", "Weight", "BW", "bw", "body_weight",
                 "BodyWeight", "mass_kg", "live_weight"],
        description="Body mass in kilograms",
    ),

    # ── Adverse event (VeDDRA output layer) ──────────────────────────────────
    OntologyProperty(
        canonical="adverse_event_score",
        uri="https://www.ema.europa.eu/en/veterinary-regulatory/",
        unit="1",
        aliases=["AE_score", "ae_score", "AdverseEventScore"],
        description="VeDDRA adverse event probability score (0–1)",
    ),
]

# ---------------------------------------------------------------------------
# Alias lookup table — built once at import time, O(1) access
# (identical pattern to DP vocab.py)
# ---------------------------------------------------------------------------

_ALIAS_MAP: Dict[str, str] = {}
_URI_MAP: Dict[str, str] = {}
_UNIT_MAP: Dict[str, str] = {}

for _prop in PROPERTIES:
    _ALIAS_MAP[_prop.canonical] = _prop.canonical
    _URI_MAP[_prop.canonical] = _prop.uri
    _UNIT_MAP[_prop.canonical] = _prop.unit
    for _alias in _prop.aliases:
        _ALIAS_MAP[_alias] = _prop.canonical
        _ALIAS_MAP[_alias.lower()] = _prop.canonical


# ---------------------------------------------------------------------------
# Public API — identical signatures to DP vocab.py
# ---------------------------------------------------------------------------

def canonical_key(alias: str) -> str:
    """
    Resolve any vendor alias to the canonical property key in O(1).
    Unknown aliases are returned unchanged (pass-through, not an error).

    >>> canonical_key("HR")
    'heart_rate_bpm'
    >>> canonical_key("SpO2")
    'spo2_pct'
    >>> canonical_key("unknown_sensor")
    'unknown_sensor'
    """
    return _ALIAS_MAP.get(alias, _ALIAS_MAP.get(alias.lower(), alias))


def normalise_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """
    Rewrite all keys in *d* to their canonical forms in a single pass.
    Duplicate resolutions (two aliases for the same canonical) are merged;
    last value wins. Mirrors DP normalise_dict() exactly.

    >>> normalise_dict({"HR": 72, "SpO2": 98.0})
    {'heart_rate_bpm': 72, 'spo2_pct': 98.0}
    """
    return {canonical_key(k): v for k, v in d.items()}


def to_jsonld(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Export a state snapshot as a self-describing JSON-LD document.
    All canonical keys carry their ontology URIs in the @context block.
    Mirrors DP to_jsonld() replacing GLOSIS URIs with Uberon/SNOMED/VeDDRA.

    >>> doc = to_jsonld({"heart_rate_bpm": 72})
    >>> doc["@context"]["heart_rate_bpm"]["@id"]
    'http://purl.obolibrary.org/obo/CMO_0000052'
    """
    context: Dict[str, Any] = {
        "@vocab": "http://purl.obolibrary.org/obo/",
        "ucum": "http://unitsofmeasure.org/",
        "veddra": "https://www.ema.europa.eu/en/veterinary-regulatory/",
        "ncbitaxon": "http://purl.obolibrary.org/obo/NCBITaxon_",
        "snomed": "http://snomed.info/id/",
        "uberon": "http://purl.obolibrary.org/obo/UBERON_",
    }
    data: Dict[str, Any] = {}

    for k, v in state.items():
        uri = _URI_MAP.get(k)
        unit = _UNIT_MAP.get(k)
        if uri:
            context[k] = {"@id": uri, "@type": "@id"}
            if unit:
                context[k]["ucum:unit"] = unit
        if not isinstance(v, (dict, list)):
            data[k] = v

    return {
        "@context": context,
        "@type": "DigitalSomaStateSnapshot",
        **data,
    }


def list_properties() -> List[Dict[str, Any]]:
    """Return all registered properties as a list of dicts (for introspection)."""
    return [
        {
            "canonical": p.canonical,
            "uri": p.uri,
            "unit": p.unit,
            "aliases": p.aliases,
            "description": p.description,
            "veddra_term": p.veddra_term,
            "veddra_id": p.veddra_id,
        }
        for p in PROPERTIES
    ]


def register_property(prop: OntologyProperty) -> None:
    """
    Register a new OntologyProperty at runtime.
    Extends the vocabulary without modifying this file.
    Open-world extensibility — new properties can be registered at runtime.
    """
    PROPERTIES.append(prop)
    _ALIAS_MAP[prop.canonical] = prop.canonical
    _URI_MAP[prop.canonical] = prop.uri
    _UNIT_MAP[prop.canonical] = prop.unit
    for alias in prop.aliases:
        _ALIAS_MAP[alias] = prop.canonical
        _ALIAS_MAP[alias.lower()] = prop.canonical
