"""
digitalsoma/fhir/fhir_io.py — HL7 FHIR R4 I/O layer for DigitalSoma.

Two public entry points:

    to_fhir_bundle(ds)           → FHIR R4 Bundle (dict)
    from_fhir_bundle(bundle)     → readings dict → feeds update_sync()

FHIR resources produced:
    Bundle          — transaction bundle containing all resources
    Patient         — animal subject (name, species as NCBITaxon extension)
    Device          — digital twin identifier (DigitalSoma soma_id)
    Observation     — one per canonical state property with SNOMED/LOINC codes
    DiagnosticReport— VeDDRA adverse event findings

Coding systems used:
    SNOMED CT   http://snomed.info/sct
    LOINC       http://loinc.org
    UCUM        http://unitsofmeasure.org
    VeDDRA      https://www.ema.europa.eu/en/veterinary-regulatory/
    NCBITaxon   http://purl.obolibrary.org/obo/NCBITaxon_

Zero external runtime dependencies. Pure Python standard library only.
FHIR version: R4 (4.0.1)
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from digitalsoma.soma_api import DigitalSoma

# ---------------------------------------------------------------------------
# FHIR R4 coding map
# canonical_key  →  {loinc, snomed, display, ucum_fhir}
#
# loinc   : LOINC code (preferred for standard vitals)
# snomed  : SNOMED CT concept ID
# display : human-readable display name
# ucum    : UCUM unit string as used in FHIR Quantity.unit
# system  : 'loinc' | 'snomed'  (which code to use as primary Coding)
# ---------------------------------------------------------------------------

_FHIR_CODING: Dict[str, Dict[str, str]] = {
    # ── Cardiovascular ──────────────────────────────────────────────────────
    "heart_rate_bpm": {
        "loinc": "8867-4", "snomed": "364075005",
        "display": "Heart rate", "ucum": "/min", "system": "loinc",
    },
    "systolic_bp_mmHg": {
        "loinc": "8480-6", "snomed": "271649006",
        "display": "Systolic blood pressure", "ucum": "mm[Hg]", "system": "loinc",
    },
    "diastolic_bp_mmHg": {
        "loinc": "8462-4", "snomed": "271650006",
        "display": "Diastolic blood pressure", "ucum": "mm[Hg]", "system": "loinc",
    },
    "mean_arterial_pressure_mmHg": {
        "loinc": "8478-0", "snomed": "251068005",
        "display": "Mean arterial pressure", "ucum": "mm[Hg]", "system": "loinc",
    },
    "cardiac_output_L_min": {
        "loinc": "8741-1", "snomed": "82799009",
        "display": "Cardiac output", "ucum": "L/min", "system": "loinc",
    },
    "stroke_volume_mL": {
        "loinc": "20562-7", "snomed": "90096001",
        "display": "Stroke volume", "ucum": "mL", "system": "loinc",
    },
    # ── Respiratory ─────────────────────────────────────────────────────────
    "respiratory_rate_bpm": {
        "loinc": "9279-1", "snomed": "86290005",
        "display": "Respiratory rate", "ucum": "/min", "system": "loinc",
    },
    "spo2_pct": {
        "loinc": "59408-5", "snomed": "103228002",
        "display": "Oxygen saturation by pulse oximetry", "ucum": "%", "system": "loinc",
    },
    "vo2_L_min": {
        "loinc": "19139-6", "snomed": "250810003",
        "display": "Oxygen consumption", "ucum": "L/min", "system": "loinc",
    },
    "vco2_L_min": {
        "snomed": "250811004",
        "display": "Carbon dioxide production", "ucum": "L/min", "system": "snomed",
    },
    "minute_ventilation_L_min": {
        "loinc": "20155-0", "snomed": "250853002",
        "display": "Minute ventilation", "ucum": "L/min", "system": "loinc",
    },
    # ── Temperature ─────────────────────────────────────────────────────────
    "core_temp_C": {
        "loinc": "8310-5", "snomed": "276885007",
        "display": "Body temperature", "ucum": "Cel", "system": "loinc",
    },
    "ambient_temp_C": {
        "snomed": "703421000",
        "display": "Ambient temperature", "ucum": "Cel", "system": "snomed",
    },
    "skin_temp_C": {
        "loinc": "91556-1", "snomed": "415882003",
        "display": "Skin temperature", "ucum": "Cel", "system": "loinc",
    },
    "thermal_comfort_index": {
        "snomed": "364623001",
        "display": "Thermal comfort index", "ucum": "1", "system": "snomed",
    },
    # ── Metabolic / Biochemistry ────────────────────────────────────────────
    "blood_glucose_mmol_L": {
        "loinc": "2339-0", "snomed": "33747003",
        "display": "Glucose [Moles/volume] in Blood", "ucum": "mmol/L", "system": "loinc",
    },
    "cortisol_nmol_L": {
        "loinc": "2143-6", "snomed": "104588009",
        "display": "Cortisol [Moles/volume] in Serum or Plasma",
        "ucum": "nmol/L", "system": "loinc",
    },
    "insulin_pmol_L": {
        "loinc": "20448-9", "snomed": "271234007",
        "display": "Insulin [Moles/volume] in Serum or Plasma",
        "ucum": "pmol/L", "system": "loinc",
    },
    "rmr_kcal_day": {
        "snomed": "251845006",
        "display": "Resting metabolic rate", "ucum": "kcal/d", "system": "snomed",
    },
    "rmr_W": {
        "snomed": "251845006",
        "display": "Resting metabolic rate (watts)", "ucum": "W", "system": "snomed",
    },
    # ── Activity / Gait ─────────────────────────────────────────────────────
    "acceleration_m_s2": {
        "snomed": "364645001",
        "display": "Limb acceleration", "ucum": "m/s2", "system": "snomed",
    },
    "activity_counts": {
        "loinc": "55423-8", "snomed": "68130003",
        "display": "Physical activity", "ucum": "1", "system": "loinc",
    },
    "lying_time_min": {
        "snomed": "102542000",
        "display": "Lying / recumbency time", "ucum": "min", "system": "snomed",
    },
    # ── Stress / Composite scores ───────────────────────────────────────────
    "physiological_stress_index": {
        "snomed": "73595000",
        "display": "Physiological stress index", "ucum": "1", "system": "snomed",
    },
    "adverse_event_score": {
        "snomed": "404684003",
        "display": "Adverse event score (VeDDRA)", "ucum": "1", "system": "snomed",
    },
    # ── Haematology ─────────────────────────────────────────────────────────
    "haematocrit_pct": {
        "loinc": "20570-8", "snomed": "28317006",
        "display": "Hematocrit [Volume Fraction] of Blood", "ucum": "%", "system": "loinc",
    },
    "haemoglobin_g_dL": {
        "loinc": "718-7", "snomed": "259695003",
        "display": "Hemoglobin [Mass/volume] in Blood", "ucum": "g/dL", "system": "loinc",
    },
    "wbc_10e9_L": {
        "loinc": "6690-2", "snomed": "767002",
        "display": "Leukocytes [#/volume] in Blood", "ucum": "10*9/L", "system": "loinc",
    },
    "creatinine_umol_L": {
        "loinc": "14682-9", "snomed": "70901006",
        "display": "Creatinine [Moles/volume] in Serum or Plasma",
        "ucum": "umol/L", "system": "loinc",
    },
    "body_mass_kg": {
        "loinc": "29463-7", "snomed": "27113001",
        "display": "Body weight", "ucum": "kg", "system": "loinc",
    },
}

# VeDDRA term → SNOMED CT concept for DiagnosticReport coding
_VEDDRA_TO_SNOMED: Dict[str, Dict[str, str]] = {
    "Hyperthermia":  {"snomed": "386689009", "display": "Hyperthermia"},
    "Hypothermia":   {"snomed": "386692006", "display": "Hypothermia"},
    "Tachycardia":   {"snomed": "3424008",   "display": "Tachycardia"},
    "Bradycardia":   {"snomed": "48867003",  "display": "Bradycardia"},
    "Hypoxia":       {"snomed": "389086002", "display": "Hypoxia"},
    "Distress":      {"snomed": "274668005", "display": "Physiological distress"},
}

# LOINC inbound alias → canonical DigitalSoma key (for from_fhir_bundle)
_LOINC_TO_CANONICAL: Dict[str, str] = {
    "8867-4":  "heart_rate_bpm",
    "8480-6":  "systolic_bp_mmHg",
    "8462-4":  "diastolic_bp_mmHg",
    "8478-0":  "mean_arterial_pressure_mmHg",
    "8741-1":  "cardiac_output_L_min",
    "20562-7": "stroke_volume_mL",
    "9279-1":  "respiratory_rate_bpm",
    "59408-5": "spo2_pct",
    "19139-6": "vo2_L_min",
    "20155-0": "minute_ventilation_L_min",
    "8310-5":  "core_temp_C",
    "91556-1": "skin_temp_C",
    "2339-0":  "blood_glucose_mmol_L",
    "2143-6":  "cortisol_nmol_L",
    "20448-9": "insulin_pmol_L",
    "55423-8": "activity_counts",
    "20570-8": "haematocrit_pct",
    "718-7":   "haemoglobin_g_dL",
    "6690-2":  "wbc_10e9_L",
    "14682-9": "creatinine_umol_L",
    "29463-7": "body_mass_kg",
}

# NCBITaxon IDs for species display in Patient resource
_TAXON_DISPLAY: Dict[str, str] = {
    "9796":  "Equus caballus (horse)",
    "9913":  "Bos taurus (cattle)",
    "9940":  "Ovis aries (sheep)",
    "9615":  "Canis lupus familiaris (dog)",
    "8030":  "Salmo salar (Atlantic salmon)",
    "9823":  "Sus scrofa domesticus (pig)",
}


# ---------------------------------------------------------------------------
# FHIRMapper — low-level building blocks
# ---------------------------------------------------------------------------

class FHIRMapper:
    """
    Stateless FHIR R4 resource builder.

    All methods return plain Python dicts (JSON-serialisable).
    No external dependencies — standard library only.

    Usage
    -----
    >>> mapper = FHIRMapper()
    >>> obs = mapper.observation("heart_rate_bpm", 72.0, subject_ref="Patient/horse-001")
    >>> bundle = mapper.bundle([obs])
    """

    FHIR_VERSION = "4.0.1"
    FHIR_BASE = "http://hl7.org/fhir"

    # ── Primitive builders ───────────────────────────────────────────────────

    @staticmethod
    def _coding(system: str, code: str, display: str) -> Dict[str, str]:
        return {"system": system, "code": code, "display": display}

    @staticmethod
    def _quantity(value: float, unit: str, system: str = "http://unitsofmeasure.org",
                  code: Optional[str] = None) -> Dict[str, Any]:
        return {
            "value": round(value, 6),
            "unit": unit,
            "system": system,
            "code": code or unit,
        }

    @staticmethod
    def _reference(ref: str) -> Dict[str, str]:
        return {"reference": ref}

    @staticmethod
    def _now_iso() -> str:
        """Current time as FHIR dateTime (ISO 8601 UTC)."""
        t = time.gmtime()
        return (f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}"
                f"T{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}+00:00")

    # ── Resource builders ────────────────────────────────────────────────────

    def patient(
        self,
        animal_id: str,
        taxa: str = "",
        ncbi_taxon_id: str = "",
        site_name: str = "",
    ) -> Dict[str, Any]:
        """
        Build a FHIR R4 Patient resource representing an animal subject.

        HL7 FHIR does not have a native Animal resource in R4; the standard
        approach is to use Patient with species coded as an extension using
        the NCBITaxon identifier.
        """
        species_display = _TAXON_DISPLAY.get(ncbi_taxon_id, taxa or "Animal")
        resource: Dict[str, Any] = {
            "resourceType": "Patient",
            "id": animal_id or str(uuid.uuid4()),
            "meta": {
                "profile": [
                    "http://hl7.org/fhir/StructureDefinition/Patient"
                ]
            },
            "extension": [
                {
                    "url": "http://hl7.org/fhir/StructureDefinition/patient-animal",
                    "extension": [
                        {
                            "url": "species",
                            "valueCodeableConcept": {
                                "coding": [
                                    self._coding(
                                        system="http://purl.obolibrary.org/obo/NCBITaxon_",
                                        code=ncbi_taxon_id,
                                        display=species_display,
                                    )
                                ],
                                "text": species_display,
                            },
                        }
                    ],
                }
            ],
            "identifier": [
                {
                    "system": "urn:digitalsoma:animal",
                    "value": animal_id,
                }
            ],
            "name": [{"text": f"{taxa} — {animal_id}" if taxa else animal_id}],
            "active": True,
        }
        if site_name:
            resource["extension"].append({
                "url": "urn:digitalsoma:extension:site",
                "valueString": site_name,
            })
        return resource

    def device(self, soma_id: str, animal_id: str) -> Dict[str, Any]:
        """
        Build a FHIR R4 Device resource representing the DigitalSoma twin.
        The Device carries the soma_id as its identifier and is linked to
        the Patient (animal) subject.
        """
        return {
            "resourceType": "Device",
            "id": soma_id,
            "identifier": [
                {
                    "system": "urn:digitalsoma:soma_id",
                    "value": soma_id,
                }
            ],
            "deviceName": [
                {
                    "name": "DigitalSoma Digital Twin",
                    "type": "user-friendly-name",
                }
            ],
            "type": {
                "coding": [
                    self._coding(
                        system="http://snomed.info/sct",
                        code="706689003",
                        display="Digital health device",
                    )
                ]
            },
            "version": [{"value": "2.2.0"}],
            "patient": self._reference(f"Patient/{animal_id}"),
            "note": [
                {
                    "text": (
                        "DigitalSoma v2.1.0 — physics-based physiological digital twin. "
                        "Solver chain: cardiovascular, metabolic, thermoregulation, "
                        "respiratory, neuroendocrine, VeDDRA adverse event screen."
                    )
                }
            ],
        }

    def observation(
        self,
        canonical_key: str,
        value: float,
        subject_ref: str,
        device_ref: Optional[str] = None,
        timestamp: Optional[float] = None,
        status: str = "final",
    ) -> Optional[Dict[str, Any]]:
        """
        Build a FHIR R4 Observation resource for a single canonical property.

        Returns None if the canonical_key has no FHIR coding mapping
        (i.e. it is an internal computed key not suitable for clinical export).
        """
        coding_def = _FHIR_CODING.get(canonical_key)
        if coding_def is None:
            return None

        # Primary coding — prefer LOINC when available
        codings = []
        if coding_def.get("loinc"):
            codings.append(self._coding(
                system="http://loinc.org",
                code=coding_def["loinc"],
                display=coding_def["display"],
            ))
        if coding_def.get("snomed"):
            codings.append(self._coding(
                system="http://snomed.info/sct",
                code=coding_def["snomed"],
                display=coding_def["display"],
            ))

        iso_ts = self._now_iso() if timestamp is None else _epoch_to_iso(timestamp)

        obs: Dict[str, Any] = {
            "resourceType": "Observation",
            "id": str(uuid.uuid4()),
            "status": status,
            "category": [
                {
                    "coding": [
                        self._coding(
                            system="http://terminology.hl7.org/CodeSystem/observation-category",
                            code="vital-signs",
                            display="Vital Signs",
                        )
                    ]
                }
            ],
            "code": {
                "coding": codings,
                "text": coding_def["display"],
            },
            "subject": self._reference(subject_ref),
            "effectiveDateTime": iso_ts,
            "valueQuantity": self._quantity(
                value=value,
                unit=coding_def["ucum"],
            ),
            "extension": [
                {
                    "url": "urn:digitalsoma:canonical_key",
                    "valueString": canonical_key,
                }
            ],
        }
        if device_ref:
            obs["device"] = self._reference(device_ref)

        return obs

    def diagnostic_report(
        self,
        ae_flags: List[Dict[str, Any]],
        ae_score: float,
        subject_ref: str,
        soma_id: str,
        report_id: Optional[str] = None,
        observation_refs: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Build a FHIR R4 DiagnosticReport encoding VeDDRA adverse event findings.

        Each ae_flag is mapped to a SNOMED CT conclusion coding. The VeDDRA
        term ID is carried as an extension on each coded conclusion.
        The report status is 'final' when ae_score == 0 (no flags),
        'amended' when flags are present.
        """
        conclusions = []
        conclusion_codes = []

        for flag in ae_flags:
            term = flag.get("veddra_term", "")
            veddra_id = flag.get("veddra_id", "")
            snomed_entry = _VEDDRA_TO_SNOMED.get(term)

            if snomed_entry:
                conclusion_codes.append({
                    "coding": [
                        self._coding(
                            system="http://snomed.info/sct",
                            code=snomed_entry["snomed"],
                            display=snomed_entry["display"],
                        ),
                        self._coding(
                            system="https://www.ema.europa.eu/en/veterinary-regulatory/",
                            code=veddra_id,
                            display=term,
                        ),
                    ],
                    "text": f"{term} [VeDDRA {veddra_id}]",
                })
                conclusions.append(f"{term} [VeDDRA {veddra_id}]")

        status = "amended" if ae_flags else "final"
        conclusion_text = (
            "; ".join(conclusions) if conclusions
            else "No adverse events detected."
        )

        report: Dict[str, Any] = {
            "resourceType": "DiagnosticReport",
            "id": report_id or str(uuid.uuid4()),
            "meta": {
                "profile": [
                    "http://hl7.org/fhir/StructureDefinition/DiagnosticReport"
                ]
            },
            "status": status,
            "category": [
                {
                    "coding": [
                        self._coding(
                            system="http://terminology.hl7.org/CodeSystem/v2-0074",
                            code="VET",
                            display="Veterinary",
                        )
                    ]
                }
            ],
            "code": {
                "coding": [
                    self._coding(
                        system="http://loinc.org",
                        code="11488-4",
                        display="Consult note",
                    ),
                    self._coding(
                        system="https://www.ema.europa.eu/en/veterinary-regulatory/",
                        code="VeDDRA_AE_Screen",
                        display="VeDDRA Adverse Event Screen",
                    ),
                ],
                "text": "VeDDRA Adverse Event Screening Report",
            },
            "subject": self._reference(subject_ref),
            "effectiveDateTime": self._now_iso(),
            "issued": self._now_iso(),
            "conclusion": conclusion_text,
            "conclusionCode": conclusion_codes,
            "extension": [
                {
                    "url": "urn:digitalsoma:soma_id",
                    "valueString": soma_id,
                },
                {
                    "url": "urn:digitalsoma:ae_score",
                    "valueDecimal": round(ae_score, 4),
                },
                {
                    "url": "urn:digitalsoma:reporting_standard",
                    "valueString": "VeDDRA v2.2",
                },
            ],
        }
        if observation_refs:
            report["result"] = [self._reference(ref) for ref in observation_refs]

        return report

    def bundle(
        self,
        entries: List[Dict[str, Any]],
        bundle_type: str = "collection",
    ) -> Dict[str, Any]:
        """
        Wrap a list of FHIR resources into a FHIR R4 Bundle.

        bundle_type: 'collection' (read-only set) | 'transaction' (write)
        """
        bundle_entries = []
        for resource in entries:
            if resource is None:
                continue
            rt = resource.get("resourceType", "Resource")
            rid = resource.get("id", str(uuid.uuid4()))
            entry: Dict[str, Any] = {
                "fullUrl": f"urn:uuid:{rid}",
                "resource": resource,
            }
            if bundle_type == "transaction":
                entry["request"] = {
                    "method": "PUT",
                    "url": f"{rt}/{rid}",
                }
            bundle_entries.append(entry)

        return {
            "resourceType": "Bundle",
            "id": str(uuid.uuid4()),
            "meta": {"lastUpdated": self._now_iso()},
            "type": bundle_type,
            "timestamp": self._now_iso(),
            "total": len(bundle_entries),
            "entry": bundle_entries,
        }


# ---------------------------------------------------------------------------
# Public API — module-level functions
# ---------------------------------------------------------------------------

def to_fhir_bundle(
    ds: "DigitalSoma",
    bundle_type: str = "collection",
    include_device: bool = True,
) -> Dict[str, Any]:
    """
    Serialise a DigitalSoma twin's current state as a FHIR R4 Bundle.

    Parameters
    ----------
    ds           : DigitalSoma instance (must have been built with build_soma())
    bundle_type  : 'collection' (default) | 'transaction'
    include_device: include a FHIR Device resource for the twin itself

    Returns
    -------
    dict  — FHIR R4 Bundle (JSON-serialisable)

    Example
    -------
    >>> import json
    >>> from digitalsoma.soma_api import build_soma, SomaConfig
    >>> from digitalsoma.fhir import to_fhir_bundle
    >>> ds = build_soma(SomaConfig(animal_type="equine_adult", animal_id="horse-001"))
    >>> ds.update_sync({"heart_rate_bpm": 168, "core_temp_C": 38.7, "spo2_pct": 97.5})
    >>> bundle = to_fhir_bundle(ds)
    >>> print(json.dumps(bundle, indent=2)[:400])
    """
    mapper = FHIRMapper()
    sl = ds.structural_layer
    state = ds._dl.snapshot()

    animal_id = sl.get("animal_id", str(uuid.uuid4()))
    soma_id = ds.soma_id
    taxa = sl.get("taxa", "")
    ncbi_taxon_id = sl.get("ncbi_taxon_id", "")
    site_name = sl.get("site_name", "")

    subject_ref = f"Patient/{animal_id}"
    device_ref = f"Device/{soma_id}" if include_device else None

    resources: List[Dict[str, Any]] = []

    # 1. Patient (animal subject)
    patient = mapper.patient(
        animal_id=animal_id,
        taxa=taxa,
        ncbi_taxon_id=ncbi_taxon_id,
        site_name=site_name,
    )
    resources.append(patient)

    # 2. Device (digital twin)
    if include_device:
        device = mapper.device(soma_id=soma_id, animal_id=animal_id)
        resources.append(device)

    # 3. Observations — one per mapped canonical key
    obs_refs: List[str] = []
    timestamp = state.get("_timestamp", None)

    for key, value in state.items():
        if key.startswith("_") or not isinstance(value, (int, float)):
            continue
        obs = mapper.observation(
            canonical_key=key,
            value=float(value),
            subject_ref=subject_ref,
            device_ref=device_ref,
            timestamp=timestamp,
        )
        if obs is not None:
            resources.append(obs)
            obs_refs.append(f"Observation/{obs['id']}")

    # 4. DiagnosticReport (VeDDRA adverse event screen)
    ae_flags = state.get("ae_flags", [])
    ae_score = float(state.get("adverse_event_score", 0.0))
    diag_report = mapper.diagnostic_report(
        ae_flags=ae_flags,
        ae_score=ae_score,
        subject_ref=subject_ref,
        soma_id=soma_id,
        observation_refs=obs_refs,
    )
    resources.append(diag_report)

    return mapper.bundle(resources, bundle_type=bundle_type)


def from_fhir_bundle(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse a FHIR R4 Bundle of Observation resources and return a readings
    dict suitable for passing directly to DigitalSoma.update_sync().

    Only Observation resources are processed. Patient, Device, and
    DiagnosticReport entries are silently ignored.

    Coding resolution order:
      1. LOINC code in _LOINC_TO_CANONICAL lookup
      2. DigitalSoma canonical_key extension (urn:digitalsoma:canonical_key)
      3. Skipped if neither is present

    Parameters
    ----------
    bundle : dict — FHIR R4 Bundle

    Returns
    -------
    dict  — {canonical_key: float_value, ...}

    Example
    -------
    >>> from digitalsoma.fhir import from_fhir_bundle
    >>> readings = from_fhir_bundle(incoming_fhir_bundle)
    >>> ds.update_sync(readings)
    """
    readings: Dict[str, float] = {}

    entries = bundle.get("entry", [])
    for entry in entries:
        resource = entry.get("resource", {})
        if resource.get("resourceType") != "Observation":
            continue

        # Try DigitalSoma canonical_key extension first (round-trip)
        canonical_key: Optional[str] = None
        for ext in resource.get("extension", []):
            if ext.get("url") == "urn:digitalsoma:canonical_key":
                canonical_key = ext.get("valueString")
                break

        # Fall back to LOINC code lookup
        if canonical_key is None:
            for coding in resource.get("code", {}).get("coding", []):
                if coding.get("system") == "http://loinc.org":
                    loinc_code = coding.get("code", "")
                    canonical_key = _LOINC_TO_CANONICAL.get(loinc_code)
                    if canonical_key:
                        break

        if canonical_key is None:
            continue

        # Extract value
        vq = resource.get("valueQuantity")
        if vq and isinstance(vq.get("value"), (int, float)):
            readings[canonical_key] = float(vq["value"])
            continue

        # valueCodeableConcept / valueString not supported as numeric
        # valueBoolean, valueInteger as fallback
        if isinstance(resource.get("valueInteger"), int):
            readings[canonical_key] = float(resource["valueInteger"])

    return readings


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _epoch_to_iso(epoch: float) -> str:
    """Convert Unix epoch float to FHIR dateTime string (ISO 8601 UTC)."""
    t = time.gmtime(epoch)
    return (f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}"
            f"T{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}+00:00")
