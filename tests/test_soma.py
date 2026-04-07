"""
tests/test_soma.py — DigitalSoma core framework test suite.

Run: pytest tests/test_soma.py -v
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
from digitalsoma import build_soma, SomaConfig, register_animal_type


# ---------------------------------------------------------------------------
# Structural layer
# ---------------------------------------------------------------------------

def test_build_soma_bovine():
    ds = build_soma(SomaConfig(animal_type="bovine_adult", site_name="Test farm"))
    sl = ds.structural_layer
    assert sl["taxa"] == "Bos taurus"
    assert sl["body_mass_kg"] == 600.0
    assert sl["hr_normal_bpm"] == 60.0


def test_build_soma_all_builtin_types():
    for atype in ["bovine_adult", "ovine_adult", "canine_adult",
                  "salmonid_adult", "equine_adult"]:
        ds = build_soma(SomaConfig(animal_type=atype))
        assert ds.structural_layer["animal_type"] == atype


def test_build_soma_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown animal type"):
        build_soma(SomaConfig(animal_type="martian_quadruped"))


def test_body_mass_override():
    ds = build_soma(SomaConfig(animal_type="bovine_adult", body_mass_kg=450.0))
    assert ds.structural_layer["body_mass_kg"] == 450.0


def test_register_custom_animal_type():
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
    assert ds.structural_layer["taxa"] == "Vicugna pacos"


# ---------------------------------------------------------------------------
# Solver chain
# ---------------------------------------------------------------------------

def test_solvers_registered_at_build():
    ds = build_soma(SomaConfig(animal_type="bovine_adult"))
    expected = [
        "cardiovascular_baseline", "metabolic_rate", "thermoregulation",
        "respiratory_gas_exchange", "neuroendocrine_stress", "adverse_event_screen",
    ]
    assert ds.solvers == expected


def test_update_sync_derives_cardiac_output():
    ds = build_soma(SomaConfig(animal_type="bovine_adult"))
    state = ds.update_sync({"heart_rate_bpm": 60})
    # cardiac_output_L_min = (60 * 80) / 1000 = 4.8
    assert abs(state["cardiac_output_L_min"] - 4.8) < 0.01


def test_update_sync_derives_rmr():
    ds = build_soma(SomaConfig(animal_type="bovine_adult"))
    state = ds.update_sync({"core_temp_C": 38.5})
    # Kleiber: 70 * 600^0.75 ≈ 70 * 106.9 ≈ 7483 kcal/day → W
    assert state["rmr_W"] > 0


def test_update_sync_derives_stress_index():
    ds = build_soma(SomaConfig(animal_type="bovine_adult"))
    state = ds.update_sync({
        "heart_rate_bpm": 110,     # tachycardic (normal=60)
        "core_temp_C": 41.0,
    })
    assert state["physiological_stress_index"] > 0.5


def test_solver_chain_dag_compositionality():
    """Thermoregulation solver consumes rmr_W from metabolic_rate solver."""
    ds = build_soma(SomaConfig(animal_type="bovine_adult"))
    state = ds.update_sync({
        "core_temp_C": 40.0,
        "ambient_temp_C": 30.0,
    })
    # net_heat_flux_W requires rmr_W (metabolic) and core/ambient temp (thermo)
    assert "net_heat_flux_W" in state
    assert "thermal_comfort_index" in state


def test_alias_resolution_in_update_sync():
    """update_sync() must accept vendor aliases, not just canonical keys."""
    ds = build_soma(SomaConfig(animal_type="bovine_adult"))
    state = ds.update_sync({"HR": 72, "Tb": 38.5, "SpO2": 98.0})
    assert state.get("heart_rate_bpm") == 72
    assert state.get("core_temp_C") == 38.5
    assert state.get("spo2_pct") == 98.0


# ---------------------------------------------------------------------------
# Dynamic layer — KVS and TSL
# ---------------------------------------------------------------------------

def test_query_history_returns_records():
    ds = build_soma(SomaConfig(animal_type="bovine_adult"))
    for hr in [60, 65, 70, 75, 80]:
        ds.update_sync({"heart_rate_bpm": hr})
    history = ds.query_history("heart_rate_bpm")
    assert len(history) == 5
    values = [r["value"] for r in history]
    assert 60 in values and 80 in values


def test_query_history_limit():
    ds = build_soma(SomaConfig(animal_type="bovine_adult"))
    for hr in range(60, 70):
        ds.update_sync({"heart_rate_bpm": hr})
    history = ds.query_history("heart_rate_bpm", limit=3)
    assert len(history) == 3


def test_query_history_alias_resolution():
    ds = build_soma(SomaConfig(animal_type="bovine_adult"))
    ds.update_sync({"HR": 72})
    # query via alias "HR" should resolve to "heart_rate_bpm" in TSL
    history = ds.query_history("HR")
    assert len(history) >= 1


# ---------------------------------------------------------------------------
# Threshold Event System
# ---------------------------------------------------------------------------

def test_tes_fires_on_hyperthermia():
    fired_events = []
    ds = build_soma(SomaConfig(animal_type="bovine_adult"))
    ds._tes.register_handler(
        lambda key, val, label: fired_events.append(label)
    )
    ds.update_sync({"core_temp_C": 41.5})   # above 40.5 °C threshold
    assert any("hyperthermia" in e.lower() for e in fired_events)


def test_tes_does_not_fire_in_normal_range():
    fired_events = []
    ds = build_soma(SomaConfig(animal_type="bovine_adult"))
    ds._tes.register_handler(
        lambda key, val, label: fired_events.append(label)
    )
    ds.update_sync({"core_temp_C": 38.5, "heart_rate_bpm": 62})
    assert len(fired_events) == 0


def test_tes_custom_threshold():
    fired = []
    ds = build_soma(SomaConfig(
        animal_type="bovine_adult",
        alarm_thresholds={"heart_rate_bpm": {"low": 50.0, "high": 70.0, "label": "custom_hr_alarm"}}
    ))
    ds._tes.register_handler(lambda k, v, l: fired.append(l))
    ds.update_sync({"heart_rate_bpm": 80})   # above custom high=70
    assert "custom_hr_alarm" in fired


# ---------------------------------------------------------------------------
# VeDDRA adverse event screening
# ---------------------------------------------------------------------------

def test_veddra_no_flags_at_baseline():
    ds = build_soma(SomaConfig(animal_type="bovine_adult"))
    state = ds.update_sync({
        "core_temp_C": 38.5, "heart_rate_bpm": 60,
        "spo2_pct": 98.5, "respiratory_rate_bpm": 20,
    })
    assert state["adverse_event_score"] == 0.0
    assert state["ae_flags"] == []


def test_veddra_flags_hyperthermia():
    ds = build_soma(SomaConfig(animal_type="bovine_adult"))
    state = ds.update_sync({"core_temp_C": 41.0, "heart_rate_bpm": 60})
    terms = [f["veddra_term"] for f in state["ae_flags"]]
    assert "Hyperthermia" in terms


def test_veddra_flags_tachycardia():
    ds = build_soma(SomaConfig(animal_type="bovine_adult"))
    state = ds.update_sync({"heart_rate_bpm": 110, "core_temp_C": 38.5})
    terms = [f["veddra_term"] for f in state["ae_flags"]]
    assert "Tachycardia" in terms


def test_veddra_flags_hypoxia():
    ds = build_soma(SomaConfig(animal_type="bovine_adult"))
    state = ds.update_sync({"spo2_pct": 88.0})
    terms = [f["veddra_term"] for f in state["ae_flags"]]
    assert "Hypoxia" in terms


def test_veddra_report_structure():
    ds = build_soma(SomaConfig(animal_type="bovine_adult"))
    ds.update_sync({"core_temp_C": 41.0, "heart_rate_bpm": 110})
    report = ds.veddra_report()
    assert report["@type"] == "VeDDRA_AdverseEventReport"
    assert "report_id" in report
    assert "clinical_signs" in report
    assert report["reporting_standard"] == "VeDDRA v2.2"
    assert report["taxa"] == "Bos taurus"


# ---------------------------------------------------------------------------
# JSON-LD export
# ---------------------------------------------------------------------------

def test_jsonld_export_type():
    ds = build_soma(SomaConfig(animal_type="bovine_adult"))
    ds.update_sync({"heart_rate_bpm": 72})
    doc = ds.to_jsonld()
    assert doc["@type"] == "DigitalSoma"
    assert "@context" in doc
    assert doc["taxa"] == "Bos taurus"


# ---------------------------------------------------------------------------
# Solver extensibility
# ---------------------------------------------------------------------------

def test_register_custom_solver():
    ds = build_soma(SomaConfig(animal_type="bovine_adult"))

    def dummy_solver(params, state):
        return {"custom_output": 42.0}

    ds.register_method("dummy", dummy_solver)
    assert "dummy" in ds.solvers
    state = ds.update_sync({})
    assert state.get("custom_output") == 42.0


def test_custom_solver_consumes_builtin_output():
    """Mirrors DP E4: custom solver reads built-in solver output in same update cycle."""
    ds = build_soma(SomaConfig(animal_type="bovine_adult"))

    def hrv_solver(params, state):
        co = state.get("cardiac_output_L_min", 0)
        return {"test_hrv_marker": co * 10}

    ds.register_method("hrv_test", hrv_solver)
    state = ds.update_sync({"heart_rate_bpm": 60})

    # cardiac_output_L_min should be 4.8; test_hrv_marker = 48.0
    assert abs(state.get("test_hrv_marker", 0) - 48.0) < 0.1


def test_unregister_solver():
    ds = build_soma(SomaConfig(animal_type="bovine_adult"))
    ds.unregister_method("adverse_event_screen")
    assert "adverse_event_screen" not in ds.solvers
    # State update should still work without it
    state = ds.update_sync({"heart_rate_bpm": 60})
    assert "cardiac_output_L_min" in state


def test_update_before_build_raises():
    from digitalsoma.soma_api import DigitalSoma
    ds = DigitalSoma()
    with pytest.raises(RuntimeError, match="build_soma"):
        ds.update_sync({"heart_rate_bpm": 60})
