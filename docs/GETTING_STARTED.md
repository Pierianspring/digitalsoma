# Getting Started with DigitalSoma

DigitalSoma is a dynamic physiological digital twin engine for living animals. This guide takes you from installation to a working twin in under ten minutes.

---

## Prerequisites

- Python 3.9 or later
- `pip` (any recent version)
- No other dependencies — DigitalSoma uses the Python standard library only

---

## 1. Installation

```bash
pip install digitalsoma
```

Verify the installation:

```python
import digitalsoma
print(digitalsoma.__version__)   # → 3.0.0
```

Optional extras:

```bash
pip install "digitalsoma[yaml]"   # PyYAML support for config files
pip install "digitalsoma[llm]"    # Anthropic SDK for LLM agent interface
pip install "digitalsoma[dev]"    # pytest + build tools
```

---

## 2. Your first digital twin

Build a porcine twin and inspect the structural layer:

```python
from digitalsoma import build_soma, SomaConfig

config = SomaConfig(
    animal_type = "porcine_adult",
    animal_id   = "pig-001",
    site_name   = "Research Unit 3",
)

ds = build_soma(config)
print(ds.structural_layer)
# {'taxa': 'Sus scrofa domesticus', 'ncbi_taxon_id': '9823',
#  'body_mass_kg': 90.0, 'hr_normal_bpm': 75.0, ...}
```

Six species are available out of the box: `porcine_adult`, `equine_adult`, `bovine_adult`, `ovine_adult`, `canine_adult`, `salmonid_adult`.

---

## 3. Pushing sensor readings

```python
state = ds.update_sync({
    "HR":   75,      # vendor alias → heart_rate_bpm (resolved automatically)
    "Tb":   38.8,    # vendor alias → core_temp_C
    "SpO2": 98.5,    # vendor alias → spo2_pct
    "RR":   20,      # vendor alias → respiratory_rate_bpm
})

# Directly measured variables (normalised)
print(state["heart_rate_bpm"])          # 75.0
print(state["core_temp_C"])             # 38.8

# Variables derived by the solver chain
print(state["cardiac_output_L_min"])    # ~4.5
print(state["thermal_comfort_index"])   # ~0.0 (balanced)
print(state["physiological_stress_index"])  # ~0.02
print(state["adverse_event_score"])     # 0.0
```

The six built-in solvers run automatically in dependency order. These solvers are a starting point — you can add, replace, or supplement them with your own computational models.

---

## 4. Threshold alarms

```python
def on_alarm(key: str, value: float, label: str) -> None:
    print(f"ALARM  {label}: {key} = {value:.2f}")

ds._tes.register_handler(on_alarm)

state = ds.update_sync({
    "core_temp_C":    41.0,   # > T_base + 1.5°C → VeDDRA Hyperthermia
    "heart_rate_bpm": 115.0,  # > 75 × 1.5 → VeDDRA Tachycardia
    "spo2_pct":       92.0,
})
# ALARM  hyperthermia/hypothermia: core_temp_C = 41.00
```

---

## 5. Time-series history

```python
# All recorded values for heart rate
history = ds.query_history("heart_rate_bpm")

# Last 3 readings only
recent = ds.query_history("core_temp_C", limit=3)

# Readings since a Unix timestamp
since  = ds.query_history("cortisol_nmol_L", since=1712000000.0)
```

---

## 6. VeDDRA adverse event report

```python
# Simulate heat stress
ds.update_sync({
    "core_temp_C":          40.6,
    "heart_rate_bpm":       130.0,
    "respiratory_rate_bpm":  68.0,
    "cortisol_nmol_L":      190.0,
})

report = ds.veddra_report()
print(report["reporting_standard"])   # VeDDRA Rev.16 — EMA/CVMP/PhVWP/10418/2009
print(report["adverse_event_score"])  # 0.38
for sign in report["clinical_signs"]:
    print(f"  [PT {sign['veddra_pt_code']}] {sign['veddra_term']}")
# [PT 604] Hyperthermia
# [PT 122] Tachycardia
# [PT 515] Tachypnoea
```

VeDDRA codes are the official EMA Rev.16 Preferred Term codes, corrected in v3.0.0 from the incorrect 8-digit codes used in v2.x.

---

## 7. FHIR R4 export

```python
from digitalsoma.fhir import to_fhir_bundle, from_fhir_bundle

# Export current state as a FHIR R4 Bundle
bundle = to_fhir_bundle(ds)
print(bundle["total"])   # 21 resources

# DiagnosticReport carries VeDDRA flags mapped to SNOMED CT
dr = next(e["resource"] for e in bundle["entry"]
          if e["resource"]["resourceType"] == "DiagnosticReport")
print(dr["status"])      # "amended"
print(dr["conclusion"])  # "Hyperthermia [VeDDRA PT 604]; ..."

# Round-trip: parse incoming FHIR Observations back into the twin
readings = from_fhir_bundle(bundle)
ds.update_sync(readings)
```

---

## 8. JSON-LD ontology export

```python
doc = ds.to_jsonld()
# doc["@context"]["heart_rate_bpm"]["@id"]
# → "http://purl.obolibrary.org/obo/CMO_0000052"
# doc["@context"]["spo2_pct"]["@id"]
# → "http://snomed.info/id/103228002"  (corrected in v3.0.0)
```

---

## 9. Custom sensors (BYOD manifest)

```python
from digitalsoma.sensor.sensor_layer import SensorLayer, SensorManifestEntry

layer = SensorLayer()
layer.register_sensor(SensorManifestEntry(
    sensor_id      = "CGM_01",
    property_alias = "glucose",
    unit           = "mg/dL",        # auto-converted to mmol/L
    description    = "Continuous glucose monitor",
))

readings = layer.ingest([
    {"sensor_id": "CGM_01", "value": 90.0, "quality_flag": 0},
])
state = ds.update_sync(readings)
```

Fourteen unit conversions are built in: °F→°C, K→°C, kPa→mmHg, psi→mmHg, bar→mmHg, mg/dL→mmol/L, μg/dL→nmol/L, lb→kg, g→kg, Hz→/min, and more.

---

## 10. User-defined solvers

DigitalSoma's solver chain is fully extensible. Any function that accepts `params: dict` and `state: dict` and returns a dict of new properties can be registered. The function may implement any computational approach — allometric equations, regression models, machine learning inference, compartmental models, or empirical lookup tables.

```python
def welfare_solver(params: dict, state: dict) -> dict:
    """Animal Welfare Index combining thermal, stress, and oxygen components."""
    tci  = state.get("thermal_comfort_index", 0.0)
    psi  = state.get("physiological_stress_index", 0.0)
    spo2 = state.get("spo2_pct", 98.0)

    thermal_w = max(0.0, 1.0 - abs(tci) * 2.0)
    stress_w  = max(0.0, 1.0 - psi)
    oxygen_w  = max(0.0, min(1.0, (spo2 - 90.0) / 8.0))

    awi = 0.40*thermal_w + 0.40*stress_w + 0.20*oxygen_w
    return {"animal_welfare_index": round(awi, 4)}

ds.register_method("welfare_index", welfare_solver)
# animal_welfare_index now appears in every subsequent update_sync() output
```

Built-in solvers can be replaced:

```python
ds.unregister_method("metabolic_rate")
ds.register_method("metabolic_rate", my_mechanistic_model)
```

---

## 11. Adding a custom species

```python
from digitalsoma import register_animal_type

register_animal_type("alpaca_adult", {
    "taxa":               "Vicugna pacos",
    "ncbi_taxon_id":      "30538",
    "body_mass_kg":        65.0,
    "core_temp_normal_C":  38.0,
    "hr_normal_bpm":       70.0,
    "rr_normal_bpm":       20.0,
    "systems": ["cardiovascular", "metabolic", "thermoregulation"],
})
```

---

## 12. Run the examples

```bash
python examples/e1_build_and_describe.py    # structural layer across all 6 species
python examples/e2_solver_chain.py          # heat-stress / recovery cycle
python examples/e3_ontology_compliance.py   # alias resolution and JSON-LD
python examples/e4_custom_solver.py         # user-defined solver + VeDDRA report
python examples/e5_fhir_integration.py      # FHIR R4 export and round-trip
```

---

## 13. Run the tests

```bash
pip install "digitalsoma[dev]"
pytest tests/ -v
```

---

## Next steps

- **[Technical Documentation](USER_MANUAL.md)** — complete reference including the standards and data models chapter, FHIR integration, and VeDDRA pharmacovigilance
- **[GitHub](https://github.com/Pierianspring/digitalsoma)** — source code, issues, and discussions
- **[ORCID](https://orcid.org/0000-0002-9986-5324)** — Dr. ir. Ali Youssef

---

## References

The following references underpin the built-in solvers and standards implemented in DigitalSoma v3.0.0. References are listed by topic.

### Digital twin concept

- Grieves, M. (2014). Digital twin: Manufacturing excellence through virtual factory replication. White Paper. Florida Institute of Technology.
- Tao, F., Sui, F., Liu, A., et al. (2019). Digital twin-driven product design framework. *International Journal of Production Research*, 57(12), 3935–3953.

### Solver 1 — Cardiovascular (Fick equation)

- Fick, A. (1870). Über die Messung des Blutquantums in den Herzventrikeln. *Sitzungsberichte der Physikalisch-Medizinischen Gesellschaft zu Würzburg*, 2, 16–28.
- Guyton, A. C., & Hall, J. E. (2015). *Textbook of Medical Physiology* (13th ed.). Elsevier Saunders.
- Evans, D. L., & Rose, R. J. (1988). Cardiovascular and respiratory responses to exercise in thoroughbred horses. *Journal of Experimental Biology*, 134(1), 397–408.

### Solver 2 — Metabolic rate (Kleiber's law + Q10)

- Kleiber, M. (1947). Body size and metabolic rate. *Physiological Reviews*, 27(4), 511–541.
- Kleiber, M. (1961). *The Fire of Life: An Introduction to Animal Energetics*. Wiley, New York.
- Blaxter, K. L. (1989). *Energy Metabolism in Animals and Man*. Cambridge University Press.
- Brown, J. H., Gillooly, J. F., Allen, A. P., Savage, V. M., & West, G. B. (2004). Toward a metabolic theory of ecology. *Ecology*, 85(7), 1771–1789.

### Solver 3 — Thermoregulation (Newton's law of cooling)

- Newton, I. (1701). Scala graduum caloris. *Philosophical Transactions of the Royal Society*, 22, 824–829.
- Mount, L. E. (1979). *Adaptation to Thermal Environment: Man and His Productive Animals*. Edward Arnold, London.
- Gebremedhin, K. G., & Wu, B. (2001). A model of evaporative cooling of wet skin surface and fur layer. *Journal of Thermal Biology*, 26(6), 537–545.
- Mader, T. L., Davis, M. S., & Brown-Brandl, T. (2006). Environmental factors influencing heat stress in feedlot cattle. *Journal of Animal Science*, 84(3), 712–719.

### Solver 4 — Respiratory gas exchange

- Brouwer, E. (1965). Report of sub-committee on constants and factors. In K. L. Blaxter (Ed.), *Energy Metabolism*. Academic Press, London.
- West, J. B. (2012). *Respiratory Physiology: The Essentials* (9th ed.). Lippincott Williams & Wilkins.
- Weibel, E. R. (1984). *The Pathway for Oxygen*. Harvard University Press.
- McLean, J. A., & Tobin, G. (1987). *Animal and Human Calorimetry*. Cambridge University Press.

### Solver 5 — Physiological Stress Index (PSI)

> **Important:** The PSI is an original formulation developed specifically for DigitalSoma, designed to trigger the Threshold Event System alarm and the VeDDRA Dyspnoea flag. It is **not a validated clinical index**. The individual components draw on the references below, but the composite formula and thresholds have not been validated in any species. Do not use the PSI as a standalone clinical diagnostic criterion.

- Selye, H. (1936). A syndrome produced by diverse nocuous agents. *Nature*, 138(3479), 32.
- Mormède, P., et al. (2007). Exploration of the hypothalamic-pituitary-adrenal function as a tool to evaluate animal welfare. *Physiology & Behavior*, 92(3), 317–339.
- von Borell, E., et al. (2007). Heart rate variability as a measure of autonomic regulation of cardiac activity for assessing stress and welfare in farm animals. *Physiology & Behavior*, 92(3), 293–316.
- Moberg, G. P., & Mench, J. A. (Eds.) (2000). *The Biology of Animal Stress*. CABI Publishing.

### Solver 6 — VeDDRA adverse event screen

- European Medicines Agency — CVMP PhVWP-V. (2025). Combined VeDDRA list of clinical terms for reporting suspected adverse events in animals and humans to veterinary medicinal products — Rev.16. EMA/CVMP/PhVWP/10418/2009 Rev.16. Effective 1 October 2025. EMA, Amsterdam.
- European Parliament and Council. (2019). Regulation (EU) 2019/6 on veterinary medicinal products. *Official Journal of the European Union*, L4, 43–167.

### Ontology and interoperability standards

- Smith, B., et al. (2007). The OBO Foundry: coordinated evolution of ontologies to support biomedical data integration. *Nature Biotechnology*, 25(11), 1251–1255.
- HL7 International. (2019). HL7 FHIR R4 Specification. https://www.hl7.org/fhir/R4/
- McDonald, C. J., et al. (2003). LOINC, a universal standard for identifying laboratory observations. *Clinical Chemistry*, 49(4), 624–633.
- SNOMED International. (2024). SNOMED CT — The global language of healthcare. https://www.snomed.org
