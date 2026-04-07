"""
E3. Ontology compliance — alias resolution and JSON-LD export.

Mirrors DP E3 (28/28 GLOSIS alias tests) — validates that all known
device aliases resolve correctly to canonical keys with their
Uberon/SNOMED/VeDDRA URIs, and that the JSON-LD export is well-formed.

Run: python examples/e3_ontology_compliance.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from digitalsoma.ontology.vocab import canonical_key, normalise_dict, to_jsonld

# 30 alias resolution tests across device vendors / database conventions
TEST_CASES = [
    # (source_alias,              expected_canonical,           source_label)
    ("HR",                        "heart_rate_bpm",             "Generic wearable"),
    ("heart_rate",                "heart_rate_bpm",             "Generic wearable"),
    ("ECG_HR",                    "heart_rate_bpm",             "ECG device"),
    ("PPG_HR",                    "heart_rate_bpm",             "PPG sensor"),
    ("SpO2",                      "spo2_pct",                   "Pulse oximeter"),
    ("oxygen_saturation",         "spo2_pct",                   "Clinical system"),
    ("Tb",                        "core_temp_C",                "Rumen bolus"),
    ("core_temperature",          "core_temp_C",                "Telemetry collar"),
    ("rectal_temp",               "core_temp_C",                "Manual clinical"),
    ("RR",                        "respiratory_rate_bpm",       "Respiratory belt"),
    ("breaths_per_min",           "respiratory_rate_bpm",       "Video analysis"),
    ("SBP",                       "systolic_bp_mmHg",           "Blood pressure cuff"),
    ("systolicBloodPressure",     "systolic_bp_mmHg",           "Clinical DB"),
    ("DBP",                       "diastolic_bp_mmHg",          "Blood pressure cuff"),
    ("MAP",                       "mean_arterial_pressure_mmHg","Haemodynamic monitor"),
    ("glucose",                   "blood_glucose_mmol_L",       "CGM device"),
    ("BGlucose",                  "blood_glucose_mmol_L",       "Hand glucometer alias"),
    ("BloodGlucose",              "blood_glucose_mmol_L",       "Clinical system"),
    ("cortisol",                  "cortisol_nmol_L",            "Lab assay"),
    ("CORT",                      "cortisol_nmol_L",            "Research label"),
    ("accel",                     "acceleration_m_s2",          "Accelerometer"),
    ("ACC",                       "acceleration_m_s2",          "IMU device"),
    ("activity",                  "activity_counts",            "Activity monitor"),
    ("weight",                    "body_mass_kg",               "Weigh scale"),
    ("BW",                        "body_mass_kg",               "Livestock scale"),
    ("live_weight",               "body_mass_kg",               "Farm management DB"),
    ("HCT",                       "haematocrit_pct",            "Haematology analyser"),
    ("Hb",                        "haemoglobin_g_dL",           "Blood panel"),
    ("WBC",                       "wbc_10e9_L",                 "Haematology analyser"),
    ("AE_score",                  "adverse_event_score",        "VeDDRA output layer"),
]

print("=" * 80)
print("E3. DigitalSoma — ontology alias resolution compliance")
print("=" * 80)
print(f"\n{'Source alias':<35} {'Expected canonical':<35} {'Source':<25} {'Result'}")
print("-" * 105)

passed = 0
failed = 0
for alias, expected, source in TEST_CASES:
    resolved = canonical_key(alias)
    ok = resolved == expected
    status = "PASS" if ok else "FAIL"
    if ok:
        passed += 1
    else:
        failed += 1
    print(f"{alias:<35} {expected:<35} {source:<25} {status}")

print()
print(f"Overall: {passed}/{len(TEST_CASES)} PASS  |  {failed} FAIL")

# JSON-LD export validation
print()
print("JSON-LD export validation:")
sample_state = {
    "heart_rate_bpm": 72,
    "core_temp_C": 38.5,
    "spo2_pct": 98.0,
    "blood_glucose_mmol_L": 4.2,
    "adverse_event_score": 0.0,
}
doc = to_jsonld(sample_state)
context = doc.get("@context", {})
uri_checks = [
    ("heart_rate_bpm", "purl.obolibrary.org"),
    ("core_temp_C",    "purl.obolibrary.org"),
    ("spo2_pct",       "snomed.info"),
]
for key, expected_domain in uri_checks:
    uri = context.get(key, {}).get("@id", "")
    ok = expected_domain in uri
    print(f"  {key:<35} URI={uri[:55]:<55} {'PASS' if ok else 'FAIL'}")
