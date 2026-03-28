# Getting Started with DigitalSoma

This guide takes you from installation to a working physiological digital twin in under ten minutes. No prior experience with digital twins or veterinary informatics is required.

---

## Prerequisites

- Python 3.9 or later
- `pip` (any recent version)
- No other dependencies — DigitalSoma uses the Python standard library only

---

## 1. Installation

Clone the repository and install in editable mode:

```bash
git clone https://github.com/Pierianspring/digitalsoma.git
cd digitalsoma
pip install -e .
```

Verify the installation:

```python
import digitalsoma
print(digitalsoma.__version__)   # → 1.0.0
```

---

## 2. Your first digital twin

A DigitalSoma twin is created with two objects: a `SomaConfig` describing the animal, and `build_soma()` which constructs the twin from that config.

```python
from digitalsoma import build_soma, SomaConfig

ds = build_soma(SomaConfig(
    animal_type = "bovine_adult",
    site_name   = "Farm A, Manitoba",
))
```

That is all that is needed to initialise a fully parameterised physiological digital twin. The twin now holds the structural layer for an adult *Bos taurus*: body mass 600 kg, resting heart rate 60 bpm, normal core temperature 38.5 °C, and six anatomical systems registered.

Inspect the structural layer:

```python
sl = ds.structural_layer
print(sl["taxa"])               # → Bos taurus
print(sl["body_mass_kg"])       # → 600.0
print(sl["hr_normal_bpm"])      # → 60.0
print(sl["core_temp_normal_C"]) # → 38.5
print(ds.solvers)               # → list of 6 registered solvers
```

---

## 3. Pushing sensor readings

Feed sensor data to the twin with `update_sync()`. Pass any dict of key-value pairs — DigitalSoma resolves vendor aliases automatically and converts units on the fly.

```python
state = ds.update_sync({
    "HR":          72,      # alias for heart_rate_bpm
    "core_temp_C": 39.1,
    "SpO2":        97.5,    # alias for spo2_pct
    "RR":          28,      # alias for respiratory_rate_bpm
})
```

`update_sync()` returns the full merged state dict after all six solvers have run.

```python
# Directly measured variables
print(state["heart_rate_bpm"])          # → 72.0
print(state["core_temp_C"])             # → 39.1
print(state["spo2_pct"])                # → 97.5

# Variables inferred by the solver chain
print(state["cardiac_output_L_min"])    # → 5.76
print(state["rmr_W"])                   # → 133.4
print(state["thermal_comfort_index"])   # → 0.07  (slight heat load)
print(state["physiological_stress_index"]) # → 0.18
print(state["adverse_event_score"])     # → 0.0   (no active flags)
```

---

## 4. Threshold alarms

The Threshold Event System (TES) checks every variable on every `update_sync()` call. Push a reading that exceeds the hyperthermia threshold:

```python
state = ds.update_sync({
    "core_temp_C":          41.0,   # > 40.5 → hyperthermia alarm
    "heart_rate_bpm":       105,    # > 120 threshold — not yet breached
    "respiratory_rate_bpm": 50,
    "spo2_pct":             95.0,
})

print(state["adverse_event_score"])    # → 0.167
print(state["ae_flags"])
# → [{"veddra_term": "Hyperthermia", "veddra_id": "10020557", ...}]
```

Register a callback to receive alarm events in real time:

```python
def on_alarm(key, value, label):
    print(f"ALARM  {label}: {key} = {value:.2f}")

ds._tes.register_handler(on_alarm)

# Next update_sync() will call on_alarm() for any breach
ds.update_sync({"core_temp_C": 41.2, "heart_rate_bpm": 108, "spo2_pct": 92.0})
# ALARM  hyperthermia/hypothermia: core_temp_C = 41.20
# ALARM  hypoxaemia: spo2_pct = 92.00
```

---

## 5. Time-series history

Every state snapshot is stored in the Time-Series Log. Query any property over any window:

```python
# All recorded values for heart rate
history = ds.query_history("heart_rate_bpm")
for record in history:
    print(f"t={record['timestamp']:.1f}  HR={record['value']} bpm")

# Last 3 readings only
recent = ds.query_history("core_temp_C", limit=3)

# Readings since a Unix timestamp
import time
window = ds.query_history("spo2_pct", since=time.time() - 300)  # last 5 minutes
```

---

## 6. VeDDRA adverse event report

Generate a structured pharmacovigilance report from the current state:

```python
report = ds.veddra_report()

print(report["taxa"])                   # → Bos taurus
print(report["adverse_event_score"])    # → 0.333
print(report["reporting_standard"])     # → VeDDRA v2.2

for sign in report["clinical_signs"]:
    print(f"[{sign['veddra_id']}] {sign['veddra_term']}"
          f" ({sign['state_key']} = {sign['value']:.2f})")
# [10020557] Hyperthermia (core_temp_C = 41.20)
# [10021143] Hypoxia (spo2_pct = 92.00)
```

---

## 7. JSON-LD export

Export the current state as a self-describing linked-data document. Every property carries its ontology URI in the `@context` block:

```python
import json
doc = ds.to_jsonld()
print(json.dumps(doc, indent=2))
# {
#   "@context": {
#     "heart_rate_bpm": "http://purl.obolibrary.org/obo/CMO_0000052",
#     "spo2_pct": "http://snomed.info/id/59408-5",
#     ...
#   },
#   "@type": "DigitalSoma",
#   "taxa": "Bos taurus",
#   "heart_rate_bpm": 108.0,
#   ...
# }
```

---

## 8. Custom sensors (BYOD manifest)

Any sensor stream can be ingested using the six-field manifest contract. Units are converted automatically.

```python
from digitalsoma.sensor.sensor_layer import SensorManifest, SensorManifestEntry

manifest = SensorManifest()
manifest.register(SensorManifestEntry(
    sensor_id    = "collar_001",
    canonical_key = "heart_rate_bpm",
    unit         = "bpm",
))
manifest.register(SensorManifestEntry(
    sensor_id    = "rectal_probe_02",
    canonical_key = "core_temp_C",
    unit         = "°F",          # → automatically converted to °C
))

# Read a batch from manifest into update_sync()
readings = manifest.read_batch([
    {"sensor_id": "collar_001",    "value": 74.0, "quality_flag": 0},
    {"sensor_id": "rectal_probe_02", "value": 102.8, "quality_flag": 0},
])
state = ds.update_sync(readings)
```

Use a preset manifest for a standard cattle wearable collar suite:

```python
from digitalsoma.sensor.sensor_layer import wearable_cattle_manifest
manifest = wearable_cattle_manifest()
```

---

## 9. Custom solvers

Register any Python function as a solver with `register_method()`. Custom solvers run after all built-ins in the DAG, so they can consume cardiovascular, metabolic, and stress outputs from the same update cycle.

```python
def hrv_estimator(params: dict, state: dict) -> dict:
    hr  = state.get("heart_rate_bpm")
    psi = state.get("physiological_stress_index", 0.0)
    if hr is None or hr <= 0:
        return {}
    rr_ms = (60.0 / hr) * 1000.0
    rmssd = rr_ms * 0.065 * (1.0 - 0.85 * psi)
    return {
        "hrv_rmssd_ms": max(rmssd, 2.0),
        "hrv_status":   "normal" if rmssd >= 30 else "reduced" if rmssd >= 15 else "suppressed",
    }

ds.register_method("hrv_estimator", hrv_estimator)

state = ds.update_sync({"heart_rate_bpm": 72, "core_temp_C": 38.5})
print(state["hrv_rmssd_ms"])    # → 57.3
print(state["hrv_status"])      # → normal
```

---

## 10. Custom species

Register a new animal type without modifying the codebase:

```python
from digitalsoma import register_animal_type, build_soma, SomaConfig

register_animal_type("feline_adult", {
    "taxa":                "Felis catus",
    "ncbi_taxon_id":       "9685",
    "body_mass_kg":        4.5,
    "core_temp_normal_C":  38.6,
    "hr_normal_bpm":       150.0,
    "rr_normal_bpm":       30.0,
    "systems":             ["cardiovascular", "metabolic", "thermoregulation",
                            "respiratory", "neuroendocrine"],
})

ds = build_soma(SomaConfig(animal_type="feline_adult", site_name="Vet clinic"))
state = ds.update_sync({"heart_rate_bpm": 160, "core_temp_C": 39.0})
```

---

## 11. Run the examples

```bash
python examples/e1_build_and_describe.py    # structural layer across all 5 species
python examples/e2_solver_chain.py          # heat-stress/recovery cycle
python examples/e3_ontology_compliance.py   # alias resolution and JSON-LD
python examples/e4_custom_solver.py         # HRV extension + VeDDRA report
```

---

## 12. Run the tests

```bash
# With pytest
python -m pytest tests/ -v

# Without pytest
python tests/test_soma.py
python tests/test_ontology.py
```

---

## Next steps

- **[User Manual](USER_MANUAL.md)** — complete API reference, all classes, all methods, all configuration options
- **[Examples](../examples/)** — four annotated examples covering the full feature set
- **[ORCID](https://orcid.org/0000-0002-9986-5324)** — Dr. ir. Ali Youssef's research profile
