"""
examples/e5_fhir_integration.py — HL7 FHIR R4 integration example.

Demonstrates:
    1. Build an equine DigitalSoma twin and ingest sensor readings
    2. Export to a FHIR R4 Bundle via ds.to_fhir_bundle()
    3. Inspect the produced Patient, Device, Observation, DiagnosticReport
    4. Round-trip: parse the bundle back via from_fhir_bundle()
    5. Ingest the parsed readings into a fresh twin and verify equivalence
    6. Build a FHIR 'transaction' bundle for POST to a FHIR server
    7. Use FHIRMapper directly for custom resource construction

Author : Dr. ir. Ali Youssef (ORCID: 0000-0002-9986-5324)
         Agroecosystems Laboratory, University of Manitoba & BioTwinR Ltd.
Licence: CC BY 4.0
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from digitalsoma.soma_api import build_soma, SomaConfig
from digitalsoma.fhir import to_fhir_bundle, from_fhir_bundle, FHIRMapper


# ---------------------------------------------------------------------------
# 1. Build twin and ingest a realistic gallop scenario
# ---------------------------------------------------------------------------

print("=" * 64)
print("DigitalSoma v2.1.0 — FHIR R4 Integration Example")
print("=" * 64)

config = SomaConfig(
    animal_type="equine_adult",
    animal_id="stallion-eclipse-001",
    site_name="Newmarket Training Centre",
)
ds = build_soma(config)

readings = {
    "heart_rate_bpm":        168.0,
    "core_temp_C":            38.7,
    "spo2_pct":               97.5,
    "respiratory_rate_bpm":  100.0,
    "cortisol_nmol_L":        30.0,
    "body_mass_kg":          500.0,
    "haematocrit_pct":        42.0,
    "haemoglobin_g_dL":       14.2,
    "blood_glucose_mmol_L":    5.8,
}
state = ds.update_sync(readings)

print(f"\n[1] Twin built  : {ds.soma_id}")
print(f"    Animal ID   : stallion-eclipse-001")
print(f"    Species     : {ds.structural_layer['taxa']}")
print(f"    CO          : {state.get('cardiac_output_L_min', 0):.2f} L/min")
print(f"    PSI         : {state.get('physiological_stress_index', 0):.3f}")
print(f"    AE score    : {state.get('adverse_event_score', 0):.2f}")


# ---------------------------------------------------------------------------
# 2. Export to FHIR R4 Bundle
# ---------------------------------------------------------------------------

bundle = to_fhir_bundle(ds, bundle_type="collection")

print(f"\n[2] FHIR R4 Bundle exported")
print(f"    Bundle ID   : {bundle['id']}")
print(f"    Bundle type : {bundle['type']}")
print(f"    Entries     : {bundle['total']}")


# ---------------------------------------------------------------------------
# 3. Inspect resources by type
# ---------------------------------------------------------------------------

resources_by_type: dict = {}
for entry in bundle["entry"]:
    rt = entry["resource"]["resourceType"]
    resources_by_type.setdefault(rt, []).append(entry["resource"])

print(f"\n[3] Resources produced:")
for rt, items in resources_by_type.items():
    print(f"    {rt:22s}: {len(items)} resource(s)")

# Patient details
patient = resources_by_type.get("Patient", [{}])[0]
species_ext = next(
    (e for e in patient.get("extension", [])
     if "patient-animal" in e.get("url", "")),
    None,
)
if species_ext:
    species_text = (
        species_ext["extension"][0]
        ["valueCodeableConcept"]["text"]
    )
    print(f"\n    Patient species : {species_text}")

# Device
device = resources_by_type.get("Device", [{}])[0]
print(f"    Device name     : {device.get('deviceName', [{}])[0].get('name', '')}")

# Sample Observation
obs_list = resources_by_type.get("Observation", [])
print(f"\n    Sample Observations (first 5):")
for obs in obs_list[:5]:
    code_text = obs["code"]["text"]
    vq = obs.get("valueQuantity", {})
    val = vq.get("value", "—")
    unit = vq.get("unit", "")
    loinc = next(
        (c["code"] for c in obs["code"]["coding"]
         if c["system"] == "http://loinc.org"),
        "—",
    )
    print(f"      [{loinc:10s}] {code_text:45s}: {val} {unit}")

# DiagnosticReport
dr_list = resources_by_type.get("DiagnosticReport", [])
if dr_list:
    dr = dr_list[0]
    print(f"\n    DiagnosticReport status  : {dr['status']}")
    print(f"    Conclusion               : {dr['conclusion']}")
    ae_score_ext = next(
        (e for e in dr.get("extension", [])
         if "ae_score" in e.get("url", "")),
        None,
    )
    if ae_score_ext:
        print(f"    AE score (extension)     : {ae_score_ext['valueDecimal']}")


# ---------------------------------------------------------------------------
# 4. Trigger an adverse event and re-export
# ---------------------------------------------------------------------------

print("\n[4] Injecting heat stress scenario (temp=40.2°C, cort=190 nmol/L)...")
state2 = ds.update_sync({
    "core_temp_C":       40.2,
    "cortisol_nmol_L":  190.0,
    "heart_rate_bpm":   192.0,
})
bundle2 = to_fhir_bundle(ds)
dr2 = next(
    (e["resource"] for e in bundle2["entry"]
     if e["resource"]["resourceType"] == "DiagnosticReport"),
    {},
)
print(f"    DiagnosticReport status  : {dr2.get('status')}")
print(f"    Conclusion               : {dr2.get('conclusion')}")
print(f"    Coded findings           : {len(dr2.get('conclusionCode', []))} VeDDRA flag(s)")
for cc in dr2.get("conclusionCode", []):
    print(f"      → {cc['text']}")


# ---------------------------------------------------------------------------
# 5. Round-trip: from_fhir_bundle → update_sync on a fresh twin
# ---------------------------------------------------------------------------

print("\n[5] Round-trip: parsing bundle back via from_fhir_bundle()...")
parsed_readings = from_fhir_bundle(bundle)

print(f"    Canonical properties parsed: {len(parsed_readings)}")
for k, v in sorted(parsed_readings.items()):
    print(f"      {k:40s}: {v:.4g}")

# Feed into a fresh twin and verify heart rate matches
ds2 = build_soma(SomaConfig(
    animal_type="equine_adult",
    animal_id="stallion-eclipse-001-copy",
))
state3 = ds2.update_sync(parsed_readings)

original_hr = readings["heart_rate_bpm"]
round_trip_hr = parsed_readings.get("heart_rate_bpm", None)
match = abs(original_hr - round_trip_hr) < 0.001 if round_trip_hr else False
print(f"\n    Heart rate round-trip: {original_hr} → {round_trip_hr} {'✓ match' if match else '✗ mismatch'}")


# ---------------------------------------------------------------------------
# 6. Transaction bundle for POST to a FHIR server
# ---------------------------------------------------------------------------

print("\n[6] Building 'transaction' bundle for FHIR server POST...")
tx_bundle = to_fhir_bundle(ds2, bundle_type="transaction")
print(f"    Bundle type : {tx_bundle['type']}")
print(f"    Entries     : {tx_bundle['total']}")
first_entry = tx_bundle["entry"][0]
print(f"    First entry request: {first_entry['request']['method']} {first_entry['request']['url']}")


# ---------------------------------------------------------------------------
# 7. Direct FHIRMapper usage — custom observation
# ---------------------------------------------------------------------------

print("\n[7] FHIRMapper direct usage — custom observation...")
mapper = FHIRMapper()

custom_obs = mapper.observation(
    canonical_key="cortisol_nmol_L",
    value=190.0,
    subject_ref="Patient/stallion-eclipse-001",
    device_ref=f"Device/{ds.soma_id}",
)
print(f"    Resource type : {custom_obs['resourceType']}")
print(f"    Code text     : {custom_obs['code']['text']}")
print(f"    Value         : {custom_obs['valueQuantity']['value']} {custom_obs['valueQuantity']['unit']}")
loinc_coding = next(
    (c for c in custom_obs["code"]["coding"] if c["system"] == "http://loinc.org"),
    None,
)
if loinc_coding:
    print(f"    LOINC code    : {loinc_coding['code']} ({loinc_coding['display']})")


# ---------------------------------------------------------------------------
# 8. Write full bundle to file
# ---------------------------------------------------------------------------

out_path = os.path.join(os.path.dirname(__file__), "equine_fhir_bundle.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(bundle, f, indent=2)

print(f"\n[8] Full FHIR bundle written to: {out_path}")
print(f"    Size: {os.path.getsize(out_path):,} bytes")

print("\n" + "=" * 64)
print("FHIR R4 integration example complete.")
print("=" * 64)
