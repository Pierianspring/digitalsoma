"""
soma_api.py — Core DigitalSoma framework.

Five-layer architecture:
  Structural Layer  : immutable animal identity, anatomy, normal-range config
  Dynamic Layer     : KV store, time-series log, threshold event system
  Functional Layer  : composable solver chain (Model Zoo) via register_method()

Two transversal layers complete the architecture:
  Ontology & Normalisation Layer : vocab.py canonical keys + JSON-LD export
  LLM Agentic Interface Layer    : soma_agent.py (OpenAI-compatible tool schemas)

Zero external runtime dependencies. Standard library only.
"""

from __future__ import annotations

import copy
import json
import logging
import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from digitalsoma.ontology.vocab import canonical_key, normalise_dict, to_jsonld

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Animal Type Registry (ATR) — mirrors Soil Type Registry (STR)
# Five named templates; users may extend via register_animal_type()
# ---------------------------------------------------------------------------

_ANIMAL_TYPE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "bovine_adult": {
        "taxa": "Bos taurus",
        "ncbi_taxon_id": "9913",
        "body_mass_kg": 600.0,
        "core_temp_normal_C": 38.5,
        "hr_normal_bpm": 60.0,
        "rr_normal_bpm": 20.0,
        "systems": ["cardiovascular", "metabolic", "thermoregulation",
                    "respiratory", "musculoskeletal", "neuroendocrine"],
    },
    "ovine_adult": {
        "taxa": "Ovis aries",
        "ncbi_taxon_id": "9940",
        "body_mass_kg": 70.0,
        "core_temp_normal_C": 39.0,
        "hr_normal_bpm": 75.0,
        "rr_normal_bpm": 25.0,
        "systems": ["cardiovascular", "metabolic", "thermoregulation",
                    "respiratory", "musculoskeletal", "neuroendocrine"],
    },
    "canine_adult": {
        "taxa": "Canis lupus familiaris",
        "ncbi_taxon_id": "9615",
        "body_mass_kg": 25.0,
        "core_temp_normal_C": 38.5,
        "hr_normal_bpm": 90.0,
        "rr_normal_bpm": 22.0,
        "systems": ["cardiovascular", "metabolic", "thermoregulation",
                    "respiratory", "musculoskeletal", "neuroendocrine"],
    },
    "salmonid_adult": {
        "taxa": "Salmo salar",
        "ncbi_taxon_id": "8030",
        "body_mass_kg": 4.5,
        "core_temp_normal_C": None,   # ectotherm — ambient-dependent
        "hr_normal_bpm": 50.0,
        "rr_normal_bpm": None,        # gill ventilation rate used instead
        "systems": ["cardiovascular", "metabolic", "osmoregulation",
                    "respiratory", "immune"],
    },
    "equine_adult": {
        "taxa": "Equus caballus",
        "ncbi_taxon_id": "9796",
        "body_mass_kg": 500.0,
        "core_temp_normal_C": 37.8,
        "hr_normal_bpm": 36.0,
        "rr_normal_bpm": 12.0,
        "systems": ["cardiovascular", "metabolic", "thermoregulation",
                    "respiratory", "musculoskeletal", "neuroendocrine"],
    },
}


def register_animal_type(name: str, config: Dict[str, Any]) -> None:
    """Add a custom animal type template to the registry."""
    _ANIMAL_TYPE_REGISTRY[name] = copy.deepcopy(config)
    logger.info("ATR: registered animal type '%s'", name)


# ---------------------------------------------------------------------------
# Structural Layer dataclasses
# ---------------------------------------------------------------------------

@dataclass
class AnatomicalSystem:
    """
    Mirrors HorizonLayer in DP. Represents one physiological system
    (e.g. cardiovascular) within the digital twin's structural layer.
    """
    system_id: str                          # e.g. "cardiovascular"
    uberon_id: str                          # e.g. "UBERON:0001981"
    display_name: str
    state_variables: List[str]              # canonical keys tracked in this system
    normal_ranges: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SomaConfig:
    """
    Top-level configuration object passed to build_soma().
    """
    animal_type: str                        # key into ATR
    animal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    site_name: str = ""
    species_override: Optional[str] = None
    body_mass_kg: Optional[float] = None
    alarm_thresholds: Dict[str, Any] = field(default_factory=dict)
    custom_systems: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Threshold Event System (TES)
# ---------------------------------------------------------------------------

class ThresholdEventSystem:
    """
    Observer-pattern alarm system. Fires registered callbacks when a
    canonical state variable breaches its configured threshold.
    Threshold Event System — alarm types are physiological (temperature, HR, SpO2, cortisol).
    """

    # Default physiological alarms (bovine reference values)
    DEFAULT_ALARMS = {
        "core_temp_C":         {"low": 37.5, "high": 40.5, "label": "hyperthermia/hypothermia"},
        "heart_rate_bpm":      {"low": 30.0, "high": 120.0, "label": "bradycardia/tachycardia"},
        "respiratory_rate_bpm":{"low": 8.0,  "high": 60.0,  "label": "bradypnea/tachypnea"},
        "spo2_pct":            {"low": 90.0, "high": None,   "label": "hypoxaemia"},
        "blood_glucose_mmol_L":{"low": 2.5,  "high": 10.0,  "label": "hypoglycaemia/hyperglycaemia"},
        "cortisol_nmol_L":     {"low": None, "high": 200.0,  "label": "stress/HPA activation"},
    }

    def __init__(self, overrides: Optional[Dict[str, Any]] = None) -> None:
        self._thresholds: Dict[str, Any] = copy.deepcopy(self.DEFAULT_ALARMS)
        if overrides:
            self._thresholds.update(overrides)
        self._handlers: List[Callable[[str, float, str], None]] = []

    def register_handler(self, fn: Callable[[str, float, str], None]) -> None:
        """Register a callback: fn(canonical_key, value, alarm_label)."""
        self._handlers.append(fn)

    def check(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Evaluate state against thresholds; fire handlers and return fired events."""
        fired: List[Dict[str, Any]] = []
        for key, limits in self._thresholds.items():
            val = state.get(key)
            if val is None:
                continue
            lo, hi = limits.get("low"), limits.get("high")
            label = limits.get("label", key)
            if (lo is not None and val < lo) or (hi is not None and val > hi):
                event = {"key": key, "value": val, "label": label,
                         "timestamp": time.time()}
                fired.append(event)
                for handler in self._handlers:
                    try:
                        handler(key, val, label)
                    except Exception as exc:   # noqa: BLE001
                        logger.warning("TES handler raised: %s", exc)
        return fired


# ---------------------------------------------------------------------------
# Dynamic Layer
# ---------------------------------------------------------------------------

class DynamicLayer:
    """
    Manages live physiological state through three optimised structures:
      KVS : O(1) current state access
      TSL : append-only time-series log, queryable via query_history()
      TES : threshold event system
    Mirrors DP DynamicLayer exactly.
    """

    def __init__(self, tes: ThresholdEventSystem) -> None:
        self._kvs: Dict[str, Any] = {}
        self._tsl: List[Dict[str, Any]] = []
        self._tes = tes

    # -- state access --------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        return self._kvs.get(canonical_key(key), default)

    def set(self, key: str, value: Any) -> None:
        self._kvs[canonical_key(key)] = value

    def snapshot(self) -> Dict[str, Any]:
        return copy.deepcopy(self._kvs)

    # -- time-series ---------------------------------------------------------

    def log_snapshot(self, extra: Optional[Dict[str, Any]] = None) -> None:
        record = {"timestamp": time.time(), "state": self.snapshot()}
        if extra:
            record.update(extra)
        self._tsl.append(record)

    def query_history(
        self,
        key: str,
        since: Optional[float] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return time-stamped values for *key* from the TSL."""
        ckey = canonical_key(key)
        results = [
            {"timestamp": r["timestamp"], "value": r["state"].get(ckey)}
            for r in self._tsl
            if ckey in r["state"]
            and (since is None or r["timestamp"] >= since)
        ]
        if limit is not None:
            results = results[-limit:]
        return results

    # -- threshold checks ----------------------------------------------------

    def check_thresholds(self) -> List[Dict[str, Any]]:
        return self._tes.check(self._kvs)


# ---------------------------------------------------------------------------
# Functional Layer — Model Zoo (solver chain)
# ---------------------------------------------------------------------------

class ModelZoo:
    """
    Strategy-pattern solver registry. Mirrors DP ModelZoo exactly.

    Each solver is a callable:
        fn(params: dict, state: dict) -> dict

    Solvers execute in registration order on every update() call.
    Each solver's output is merged into *state* before the next solver runs,
    forming a DAG of data dependencies.
    """

    # Built-in solver names (can be unregistered and replaced)
    BUILTIN_NAMES = frozenset([
        "cardiovascular_baseline",
        "metabolic_rate",
        "thermoregulation",
        "respiratory_gas_exchange",
        "neuroendocrine_stress",
        "adverse_event_screen",
    ])

    def __init__(self) -> None:
        self._registry: Dict[str, Callable[[Dict, Dict], Dict]] = {}
        self._order: List[str] = []

    def register_method(self, name: str, fn: Callable[[Dict, Dict], Dict]) -> None:
        """Register (or replace) a solver by name."""
        if name not in self._registry:
            self._order.append(name)
        self._registry[name] = fn
        logger.info("ModelZoo: registered solver '%s'", name)

    def unregister_method(self, name: str) -> None:
        """Remove a solver from the chain."""
        if name in self._registry:
            del self._registry[name]
            self._order.remove(name)
            logger.info("ModelZoo: unregistered solver '%s'", name)

    def run(self, params: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute all registered solvers in order.
        Each solver receives the accumulated state from all previous solvers.
        Returns the final merged state dict.
        """
        merged = copy.deepcopy(state)
        for name in self._order:
            fn = self._registry[name]
            try:
                result = fn(params, merged)
                if isinstance(result, dict):
                    merged.update(result)
            except Exception as exc:   # noqa: BLE001
                logger.error("Solver '%s' raised: %s", name, exc)
        return merged

    def list_solvers(self) -> List[str]:
        return list(self._order)


# ---------------------------------------------------------------------------
# Built-in solvers
# ---------------------------------------------------------------------------

def _solver_cardiovascular_baseline(params: Dict, state: Dict) -> Dict:
    """
    Cardiovascular baseline inference.
    Estimates cardiac output from HR and stroke volume (Fick approximation).
    Flags tachycardia / bradycardia relative to species normal range.
    """
    hr = state.get("heart_rate_bpm")
    sv_ml = state.get("stroke_volume_mL", params.get("stroke_volume_mL_default", 80.0))
    if hr is None:
        return {}
    cardiac_output_L_min = (hr * sv_ml) / 1000.0
    # Mean arterial pressure estimate (if systolic/diastolic available)
    sbp = state.get("systolic_bp_mmHg")
    dbp = state.get("diastolic_bp_mmHg")
    map_mmhg = None
    if sbp is not None and dbp is not None:
        map_mmhg = dbp + (sbp - dbp) / 3.0
    result = {"cardiac_output_L_min": cardiac_output_L_min}
    if map_mmhg is not None:
        result["mean_arterial_pressure_mmHg"] = map_mmhg
    return result


def _solver_metabolic_rate(params: Dict, state: Dict) -> Dict:
    """
    Resting metabolic rate (RMR) via Kleiber's law: RMR = 70 * M^0.75 kcal/day.
    Adjusts for body temperature (Q10 = 2.0 for endotherms).
    """
    mass_kg = params.get("body_mass_kg", state.get("body_mass_kg"))
    if mass_kg is None:
        return {}
    rmr_kcal_day = 70.0 * (mass_kg ** 0.75)
    # Temperature correction (Q10)
    temp_c = state.get("core_temp_C", params.get("core_temp_normal_C", 38.5))
    temp_ref = params.get("core_temp_normal_C", 38.5)
    q10 = params.get("metabolic_q10", 2.0)
    rmr_adjusted = rmr_kcal_day * (q10 ** ((temp_c - temp_ref) / 10.0))
    return {
        "rmr_kcal_day": rmr_adjusted,
        "rmr_W": rmr_adjusted * 0.04845,   # kcal/day → Watts
    }


def _solver_thermoregulation(params: Dict, state: Dict) -> Dict:
    """
    Simple Newton's-law heat balance.
    Net heat flux = metabolic heat production - convective loss to environment.
    Infers thermal comfort index (TCI): 0 = thermoneutral, <0 = cold stress, >0 = heat stress.
    """
    core_temp = state.get("core_temp_C")
    ambient_temp = state.get("ambient_temp_C", params.get("ambient_temp_C_default", 20.0))
    rmr_w = state.get("rmr_W")
    if core_temp is None or rmr_w is None:
        return {}
    # Thermal conductance estimate (W / °C) — species-dependent
    k_w_per_C = params.get("thermal_conductance_W_per_C", 0.05 * params.get("body_mass_kg", 100.0) ** 0.5)
    heat_loss_w = k_w_per_C * (core_temp - ambient_temp)
    net_heat_w = rmr_w - heat_loss_w
    tci = net_heat_w / rmr_w          # dimensionless; >0.1 → heat stress
    return {
        "heat_loss_W": heat_loss_w,
        "net_heat_flux_W": net_heat_w,
        "thermal_comfort_index": tci,
    }


def _solver_respiratory_gas_exchange(params: Dict, state: Dict) -> Dict:
    """
    Alveolar gas exchange approximation.
    Estimates O2 consumption and CO2 production from metabolic rate (RQ = 0.85).
    """
    rmr_w = state.get("rmr_W")
    rr = state.get("respiratory_rate_bpm")
    spo2 = state.get("spo2_pct", 98.0)
    if rmr_w is None:
        return {}
    rq = params.get("respiratory_quotient", 0.85)
    vo2_L_min = rmr_w * 0.01433 / 4.8          # approx: 1W ≈ 0.01433 kcal/min; 1 L O2 ≈ 4.8 kcal
    vco2_L_min = vo2_L_min * rq
    result = {
        "vo2_L_min": vo2_L_min,
        "vco2_L_min": vco2_L_min,
    }
    if rr is not None:
        tidal_vol_L = params.get("tidal_volume_L_default", 0.5)
        minute_ventilation_L_min = rr * tidal_vol_L
        result["minute_ventilation_L_min"] = minute_ventilation_L_min
    return result


def _solver_neuroendocrine_stress(params: Dict, state: Dict) -> Dict:
    """
    HPA axis stress index.
    Combines cortisol level (if available) with heart rate deviation and
    thermal comfort index to produce a composite physiological stress score (0–1).
    """
    hr = state.get("heart_rate_bpm")
    hr_normal = params.get("hr_normal_bpm", 60.0)
    cortisol = state.get("cortisol_nmol_L")
    cortisol_ref = params.get("cortisol_normal_nmol_L", 30.0)
    tci = state.get("thermal_comfort_index", 0.0)

    components = []
    if hr is not None and hr_normal > 0:
        hr_dev = abs(hr - hr_normal) / hr_normal
        components.append(min(hr_dev, 1.0))
    if cortisol is not None:
        cort_dev = max(0.0, (cortisol - cortisol_ref) / cortisol_ref)
        components.append(min(cort_dev, 1.0))
    if tci is not None:
        components.append(min(abs(tci), 1.0))

    if not components:
        return {}
    stress_index = sum(components) / len(components)
    return {"physiological_stress_index": stress_index}


def _solver_adverse_event_screen(params: Dict, state: Dict) -> Dict:
    """
    VeDDRA-aligned adverse event screening.
    Maps physiological state variables to VeDDRA clinical sign categories and
    computes an adverse event probability score (0–1) for pharmacovigilance reporting.
    Each flagged sign is annotated with its VeDDRA term ID.
    """
    flags: List[Dict[str, Any]] = []

    # VeDDRA term mappings: {state_key: (threshold_fn, veddra_term, veddra_id)}
    _VEDDRA_SCREENS = [
        ("core_temp_C",         lambda v, p: v > p.get("core_temp_normal_C", 38.5) + 1.5,
         "Hyperthermia", "10020557"),
        ("core_temp_C",         lambda v, p: v < p.get("core_temp_normal_C", 38.5) - 2.0,
         "Hypothermia", "10021113"),
        ("heart_rate_bpm",      lambda v, p: v > p.get("hr_normal_bpm", 60.0) * 1.5,
         "Tachycardia", "10043071"),
        ("heart_rate_bpm",      lambda v, p: v < p.get("hr_normal_bpm", 60.0) * 0.6,
         "Bradycardia", "10006093"),
        ("spo2_pct",            lambda v, _p: v < 90.0,
         "Hypoxia", "10021143"),
        ("physiological_stress_index", lambda v, _p: v > 0.7,
         "Distress", "10013029"),
    ]

    for key, threshold_fn, veddra_term, veddra_id in _VEDDRA_SCREENS:
        val = state.get(key)
        if val is not None and threshold_fn(val, params):
            flags.append({
                "state_key": key,
                "value": val,
                "veddra_term": veddra_term,
                "veddra_id": veddra_id,
                "veddra_namespace": "https://www.ema.europa.eu/en/veterinary-regulatory/",
            })

    ae_score = min(len(flags) / max(len(_VEDDRA_SCREENS), 1), 1.0)
    return {
        "ae_flags": flags,
        "adverse_event_score": ae_score,
    }


# ---------------------------------------------------------------------------
# Core DigitalSoma class
# ---------------------------------------------------------------------------

class DigitalSoma:
    """
    The DigitalSoma (DS) is the core computational object — the digital twin
    of a living animal.

        build_soma(config)          ← initialise structural layer
        update_sync(readings)       ← ingest sensor data + run solver chain
        query_history(key)          ← time-series access
        register_method(name, fn)   ← extend Model Zoo
        to_jsonld()                 ← JSON-LD export (Uberon/SNOMED/VeDDRA URIs)
        describe()                  ← LLM-ready state summary

    Separation of concerns:
        Structural Layer  — set once by build_soma(), never modified at runtime
        Dynamic Layer     — updated on every update_sync() call
        Functional Layer  — solver chain runs on every update_sync() call
    """

    def __init__(self) -> None:
        # Structural Layer
        self._sl: Dict[str, Any] = {}
        self._systems: List[AnatomicalSystem] = []
        self._params: Dict[str, Any] = {}

        # Dynamic Layer
        self._tes = ThresholdEventSystem()
        self._dl = DynamicLayer(self._tes)

        # Functional Layer
        self._zoo = ModelZoo()
        self._register_builtin_solvers()

        self._soma_id: str = str(uuid.uuid4())
        self._built: bool = False

    # -- Structural Layer ----------------------------------------------------

    def build_soma(self, config: SomaConfig) -> "DigitalSoma":
        """
        Initialise the structural layer from a SomaConfig.
        """
        template = _ANIMAL_TYPE_REGISTRY.get(config.animal_type)
        if template is None:
            raise ValueError(
                f"Unknown animal type '{config.animal_type}'. "
                f"Available: {list(_ANIMAL_TYPE_REGISTRY)}"
            )
        self._sl = copy.deepcopy(template)
        self._sl["animal_id"] = config.animal_id
        self._sl["animal_type"] = config.animal_type
        self._sl["site_name"] = config.site_name

        if config.species_override:
            self._sl["taxa"] = config.species_override
        if config.body_mass_kg is not None:
            self._sl["body_mass_kg"] = config.body_mass_kg
        if config.metadata:
            self._sl["metadata"] = config.metadata

        # Build params dict consumed by solvers
        self._params = {
            "body_mass_kg": self._sl.get("body_mass_kg"),
            "core_temp_normal_C": self._sl.get("core_temp_normal_C"),
            "hr_normal_bpm": self._sl.get("hr_normal_bpm"),
            "rr_normal_bpm": self._sl.get("rr_normal_bpm"),
        }

        # Threshold overrides
        if config.alarm_thresholds:
            self._tes._thresholds.update(config.alarm_thresholds)

        # Register custom systems from config
        for sys_cfg in config.custom_systems:
            asys = AnatomicalSystem(**sys_cfg)
            self._systems.append(asys)

        self._built = True
        logger.info("DigitalSoma built: %s (%s)", config.animal_id, self._sl["taxa"])
        return self

    # -- Sensor ingest + solver chain ----------------------------------------

    def update_sync(self, readings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ingest a sensor reading dict, resolve canonical keys, run the solver
        chain, update dynamic layer, check thresholds, log snapshot.

        Returns the full merged state dict (structural params + sensor readings
        + all derived solver outputs).

        Mirrors DP update_sync().
        """
        if not self._built:
            raise RuntimeError("Call build_soma() before update_sync().")

        # 1. Normalise incoming keys via ontology layer
        norm = normalise_dict(readings)

        # 2. Write normalised readings into KV store
        for k, v in norm.items():
            self._dl.set(k, v)

        # 3. Build state dict: structural params + current KV store
        state = {**self._params, **self._dl.snapshot()}

        # 4. Run solver chain (Model Zoo)
        derived = self._zoo.run(self._params, state)

        # 5. Write derived quantities back into KV store
        for k, v in derived.items():
            if k not in self._params:   # never overwrite structural constants
                self._dl.set(k, v)

        # 6. Check thresholds
        fired = self._dl.check_thresholds()
        if fired:
            logger.warning("TES: %d alarm(s) fired: %s",
                           len(fired), [e["label"] for e in fired])

        # 7. Log snapshot to TSL
        self._dl.log_snapshot({"alarm_count": len(fired)})

        return self._dl.snapshot()

    # -- Time-series access --------------------------------------------------

    def query_history(
        self,
        key: str,
        since: Optional[float] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return time-stamped historical values for a canonical key."""
        return self._dl.query_history(key, since=since, limit=limit)

    # -- Solver extensibility ------------------------------------------------

    def register_method(self, name: str, fn: Callable[[Dict, Dict], Dict]) -> None:
        """
        Add a custom solver to the Model Zoo.
        Custom solvers can consume outputs of built-in solvers because
        they execute after all built-ins in the DAG chain.
        Mirrors DP register_method().
        """
        self._zoo.register_method(name, fn)

    def unregister_method(self, name: str) -> None:
        """Remove a solver (built-in or custom) from the chain."""
        self._zoo.unregister_method(name)

    # -- Ontology & export ---------------------------------------------------

    def to_jsonld(self) -> Dict[str, Any]:
        """
        Export current state as a JSON-LD document.
        All keys carry Uberon / SNOMED / VeDDRA URIs via vocab.py.
        Mirrors DP to_jsonld().
        """
        state = self._dl.snapshot()
        doc = to_jsonld(state)
        doc["@type"] = "DigitalSoma"
        doc["soma_id"] = self._soma_id
        doc["taxa"] = self._sl.get("taxa", "")
        doc["ncbi_taxon_id"] = self._sl.get("ncbi_taxon_id", "")
        doc["animal_id"] = self._sl.get("animal_id", "")
        return doc

    def veddra_report(self) -> Dict[str, Any]:
        """
        Generate a VeDDRA-compliant adverse event report from current state.
        Suitable for submission to EMA EVVET3 / VMD / FDA-CVM.
        """
        state = self._dl.snapshot()
        flags = state.get("ae_flags", [])
        return {
            "@type": "VeDDRA_AdverseEventReport",
            "report_id": str(uuid.uuid4()),
            "soma_id": self._soma_id,
            "animal_id": self._sl.get("animal_id", ""),
            "taxa": self._sl.get("taxa", ""),
            "timestamp": time.time(),
            "adverse_event_score": state.get("adverse_event_score", 0.0),
            "clinical_signs": flags,
            "veddra_namespace": "https://www.ema.europa.eu/en/veterinary-regulatory/",
            "reporting_standard": "VeDDRA v2.2",
        }

    # -- LLM-ready description -----------------------------------------------

    def describe(self) -> str:
        """
        Return a structured natural-language-ready description of the twin's
        current state. Used by soma_agent.py for LLM tool responses.
        Mirrors DP dp_describe().
        """
        state = self._dl.snapshot()
        sl = self._sl
        lines = [
            f"DigitalSoma — {sl.get('taxa', 'unknown species')}",
            f"Animal ID : {sl.get('animal_id', '')}",
            f"Type      : {sl.get('animal_type', '')}",
            f"Site      : {sl.get('site_name', '')}",
            "",
            "--- Current physiological state ---",
        ]
        priority_keys = [
            "core_temp_C", "heart_rate_bpm", "respiratory_rate_bpm",
            "spo2_pct", "blood_glucose_mmol_L", "cortisol_nmol_L",
            "cardiac_output_L_min", "rmr_W", "thermal_comfort_index",
            "physiological_stress_index", "adverse_event_score",
        ]
        for k in priority_keys:
            v = state.get(k)
            if v is not None:
                lines.append(f"  {k:40s}: {v:.4g}")
        ae_flags = state.get("ae_flags", [])
        if ae_flags:
            lines.append("")
            lines.append("--- VeDDRA adverse event flags ---")
            for f in ae_flags:
                lines.append(
                    f"  [{f['veddra_id']}] {f['veddra_term']} "
                    f"(key={f['state_key']}, value={f['value']:.4g})"
                )
        return "\n".join(lines)

    # -- Properties ----------------------------------------------------------

    @property
    def soma_id(self) -> str:
        return self._soma_id

    @property
    def structural_layer(self) -> Dict[str, Any]:
        return copy.deepcopy(self._sl)

    @property
    def solvers(self) -> List[str]:
        return self._zoo.list_solvers()

    # -- Internal ------------------------------------------------------------

    def _register_builtin_solvers(self) -> None:
        self._zoo.register_method("cardiovascular_baseline", _solver_cardiovascular_baseline)
        self._zoo.register_method("metabolic_rate", _solver_metabolic_rate)
        self._zoo.register_method("thermoregulation", _solver_thermoregulation)
        self._zoo.register_method("respiratory_gas_exchange", _solver_respiratory_gas_exchange)
        self._zoo.register_method("neuroendocrine_stress", _solver_neuroendocrine_stress)
        self._zoo.register_method("adverse_event_screen", _solver_adverse_event_screen)


# ---------------------------------------------------------------------------
# Convenience constructor
# ---------------------------------------------------------------------------

def build_soma(config: SomaConfig) -> DigitalSoma:
    """
    Convenience function. Returns a fully initialised DigitalSoma.

    Example
    -------
    >>> from digitalsoma.soma_api import build_soma, SomaConfig
    >>> ds = build_soma(SomaConfig(animal_type="bovine_adult", site_name="Farm A"))
    >>> state = ds.update_sync({"heart_rate_bpm": 72, "core_temp_C": 39.1})
    >>> print(ds.describe())
    """
    ds = DigitalSoma()
    ds.build_soma(config)
    return ds
