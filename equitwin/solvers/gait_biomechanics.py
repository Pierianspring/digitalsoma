"""
equitwin/solvers/gait_biomechanics.py
===============================================================================
EquiTwin — Biomechanical / Gait / Stride Analysis Pipeline
===============================================================================

Three composable solvers registered into DigitalSoma via register_method().
They form a strict DAG: each solver consumes outputs of the one before it.

    DAG order (after DigitalSoma built-ins):
    ─────────────────────────────────────────
    [7]  equine_stride_kinematics
            ↓  stride_length_m, stride_frequency_hz, swing/stance times,
               vertical_displacement_m
    [8]  equine_gait_symmetry
            ↓  stride_symmetry_index, limb_loading_asymmetry,
               diagonal_advanced_placement, subclinical_lameness_flag
    [9]  equine_injury_risk
            ↓  injury_risk_index, risk_category, pre_pathological_flag,
               recommended_action

Inputs consumed from DigitalSoma built-ins (must run first):
    cardiovascular_baseline  → cardiac_output_L_min
    metabolic_rate           → rmr_W
    neuroendocrine_stress    → physiological_stress_index

Sensor inputs expected in state (via update_sync / EnergyTag manifest):
    acceleration_m_s2        IMU vertical acceleration (dorsal-ventral axis)
    acceleration_lateral_m_s2  IMU lateral (mediolateral) acceleration
    acceleration_fore_m_s2   IMU fore-aft (craniocaudal) acceleration
    limb_lf_load_pct         Left forelimb load (% of total; 0-100)
    limb_rf_load_pct         Right forelimb load
    limb_lh_load_pct         Left hindlimb load
    limb_rh_load_pct         Right hindlimb load
    speed_m_s                Current speed (GPS or radar)
    strike_interval_s        Time between consecutive hoof strikes (stride sensor)
    stance_time_lf_s         Left forelimb stance duration (force plate or IMU)
    stance_time_rf_s         Right forelimb stance duration
    stance_time_lh_s         Left hindlimb stance duration
    stance_time_rh_s         Right hindlimb stance duration

References
----------
Pfau T. et al. (2012) Assessment of symmetry of whole body and head movement
    in horses trotting in a straight line. Equine Vet J 44(5):571-576.
Weishaupt M.A. et al. (2010) Vertical ground reaction forces and fore/hind limb
    load sharing in horses at walk. Equine Vet J 42(Suppl 38):74-77.
Maliye S. & Marshall J.F. (2016) Objective assessment of over-ground
    locomotion in horses. Vet J 211:67-74.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# Species reference constants (equine_adult, Equus caballus)
# ────────────────────────────────────────────────────────────────────────────

EQUINE_REF = {
    # Symmetry indices: perfect symmetry = 1.0
    # Source: Pfau et al. (2012) — healthy horses trotting
    "stride_symmetry_index_min":   0.95,   # below this = subclinical asymmetry
    "stride_symmetry_index_alert": 0.90,   # below this = clinical asymmetry
    "limb_load_asymmetry_max":     0.06,   # >6% difference = significant (Weishaupt 2010)
    "limb_load_asymmetry_alert":   0.10,   # >10% = high risk

    # Stride kinematics: walk / trot / canter / gallop
    # stride_length_m = distance from hoof strike to next strike of same limb
    "stride_length_normal_m": {
        "walk":   1.5,   # 1.3 – 1.8 m
        "trot":   2.8,   # 2.5 – 3.2 m
        "canter": 3.5,   # 3.0 – 4.2 m
        "gallop": 5.5,   # 5.0 – 7.0 m (race-pace Thoroughbred)
    },
    "stride_freq_normal_hz": {
        "walk":   0.90,  # 0.8 – 1.0 Hz
        "trot":   1.45,  # 1.3 – 1.6 Hz
        "canter": 1.80,  # 1.6 – 2.0 Hz
        "gallop": 2.30,  # 2.0 – 2.6 Hz
    },

    # Stance time: forelimbs bear ~60% of total load at trot
    "forelimb_load_fraction_normal": 0.60,   # 58-62% is normal range
    "stance_time_symmetry_min":      0.94,   # below this = stance asymmetry

    # Vertical displacement of withers per stride (dorsal-ventral IMU)
    "vertical_displacement_normal_m": {
        "walk":   0.04,
        "trot":   0.06,
        "canter": 0.10,
        "gallop": 0.14,
    },

    # DAP: Diagonal Advanced Placement (ms) — negative = DALS (broken back)
    # Source: Witte et al. (2004)
    "dap_normal_range_ms": (-30, 30),       # ±30 ms normal; outside = compensation
}


def _classify_gait(speed_m_s: float) -> str:
    """Classify gait from speed. Thresholds from equine locomotion literature."""
    if speed_m_s < 2.0:
        return "walk"
    elif speed_m_s < 5.0:
        return "trot"
    elif speed_m_s < 9.0:
        return "canter"
    else:
        return "gallop"


# ────────────────────────────────────────────────────────────────────────────
# Solver 7: equine_stride_kinematics
# ────────────────────────────────────────────────────────────────────────────

def solver_equine_stride_kinematics(params: Dict[str, Any],
                                    state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Derive stride kinematics from accelerometer and timing sensor data.

    Inputs consumed
    ───────────────
    acceleration_m_s2          Dorsal-ventral (vertical) IMU acceleration (g or m/s²)
    acceleration_lateral_m_s2  Mediolateral IMU acceleration
    acceleration_fore_m_s2     Fore-aft IMU acceleration
    strike_interval_s          Time between consecutive hoof strikes
    speed_m_s                  Current GPS/radar speed
    body_mass_kg               From structural layer (params)

    Outputs produced
    ────────────────
    gait_classification        walk | trot | canter | gallop
    stride_frequency_hz        Strides per second
    stride_length_m            Distance covered per complete stride
    stride_duration_s          Time for one complete stride
    vertical_displacement_m    Estimated withers vertical excursion per stride
    stride_length_deviation    Deviation from species normal (positive = longer)
    stride_freq_deviation       Deviation from species normal (positive = faster)
    resultant_acceleration_m_s2 Combined IMU vector magnitude
    """
    speed      = state.get("speed_m_s")
    strike_int = state.get("strike_interval_s")
    acc_v      = state.get("acceleration_m_s2",         0.0)
    acc_l      = state.get("acceleration_lateral_m_s2", 0.0)
    acc_f      = state.get("acceleration_fore_m_s2",    0.0)
    mass_kg    = params.get("body_mass_kg", state.get("body_mass_kg", 500.0))

    result: Dict[str, Any] = {}

    # ── Gait classification ──
    gait = _classify_gait(speed) if speed is not None else "unknown"
    result["gait_classification"] = gait

    # ── Stride frequency and duration ──
    if strike_int is not None and strike_int > 0:
        stride_freq_hz   = 1.0 / strike_int
        stride_duration_s = strike_int
        result["stride_frequency_hz"]  = round(stride_freq_hz, 3)
        result["stride_duration_s"]    = round(stride_duration_s, 3)

        # ── Stride length ──
        if speed is not None and speed > 0:
            stride_length_m = speed / stride_freq_hz
            result["stride_length_m"] = round(stride_length_m, 3)

            # Deviation from species normal for this gait
            if gait in EQUINE_REF["stride_length_normal_m"]:
                normal_len = EQUINE_REF["stride_length_normal_m"][gait]
                result["stride_length_deviation"] = round(
                    (stride_length_m - normal_len) / normal_len, 4)

        # Frequency deviation
        if gait in EQUINE_REF["stride_freq_normal_hz"]:
            normal_freq = EQUINE_REF["stride_freq_normal_hz"][gait]
            result["stride_freq_deviation"] = round(
                (stride_freq_hz - normal_freq) / normal_freq, 4)

    # ── Vertical displacement from IMU ──
    # Double-integration of vertical acceleration over stance phase.
    # Simplified: amplitude estimate from peak acceleration and stride duration.
    if strike_int is not None and acc_v is not None:
        # Vertical displacement ≈ a × t² / (4π²) for sinusoidal motion
        stride_dur = strike_int
        vert_disp_m = abs(acc_v) * (stride_dur ** 2) / (4 * math.pi ** 2)
        vert_disp_m = min(vert_disp_m, 0.30)   # physiological cap
        result["vertical_displacement_m"] = round(vert_disp_m, 4)

        if gait in EQUINE_REF["vertical_displacement_normal_m"]:
            normal_vd = EQUINE_REF["vertical_displacement_normal_m"][gait]
            result["vertical_displacement_deviation"] = round(
                (vert_disp_m - normal_vd) / normal_vd, 4)

    # ── Resultant acceleration magnitude ──
    resultant = math.sqrt(acc_v**2 + acc_l**2 + acc_f**2)
    result["resultant_acceleration_m_s2"] = round(resultant, 4)

    logger.debug("stride_kinematics: gait=%s freq=%.3f Hz length=%.3f m",
                 gait,
                 result.get("stride_frequency_hz", 0),
                 result.get("stride_length_m", 0))
    return result


# ────────────────────────────────────────────────────────────────────────────
# Solver 8: equine_gait_symmetry
# ────────────────────────────────────────────────────────────────────────────

def solver_equine_gait_symmetry(params: Dict[str, Any],
                                 state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute bilateral symmetry indices from limb load and stance time data.

    This is the core of EquiTwin's pre-pathological detection capability.
    A stride_symmetry_index < 0.95 indicates subclinical asymmetry invisible
    to the human eye but detectable by continuous sensor monitoring.

    Inputs consumed
    ───────────────
    From state (sensor readings):
        limb_lf_load_pct, limb_rf_load_pct    Forelimb load fractions
        limb_lh_load_pct, limb_rh_load_pct    Hindlimb load fractions
        stance_time_lf_s, stance_time_rf_s    Forelimb stance durations
        stance_time_lh_s, stance_time_rh_s    Hindlimb stance durations
        stride_duration_s                      From solver_equine_stride_kinematics
        acceleration_lateral_m_s2             Mediolateral head movement proxy

    Outputs produced
    ────────────────
    stride_symmetry_index       1.0 = perfect; <0.95 = subclinical; <0.90 = clinical
    forelimb_load_symmetry      1.0 = equal load LF/RF
    hindlimb_load_symmetry      1.0 = equal load LH/RH
    limb_loading_asymmetry      Max absolute load imbalance across all limbs (fraction)
    forelimb_load_fraction      % of total load on forelimbs (normal ~60%)
    stance_time_symmetry        Symmetry of LF vs RF stance duration
    diagonal_advanced_placement_ms  DAP: LF-RH vs RF-LH diagonal timing (ms)
    subclinical_lameness_flag   True if SSI < 0.95
    lame_limb_suspect           "LF"|"RF"|"LH"|"RH"|"bilateral"|None
    """
    result: Dict[str, Any] = {}

    # ── Limb load fractions ──
    lf = state.get("limb_lf_load_pct")
    rf = state.get("limb_rf_load_pct")
    lh = state.get("limb_lh_load_pct")
    rh = state.get("limb_rh_load_pct")

    loads_available = all(v is not None for v in [lf, rf, lh, rh])

    if loads_available:
        total = lf + rf + lh + rh
        if total > 0:
            # Normalise to fractions
            lf_f = lf / total
            rf_f = rf / total
            lh_f = lh / total
            rh_f = rh / total

            # Forelimb load fraction (normal ~0.60)
            fl_fraction = lf_f + rf_f
            result["forelimb_load_fraction"] = round(fl_fraction, 4)

            # Bilateral symmetry: 1 - (|L-R| / (L+R))
            fl_sym = 1.0 - abs(lf_f - rf_f) / max(lf_f + rf_f, 1e-6)
            hl_sym = 1.0 - abs(lh_f - rh_f) / max(lh_f + rh_f, 1e-6)
            result["forelimb_load_symmetry"] = round(fl_sym, 4)
            result["hindlimb_load_symmetry"] = round(hl_sym, 4)

            # Overall limb loading asymmetry (max imbalance)
            limb_dict = {"LF": lf_f, "RF": rf_f, "LH": lh_f, "RH": rh_f}
            max_load   = max(limb_dict.values())
            min_load   = min(limb_dict.values())
            asym = (max_load - min_load) / max(max_load, 1e-6)
            result["limb_loading_asymmetry"] = round(asym, 4)

            # Suspect lame limb: the limb with unusually LOW load bears less
            # (horse avoids loading painful limb)
            ALERT = EQUINE_REF["limb_load_asymmetry_alert"]
            if asym > ALERT:
                min_limb = min(limb_dict, key=limb_dict.get)
                result["lame_limb_suspect"] = min_limb
            else:
                result["lame_limb_suspect"] = None

    # ── Stance time symmetry ──
    st_lf = state.get("stance_time_lf_s")
    st_rf = state.get("stance_time_rf_s")
    st_lh = state.get("stance_time_lh_s")
    st_rh = state.get("stance_time_rh_s")

    if st_lf is not None and st_rf is not None and st_lf > 0 and st_rf > 0:
        st_sym = 1.0 - abs(st_lf - st_rf) / max(st_lf + st_rf, 1e-6)
        result["stance_time_symmetry"] = round(st_sym, 4)

        # DAP: diagonal advanced placement
        # Positive DAP: LF strikes before RH (DALS — diagonal at left side)
        # Normal range: ±30 ms
        if st_lh is not None and st_rh is not None:
            dap_lf_rh = (st_lf - st_rh) * 1000.0   # convert to ms
            dap_rf_lh = (st_rf - st_lh) * 1000.0
            dap_mean_ms = (dap_lf_rh + dap_rf_lh) / 2.0
            result["diagonal_advanced_placement_ms"] = round(dap_mean_ms, 1)

    # ── Composite stride symmetry index (SSI) ──
    # Combines forelimb load symmetry, hindlimb load symmetry, and stance time
    # symmetry into a single 0–1 index (1.0 = perfect symmetry).
    components = []
    if "forelimb_load_symmetry" in result:
        components.append(result["forelimb_load_symmetry"])
    if "hindlimb_load_symmetry" in result:
        components.append(result["hindlimb_load_symmetry"])
    if "stance_time_symmetry" in result:
        components.append(result["stance_time_symmetry"])

    # Lateral acceleration: head displacement is a validated lameness proxy
    acc_l = state.get("acceleration_lateral_m_s2")
    if acc_l is not None:
        # Normalise: >0.5 m/s² lateral head movement = significant asymmetry
        lateral_sym = max(0.0, 1.0 - abs(acc_l) / 0.5)
        components.append(lateral_sym)

    if components:
        ssi = sum(components) / len(components)
        result["stride_symmetry_index"] = round(ssi, 4)

        # Subclinical lameness flag
        subclinical_thresh = EQUINE_REF["stride_symmetry_index_min"]
        clinical_thresh    = EQUINE_REF["stride_symmetry_index_alert"]
        result["subclinical_lameness_flag"] = ssi < subclinical_thresh

        if ssi < clinical_thresh:
            result["symmetry_status"] = "clinical_asymmetry"
        elif ssi < subclinical_thresh:
            result["symmetry_status"] = "subclinical_asymmetry"
        else:
            result["symmetry_status"] = "normal"

    logger.debug("gait_symmetry: SSI=%.4f status=%s lame_suspect=%s",
                 result.get("stride_symmetry_index", 0),
                 result.get("symmetry_status", "unknown"),
                 result.get("lame_limb_suspect"))
    return result


# ────────────────────────────────────────────────────────────────────────────
# Solver 9: equine_injury_risk
# ────────────────────────────────────────────────────────────────────────────

def solver_equine_injury_risk(params: Dict[str, Any],
                               state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Composite injury risk index synthesising gait symmetry, physiological
    stress, and fatigue state.

    This is EquiTwin's pre-pathological detection output — the "early warning
    system that predicts risk thresholds, allowing for preventative
    intervention before a minor strain becomes a catastrophic failure."

    Inputs consumed
    ───────────────
    From solver_equine_gait_symmetry:
        stride_symmetry_index, limb_loading_asymmetry
        subclinical_lameness_flag, lame_limb_suspect
    From DigitalSoma built-ins:
        physiological_stress_index   (neuroendocrine_stress)
        thermal_comfort_index        (thermoregulation)
        rmr_W                        (metabolic_rate)
    From solver_equine_stride_kinematics:
        stride_length_deviation, vertical_displacement_deviation

    Outputs produced
    ────────────────
    injury_risk_index       Composite 0.0–1.0 (0=safe, 1=critical)
    risk_category           "low" | "moderate" | "elevated" | "high" | "critical"
    pre_pathological_flag   True if risk detected before clinical symptoms
    risk_contributors       Dict of individual component scores
    recommended_action      Human-readable intervention recommendation
    """
    result: Dict[str, Any] = {}

    # ── Component 1: Gait symmetry risk ──
    ssi = state.get("stride_symmetry_index", 1.0)
    # Map SSI (1.0=perfect) to risk (0.0=safe, 1.0=critical)
    # SSI 1.0 → risk 0.0; SSI 0.90 → risk 1.0 (linear mapping)
    sym_risk = max(0.0, min(1.0, (1.0 - ssi) / 0.10))

    # ── Component 2: Limb loading asymmetry risk ──
    load_asym = state.get("limb_loading_asymmetry", 0.0)
    # 0% asym → risk 0.0; ≥10% asym → risk 1.0
    load_risk = max(0.0, min(1.0, load_asym / 0.10))

    # ── Component 3: Physiological stress risk ──
    psi = state.get("physiological_stress_index", 0.0)
    # Already 0–1; weight at 0.6 (partial contributor)
    stress_risk = psi * 0.6

    # ── Component 4: Thermal / fatigue risk ──
    tci = state.get("thermal_comfort_index", 0.0)
    # TCI > 0.15 = heat stress; > 0.35 = severe
    thermal_risk = max(0.0, min(1.0, abs(tci) / 0.35))

    # ── Component 5: Stride length deviation ──
    sl_dev = abs(state.get("stride_length_deviation", 0.0))
    # >15% deviation from normal = significant risk
    stride_risk = max(0.0, min(1.0, sl_dev / 0.15))

    # ── Weighted composite ──
    # Symmetry and load asymmetry are primary indicators; others modulate
    weights = {
        "gait_symmetry":        0.35,
        "limb_load_asymmetry":  0.30,
        "physiological_stress": 0.15,
        "thermal_fatigue":      0.10,
        "stride_deviation":     0.10,
    }
    components = {
        "gait_symmetry":        round(sym_risk, 4),
        "limb_load_asymmetry":  round(load_risk, 4),
        "physiological_stress": round(stress_risk, 4),
        "thermal_fatigue":      round(thermal_risk, 4),
        "stride_deviation":     round(stride_risk, 4),
    }
    injury_risk = sum(
        components[k] * weights[k] for k in weights
    )
    injury_risk = round(min(injury_risk, 1.0), 4)

    result["injury_risk_index"]  = injury_risk
    result["risk_contributors"]  = components

    # ── Risk category ──
    if injury_risk < 0.20:
        cat = "low"
    elif injury_risk < 0.40:
        cat = "moderate"
    elif injury_risk < 0.60:
        cat = "elevated"
    elif injury_risk < 0.80:
        cat = "high"
    else:
        cat = "critical"
    result["risk_category"] = cat

    # ── Pre-pathological flag ──
    # Fires when risk is detectable before clinical symptoms are visible
    subclinical = state.get("subclinical_lameness_flag", False)
    pre_path = subclinical or (injury_risk >= 0.40 and ssi >= 0.90)
    result["pre_pathological_flag"] = bool(pre_path)

    # ── Recommended action ──
    lame_limb = state.get("lame_limb_suspect")
    limb_str = f" (suspect: {lame_limb})" if lame_limb else ""

    if cat == "low":
        action = "Continue normal training programme. Monitor trends."
    elif cat == "moderate":
        action = (f"Reduce training intensity by 20%. Schedule veterinary"
                  f" inspection within 48 h{limb_str}.")
    elif cat == "elevated":
        action = (f"Halt high-intensity work. Veterinary inspection required"
                  f" within 24 h{limb_str}. Apply targeted physiotherapy.")
    elif cat == "high":
        action = (f"Immediate rest. Veterinary inspection today{limb_str}."
                  f" Diagnostic imaging recommended.")
    else:  # critical
        action = (f"STOP immediately. Emergency veterinary assessment required"
                  f"{limb_str}. Do not continue exercise.")

    result["recommended_action"] = action

    logger.info("injury_risk: index=%.4f category=%s pre_path=%s limb=%s",
                injury_risk, cat, pre_path, lame_limb)
    return result


# ────────────────────────────────────────────────────────────────────────────
# TES alarm additions for gait-specific thresholds
# ────────────────────────────────────────────────────────────────────────────

GAIT_TES_ALARMS = {
    "stride_symmetry_index": {
        "low":   EQUINE_REF["stride_symmetry_index_alert"],   # 0.90
        "high":  None,
        "label": "clinical_gait_asymmetry",
    },
    "limb_loading_asymmetry": {
        "low":   None,
        "high":  EQUINE_REF["limb_load_asymmetry_alert"],     # 0.10
        "label": "limb_load_imbalance",
    },
    "injury_risk_index": {
        "low":   None,
        "high":  0.60,
        "label": "elevated_injury_risk",
    },
}


# ────────────────────────────────────────────────────────────────────────────
# Convenience registration function
# ────────────────────────────────────────────────────────────────────────────

def register_gait_pipeline(ds) -> None:
    """
    Register all three gait solvers into an existing DigitalSoma twin
    and extend the Threshold Event System with gait-specific alarms.

    Parameters
    ----------
    ds : DigitalSoma
        A fully built twin (build_soma() already called).

    Usage
    -----
    >>> from digitalsoma import build_soma, SomaConfig
    >>> from equitwin.solvers.gait_biomechanics import register_gait_pipeline
    >>> ds = build_soma(SomaConfig(animal_type="equine_adult"))
    >>> register_gait_pipeline(ds)
    >>> print(ds.solvers)   # 9 solvers including all three gait solvers
    """
    ds.register_method("equine_stride_kinematics", solver_equine_stride_kinematics)
    ds.register_method("equine_gait_symmetry",     solver_equine_gait_symmetry)
    ds.register_method("equine_injury_risk",       solver_equine_injury_risk)

    # Add gait-specific TES alarms
    ds._tes._thresholds.update(GAIT_TES_ALARMS)

    logger.info(
        "EquiTwin gait pipeline registered: 3 solvers + %d TES alarms",
        len(GAIT_TES_ALARMS)
    )
