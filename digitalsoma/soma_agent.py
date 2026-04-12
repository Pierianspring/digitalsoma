"""
soma_agent.py — DigitalSoma LLM Agentic Interface Layer.

Exposes the DigitalSoma twin as 11 OpenAI-compatible tool schemas,
allowing LLM agents (Claude, GPT-4, Gemini) to query animal physiology
in natural language and receive structured, model-validated answers.

Tool schemas follow the OpenAI function-calling JSON schema spec.
All tool responses are structured dicts (JSON-serialisable).

Tools exposed:
    ds_describe          — full twin state summary
    ds_get_state         — retrieve a specific canonical property value
    ds_update            — ingest sensor readings and re-run solver chain
    ds_query_history     — retrieve time-series for a property
    ds_list_solvers      — list registered solvers in DAG order
    ds_to_jsonld         — export state as JSON-LD linked data
    ds_veddra_report     — generate VeDDRA adverse event report
    ds_alarm_status      — check threshold event system status
    ds_manifest_summary  — list registered sensors
    ds_structural_layer  — return species identity and normal ranges
    ds_to_fhir_bundle    — export state as HL7 FHIR R4 Bundle

Note: custom solver registration is available via the Python API only —
call ds.register_method(name, fn) directly on the DigitalSoma instance.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool schema definitions (OpenAI-compatible)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "ds_describe",
            "description": (
                "Return a structured natural-language summary of the DigitalSoma twin's "
                "current physiological state, including all computed solver outputs and "
                "any active VeDDRA adverse event flags."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ds_get_state",
            "description": (
                "Retrieve the current value of a specific physiological property from "
                "the digital twin's state. Accepts any known alias (e.g. 'HR', 'SpO2', "
                "'core_temp') which is resolved to its canonical key automatically."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "property": {
                        "type": "string",
                        "description": "Property alias or canonical key (e.g. 'heart_rate_bpm', 'HR', 'SpO2')",
                    }
                },
                "required": ["property"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ds_update",
            "description": (
                "Ingest new sensor readings into the digital twin. The solver chain "
                "re-runs automatically on ingestion, updating all derived physiological "
                "variables. Returns the full updated state snapshot."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "readings": {
                        "type": "object",
                        "description": (
                            "Dict of {property_alias: value} pairs. "
                            "Example: {\"HR\": 72, \"core_temp\": 39.1, \"SpO2\": 98.0}"
                        ),
                        "additionalProperties": True,
                    }
                },
                "required": ["readings"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ds_query_history",
            "description": (
                "Retrieve the time-series history for a physiological property "
                "from the twin's time-series log (TSL). Returns timestamped records."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "property": {
                        "type": "string",
                        "description": "Property alias or canonical key",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of records to return (most recent first)",
                        "default": 20,
                    },
                },
                "required": ["property"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ds_list_solvers",
            "description": (
                "List all solvers currently registered in the Model Zoo, "
                "including both built-in physiological solvers and any "
                "user-registered custom solvers."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ds_to_jsonld",
            "description": (
                "Export the twin's current state as a JSON-LD document with "
                "full Uberon, SNOMED, and VeDDRA ontology URI annotations. "
                "Suitable for submission to regulatory or interoperability systems."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ds_veddra_report",
            "description": (
                "Generate a VeDDRA-compliant adverse event report from the "
                "twin's current state. Lists all flagged clinical signs with "
                "their VeDDRA term IDs. Suitable for EMA EVVET3 / VMD / FDA-CVM submission."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ds_alarm_status",
            "description": (
                "Check the Threshold Event System (TES) for any currently active "
                "physiological alarms (e.g. hyperthermia, tachycardia, hypoxaemia). "
                "Returns a list of fired alarm events."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ds_manifest_summary",
            "description": (
                "Return a summary of all sensors currently registered in the "
                "BYOD sensor manifest, including their sensor IDs, canonical "
                "property mappings, and units."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ds_structural_layer",
            "description": (
                "Return the twin's structural layer: species identity, "
                "NCBITaxon ID, body mass, normal physiological ranges, and "
                "registered anatomical systems."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ds_to_fhir_bundle",
            "description": (
                "Export the current DigitalSoma twin state as a HL7 FHIR R4 Bundle. "
                "Produces a Patient resource (animal subject with NCBITaxon species "
                "extension), a Device resource (DigitalSoma twin), one Observation "
                "resource per mapped canonical property (LOINC + SNOMED CT coded, "
                "UCUM units), and a DiagnosticReport encoding any active VeDDRA "
                "adverse event findings. Suitable for submission to FHIR-compliant "
                "veterinary EHR systems and clinical decision support pipelines."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bundle_type": {
                        "type": "string",
                        "enum": ["collection", "transaction"],
                        "description": (
                            "'collection' (default) — read-only bundle for querying. "
                            "'transaction' — write bundle for POSTing to a FHIR server."
                        ),
                    },
                },
                "required": [],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# SomaDispatcher — routes tool calls to DigitalSoma methods
# ---------------------------------------------------------------------------

class SomaDispatcher:
    """
    Dispatches OpenAI-compatible tool calls to DigitalSoma methods.

    Usage with any OpenAI-compatible LLM SDK:
        dispatcher = SomaDispatcher(ds, sensor_layer)
        tool_result = dispatcher.dispatch(tool_name, tool_args)
    """

    def __init__(self, soma, sensor_layer=None) -> None:
        """
        Parameters
        ----------
        soma         : DigitalSoma instance
        sensor_layer : SensorLayer instance (optional; used by ds_manifest_summary)
        """
        self._soma = soma
        self._sensor_layer = sensor_layer

    def dispatch(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route a tool call to the appropriate DigitalSoma method.
        Returns a JSON-serialisable dict.
        """
        handler = getattr(self, f"_tool_{tool_name}", None)
        if handler is None:
            return {"error": f"Unknown tool: {tool_name}"}
        try:
            return handler(**args)
        except Exception as exc:   # noqa: BLE001
            logger.error("Tool '%s' raised: %s", tool_name, exc)
            return {"error": str(exc)}

    # -- Tool implementations ------------------------------------------------

    def _tool_ds_describe(self) -> Dict[str, Any]:
        return {"description": self._soma.describe()}

    def _tool_ds_get_state(self, property: str) -> Dict[str, Any]:
        from digitalsoma.ontology.vocab import canonical_key
        ckey = canonical_key(property)
        value = self._soma._dl.get(ckey)
        return {
            "property": property,
            "canonical_key": ckey,
            "value": value,
            "found": value is not None,
        }

    def _tool_ds_update(self, readings: Dict[str, Any]) -> Dict[str, Any]:
        state = self._soma.update_sync(readings)
        # Return only the most clinically relevant keys to keep LLM context lean
        priority = [
            "heart_rate_bpm", "core_temp_C", "respiratory_rate_bpm",
            "spo2_pct", "blood_glucose_mmol_L", "cortisol_nmol_L",
            "cardiac_output_L_min", "rmr_W", "thermal_comfort_index",
            "physiological_stress_index", "adverse_event_score",
        ]
        summary = {k: state[k] for k in priority if k in state}
        ae_flags = state.get("ae_flags", [])
        return {
            "state_summary": summary,
            "ae_flags": ae_flags,
            "solver_chain_ran": True,
        }

    def _tool_ds_query_history(
        self, property: str, limit: int = 20
    ) -> Dict[str, Any]:
        records = self._soma.query_history(property, limit=limit)
        return {"property": property, "records": records, "count": len(records)}

    def _tool_ds_list_solvers(self) -> Dict[str, Any]:
        return {"solvers": self._soma.solvers}

    def _tool_ds_to_jsonld(self) -> Dict[str, Any]:
        return self._soma.to_jsonld()

    def _tool_ds_veddra_report(self) -> Dict[str, Any]:
        return self._soma.veddra_report()

    def _tool_ds_alarm_status(self) -> Dict[str, Any]:
        fired = self._soma._dl.check_thresholds()
        return {
            "alarms_active": len(fired) > 0,
            "alarm_count": len(fired),
            "alarms": fired,
        }

    def _tool_ds_manifest_summary(self) -> Dict[str, Any]:
        if self._sensor_layer is None:
            return {"error": "No SensorLayer registered with this dispatcher."}
        return {"sensors": self._sensor_layer.manifest_summary()}

    def _tool_ds_structural_layer(self) -> Dict[str, Any]:
        return {"structural_layer": self._soma.structural_layer}

    def _tool_ds_to_fhir_bundle(
        self,
        bundle_type: str = "collection",
    ) -> Dict[str, Any]:
        return self._soma.to_fhir_bundle(bundle_type=bundle_type)


# ---------------------------------------------------------------------------
# JSON-LD context manifest (for LLM system prompt injection)
# ---------------------------------------------------------------------------

SOMA_LLM_CONTEXT: Dict[str, Any] = {
    "framework": "DigitalSoma",
    "version": "3.0.0",
    "description": (
        "DigitalSoma is a digital twin framework for animal physiology monitoring. "
        "It represents a living animal as a continuously updated computational object "
        "with three layers: Structural (species identity and anatomy), "
        "Dynamic (real-time physiological state), and Functional (solver chain). "
        "All properties are anchored to Uberon, SNOMED, VeDDRA, and NCBITaxon ontology URIs. "
        "FHIR R4 export is available via ds_to_fhir_bundle."
    ),
    "available_tools": [t["function"]["name"] for t in TOOL_SCHEMAS],
    "ontology_namespaces": {
        "Uberon": "http://purl.obolibrary.org/obo/UBERON_",
        "SNOMED": "http://snomed.info/id/",
        "VeDDRA": "https://www.ema.europa.eu/en/veterinary-regulatory/",
        "NCBITaxon": "http://purl.obolibrary.org/obo/NCBITaxon_",
        "UCUM": "http://unitsofmeasure.org/",
        "LOINC": "http://loinc.org",
        "FHIR_R4": "http://hl7.org/fhir/R4",
    },
    "example_queries": [
        "Is this animal showing signs of heat stress?",
        "What is the current heart rate and is it within normal range?",
        "Are there any active VeDDRA adverse event flags?",
        "Show me the core temperature trend over the last 10 readings.",
        "What is the physiological stress index and what is driving it?",
    ],
}
