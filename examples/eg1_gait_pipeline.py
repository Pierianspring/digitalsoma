"""
examples/eg1_gait_pipeline.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EquiTwin — Gait Biomechanics Pipeline: Full Worked Example

Demonstrates all three gait solvers across five scenarios:
  1. Thermoneutral baseline — healthy symmetric gallop
  2. Subclinical left forelimb asymmetry — below human visual threshold
  3. Clinical lameness — left forelimb clearly loading less
  4. Heat stress compound — asymmetry + thermal load
  5. Recovery — returning toward baseline

Run:
    cd digitalsoma_github
    python examples/eg1_gait_pipeline.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from digitalsoma import build_soma, SomaConfig
from equitwin.gait_biomechanics import register_gait_pipeline, GAIT_ALARMS

# ─────────────────────────────────────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 78)
print("EquiTwin  |  Gait Biomechanics Pipeline  |  eg1_gait_pipeline.py")
print("=" * 78)

# Build HorseTwin
ds = build_soma(SomaConfig(
    animal_type = "equine_adult",
    animal_id   = "ET-HORSE-001",
    site_name   = "Ascot Racecourse, Trial A",
))

# Register gait pipeline (vocabulary + solvers + alarms)
register_gait_pipeline(ds)

print(f"\nAnimal   : {ds.structural_layer['taxa']}")
print(f"ID       : {ds.structural_layer['animal_id']}")
print(f"Site     : {ds.structural_layer['site_name']}")
print(f"\nSolvers registered ({len(ds.solvers)} total):")
for i, s in enumerate(ds.solvers, 1):
    marker = " ← gait extension" if "equine" in s else ""
    print(f"  {i:2d}. {s}{marker}")

# Alarm log collector
alarm_log = []
def on_alarm(key, value, label):
    alarm_log.append(f"  ⚠  {label:<35}  {key} = {value:.4f}")

ds._tes.register_handler(on_alarm)

# ─────────────────────────────────────────────────────────────────────────────
# Five scenarios
# ─────────────────────────────────────────────────────────────────────────────

scenarios = [
    {
        "label":       "1. Healthy baseline (symmetric gallop)",
        "description": "Thermoneutral conditions, near-perfect bilateral symmetry.",
        "readings": {
            # Stride kinematics
            "stride_duration_s":         0.48,
            "stride_length_m":           6.20,
            "speed_m_s":                 14.2,
            # Forelimb accelerations (m/s²) — symmetric
            "forelimb_vertical_acc_LF":  22.5,
            "forelimb_vertical_acc_RF":  22.8,
            # Hindlimb accelerations
            "hindlimb_vertical_acc_LH":  18.2,
            "hindlimb_vertical_acc_RH":  18.0,
            # Stance durations — symmetric
            "stance_duration_LF_s":      0.196,
            "stance_duration_RF_s":      0.194,
            # Physiological
            "heart_rate_bpm":            168,
            "core_temp_C":               38.7,
            "spo2_pct":                  97.5,
            "respiratory_rate_bpm":      100,
            "ambient_temp_C":            18.0,
        },
    },
    {
        "label":       "2. Subclinical LF asymmetry (pre-pathological)",
        "description": "Left forelimb loading 5% below right — invisible to naked eye.",
        "readings": {
            "stride_duration_s":         0.49,
            "stride_length_m":           6.05,
            "speed_m_s":                 13.8,
            "forelimb_vertical_acc_LF":  20.8,   # reduced — offloading left fore
            "forelimb_vertical_acc_RF":  23.1,
            "hindlimb_vertical_acc_LH":  18.0,
            "hindlimb_vertical_acc_RH":  18.3,
            "stance_duration_LF_s":      0.188,  # shorter — guarding left fore
            "stance_duration_RF_s":      0.202,
            "heart_rate_bpm":            174,
            "core_temp_C":               38.9,
            "spo2_pct":                  97.0,
            "respiratory_rate_bpm":      108,
            "ambient_temp_C":            18.0,
        },
    },
    {
        "label":       "3. Clinical LF lameness",
        "description": "Left forelimb loading 14% below right — visible head nod.",
        "readings": {
            "stride_duration_s":         0.52,
            "stride_length_m":           5.70,
            "speed_m_s":                 12.4,
            "forelimb_vertical_acc_LF":  17.4,   # strongly reduced
            "forelimb_vertical_acc_RF":  24.6,
            "hindlimb_vertical_acc_LH":  17.8,
            "hindlimb_vertical_acc_RH":  18.5,
            "stance_duration_LF_s":      0.175,  # significantly shorter
            "stance_duration_RF_s":      0.218,
            "heart_rate_bpm":            188,
            "core_temp_C":               39.2,
            "spo2_pct":                  96.5,
            "respiratory_rate_bpm":      118,
            "ambient_temp_C":            18.0,
        },
    },
    {
        "label":       "4. Heat stress compound (asymmetry + thermal load)",
        "description": "Subclinical asymmetry compounded by high ambient temp and humidity.",
        "readings": {
            "stride_duration_s":         0.50,
            "stride_length_m":           5.90,
            "speed_m_s":                 13.2,
            "forelimb_vertical_acc_LF":  21.0,
            "forelimb_vertical_acc_RF":  23.8,
            "hindlimb_vertical_acc_LH":  17.9,
            "hindlimb_vertical_acc_RH":  18.1,
            "stance_duration_LF_s":      0.190,
            "stance_duration_RF_s":      0.205,
            "heart_rate_bpm":            192,
            "core_temp_C":               40.1,   # approaching hyperthermia
            "spo2_pct":                  96.2,
            "respiratory_rate_bpm":      126,
            "cortisol_nmol_L":           185.0,  # elevated HPA activation
            "ambient_temp_C":            34.0,   # hot day
        },
    },
    {
        "label":       "5. Recovery",
        "description": "Post-intervention: walking, symmetry improving, vitals stabilising.",
        "readings": {
            "stride_duration_s":         0.82,
            "stride_length_m":           1.85,
            "speed_m_s":                 2.4,
            "forelimb_vertical_acc_LF":  9.8,
            "forelimb_vertical_acc_RF":  10.1,
            "hindlimb_vertical_acc_LH":  8.2,
            "hindlimb_vertical_acc_RH":  8.0,
            "stance_duration_LF_s":      0.420,
            "stance_duration_RF_s":      0.425,
            "heart_rate_bpm":            58,
            "core_temp_C":               38.5,
            "spo2_pct":                  98.5,
            "respiratory_rate_bpm":      14,
            "ambient_temp_C":            18.0,
        },
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Run scenarios and print results
# ─────────────────────────────────────────────────────────────────────────────

COL = {
    "red":    "\033[91m",
    "yellow": "\033[93m",
    "green":  "\033[92m",
    "cyan":   "\033[96m",
    "bold":   "\033[1m",
    "reset":  "\033[0m",
}

def grade_color(grade):
    return {
        "low":      COL["green"],
        "moderate": COL["cyan"],
        "elevated": COL["yellow"],
        "critical": COL["red"],
    }.get(grade, "")

def si_color(si):
    if si is None: return ""
    if si >= 0.97: return COL["green"]
    if si >= 0.93: return COL["yellow"]
    return COL["red"]

for scenario in scenarios:
    alarm_log.clear()
    state = ds.update_sync(scenario["readings"])

    print(f"\n{'─'*78}")
    print(f"  {COL['bold']}{scenario['label']}{COL['reset']}")
    print(f"  {scenario['description']}")
    print(f"{'─'*78}")

    # ── Kinematics ──────────────────────────────────────────────────────────
    print(f"\n  STRIDE KINEMATICS")
    sf  = state.get("stride_frequency_Hz")
    sv  = state.get("stride_velocity_m_s")
    sl  = state.get("stride_length_m")
    sd  = state.get("stride_duration_s")
    print(f"    Stride duration   : {sd:.3f} s" if sd else "    Stride duration   : —")
    print(f"    Stride length     : {sl:.2f} m" if sl else "    Stride length     : —")
    print(f"    Stride frequency  : {sf:.3f} Hz" if sf else "    Stride frequency  : —")
    print(f"    Velocity          : {sv:.2f} m/s  ({sv*3.6:.1f} km/h)" if sv else "    Velocity          : —")

    # ── Symmetry ────────────────────────────────────────────────────────────
    print(f"\n  GAIT SYMMETRY")
    si_fore = state.get("forelimb_symmetry_index")
    si_hind = state.get("hindlimb_symmetry_index")
    si_comp = state.get("stride_symmetry_index")
    lla     = state.get("limb_loading_asymmetry")
    sda     = state.get("stance_duration_asymmetry_s")
    lame    = state.get("lame_limb_side", "none")
    sub_dev = state.get("subclinical_deviation_flag", False)
    lame_fl = state.get("lameness_detection_flag", False)

    if si_fore is not None:
        c = si_color(si_fore)
        print(f"    Forelimb SI       : {c}{si_fore:.4f}{COL['reset']}")
    if si_hind is not None:
        c = si_color(si_hind)
        print(f"    Hindlimb SI       : {c}{si_hind:.4f}{COL['reset']}")
    if si_comp is not None:
        c = si_color(si_comp)
        print(f"    Composite SI      : {c}{si_comp:.4f}{COL['reset']}  (≥0.97 normal | <0.97 subclinical | <0.93 lame)")
    if lla is not None:
        print(f"    Loading asymmetry : {lla:.2f}%")
    if sda is not None:
        print(f"    Stance asym (LF-RF): {sda*1000:.1f} ms")
    if sub_dev:
        print(f"    {COL['yellow']}⚠  Subclinical deviation detected{COL['reset']}")
    if lame_fl:
        print(f"    {COL['red']}⛔  Clinical lameness threshold breached{COL['reset']}")
    if lame != "none":
        print(f"    Suspected limb    : {COL['yellow']}{lame}{COL['reset']}")

    # ── Injury Risk ──────────────────────────────────────────────────────────
    print(f"\n  INJURY RISK")
    grf  = state.get("peak_grf_proxy_N_kg")
    tsp  = state.get("tendon_strain_proxy")
    iri  = state.get("injury_risk_index")
    grad = state.get("injury_risk_grade", "—")
    gc   = grade_color(grad)

    if grf  is not None: print(f"    Peak GRF proxy    : {grf:.2f} N/kg")
    if tsp  is not None: print(f"    Tendon strain     : {tsp:.4f}  (safe <0.50 | elevated 0.50-0.75 | critical >0.75)")
    if iri  is not None: print(f"    Injury risk index : {gc}{iri:.4f}{COL['reset']}")
    print(f"    Risk grade        : {gc}{grad.upper()}{COL['reset']}")

    # ── Physiology (DigitalSoma built-ins) ───────────────────────────────────
    print(f"\n  PHYSIOLOGY (DigitalSoma solvers)")
    co   = state.get("cardiac_output_L_min")
    rmr  = state.get("rmr_W")
    tci  = state.get("thermal_comfort_index")
    psi  = state.get("physiological_stress_index")
    ae   = state.get("adverse_event_score", 0.0)
    flags = [f["veddra_term"] for f in state.get("ae_flags", [])]
    if co  is not None: print(f"    Cardiac output    : {co:.2f} L/min")
    if rmr is not None: print(f"    RMR               : {rmr:.1f} W")
    if tci is not None: print(f"    Thermal comfort   : {tci:.3f}")
    if psi is not None: print(f"    Stress index      : {psi:.3f}")
    print(f"    AE score (VeDDRA) : {ae:.3f}" + (f"  → {', '.join(flags)}" if flags else ""))

    # ── Alarms ───────────────────────────────────────────────────────────────
    if alarm_log:
        print(f"\n  ALARMS FIRED")
        for a in alarm_log:
            print(a)
    else:
        print(f"\n  {COL['green']}No alarms{COL['reset']}")

# ─────────────────────────────────────────────────────────────────────────────
# Summary table
# ─────────────────────────────────────────────────────────────────────────────

print(f"\n\n{'═'*78}")
print(f"  SCENARIO SUMMARY")
print(f"{'═'*78}")
print(f"  {'Scenario':<35} {'SI':>6}  {'IRI':>6}  {'Grade':<10}  {'Lame limb'}")
print(f"  {'─'*35} {'─'*6}  {'─'*6}  {'─'*10}  {'─'*12}")

alarm_log.clear()
# Re-run all scenarios cleanly for summary
summary_ds = build_soma(SomaConfig(animal_type="equine_adult"))
register_gait_pipeline(summary_ds)

for s in scenarios:
    st = summary_ds.update_sync(s["readings"])
    si   = st.get("stride_symmetry_index")
    iri  = st.get("injury_risk_index")
    grad = st.get("injury_risk_grade", "—")
    lame = st.get("lame_limb_side", "none")
    si_s  = f"{si:.4f}" if si is not None else "  —  "
    iri_s = f"{iri:.4f}" if iri is not None else "  —  "
    gc = grade_color(grad)
    print(f"  {s['label'][:35]:<35} {si_s:>6}  {iri_s:>6}  {gc}{grad:<10}{COL['reset']}  {lame}")

print(f"\n{'═'*78}")
print(f"  Pipeline: DigitalSoma v1.0 (6 built-in solvers) + EquiTwin Gait (3 solvers)")
print(f"  Total:    9 solvers · 15 new canonical properties · 4 new TES alarms")
print(f"{'═'*78}\n")
