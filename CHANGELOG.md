# Changelog

All notable changes to DigitalSoma are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [3.0.0] — 2026-03-30

### Added
- **HL7 FHIR R4 integration** — `digitalsoma/fhir/` subpackage (zero external dependencies)
  - `FHIRMapper` — stateless resource builder for Patient, Device, Observation, DiagnosticReport, Bundle
  - `to_fhir_bundle(ds)` — exports twin state as a FHIR R4 Bundle: Patient (NCBITaxon species extension), Device (soma_id), one Observation per canonical property (LOINC + SNOMED CT + UCUM), DiagnosticReport (VeDDRA → SNOMED CT)
  - `from_fhir_bundle(bundle)` — parses incoming FHIR Observations back to a readings dict for `update_sync()`, resolving via LOINC codes or round-trip `urn:digitalsoma:canonical_key` extension
  - 21 canonical properties mapped to LOINC / SNOMED CT codes
  - Transaction bundle support for POST to FHIR servers
- **`to_fhir_bundle()` method** on `DigitalSoma` class
- **11th LLM tool** — `ds_to_fhir_bundle` in `soma_agent.py`
- **`porcine_adult`** added to Animal Type Registry — *Sus scrofa domesticus* (NCBITaxon: 9823, 90 kg, HR 75 bpm, 38.8 °C)
- **`examples/e5_fhir_integration.py`** — 8-step FHIR walkthrough
- **`examples/porcine_clinical_simulation.html`** — self-running four-act clinical simulation (heat stress, VeDDRA cascade, FHIR export)
- **`tests/test_fhir.py`** — 36 tests covering FHIRMapper, to_fhir_bundle, from_fhir_bundle, coding map completeness
- `docs/USER_MANUAL.md` Section 12: FHIR R4 integration (9 subsections)
- `docs/GETTING_STARTED.md` Section 11: FHIR R4 quick-start
- PyPI packaging — `pyproject.toml`, `MANIFEST.in`, `py.typed` marker
- `CHANGELOG.md`

### Changed
- `soma_agent.py` — tool count 10 → 11, version 2.0.0 → 3.0.0, LOINC + FHIR R4 added to ontology namespace map
- `digitalsoma/__init__.py` — v3.0.0, FHIR exports exposed at package level
- `setup.py` — minimal shim; all metadata moved to `pyproject.toml`
- `CITATION.cff` — version 3.0.0, date 2026-03-30

### Fixed
- All inline Digital Pedon references removed from docstrings (carried over from v2.0.0 cleanup)

---

## [2.0.0] — 2026-03-28

### Added
- Initial public release as DigitalSoma (standalone, no Digital Pedon dependency)
- Five-layer architecture: Input → ONL → Core (Structural + Dynamic + Functional) → LLM Interface → Outputs
- Animal Type Registry (ATR) — 5 species: equine_adult, bovine_adult, ovine_adult, canine_adult, salmonid_adult
- Six built-in physiological solvers (DAG execution order):
  1. `cardiovascular_baseline` — Fick cardiac output
  2. `metabolic_rate` — Kleiber allometry + Q10
  3. `thermoregulation` — Newton cooling, TCI
  4. `respiratory_gas_exchange` — RQ-based VO₂ / VCO₂ / MV
  5. `neuroendocrine_stress` — HPA axis composite PSI
  6. `adverse_event_screen` — VeDDRA v2.2 (6 clinical signs, EMA term IDs)
- Ontology layer — Uberon, SNOMED CT, VeDDRA, NCBITaxon, UCUM, PATO, HP/MP
- BYOD sensor manifest — 14 unit conversions, six-field contract
- Threshold Event System (TES) — 8 default alarms, configurable boundaries
- Time-series log (TSL) — timestamped snapshot history
- `to_jsonld()` — JSON-LD export with full ontology URIs
- `veddra_report()` — structured adverse event report
- LLM agentic interface — 10 OpenAI-compatible tool schemas, SomaDispatcher
- EquiTwin extension — equine gait biomechanics, PFERD/hSMAL 32-joint skeleton
- Full documentation: USER_MANUAL.md (14 sections), GETTING_STARTED.md
- 72 passing tests
- CC BY 4.0 licence
- CITATION.cff for GitHub/Zenodo citation badge

### Author
Dr. ir. Ali Youssef (ORCID: 0000-0002-9986-5324)
Adjunct Professor, Computational Bio-Ecosystems, Agroecosystems Laboratory,
University of Manitoba & BioTwinR Ltd., Winnipeg, Canada

---

[3.0.0]: https://github.com/Pierianspring/digitalsoma/releases/tag/v3.0.0
[2.0.0]: https://github.com/Pierianspring/digitalsoma/releases/tag/v2.0.0
