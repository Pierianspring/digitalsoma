# DigitalSoma

**A Digital Twin Framework for Animal Physiology Monitoring**

DigitalSoma (DS) is an open-source Python framework that represents a living animal as a continuously updated physiological digital twin. The framework bridges three persistent gaps in animal health monitoring: disconnected sensors and physiological models, cross-device interoperability, and the inference gap between raw sensor signals and clinically meaningful state variables.

**Author:** Dr. ir. Ali Youssef — Adjunct Professor, Computational Bio-Ecosystems, Agroecosystems Laboratory, University of Manitoba &amp; BioTwinR Ltd.
**ORCID:** [0000-0002-9986-5324](https://orcid.org/0000-0002-9986-5324)

---

## Metadata

| Code | Description | Value |
|------|-------------|-------|
| C1 | Current code version | v2.0.0 |
| C2 | License | CC BY 4.0 |
| C3 | Languages | Python 3.9, 3.10, 3.11, 3.12 — standard library only |
| C4 | Dependencies | Zero runtime dependencies. Optional: PyYAML ≥ 6.0 `[yaml]`; Anthropic SDK ≥ 0.20 `[llm]` |
| C5 | Install | `pip install -e .` |
| C6 | Ontology namespaces | Uberon, SNOMED CT, VeDDRA, NCBITaxon, UCUM, PATO, HP/MP |

---

## Architecture

DigitalSoma is built on a five-layer architecture, with each layer handling a distinct concern:

```
Input sources
  Wearable sensors · Implanted devices · Remote sensing · Lab assays · Manual entry
          │
          ▼
  ONTOLOGY & NORMALISATION LAYER          (ontology/vocab.py)
  Uberon · SNOMED · VeDDRA · NCBITaxon · UCUM
  canonical_key() · normalise_dict() · to_jsonld()
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│  DigitalSoma (soma_api.py)                                  │
│                                                             │
│  STRUCTURAL LAYER        DYNAMIC LAYER    FUNCTIONAL LAYER  │
│  Animal Type Registry    KV Store         Model Zoo         │
│  Species · Anatomy       Time-Series Log  Solver chain      │
│  Normal ranges           Threshold TES    register_method() │
│  build_soma(config)      update_sync()    Built-in solvers  │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
  LLM AGENTIC INTERFACE LAYER             (soma_agent.py)
  10 OpenAI-compatible tool schemas · SomaDispatcher
          │
          ▼
Output types
  State snapshot · Time-series export · JSON-LD export · VeDDRA AE report · LLM response
```

### Three primary layers

**Structural Layer (SL)** — populated once by `build_soma()` and never modified at runtime. Stores species identity (NCBITaxon ID), body mass, normal physiological ranges, and anatomical system registry. An Animal Type Registry (ATR) provides five named templates (`bovine_adult`, `ovine_adult`, `canine_adult`, `salmonid_adult`, `equine_adult`) via an inheritance-by-merge pattern.

**Dynamic Layer (DL)** — manages live physiological state through three optimised structures: a Key-Value Store (KVS) for O(1) current state access, an append-only Time-Series Log (TSL) for temporal queries via `query_history()`, and a Threshold Event System (TES) that fires configurable observer-pattern callbacks on physiological alarms (hyperthermia, tachycardia, hypoxaemia, hypoglycaemia, HPA activation).

**Functional Layer (FL)** — a Model Zoo where all registered solvers execute in sequence on every `update_sync()` call, each receiving a params-dict and a state-dict and returning derived quantities merged into state, forming a Directed Acyclic Graph (DAG) of physiological data dependencies.

---

## Installation

```bash
git clone https://github.com/your-org/digitalsoma
cd digitalsoma
pip install -e .

# Optional extras
pip install -e ".[yaml]"    # PyYAML support
pip install -e ".[llm]"     # Anthropic SDK for LLM agent interface
```

---

## Quick start

```python
from digitalsoma import build_soma, SomaConfig

# Build a bovine digital twin
ds = build_soma(SomaConfig(animal_type="bovine_adult", site_name="Farm A"))

# Ingest sensor readings — vendor aliases resolved automatically
state = ds.update_sync({
    "HR":       72,       # alias for heart_rate_bpm
    "Tb":       39.1,     # alias for core_temp_C
    "SpO2":     97.5,     # alias for spo2_pct
    "RR":       24,       # alias for respiratory_rate_bpm
})

# All derived variables are computed automatically
print(state["cardiac_output_L_min"])       # cardiovascular solver
print(state["rmr_W"])                      # metabolic solver
print(state["physiological_stress_index"]) # neuroendocrine solver
print(state["adverse_event_score"])        # VeDDRA screening solver
print(state["ae_flags"])                   # VeDDRA clinical sign flags

# JSON-LD export (Uberon/SNOMED/VeDDRA URIs)
doc = ds.to_jsonld()

# VeDDRA adverse event report
report = ds.veddra_report()

# Time-series query
history = ds.query_history("heart_rate_bpm", limit=10)

# Natural language description (for LLM agents)
print(ds.describe())
```

---

## Core functionalities

### F1. Animal Type Registry initialisation

```python
from digitalsoma import build_soma, SomaConfig

ds = build_soma(SomaConfig(animal_type="canine_adult", site_name="Vet clinic, Leuven"))
print(ds.structural_layer)
# {'taxa': 'Canis lupus familiaris', 'ncbi_taxon_id': '9615',
#  'body_mass_kg': 25.0, 'hr_normal_bpm': 90.0, ...}
```

Custom species are registered without modifying the codebase:

```python
from digitalsoma import register_animal_type, build_soma, SomaConfig

register_animal_type("alpaca_adult", {
    "taxa": "Vicugna pacos",
    "ncbi_taxon_id": "30538",
    "body_mass_kg": 65.0,
    "core_temp_normal_C": 38.0,
    "hr_normal_bpm": 70.0,
    "rr_normal_bpm": 20.0,
    "systems": ["cardiovascular", "metabolic", "thermoregulation"],
})
ds = build_soma(SomaConfig(animal_type="alpaca_adult"))
```

### F2. Real-time physiological inference

On every `update_sync()` call, six built-in solvers execute automatically:

| Solver | Model | Outputs |
|--------|-------|---------|
| `cardiovascular_baseline` | Fick cardiac output | `cardiac_output_L_min`, `mean_arterial_pressure_mmHg` |
| `metabolic_rate` | Kleiber's law + Q10 | `rmr_kcal_day`, `rmr_W` |
| `thermoregulation` | Newton's heat balance | `heat_loss_W`, `net_heat_flux_W`, `thermal_comfort_index` |
| `respiratory_gas_exchange` | Respiratory quotient | `vo2_L_min`, `vco2_L_min`, `minute_ventilation_L_min` |
| `neuroendocrine_stress` | HPA axis composite | `physiological_stress_index` |
| `adverse_event_screen` | VeDDRA mapping | `ae_flags`, `adverse_event_score` |

### F3. Extensible solver registry

```python
def hrv_solver(params: dict, state: dict) -> dict:
    """Custom HRV estimator — consumes cardiac_output_L_min from built-in solver."""
    hr = state.get("heart_rate_bpm", 0)
    psi = state.get("physiological_stress_index", 0)
    rmssd_ms = (60000.0 / hr) * 0.065 * (1.0 - 0.85 * psi) if hr > 0 else 0
    return {"hrv_rmssd_ms": rmssd_ms}

ds.register_method("hrv_estimator", hrv_solver)
# hrv_rmssd_ms now appears in every subsequent update_sync() output
```

Built-in solvers can be unregistered and replaced with custom alternatives:

```python
ds.unregister_method("adverse_event_screen")
ds.register_method("adverse_event_screen", my_custom_ae_solver)
```

### F4. BYOD sensor manifest

```python
from digitalsoma.sensor.sensor_layer import SensorLayer, SensorManifestEntry, wearable_cattle_manifest

# Pre-built manifest
layer = wearable_cattle_manifest()

# Or build custom
layer = SensorLayer()
layer.register_sensor(SensorManifestEntry(
    sensor_id="CGM_01",
    property_alias="glucose",
    unit="mg/dL",          # auto-converted to mmol/L
    description="Continuous glucose monitor",
))

# Ingest raw readings
readings = layer.ingest([
    {"sensor_id": "CGM_01", "value": 90.0, "quality_flag": 0},
])
state = ds.update_sync(readings)
```

Unit conversions included: °F → °C, K → °C, kPa → mmHg, psi → mmHg, mg/dL → mmol/L (glucose), μg/dL → nmol/L (cortisol), lb → kg, g → kg, Hz → /min.

### F5. Semantic interoperability and JSON-LD export

`ontology/vocab.py` anchors 44 canonical properties to Uberon, SNOMED CT, VeDDRA, and NCBITaxon URIs. `canonical_key()` resolves any vendor alias in O(1). `to_jsonld()` exports state snapshots as self-describing linked-data documents.

```python
from digitalsoma.ontology.vocab import canonical_key, normalise_dict, to_jsonld

canonical_key("HR")    # → 'heart_rate_bpm'
canonical_key("SpO2")  # → 'spo2_pct'
canonical_key("Tb")    # → 'core_temp_C'

doc = ds.to_jsonld()
# doc["@context"]["heart_rate_bpm"]["@id"]
# → 'http://purl.obolibrary.org/obo/CMO_0000052'
```

### F6. Threshold event system

```python
def alert_handler(key: str, value: float, label: str) -> None:
    print(f"ALARM: {label} — {key}={value:.2f}")
    # trigger_notification() / open_valve() / log_to_farm_system()

ds._tes.register_handler(alert_handler)
# Fires automatically on every update_sync() that breaches a threshold
```

Default alarms: hyperthermia/hypothermia, tachycardia/bradycardia, hypoxaemia, hypoglycaemia/hyperglycaemia, HPA stress activation.

### F7. VeDDRA adverse event reporting

```python
report = ds.veddra_report()
# {
#   "@type": "VeDDRA_AdverseEventReport",
#   "reporting_standard": "VeDDRA v2.2",
#   "taxa": "Bos taurus",
#   "adverse_event_score": 0.5,
#   "clinical_signs": [
#     {"veddra_id": "10020557", "veddra_term": "Hyperthermia", ...},
#     {"veddra_id": "10043071", "veddra_term": "Tachycardia",  ...},
#   ]
# }
```

### F8. LLM agentic interface

```python
from digitalsoma.soma_agent import SomaDispatcher, TOOL_SCHEMAS

dispatcher = SomaDispatcher(ds, sensor_layer=layer)

# Expose to any OpenAI-compatible LLM
tools = TOOL_SCHEMAS   # 10 tool schemas

# Dispatch a tool call
result = dispatcher.dispatch("ds_describe", {})
result = dispatcher.dispatch("ds_get_state", {"property": "HR"})
result = dispatcher.dispatch("ds_veddra_report", {})
```

---

## Ontology vocabulary

| Namespace | Role | URI base |
|-----------|------|----------|
| Uberon | Cross-species anatomy and physiology | `http://purl.obolibrary.org/obo/UBERON_` |
| SNOMED CT | Clinical findings and body structures | `http://snomed.info/id/` |
| **VeDDRA** | **Veterinary adverse event terminology** | `https://www.ema.europa.eu/en/veterinary-regulatory/` |
| NCBITaxon | Species and taxon identifiers | `http://purl.obolibrary.org/obo/NCBITaxon_` |
| UCUM | Units of measure | `http://unitsofmeasure.org/` |
| PATO | Phenotypic quality descriptors | `http://purl.obolibrary.org/obo/PATO_` |
| HP / MP | Human/mammalian phenotype ontology | `http://purl.obolibrary.org/obo/HP_` |

VeDDRA spans both the ontology layer (clinical sign term URIs registered as `OntologyProperty` dataclasses) and the functional output layer (adverse event reports serialised in VeDDRA terminology for EMA EVVET3 / VMD / FDA-CVM submission).

---

## Reproducible examples

| Example | Description | Mirrors DP |
|---------|-------------|------------|
| `examples/e1_build_and_describe.py` | Build all five ATR templates; inspect structural layer | E1 GPS initialisation |
| `examples/e2_solver_chain.py` | Drive solver chain through heat-stress/recovery cycle | E2 drying-wetting cycle |
| `examples/e3_ontology_compliance.py` | 30/30 alias resolution tests + JSON-LD URI validation | E3 ontology compliance |
| `examples/e4_custom_solver.py` | HRV solver via `register_method()` consuming built-in outputs + VeDDRA report | E4 Crank-Nicolson extension |

Run all:
```bash
python examples/e1_build_and_describe.py
python examples/e2_solver_chain.py
python examples/e3_ontology_compliance.py
python examples/e4_custom_solver.py
```

---

## Citation

If you use DigitalSoma in your research, please cite it as:

```
Youssef, A. (2026). DigitalSoma: A physics-based digital twin framework for
real-time animal physiology monitoring (v2.0.0). BioTwinR Ltd. &
University of Manitoba. https://github.com/BioTwinR/digitalsoma
ORCID: 0000-0002-9986-5324
```

See `CITATION.cff` for the full CFF-format citation.

---

## License

CC BY 4.0 — see LICENSE.
