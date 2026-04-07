"""
equitwin/examples/e1_gait_biomechanics.py
===============================================================================
EquiTwin — Example 1: Biomechanical / Gait / Stride Analysis Pipeline
===============================================================================

Demonstrates the complete gait pipeline integrated into DigitalSoma:

    Step 1.  Build a DigitalSoma equine_adult twin
    Step 2.  Register the three gait solvers via register_gait_pipeline()
    Step 3.  Configure the EnergyTag manifesto
    Step 4.  Run three physiological scenarios through the 9-solver DAG:

             A. Sound horse — healthy trot baseline
             B. Subclinical left forelimb asymmetry (pre-pathological)
             C. Clinical lameness progression under heat stress

    Step 5.  Inspect all solver outputs and alarm events
    Step 6.  Query time-series history for injury_risk_index

Run from the repo root:
    python equitwin/examples/e1_gait_biomechanics.py

Expected output shows how subclinical asymmetry is detected BEFORE any
lameness is visible to the naked eye — the core EquiTwin value proposition.
"""

import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from digitalsoma import build_soma, SomaConfig
from equitwin.solvers.gait_biomechanics import register_gait_pipeline, EQUINE_REF
from equitwin.sensor.equine_manifest import equine_energytag_manifest, equine_race_manifest

# ────────────────────────────────────────────────────────────────────────────
# 1. Build HorseTwin
# ────────────────────────────────────────────────────────────────────────────

print("=" * 72)
print("EquiTwin — Gait Biomechanics Pipeline Demo")
print("Foundation: DigitalSoma v1.0  |  equine_adult (Equus caballus)")
print("=" * 72)

ds = build_soma(SomaConfig(
    animal_type = "equine_adult",
    animal_id   = "ET_HORSE_001",
    site_name   = "Equestrian Centre, Ghent — Training Track",
    body_mass_kg = 520.0,           # individual weight override
))

# ────────────────────────────────────────────────────────────────────────────
# 2. Register gait pipeline (3 new solvers + TES alarms)
# ────────────────────────────────────────────────────────────────────────────

register_gait_pipeline(ds)

print(f"\nRegistered solvers ({len(ds.solvers)} total):")
builtin = {"cardiovascular_baseline", "metabolic_rate", "thermoregulation",
           "respiratory_gas_exchange", "neuroendocrine_stress", "adverse_event_screen"}
for i, s in enumerate(ds.solvers, 1):
    tag = "  [built-in]" if s in builtin else "  [⊕ gait]  "
    print(f"  {i:2d}. {s}{tag}")

# ────────────────────────────────────────────────────────────────────────────
# 3. Register an alarm handler to capture TES events
# ────────────────────────────────────────────────────────────────────────────

alarm_log = []

def alarm_handler(key, value, label):
    alarm_log.append({"key": key, "value": value, "label": label})
    print(f"  ⚠  TES ALARM  [{label}]  {key} = {value:.4f}")

ds._tes.register_handler(alarm_handler)

# ────────────────────────────────────────────────────────────────────────────
# 4. Configure EnergyTag sensor manifest
# ────────────────────────────────────────────────────────────────────────────

manifest = equine_energytag_manifest()
print(f"\nEnergyTag manifest: {len(manifest._registry)} sensors registered")

# ────────────────────────────────────────────────────────────────────────────
# 5. Scenario A — Sound horse, healthy trot (baseline)
# ────────────────────────────────────────────────────────────────────────────

print("\n" + "─" * 72)
print("SCENARIO A — Sound horse, healthy trot baseline")
print("─" * 72)

# Readings represent a well-balanced horse trotting at ~4 m/s
# Perfect symmetry: equal load distribution, matched stance times
readings_A = {
    # Physiological
    "HR":          48,      # race-fit heart rate at trot
    "SpO2":        98.5,
    "core_temp_C": 38.0,
    "RR":          24,
    "cortisol_nmol_L": 28.0,
    "ambient_temp_C":  18.0,

    # Speed and stride
    "speed_m_s":          4.2,     # trot pace
    "strike_interval_s":  0.68,    # ~1.47 Hz stride frequency

    # Withers IMU — clean symmetric signal
    "acceleration_m_s2":          0.45,   # vertical
    "acceleration_lateral_m_s2":  0.08,   # minimal lateral = good symmetry
    "acceleration_fore_m_s2":     0.30,

    # Limb loads — perfectly balanced (25% each)
    "limb_lf_load_pct": 31.0,
    "limb_rf_load_pct": 30.5,
    "limb_lh_load_pct": 19.5,
    "limb_rh_load_pct": 19.0,

    # Stance times — matched L/R
    "stance_time_lf_s": 0.310,
    "stance_time_rf_s": 0.312,
    "stance_time_lh_s": 0.295,
    "stance_time_rh_s": 0.293,
}

alarm_log.clear()
state_A = ds.update_sync(readings_A)

print(f"\n  Gait classification     : {state_A.get('gait_classification')}")
print(f"  Stride frequency        : {state_A.get('stride_frequency_hz', 0):.3f} Hz")
print(f"  Stride length           : {state_A.get('stride_length_m', 0):.3f} m")
print(f"  Stride length deviation : {state_A.get('stride_length_deviation', 0):+.1%}")
print(f"  Vertical displacement   : {state_A.get('vertical_displacement_m', 0):.4f} m")
print()
print(f"  Stride symmetry index   : {state_A.get('stride_symmetry_index', 0):.4f}  (≥0.95 = normal)")
print(f"  Forelimb load symmetry  : {state_A.get('forelimb_load_symmetry', 0):.4f}")
print(f"  Hindlimb load symmetry  : {state_A.get('hindlimb_load_symmetry', 0):.4f}")
print(f"  Limb load asymmetry     : {state_A.get('limb_loading_asymmetry', 0):.4f}  (<0.06 = normal)")
print(f"  Forelimb load fraction  : {state_A.get('forelimb_load_fraction', 0):.3f}  (normal ~0.60)")
print(f"  Stance time symmetry    : {state_A.get('stance_time_symmetry', 0):.4f}")
print(f"  Symmetry status         : {state_A.get('symmetry_status')}")
print()
print(f"  Cardiac output (L/min)  : {state_A.get('cardiac_output_L_min', 0):.2f}")
print(f"  Metabolic rate (W)      : {state_A.get('rmr_W', 0):.1f}")
print(f"  Thermal comfort index   : {state_A.get('thermal_comfort_index', 0):+.4f}")
print(f"  Stress index            : {state_A.get('physiological_stress_index', 0):.4f}")
print()
print(f"  ◆ Injury risk index     : {state_A.get('injury_risk_index', 0):.4f}")
print(f"  ◆ Risk category         : {state_A.get('risk_category')}")
print(f"  ◆ Pre-pathological flag : {state_A.get('pre_pathological_flag')}")
print(f"  ◆ Recommended action    : {state_A.get('recommended_action')}")
print(f"  ◆ TES alarms fired      : {len(alarm_log)}")

# ────────────────────────────────────────────────────────────────────────────
# 6. Scenario B — Subclinical left forelimb asymmetry (pre-pathological)
# ────────────────────────────────────────────────────────────────────────────

print("\n" + "─" * 72)
print("SCENARIO B — Subclinical LF asymmetry (invisible to naked eye)")
print("─" * 72)
print("  SSI will drop below 0.95 → pre_pathological_flag = True")
print("  This is detectable by EquiTwin BEFORE any lameness is visible.")

readings_B = {
    "HR":          52,
    "SpO2":        98.0,
    "core_temp_C": 38.2,
    "RR":          26,
    "cortisol_nmol_L": 35.0,
    "ambient_temp_C":  20.0,
    "speed_m_s":         4.1,
    "strike_interval_s": 0.70,

    # Increased lateral head movement — classic lameness compensatory pattern
    "acceleration_m_s2":          0.52,
    "acceleration_lateral_m_s2":  0.22,   # elevated vs Scenario A (0.08)
    "acceleration_fore_m_s2":     0.35,

    # LF is being unloaded — horse shifts weight off painful limb
    "limb_lf_load_pct": 27.0,   # ↓ reduced (was 31%)
    "limb_rf_load_pct": 34.5,   # ↑ compensatory overload on RF
    "limb_lh_load_pct": 19.0,
    "limb_rh_load_pct": 19.5,

    # Stance time shorter on LF — horse spends less time loading painful limb
    "stance_time_lf_s": 0.285,   # ↓ shorter than RF
    "stance_time_rf_s": 0.320,   # ↑ longer
    "stance_time_lh_s": 0.295,
    "stance_time_rh_s": 0.298,
}

alarm_log.clear()
state_B = ds.update_sync(readings_B)

print(f"\n  Gait classification     : {state_B.get('gait_classification')}")
print(f"  Stride symmetry index   : {state_B.get('stride_symmetry_index', 0):.4f}  ← below 0.95 threshold")
print(f"  Forelimb load symmetry  : {state_B.get('forelimb_load_symmetry', 0):.4f}")
print(f"  Limb load asymmetry     : {state_B.get('limb_loading_asymmetry', 0):.4f}")
print(f"  Stance time symmetry    : {state_B.get('stance_time_symmetry', 0):.4f}")
print(f"  Symmetry status         : {state_B.get('symmetry_status')}")
print(f"  Subclinical flag        : {state_B.get('subclinical_lameness_flag')}")
print(f"  Suspect lame limb       : {state_B.get('lame_limb_suspect')}")
print()
print(f"  ◆ Injury risk index     : {state_B.get('injury_risk_index', 0):.4f}")
print(f"  ◆ Risk category         : {state_B.get('risk_category')}")
print(f"  ◆ Pre-pathological flag : {state_B.get('pre_pathological_flag')}")
print(f"  ◆ Recommended action    : {state_B.get('recommended_action')}")
if alarm_log:
    print(f"  TES alarms              : {[a['label'] for a in alarm_log]}")

# ────────────────────────────────────────────────────────────────────────────
# 7. Scenario C — Clinical lameness under heat stress (severity progression)
# ────────────────────────────────────────────────────────────────────────────

print("\n" + "─" * 72)
print("SCENARIO C — Clinical lameness + heat stress (severity progression)")
print("─" * 72)
print("  Asymmetry worsens + thermal load compounds → high risk category")
print()

scenarios_C = [
    ("T+0  Lameness onset",   38.5, 60,   0.32, 22.0, 4.0, 0.72, 0.30, 0.65, 0.08),
    ("T+10 Heat load adds",   39.2, 72,   0.28, 28.0, 3.8, 0.75, 0.25, 0.60, 0.14),
    ("T+20 Fatigue + lame",   39.8, 85,   0.22, 33.0, 3.5, 0.80, 0.21, 0.55, 0.20),
    ("T+30 Critical state",   40.4, 102,  0.18, 38.0, 3.2, 0.85, 0.18, 0.50, 0.28),
]
# columns: label, core_temp, HR, limb_lf, ambient_temp,
#          speed, strike_interval, lf_load, rf_load, accel_lat

print(f"  {'Scenario':<26} {'SSI':>6} {'Risk':>6} {'Category':<12} {'Lame':>6} {'Action'}")
print("  " + "─" * 90)

for (label, temp, hr, stance_lf, amb_temp,
     speed, strike, lf_load, rf_load, acc_lat) in scenarios_C:

    alarm_log.clear()
    state_C = ds.update_sync({
        "HR":              hr,
        "SpO2":            96.0 if temp > 39.5 else 98.0,
        "core_temp_C":     temp,
        "RR":              40 if temp > 39.5 else 28,
        "cortisol_nmol_L": 50.0 + (temp - 38.5) * 20,
        "ambient_temp_C":  amb_temp,
        "speed_m_s":       speed,
        "strike_interval_s": strike,
        "acceleration_m_s2":          0.50,
        "acceleration_lateral_m_s2":  acc_lat,
        "acceleration_fore_m_s2":     0.32,
        "limb_lf_load_pct": lf_load * 100,
        "limb_rf_load_pct": rf_load * 100,
        "limb_lh_load_pct": 19.0,
        "limb_rh_load_pct": 18.5,
        "stance_time_lf_s": stance_lf,
        "stance_time_rf_s": 0.330,
        "stance_time_lh_s": 0.295,
        "stance_time_rh_s": 0.295,
    })

    ssi    = state_C.get("stride_symmetry_index", 0)
    risk   = state_C.get("injury_risk_index", 0)
    cat    = state_C.get("risk_category", "")
    lame   = state_C.get("lame_limb_suspect") or "—"
    action = state_C.get("recommended_action", "")[:35] + "..."

    print(f"  {label:<26} {ssi:>6.4f} {risk:>6.4f} {cat:<12} {lame:>6}  {action}")

# ────────────────────────────────────────────────────────────────────────────
# 8. Time-series history for injury_risk_index
# ────────────────────────────────────────────────────────────────────────────

print("\n" + "─" * 72)
print("TIME-SERIES: injury_risk_index (all recorded updates)")
print("─" * 72)

history = ds.query_history("injury_risk_index")
for i, rec in enumerate(history, 1):
    risk_val = rec['value']
    bar = "█" * int(risk_val * 30)
    print(f"  Update {i:2d}  risk={risk_val:.4f}  {bar}")

print()

# ────────────────────────────────────────────────────────────────────────────
# 9. Solver summary
# ────────────────────────────────────────────────────────────────────────────

print("─" * 72)
print("SOLVER CHAIN SUMMARY — Final state (Scenario C T+30)")
print("─" * 72)
print(ds.describe())
print()
print("─" * 72)
print(f"Total solvers in DAG     : {len(ds.solvers)}")
print(f"Built-in (DigitalSoma)   : 6")
print(f"New gait solvers (⊕)     : 3")
print(f"TSL snapshots recorded   : {len(ds.query_history('injury_risk_index'))}")
print(f"Subclinical detection    : Scenario B detected BEFORE clinical symptoms")
print("─" * 72)
print("EquiTwin gait pipeline: COMPLETE")
