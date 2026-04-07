"""
tests/test_ontology.py — DigitalSoma ontology layer test suite.

Ontology test suite — validates canonical key resolution and JSON-LD export.
Run: pytest tests/test_ontology.py -v

Tests cover:
    - All 30 alias resolutions
    - normalise_dict() round-trip
    - to_jsonld() URI validity
    - register_property() extensibility
    - Unit converter coverage
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
from digitalsoma.ontology.vocab import (
    canonical_key, normalise_dict, to_jsonld,
    register_property, OntologyProperty, list_properties,
)
from digitalsoma.sensor.sensor_layer import convert_unit


# ---------------------------------------------------------------------------
# Alias resolution — 30 tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("alias,expected", [
    ("HR",                         "heart_rate_bpm"),
    ("heart_rate",                 "heart_rate_bpm"),
    ("ECG_HR",                     "heart_rate_bpm"),
    ("PPG_HR",                     "heart_rate_bpm"),
    ("SpO2",                       "spo2_pct"),
    ("oxygen_saturation",          "spo2_pct"),
    ("Tb",                         "core_temp_C"),
    ("core_temperature",           "core_temp_C"),
    ("rectal_temp",                "core_temp_C"),
    ("RR",                         "respiratory_rate_bpm"),
    ("breaths_per_min",            "respiratory_rate_bpm"),
    ("SBP",                        "systolic_bp_mmHg"),
    ("systolicBloodPressure",      "systolic_bp_mmHg"),
    ("DBP",                        "diastolic_bp_mmHg"),
    ("MAP",                        "mean_arterial_pressure_mmHg"),
    ("glucose",                    "blood_glucose_mmol_L"),
    ("BGlucose",                   "blood_glucose_mmol_L"),
    ("BloodGlucose",               "blood_glucose_mmol_L"),
    ("cortisol",                   "cortisol_nmol_L"),
    ("CORT",                       "cortisol_nmol_L"),
    ("accel",                      "acceleration_m_s2"),
    ("ACC",                        "acceleration_m_s2"),
    ("activity",                   "activity_counts"),
    ("weight",                     "body_mass_kg"),
    ("BW",                         "body_mass_kg"),
    ("live_weight",                "body_mass_kg"),
    ("HCT",                        "haematocrit_pct"),
    ("Hb",                         "haemoglobin_g_dL"),
    ("WBC",                        "wbc_10e9_L"),
    ("AE_score",                   "adverse_event_score"),
])
def test_canonical_key(alias, expected):
    assert canonical_key(alias) == expected


# ---------------------------------------------------------------------------
# Pass-through for unknown aliases
# ---------------------------------------------------------------------------

def test_unknown_alias_passthrough():
    assert canonical_key("unknown_vendor_field_xyz") == "unknown_vendor_field_xyz"


# ---------------------------------------------------------------------------
# normalise_dict round-trip
# ---------------------------------------------------------------------------

def test_normalise_dict_roundtrip():
    raw = {"HR": 72, "SpO2": 98.0, "Tb": 38.5, "weight": 600.0}
    result = normalise_dict(raw)
    assert result["heart_rate_bpm"] == 72
    assert result["spo2_pct"] == 98.0
    assert result["core_temp_C"] == 38.5
    assert result["body_mass_kg"] == 600.0


def test_normalise_dict_duplicate_aliases_last_wins():
    # "HR" and "heart_rate" both resolve to heart_rate_bpm
    raw = {"HR": 60, "heart_rate": 72}
    result = normalise_dict(raw)
    assert result["heart_rate_bpm"] == 72   # last value wins


# ---------------------------------------------------------------------------
# JSON-LD export
# ---------------------------------------------------------------------------

def test_jsonld_context_structure():
    state = {"heart_rate_bpm": 72, "core_temp_C": 38.5, "spo2_pct": 98.0}
    doc = to_jsonld(state)
    assert "@context" in doc
    assert "@type" in doc
    assert doc["@type"] == "DigitalSomaStateSnapshot"


def test_jsonld_uri_validity():
    state = {
        "heart_rate_bpm": 72,
        "core_temp_C": 38.5,
        "spo2_pct": 98.0,
        "blood_glucose_mmol_L": 4.2,
    }
    doc = to_jsonld(state)
    ctx = doc["@context"]

    # heart rate → OBO CMO namespace
    assert "purl.obolibrary.org" in ctx["heart_rate_bpm"]["@id"]
    # core temp → OBO CMO namespace
    assert "purl.obolibrary.org" in ctx["core_temp_C"]["@id"]
    # SpO2 → SNOMED namespace
    assert "snomed.info" in ctx["spo2_pct"]["@id"]


def test_jsonld_ucum_units_present():
    state = {"heart_rate_bpm": 72}
    doc = to_jsonld(state)
    ctx = doc["@context"]
    assert "ucum:unit" in ctx["heart_rate_bpm"]
    assert ctx["heart_rate_bpm"]["ucum:unit"] == "/min"


# ---------------------------------------------------------------------------
# register_property extensibility
# ---------------------------------------------------------------------------

def test_register_custom_property():
    new_prop = OntologyProperty(
        canonical="rumen_ph",
        uri="http://snomed.info/id/167292006",
        unit="[pH]",
        aliases=["RumenPH", "rumen_pH", "bolus_ph"],
        description="Rumen pH from bolus sensor",
    )
    register_property(new_prop)
    assert canonical_key("RumenPH") == "rumen_ph"
    assert canonical_key("bolus_ph") == "rumen_ph"


def test_registered_properties_listed():
    props = list_properties()
    canonicals = [p["canonical"] for p in props]
    assert "heart_rate_bpm" in canonicals
    assert "spo2_pct" in canonicals
    assert "adverse_event_score" in canonicals


# ---------------------------------------------------------------------------
# Unit conversion
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,from_unit,expected_approx,expected_unit", [
    (98.6,  "degF",  37.0,    "Cel"),
    (310.0, "K",     36.85,   "Cel"),
    (10.0,  "kPa",   75.0,    "mm[Hg]"),
    (180.0, "mg/dL", 9.99,    "mmol/L"),   # 180 mg/dL glucose
    (10.0,  "μg/dL", 275.886, "nmol/L"),   # cortisol
    (1.0,   "Hz",    60.0,    "/min"),      # respiratory rate from impedance
    (2.2,   "lb",    0.998,   "kg"),
])
def test_unit_conversion(value, from_unit, expected_approx, expected_unit):
    converted, unit = convert_unit(value, from_unit)
    assert unit == expected_unit
    assert abs(converted - expected_approx) < 0.5, (
        f"Expected ~{expected_approx}, got {converted}"
    )


def test_unit_passthrough_for_unknown():
    val, unit = convert_unit(42.0, "furlongs")
    assert val == 42.0
    assert unit == "furlongs"
