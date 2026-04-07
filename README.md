# DigitalSoma

**A physics-based digital twin framework for real-time animal physiology monitoring**

[![PyPI version](https://img.shields.io/pypi/v/digitalsoma.svg)](https://pypi.org/project/digitalsoma/)
[![Python](https://img.shields.io/pypi/pyversions/digitalsoma.svg)](https://pypi.org/project/digitalsoma/)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![ORCID](https://img.shields.io/badge/ORCID-0000--0002--9986--5324-green.svg)](https://orcid.org/0000-0002-9986-5324)

**Author:** Dr. ir. Ali Youssef — Adjunct Professor, Computational Bio-Ecosystems,
Agroecosystems Laboratory, University of Manitoba & BioTwinR Ltd., Winnipeg, Canada

---

## Install

```bash
pip install digitalsoma
```

```bash
# Optional extras
pip install "digitalsoma[yaml]"   # PyYAML support
pip install "digitalsoma[llm]"    # Anthropic SDK for LLM agent interface
pip install "digitalsoma[dev]"    # pytest + build tools
```

---

## 60-second quick start

```python
from digitalsoma import build_soma, SomaConfig

# Build a porcine digital twin
ds = build_soma(SomaConfig(animal_type="porcine_adult", animal_id="pig-001"))

# Ingest sensor readings — vendor aliases resolved automatically
state = ds.update_sync({
    "HR":    110,    # alias → heart_rate_bpm
    "Tb":    40.1,   # alias → core_temp_C
    "SpO2":  97.2,   # alias → spo2_pct
    "RR":    52,     # alias → respiratory_rate_bpm
    "cort":  80.0,   # alias → cortisol_nmol_L
})

# Six solvers run automatically
print(state["cardiac_output_L_min"])        # Fick: 6.6 L/min
print(state["thermal_comfort_index"])        # Newton: 0.94 → heat stress
print(state["physiological_stress_index"])  # HPA: 0.52
print(state["adverse_event_score"])         # VeDDRA: 0.17

# FHIR R4 export (new in v2.2.0)
bundle = ds.to_fhir_bundle()
print(bundle["total"])                       # 21 resources

# VeDDRA adverse event report
report = ds.veddra_report()
print(report["clinical_signs"])              # [{veddra_id, veddra_term, ...}]
```

---

## What it does

DigitalSoma represents any living animal as a continuously updated computational object.
Raw sensor readings (heart rate, temperature, accelerometry, blood markers) enter through
a schema-agnostic manifest layer, are normalised against internationally recognised
ontology vocabularies, and pass through a composable chain of physics-based physiological
solvers that infer clinically meaningful state variables in real time.

### Five-layer architecture

```
Input sources
  Wearable · Implanted · Remote sensing · Lab assay · Manual entry
          │
          ▼
Ontology & Normalisation Layer          (digitalsoma/ontology/vocab.py)
  Uberon · SNOMED CT · VeDDRA · NCBITaxon · UCUM · PATO · HP/MP
  canonical_key()  normalise_dict()  to_jsonld()
          │
          ▼
┌─────────────────────────────────────────────────────┐
│  DigitalSoma core  (digitalsoma/soma_api.py)        │
│                                                     │
│  Structural Layer   Dynamic Layer   Functional      │
│  ATR · anatomy ·   KV store O(1)   Model Zoo DAG   │
│  normal ranges     TSL · TES        6 built-in      │
│  build_soma()      update_sync()    solvers          │
└─────────────────────────────────────────────────────┘
          │
          ▼
LLM Agentic Interface Layer             (digitalsoma/soma_agent.py)
  11 OpenAI-compatible tool schemas · SomaDispatcher
          │
          ▼
Outputs
  State snapshot · Time-series · JSON-LD · VeDDRA AE report
  FHIR R4 Bundle · LLM response
```

### Six built-in solvers (DAG execution order)

| # | Solver | Model | Key outputs |
|---|--------|-------|-------------|
| S1 | `cardiovascular_baseline` | Fick equation | `cardiac_output_L_min` |
| S2 | `metabolic_rate` | Kleiber's law + Q10 | `rmr_W`, `rmr_kcal_day` |
| S3 | `thermoregulation` | Newton's cooling law | `thermal_comfort_index` |
| S4 | `respiratory_gas_exchange` | Respiratory quotient | `vo2_L_min`, `minute_ventilation_L_min` |
| S5 | `neuroendocrine_stress` | HPA axis composite | `physiological_stress_index` |
| S6 | `adverse_event_screen` | VeDDRA v2.2 mapping | `ae_flags`, `adverse_event_score` |

Custom solvers plug in via `ds.register_method(name, fn)` and slot into the same DAG.

### Animal Type Registry — 6 species templates

| Key | Species | Body mass | HR baseline |
|-----|---------|-----------|-------------|
| `porcine_adult` | *Sus scrofa domesticus* | 90 kg | 75 bpm |
| `equine_adult` | *Equus caballus* | 500 kg | 36 bpm |
| `bovine_adult` | *Bos taurus* | 600 kg | 60 bpm |
| `ovine_adult` | *Ovis aries* | 70 kg | 75 bpm |
| `canine_adult` | *Canis lupus familiaris* | 25 kg | 90 bpm |
| `salmonid_adult` | *Salmo salar* | 4.5 kg | 50 bpm |

Custom species registered via `register_animal_type(name, config)`.

---

## HL7 FHIR R4 integration

New in v2.2.0 — zero external dependencies:

```python
from digitalsoma.fhir import to_fhir_bundle, from_fhir_bundle

# Export: Patient + Device + Observations (LOINC + SNOMED CT + UCUM) + DiagnosticReport
bundle = ds.to_fhir_bundle()                        # collection bundle
tx     = ds.to_fhir_bundle(bundle_type="transaction") # POST to FHIR server

# Ingest: parse incoming FHIR Observations → readings dict → update_sync()
readings = from_fhir_bundle(incoming_bundle)
ds.update_sync(readings)
```

VeDDRA adverse event findings appear in the `DiagnosticReport` dual-coded with
SNOMED CT and VeDDRA term IDs — ready for EMA EVVET3, UK VMD, and FDA-CVM submission.

---

## VeDDRA pharmacovigilance

Six clinical signs screened on every `update_sync()` call:

| VeDDRA term | VeDDRA ID | Trigger | SNOMED CT |
|-------------|-----------|---------|-----------|
| Hyperthermia | 10020557 | T > T_base + offset | 386689009 |
| Hypothermia | 10021113 | T < T_base − offset | 386692006 |
| Tachycardia | 10043071 | HR > HR_base × 1.5 | 3424008 |
| Bradycardia | 10006093 | HR < HR_base × 0.6 | 48867003 |
| Hypoxia | 10021143 | SpO₂ < 90 % | 389086002 |
| Distress | 10013029 | PSI > 0.70 | 274668005 |

---

## Ontology namespaces

| Namespace | URI base |
|-----------|----------|
| Uberon | `http://purl.obolibrary.org/obo/UBERON_` |
| SNOMED CT | `http://snomed.info/id/` |
| VeDDRA | `https://www.ema.europa.eu/en/veterinary-regulatory/` |
| NCBITaxon | `http://purl.obolibrary.org/obo/NCBITaxon_` |
| UCUM | `http://unitsofmeasure.org/` |
| LOINC | `http://loinc.org` |

---

## Examples

```bash
python -m digitalsoma.examples.e1   # five species, structural layer
python -m digitalsoma.examples.e2   # heat-stress / recovery cycle
python -m digitalsoma.examples.e3   # ontology compliance, alias resolution
python -m digitalsoma.examples.e4   # custom HRV solver + VeDDRA report
python -m digitalsoma.examples.e5   # FHIR R4 export and round-trip
```

Or run directly from the source tree:

```bash
python examples/e5_fhir_integration.py
```

---

## Tests

```bash
pip install "digitalsoma[dev]"
pytest tests/ -v
```

---

## Citation

```bibtex
@software{youssef2026digitalsoma,
  author    = {Youssef, Ali},
  title     = {{DigitalSoma}: A physics-based digital twin framework
               for real-time animal physiology monitoring},
  year      = {2026},
  version   = {2.2.0},
  publisher = {BioTwinR Ltd. \& University of Manitoba},
  url       = {https://github.com/Pierianspring/digitalsoma},
  orcid     = {0000-0002-9986-5324},
}
```

See `CITATION.cff` for the CFF-format citation (GitHub "Cite this repository" button).

---

## Licence

CC BY 4.0 — see [LICENSE](LICENSE).
Free to use, share, and adapt with attribution.

---

## Links

- **PyPI:** https://pypi.org/project/digitalsoma/
- **GitHub:** https://github.com/Pierianspring/digitalsoma
- **Documentation:** https://github.com/Pierianspring/digitalsoma/tree/main/docs
- **ORCID:** https://orcid.org/0000-0002-9986-5324
- **Issues:** https://github.com/Pierianspring/digitalsoma/issues
