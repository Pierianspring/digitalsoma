# DigitalSoma User Manual

**Version 2.2.0** — Dr. ir. Ali Youssef (ORCID: 0000-0002-9986-5324)
Adjunct Professor, Computational Bio-Ecosystems, Agroecosystems Laboratory, University of Manitoba & BioTwinR Ltd., Winnipeg, Canada

---

## Table of contents

1. [Architecture overview](#1-architecture-overview)
2. [SomaConfig — twin configuration](#2-somaconfig)
3. [build_soma() — constructor](#3-build_soma)
4. [DigitalSoma — the twin object](#4-digitalsoma)
5. [Solver chain and Model Zoo](#5-solver-chain-and-model-zoo)
6. [Threshold Event System](#6-threshold-event-system)
7. [Ontology and vocabulary layer](#7-ontology-and-vocabulary-layer)
8. [Sensor manifest layer (BYOD)](#8-sensor-manifest-layer-byod)
9. [LLM agentic interface](#9-llm-agentic-interface)
10. [Animal Type Registry](#10-animal-type-registry)
11. [VeDDRA pharmacovigilance](#11-veddra-pharmacovigilance)
12. [FHIR R4 integration](#12-fhir-r4-integration)
13. [Canonical property reference](#13-canonical-property-reference)
14. [Unit conversion reference](#14-unit-conversion-reference)
15. [Error reference](#15-error-reference)

---

## 1. Architecture overview

DigitalSoma organises every digital twin around three nested layers and two transversal layers:

```
┌─────────────────────────────────────────────────────────────────┐
│  Input sources                                                  │
│  Wearable · Implanted · Remote sensing · Lab assay · Manual     │
└──────────────────────────┬──────────────────────────────────────┘
                           │  BYOD manifest (six-field contract)
┌──────────────────────────▼──────────────────────────────────────┐
│  Ontology & Normalisation Layer  (vocab.py)                     │
│  canonical_key() · normalise_dict() · to_jsonld()               │
└──────────────────────────┬──────────────────────────────────────┘
                           │  canonical keys
┌──────────────────────────▼──────────────────────────────────────┐
│  DigitalSoma core  (soma_api.py)                                │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ Structural   │  │ Dynamic          │  │ Functional       │  │
│  │ Layer        │  │ Layer            │  │ Layer            │  │
│  │              │  │                  │  │                  │  │
│  │ ATR template │  │ KV store         │  │ ModelZoo         │  │
│  │ Anatomy map  │  │ Time-series log  │  │ Solver DAG       │  │
│  │ Normal ranges│  │ Threshold events │  │ register_method()│  │
│  │ build_soma() │  │ update_sync()    │  │ VeDDRA screen    │  │
│  └──────────────┘  └──────────────────┘  └──────────────────┘  │
│                                                                 │
│  BYOD manifest ─────────────────────────────────── transversal │
└──────────────────────────┬──────────────────────────────────────┘
                           │  tool schemas
┌──────────────────────────▼──────────────────────────────────────┐
│  LLM Agentic Interface Layer  (soma_agent.py)                   │
│  SomaDispatcher · 10 OpenAI-compatible tool schemas             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  Outputs                                                        │
│  State snapshot · Time-series · JSON-LD · VeDDRA report · LLM  │
└─────────────────────────────────────────────────────────────────┘
```

**Structural Layer** — immutable. Set once by `build_soma()`, never modified at runtime. Holds species identity, body mass, normal physiological ranges, and anatomical system registry.

**Dynamic Layer** — live state. Overwritten on every `update_sync()` call. Comprises a key-value store (O(1) access), an append-only time-series log, and the Threshold Event System.

**Functional Layer** — computational. A directed acyclic chain of physics-based solvers that run in sequence on every `update_sync()` call.

---

## 2. SomaConfig

`SomaConfig` is a typed dataclass holding all configuration for a twin. Pass it to `build_soma()`.

```python
from digitalsoma import SomaConfig

config = SomaConfig(
    animal_type       = "bovine_adult",   # required; key into ATR
    animal_id         = "cow_042",        # optional; UUID generated if omitted
    site_name         = "Farm A",         # optional; free text
    species_override  = None,             # override taxa string
    body_mass_kg      = 550.0,            # override template body mass
    alarm_thresholds  = {},               # override TES boundaries (see §6)
    custom_systems    = [],               # list of AnatomicalSystem dicts
    metadata          = {},               # arbitrary key-value metadata
)
```

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `animal_type` | `str` | required | Key into the Animal Type Registry |
| `animal_id` | `str` | auto UUID | Unique identifier for this individual animal |
| `site_name` | `str` | `""` | Farm, clinic, or study site label |
| `species_override` | `str \| None` | `None` | Override the taxa string from the template |
| `body_mass_kg` | `float \| None` | `None` | Override template body mass |
| `alarm_thresholds` | `dict` | `{}` | Override or add TES alarm boundaries |
| `custom_systems` | `list` | `[]` | Additional `AnatomicalSystem` dicts to register |
| `metadata` | `dict` | `{}` | Arbitrary metadata stored in structural layer |

### Overriding alarm thresholds

```python
config = SomaConfig(
    animal_type      = "bovine_adult",
    alarm_thresholds = {
        "core_temp_C":    {"low": 37.0, "high": 40.0, "label": "temperature alert"},
        "spo2_pct":       {"low": 92.0, "high": None, "label": "hypoxaemia"},
    }
)
```

---

## 3. build_soma()

```python
from digitalsoma import build_soma, SomaConfig

ds = build_soma(SomaConfig(animal_type="bovine_adult"))
```

`build_soma(config)` is the canonical constructor. It creates a `DigitalSoma` instance, calls `build_soma()` on it, and returns the fully initialised twin.

Equivalent to:
```python
from digitalsoma.soma_api import DigitalSoma, SomaConfig

ds = DigitalSoma()
ds.build_soma(config)
```

**Raises** `ValueError` if `config.animal_type` is not found in the Animal Type Registry.

---

## 4. DigitalSoma

The central class. All interaction with the twin goes through this object.

### 4.1 build_soma(config)

Initialise the structural layer. Must be called before `update_sync()`.

```python
ds = DigitalSoma()
ds.build_soma(SomaConfig(animal_type="equine_adult", site_name="Stable 1"))
```

Returns `self` for chaining.

### 4.2 update_sync(readings)

```python
state = ds.update_sync({
    "heart_rate_bpm": 72,
    "core_temp_C":    39.1,
    "spo2_pct":       97.5,
})
```

Ingests a dict of sensor readings. On every call:

1. Resolves aliases to canonical keys via `canonical_key()`
2. Converts units if a converter is registered for the declared unit
3. Writes normalised values into the KV store
4. Builds the merged state dict (structural params + KV store)
5. Runs the full solver DAG (Model Zoo)
6. Writes derived outputs back into the KV store
7. Checks all TES thresholds and fires any registered callbacks
8. Appends a snapshot to the Time-Series Log

Returns the full merged state dict (all canonical keys including derived solver outputs).

**Raises** `RuntimeError` if called before `build_soma()`.

### 4.3 query_history(key, since=None, limit=None)

```python
records = ds.query_history("heart_rate_bpm")
records = ds.query_history("core_temp_C", since=time.time() - 3600)  # last hour
records = ds.query_history("spo2_pct", limit=10)                      # last 10
```

Returns a list of `{"timestamp": float, "value": any}` dicts from the Time-Series Log. Accepts any alias or canonical key.

| Parameter | Type | Description |
|---|---|---|
| `key` | `str` | Canonical key or any registered alias |
| `since` | `float \| None` | Unix timestamp; only return records at or after this time |
| `limit` | `int \| None` | Return only the last N records |

### 4.4 register_method(name, fn)

```python
def my_solver(params: dict, state: dict) -> dict:
    # params: structural constants (body_mass_kg, hr_normal_bpm, etc.)
    # state:  current accumulated state (includes all prior solver outputs)
    return {"my_output": 42.0}

ds.register_method("my_solver", my_solver)
```

Adds `fn` to the Model Zoo under the name `name`. If a solver with that name already exists it is replaced. Custom solvers execute after all built-ins in registration order.

### 4.5 unregister_method(name)

```python
ds.unregister_method("adverse_event_screen")
```

Removes a solver from the chain. Can be used to remove and replace built-in solvers.

### 4.6 to_jsonld()

```python
doc = ds.to_jsonld()
```

Returns a JSON-LD document dict. Every canonical property in the current state has its ontology URI listed in the `@context` block. The document includes `soma_id`, `taxa`, `ncbi_taxon_id`, and `animal_id` at the top level.

### 4.7 veddra_report()

```python
report = ds.veddra_report()
```

Returns a VeDDRA adverse event report dict from the current state. See [§11](#11-veddra-pharmacovigilance) for the full report structure.

### 4.8 describe()

```python
print(ds.describe())
```

Returns a formatted multi-line string summarising the twin's current physiological state. Used internally by the LLM agentic interface layer.

### 4.9 Properties

| Property | Type | Description |
|---|---|---|
| `soma_id` | `str` | UUID identifying this twin instance |
| `structural_layer` | `dict` | Deep copy of the structural layer dict |
| `solvers` | `list[str]` | Ordered list of registered solver names |

---

## 5. Solver chain and Model Zoo

### 5.1 Built-in solvers

All six built-in solvers are registered in the following DAG order at construction time:

#### cardiovascular_baseline

**Inputs from state:** `heart_rate_bpm`, `stroke_volume_mL` (default 80 mL), `systolic_bp_mmHg`, `diastolic_bp_mmHg`

**Outputs:**

| Key | Unit | Description |
|---|---|---|
| `cardiac_output_L_min` | L/min | Estimated cardiac output (Fick approximation) |
| `mean_arterial_pressure_mmHg` | mmHg | MAP = DBP + (SBP − DBP) / 3; only if BP values present |

**Equation:** `CO = HR × SV / 1000`

#### metabolic_rate

**Inputs from params:** `body_mass_kg`, `core_temp_normal_C`; **from state:** `core_temp_C`

**Outputs:**

| Key | Unit | Description |
|---|---|---|
| `rmr_kcal_day` | kcal/day | Temperature-corrected resting metabolic rate |
| `rmr_W` | W | RMR in watts |

**Equations:** `RMR = 70 × M^0.75` (Kleiber's law); `RMR_adj = RMR × Q10^((T − T_ref) / 10)` where Q10 = 2.0

#### thermoregulation

**Inputs from state:** `core_temp_C`, `ambient_temp_C` (default 20 °C), `rmr_W`

**Outputs:**

| Key | Unit | Description |
|---|---|---|
| `heat_loss_W` | W | Convective heat loss to environment |
| `net_heat_flux_W` | W | Net heat balance (metabolic production − loss) |
| `thermal_comfort_index` | dimensionless | TCI: ~0 = thermoneutral, >0.1 = heat stress, <−0.1 = cold stress |

**Equation:** `TCI = (RMR_W − k × (T_core − T_ambient)) / RMR_W`

#### respiratory_gas_exchange

**Inputs from state:** `rmr_W`, `respiratory_rate_bpm`, `spo2_pct`

**Outputs:**

| Key | Unit | Description |
|---|---|---|
| `vo2_L_min` | L/min | Estimated oxygen consumption |
| `vco2_L_min` | L/min | Estimated CO₂ production |
| `minute_ventilation_L_min` | L/min | Minute ventilation (if RR available) |

**Equations:** `VO₂ = RMR_W × 0.01433 / 4.8`; `VCO₂ = VO₂ × RQ` (RQ = 0.85); `VE = RR × V_T`

#### neuroendocrine_stress

**Inputs from state:** `heart_rate_bpm`, `cortisol_nmol_L`, `thermal_comfort_index`

**Outputs:**

| Key | Unit | Description |
|---|---|---|
| `physiological_stress_index` | 0–1 | Composite HPA-axis stress index |

**Equation:** Mean of normalised deviations from species normal for HR, cortisol, and TCI. Each component clipped to [0, 1].

#### adverse_event_screen

**Inputs from state:** `core_temp_C`, `heart_rate_bpm`, `spo2_pct`, `physiological_stress_index`

**Outputs:**

| Key | Type | Description |
|---|---|---|
| `ae_flags` | list of dicts | VeDDRA-mapped clinical sign flags |
| `adverse_event_score` | float 0–1 | Proportion of screened signs currently flagged |

Each flag dict contains: `state_key`, `value`, `veddra_term`, `veddra_id`, `veddra_namespace`.

### 5.2 Writing a custom solver

A solver is any Python callable with signature `(params: dict, state: dict) -> dict`:

```python
def my_solver(params: dict, state: dict) -> dict:
    """
    params: structural constants from the twin's config
            (body_mass_kg, hr_normal_bpm, core_temp_normal_C, etc.)
    state:  current accumulated state including all prior solver outputs.
            Safe to read any key; missing keys return None via .get().
    return: dict of new key-value pairs to add to the state.
            Do not mutate params or state directly.
    """
    hr = state.get("heart_rate_bpm")
    co = state.get("cardiac_output_L_min")   # available: cardiovascular ran first
    if hr is None:
        return {}
    return {"my_derived_variable": hr * 0.5}
```

Register it:

```python
ds.register_method("my_solver", my_solver)
```

The solver runs after all six built-ins. Solvers execute in registration order, so if you register multiple custom solvers they can chain dependencies between themselves.

---

## 6. Threshold Event System

The TES holds a dict of alarm configurations keyed by canonical property name. On every `update_sync()`, every registered threshold is evaluated against the current state.

### 6.1 Default alarms

| Property | Low | High | Label |
|---|---|---|---|
| `core_temp_C` | 37.5 | 40.5 | hyperthermia/hypothermia |
| `heart_rate_bpm` | 30.0 | 120.0 | bradycardia/tachycardia |
| `respiratory_rate_bpm` | 8.0 | 60.0 | bradypnea/tachypnea |
| `spo2_pct` | 90.0 | — | hypoxaemia |
| `blood_glucose_mmol_L` | 2.5 | 10.0 | hypoglycaemia/hyperglycaemia |
| `cortisol_nmol_L` | — | 200.0 | stress/HPA activation |

Note: these are bovine reference defaults. Override via `SomaConfig.alarm_thresholds` or by modifying `ds._tes._thresholds` directly.

### 6.2 Registering callbacks

```python
def alarm_handler(key: str, value: float, label: str) -> None:
    # key:   canonical property key (e.g. "core_temp_C")
    # value: current value that breached the threshold
    # label: human-readable alarm label
    send_alert(f"[{label}] {key} = {value:.2f}")

ds._tes.register_handler(alarm_handler)
```

Multiple handlers can be registered. All are called for every alarm event. Exceptions in handlers are caught and logged; they do not interrupt the update cycle.

### 6.3 Custom thresholds at build time

```python
config = SomaConfig(
    animal_type      = "equine_adult",
    alarm_thresholds = {
        "core_temp_C":    {"low": 37.0, "high": 38.9, "label": "equine temp alert"},
        "heart_rate_bpm": {"low": 20.0, "high": 60.0,  "label": "equine HR alert"},
    }
)
```

### 6.4 Adding thresholds for custom properties

```python
ds._tes._thresholds["hrv_rmssd_ms"] = {
    "low": 10.0, "high": None, "label": "HRV suppression"
}
```

---

## 7. Ontology and vocabulary layer

### 7.1 canonical_key(alias)

```python
from digitalsoma.ontology.vocab import canonical_key

canonical_key("HR")      # → "heart_rate_bpm"
canonical_key("SpO2")    # → "spo2_pct"
canonical_key("Tb")      # → "core_temp_C"
canonical_key("CO")      # → "cardiac_output_L_min"
```

O(1) alias resolution. If the alias is not found, the input is returned unchanged.

### 7.2 normalise_dict(d)

```python
from digitalsoma.ontology.vocab import normalise_dict

raw = {"HR": 72, "SpO2": 97.5, "Tb": 39.1}
norm = normalise_dict(raw)
# → {"heart_rate_bpm": 72, "spo2_pct": 97.5, "core_temp_C": 39.1}
```

Rewrites all keys in one pass. Unknown keys are passed through unchanged.

### 7.3 to_jsonld(state)

```python
from digitalsoma.ontology.vocab import to_jsonld

doc = to_jsonld({"heart_rate_bpm": 72, "spo2_pct": 97.5})
# Returns a JSON-LD document with @context mapping each key to its ontology URI
```

### 7.4 Ontology namespaces

| Namespace | Prefix | Authority |
|---|---|---|
| Uberon | `http://purl.obolibrary.org/obo/UBERON_` | Multi-species anatomy |
| SNOMED CT | `http://snomed.info/id/` | Clinical findings |
| VeDDRA | `https://www.ema.europa.eu/en/veterinary-regulatory/` | Veterinary AE terminology |
| NCBITaxon | `http://purl.obolibrary.org/obo/NCBITaxon_` | Species taxonomy |
| UCUM | `http://unitsofmeasure.org/` | Units of measure |
| PATO | `http://purl.obolibrary.org/obo/PATO_` | Phenotypic qualities |
| HP/MP | `http://purl.obolibrary.org/obo/HP_` | Mammalian phenotype |

---

## 8. Sensor manifest layer (BYOD)

### 8.1 SensorManifestEntry

```python
from digitalsoma.sensor.sensor_layer import SensorManifestEntry

entry = SensorManifestEntry(
    sensor_id     = "device_001",        # unique device identifier
    canonical_key = "heart_rate_bpm",    # target canonical key
    unit          = "bpm",               # raw unit of the stream
    quality_flag  = 0,                   # default quality (0=good)
    conversion_fn = None,                # optional custom converter callable
)
```

### 8.2 SensorManifest

```python
from digitalsoma.sensor.sensor_layer import SensorManifest, SensorManifestEntry

manifest = SensorManifest()
manifest.register(SensorManifestEntry(
    sensor_id="temp_probe", canonical_key="core_temp_C", unit="°F"
))

batch = manifest.read_batch([
    {"sensor_id": "temp_probe", "value": 102.2, "quality_flag": 0}
])
# → {"core_temp_C": 39.0}   # °F → °C conversion applied
```

### 8.3 Preset manifests

```python
from digitalsoma.sensor.sensor_layer import (
    wearable_cattle_manifest,
    implant_bovine_manifest,
    lab_panel_manifest,
)

manifest = wearable_cattle_manifest()   # HR, temp, SpO2, accel, RR
manifest = implant_bovine_manifest()    # rumen temp, rumen pH, bolus accel
manifest = lab_panel_manifest()         # glucose, cortisol, haematocrit, WBC
```

### 8.4 Quality flags

Quality flags follow the QARTOD convention:

| Flag | Meaning |
|---|---|
| 0 | Good |
| 1 | Questionable / not evaluated |
| 2 | Bad |

Readings with `quality_flag = 2` are logged but excluded from state updates by default.

---

## 9. LLM agentic interface

### 9.1 SomaDispatcher

```python
from digitalsoma.soma_agent import SomaDispatcher
from digitalsoma import build_soma, SomaConfig

ds = build_soma(SomaConfig(animal_type="bovine_adult"))
dispatcher = SomaDispatcher(ds)

# Dispatch a tool call (as returned by an LLM)
result = dispatcher.dispatch("ds_describe", {})
result = dispatcher.dispatch("ds_update", {"readings": {"HR": 80, "core_temp_C": 39.5}})
result = dispatcher.dispatch("ds_get_state", {"property": "cardiac_output_L_min"})
```

### 9.2 Tool schemas

```python
from digitalsoma.soma_agent import TOOL_SCHEMAS
# Pass to any OpenAI-compatible LLM API as the `tools` parameter
```

The 10 available tool schemas:

| Tool | Description |
|---|---|
| `ds_describe` | Full twin state summary |
| `ds_get_state` | Retrieve a specific property value |
| `ds_update` | Ingest sensor readings and re-run solver chain |
| `ds_query_history` | Time-series for a property |
| `ds_list_solvers` | List registered solvers |
| `ds_to_jsonld` | Export state as JSON-LD |
| `ds_veddra_report` | Generate VeDDRA adverse event report |
| `ds_alarm_status` | Check TES threshold status |
| `ds_manifest_summary` | List registered sensor manifest entries |
| `ds_structural_layer` | Inspect the structural layer |

---

## 10. Animal Type Registry

### 10.1 Built-in templates

```python
from digitalsoma.soma_api import _ANIMAL_TYPE_REGISTRY
print(list(_ANIMAL_TYPE_REGISTRY.keys()))
# → ['bovine_adult', 'ovine_adult', 'canine_adult', 'salmonid_adult', 'equine_adult']
```

### 10.2 Registering a custom species

```python
from digitalsoma import register_animal_type

register_animal_type("caprine_adult", {
    "taxa":                "Capra hircus",
    "ncbi_taxon_id":       "9925",
    "body_mass_kg":        60.0,
    "core_temp_normal_C":  39.3,
    "hr_normal_bpm":       85.0,
    "rr_normal_bpm":       25.0,
    "systems":             ["cardiovascular", "metabolic", "thermoregulation",
                            "respiratory", "musculoskeletal", "neuroendocrine"],
})
```

Required keys: `taxa`, `ncbi_taxon_id`, `body_mass_kg`, `hr_normal_bpm`, `rr_normal_bpm`, `systems`. Optional: `core_temp_normal_C` (omit or set to `None` for ectotherms).

---

## 11. VeDDRA pharmacovigilance

### 11.1 Screened clinical signs

The `adverse_event_screen` solver maps six state variables to VeDDRA term IDs:

| VeDDRA term | VeDDRA ID | Trigger condition |
|---|---|---|
| Hyperthermia | 10020557 | `core_temp_C > normal + 1.5 °C` |
| Hypothermia | 10021113 | `core_temp_C < normal − 2.0 °C` |
| Tachycardia | 10043071 | `heart_rate_bpm > normal × 1.5` |
| Bradycardia | 10006093 | `heart_rate_bpm < normal × 0.6` |
| Hypoxia | 10021143 | `spo2_pct < 90 %` |
| Distress | 10013029 | `physiological_stress_index > 0.7` |

### 11.2 VeDDRA report structure

```python
report = ds.veddra_report()
```

```json
{
  "@type":                "VeDDRA_AdverseEventReport",
  "report_id":            "uuid-string",
  "soma_id":              "uuid-string",
  "animal_id":            "cow_042",
  "taxa":                 "Bos taurus",
  "timestamp":            1704067200.0,
  "adverse_event_score":  0.333,
  "clinical_signs": [
    {
      "state_key":         "core_temp_C",
      "value":             41.2,
      "veddra_term":       "Hyperthermia",
      "veddra_id":         "10020557",
      "veddra_namespace":  "https://www.ema.europa.eu/en/veterinary-regulatory/"
    }
  ],
  "veddra_namespace":     "https://www.ema.europa.eu/en/veterinary-regulatory/",
  "reporting_standard":   "VeDDRA v2.2"
}
```

---

## 12. FHIR R4 integration

DigitalSoma v2.2.0 adds a native HL7 FHIR R4 I/O layer through the `digitalsoma.fhir` subpackage. It is a zero-dependency implementation — pure Python standard library, no `fhir.resources` package required.

### 12.1 Overview

FHIR (Fast Healthcare Interoperability Resources) is the HL7 standard for real-time clinical data exchange. DigitalSoma uses it as a transport envelope, not a replacement for its internal ontology layer. The mapping is:

| DigitalSoma concept | FHIR R4 resource |
|---|---|
| Animal subject | `Patient` with `patient-animal` species extension (NCBITaxon) |
| Digital twin identifier | `Device` |
| Each canonical state property | `Observation` (LOINC + SNOMED CT codes, UCUM units) |
| VeDDRA adverse event findings | `DiagnosticReport` (SNOMED CT conclusions + VeDDRA IDs as extensions) |
| Full twin export | `Bundle` (collection or transaction) |

### 12.2 Exporting to FHIR

`to_fhir_bundle()` is available as a method on every `DigitalSoma` instance and also as a module-level function:

```python
import json
from digitalsoma.soma_api import build_soma, SomaConfig
from digitalsoma.fhir import to_fhir_bundle

ds = build_soma(SomaConfig(animal_type="equine_adult", animal_id="eclipse-001"))
ds.update_sync({"heart_rate_bpm": 168, "core_temp_C": 38.7, "spo2_pct": 97.5})

# Method on the twin (preferred)
bundle = ds.to_fhir_bundle()

# Module-level function (identical result)
bundle = to_fhir_bundle(ds)

# Transaction bundle for POST to a FHIR server
tx_bundle = ds.to_fhir_bundle(bundle_type="transaction")

print(json.dumps(bundle, indent=2))
```

A typical export for an equine twin produces 21 entries: 1 Patient + 1 Device + 18 Observations + 1 DiagnosticReport.

### 12.3 Bundle structure

```
Bundle
├── Patient/eclipse-001
│     extension: patient-animal → NCBITaxon:9796 (Equus caballus)
│     identifier: urn:digitalsoma:animal
│
├── Device/<soma_id>
│     identifier: urn:digitalsoma:soma_id
│     patient: Patient/eclipse-001
│
├── Observation  (heart_rate_bpm = 168 /min)
│     code: LOINC 8867-4 + SNOMED 364075005
│     valueQuantity: 168.0 /min (UCUM)
│     extension: urn:digitalsoma:canonical_key = "heart_rate_bpm"
│
├── Observation  (core_temp_C = 38.7 Cel)
│     code: LOINC 8310-5 + SNOMED 276885007
│     …
│
├── … (one Observation per mapped canonical property)
│
└── DiagnosticReport
      category: VET
      code: LOINC 11488-4 + VeDDRA AE Screen
      conclusion: "Tachycardia [VeDDRA 10043071]"
      conclusionCode: SNOMED 3424008 + VeDDRA 10043071
      extension: urn:digitalsoma:ae_score = 0.1667
```

### 12.4 Coded observations

Every `Observation` carries dual coding — LOINC (preferred for standard vitals) and SNOMED CT — plus a UCUM unit and a DigitalSoma extension carrying the round-trip canonical key:

```json
{
  "resourceType": "Observation",
  "status": "final",
  "code": {
    "coding": [
      {"system": "http://loinc.org",         "code": "8867-4",    "display": "Heart rate"},
      {"system": "http://snomed.info/sct",   "code": "364075005", "display": "Heart rate"}
    ],
    "text": "Heart rate"
  },
  "valueQuantity": {"value": 168.0, "unit": "/min", "system": "http://unitsofmeasure.org"},
  "extension": [{"url": "urn:digitalsoma:canonical_key", "valueString": "heart_rate_bpm"}]
}
```

The 21 canonical properties with FHIR mappings include all standard vitals (HR, BP, SpO₂, RR, temperature), metabolic and biochemistry markers (glucose, cortisol, insulin, haematocrit, haemoglobin, WBC, creatinine), activity and composite scores (PSI, TCI, AE score, RMR, VO₂, MV), and body weight.

### 12.5 VeDDRA in the DiagnosticReport

When adverse event flags are active, each flag appears in `conclusionCode` with dual coding — the SNOMED CT clinical finding concept and the VeDDRA term ID:

```python
ds.update_sync({"core_temp_C": 40.2, "cortisol_nmol_L": 185.0, "heart_rate_bpm": 192.0})
bundle = ds.to_fhir_bundle()

# DiagnosticReport.status   = "amended"
# DiagnosticReport.conclusion = "Hyperthermia [VeDDRA 10020557]; Tachycardia [VeDDRA 10043071]; Distress [VeDDRA 10013029]"
```

| VeDDRA term | VeDDRA ID | SNOMED CT code | SNOMED display |
|---|---|---|---|
| Hyperthermia | 10020557 | 386689009 | Hyperthermia |
| Hypothermia | 10021113 | 386692006 | Hypothermia |
| Tachycardia | 10043071 | 3424008 | Tachycardia |
| Bradycardia | 10006093 | 48867003 | Bradycardia |
| Hypoxia | 10021143 | 389086002 | Hypoxia |
| Distress | 10013029 | 274668005 | Physiological distress |

### 12.6 Ingesting FHIR data

`from_fhir_bundle()` parses an incoming FHIR R4 Bundle of `Observation` resources and returns a readings dict ready for `update_sync()`. It resolves canonical keys by looking for the DigitalSoma `urn:digitalsoma:canonical_key` extension first (round-trip fidelity), then by LOINC code lookup.

```python
from digitalsoma.fhir import from_fhir_bundle

# Parse an incoming bundle (e.g. from a wearable gateway or EHR)
readings = from_fhir_bundle(incoming_bundle)
# → {"heart_rate_bpm": 72.0, "core_temp_C": 38.5, "spo2_pct": 98.2, ...}

ds.update_sync(readings)
```

Non-Observation resources (Patient, Device, DiagnosticReport) are silently ignored. Observations without a recognisable LOINC code or DigitalSoma extension are also silently skipped.

### 12.7 Using FHIRMapper directly

For custom integrations, `FHIRMapper` is exposed at the package level:

```python
from digitalsoma.fhir import FHIRMapper

mapper = FHIRMapper()

# Build individual resources
patient = mapper.patient("horse-001", taxa="Equus caballus", ncbi_taxon_id="9796")
device  = mapper.device(soma_id=ds.soma_id, animal_id="horse-001")
obs     = mapper.observation("cortisol_nmol_L", 185.0, "Patient/horse-001")
report  = mapper.diagnostic_report(ae_flags, ae_score, "Patient/horse-001", ds.soma_id)

# Assemble into a bundle
bundle  = mapper.bundle([patient, device, obs, report])
```

### 12.8 LLM tool: ds_to_fhir_bundle

The FHIR export is available as the 11th LLM tool in `soma_agent.py`:

```python
result = dispatcher.dispatch("ds_to_fhir_bundle", {"bundle_type": "collection"})
# → FHIR R4 Bundle dict (JSON-serialisable)
```

### 12.9 Posting to a FHIR server

Use `bundle_type="transaction"` and POST with any HTTP client:

```python
import json, urllib.request

tx = ds.to_fhir_bundle(bundle_type="transaction")
req = urllib.request.Request(
    "https://your-fhir-server/fhir",
    data=json.dumps(tx).encode(),
    headers={"Content-Type": "application/fhir+json"},
    method="POST",
)
with urllib.request.urlopen(req) as resp:
    print(resp.status)
```

---

## 13. Canonical property reference

A selection of the 44 canonical properties. Full list in `digitalsoma/ontology/vocab.py`.

| Canonical key | Unit | Aliases | Ontology URI |
|---|---|---|---|
| `heart_rate_bpm` | /min | HR, hr, pulse | CMO:0000052 |
| `respiratory_rate_bpm` | /min | RR, rr, BreathRate | CMO:0000136 |
| `spo2_pct` | % | SpO2, spo2, o2_sat | SNOMED:59408-5 |
| `core_temp_C` | °C | Tb, T_core, body_temp | SNOMED:386725004 |
| `skin_temp_C` | °C | T_skin, SkinTemp | SNOMED:703915002 |
| `ambient_temp_C` | °C | T_amb, ambient_temp | PATO:0000146 |
| `systolic_bp_mmHg` | mmHg | SBP, sbp | SNOMED:271649006 |
| `diastolic_bp_mmHg` | mmHg | DBP, dbp | SNOMED:271650006 |
| `mean_arterial_pressure_mmHg` | mmHg | MAP | SNOMED:251076008 |
| `cardiac_output_L_min` | L/min | CO | CMO:0000230 |
| `stroke_volume_mL` | mL | SV | CMO:0000231 |
| `blood_glucose_mmol_L` | mmol/L | BGlucose, glucose | SNOMED:33747003 |
| `cortisol_nmol_L` | nmol/L | CORT, cortisol | SNOMED:396345004 |
| `haematocrit_pct` | % | HCT, hematocrit | CMO:0000037 |
| `body_mass_kg` | kg | BW, weight, mass_kg | UBERON:0001013 |
| `activity_counts` | counts | accel_counts, activity | PATO:0000911 |

---

## 14. Unit conversion reference

DigitalSoma converts the following units automatically when they appear in sensor manifest entries or are passed directly to `update_sync()` with a declared unit.

| From | To | Factor / Formula |
|---|---|---|
| °F | °C | (v − 32) × 5/9 |
| K | °C | v − 273.15 |
| kPa | mmHg | v × 7.50062 |
| psi | mmHg | v × 51.7149 |
| bar | mmHg | v × 750.062 |
| mg/dL | mmol/L | v / 18.0182 (glucose) |
| μg/dL | nmol/L | v × 27.5886 (cortisol) |
| lb | kg | v × 0.453592 |
| lbs | kg | v × 0.453592 |
| g | kg | v / 1000 |
| Hz | /min | v × 60 |

Unit conversion is applied at the sensor manifest layer (`sensor_layer.py`). If no converter is registered for a given unit, the raw value is passed through unchanged.

---

## 15. Error reference

| Exception | Cause | Resolution |
|---|---|---|
| `RuntimeError: Call build_soma() before update_sync()` | `update_sync()` called on uninitialised twin | Call `build_soma(config)` first |
| `ValueError: Unknown animal type '...'` | `config.animal_type` not in ATR | Use a built-in template name or call `register_animal_type()` first |
| `KeyError` in solver | Solver accessed a state key that is `None` | Guard with `state.get("key")` and return `{}` if `None` |

---

*DigitalSoma v2.2.0 — Dr. ir. Ali Youssef (ORCID: 0000-0002-9986-5324), Agroecosystems Laboratory, University of Manitoba & BioTwinR Ltd., Winnipeg, Canada. CC BY 4.0.*
