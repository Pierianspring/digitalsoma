"""
equitwin/gait_biomechanics.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EquiTwin — Biomechanical / Gait / Stride Analysis Pipeline
Phase 1: HorseTwin gait extension module

Registers three new solvers into the DigitalSoma Model Zoo via
register_method() — zero changes to the DigitalSoma core required.

Three solvers in DAG order:
  1. equine_stride_kinematics    — stride length, frequency, velocity
  2. equine_gait_symmetry        — symmetry indices, subclinical deviation
  3. equine_injury_risk           — GRF proxy, tendon strain, injury risk index

Also registers six new canonical vocabulary properties via register_property()
so gait outputs are fully ontology-anchored in JSON-LD export.

Adds four TES alarms for subclinical and clinical gait events.

References
──────────
Buchner H.H.F. et al. (1996). Bilateral lameness in horses — a kinematic study.
  Veterinary Quarterly 18(4), 138-141.
Keegan K.G. (2007). Evidence-based lameness detection and quantification.
  Veterinary Clinics: Equine Practice 23(2), 341-357.
Weishaupt M.A. et al. (2006). Instrumented treadmill for measuring vertical
  ground reaction forces in horses. Veterinary Journal 171(2), 271-276.
Ross M.W. & Dyson S.J. (Eds.) (2010). Diagnosis and Management of Lameness
  in the Horse. Saunders Elsevier.

Usage
──────────
    from digitalsoma import build_soma, SomaConfig
    from equitwin.gait_biomechanics import register_gait_pipeline, GAIT_ALARMS

    ds = build_soma(SomaConfig(animal_type="equine_adult", site_name="Track A"))
    register_gait_pipeline(ds)

    # Register subclinical alarm handler
    def on_gait_alarm(key, value, label):
        print(f"[GAIT ALARM]  {label}  |  {key} = {value:.4f}")
    ds._tes.register_handler(on_gait_alarm)

    # Push a raw sensor reading dict
    state = ds.update_sync({
        "stride_duration_s":        0.48,
        "stride_length_m":          2.85,
        "forelimb_vertical_acc_LF": 12.4,
        "forelimb_vertical_acc_RF": 13.8,
        "hindlimb_vertical_acc_LH": 9.1,
        "hindlimb_vertical_acc_RH": 9.0,
        "stance_duration_LF_s":     0.195,
        "stance_duration_RF_s":     0.210,
        "speed_m_s":                14.2,
        "heart_rate_bpm":           185,
        "core_temp_C":              38.9,
    })

    print(f"Stride symmetry index : {state['stride_symmetry_index']:.4f}")
    print(f"Lameness detection    : {state['lameness_detection_flag']}")
    print(f"Tendon strain proxy   : {state['tendon_strain_proxy']:.4f}")
    print(f"Injury risk index     : {state['injury_risk_index']:.4f}")
    print(f"Subclinical deviation : {state['subclinical_deviation_flag']}")
"""

from __future__ import annotations

import math
import logging
from typing import Any, Dict, List

from digitalsoma.ontology.vocab import OntologyProperty, register_property

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# 1.  VOCABULARY EXTENSION
#     Six new canonical properties registered into the shared ontology layer.
#     Uses SNOMED, Uberon, and local EquiTwin URIs where no standard term exists.
# ─────────────────────────────────────────────────────────────────────────────

_GAIT_PROPERTIES: List[OntologyProperty] = [

    OntologyProperty(
        canonical   = "stride_duration_s",
        uri         = "http://purl.obolibrary.org/obo/NCIT_C68783",  # Stride duration
        unit        = "s",
        aliases     = ["stride_dur", "StrideDuration", "T_stride", "t_stride"],
        description = "Duration of one complete stride cycle (ipsilateral hoof strike to next) in seconds",
    ),
    OntologyProperty(
        canonical   = "stride_length_m",
        uri         = "http://purl.obolibrary.org/obo/NCIT_C68784",  # Stride length
        unit        = "m",
        aliases     = ["stride_len", "StrideLength", "SL", "sl_m"],
        description = "Distance covered in one complete stride cycle in metres",
    ),
    OntologyProperty(
        canonical   = "stride_frequency_Hz",
        uri         = "http://purl.obolibrary.org/obo/NCIT_C68785",
        unit        = "Hz",
        aliases     = ["stride_freq", "StrideFreq", "cadence_Hz", "SF"],
        description = "Stride frequency in cycles per second (strides per second)",
    ),
    OntologyProperty(
        canonical   = "stride_velocity_m_s",
        uri         = "http://snomed.info/id/364566003",
        unit        = "m/s",
        aliases     = ["speed_m_s", "velocity", "v_m_s", "Speed", "horse_speed"],
        description = "Estimated or measured locomotion velocity in metres per second",
    ),
    OntologyProperty(
        canonical   = "stride_symmetry_index",
        uri         = "http://purl.obolibrary.org/obo/EQUITWIN_0000001",
        unit        = "1",
        aliases     = ["SSI", "ssi", "symmetry_index", "StrideSymmetry"],
        description = (
            "Bilateral stride symmetry index (0–1). "
            "1.0 = perfect symmetry. "
            "<0.97 = subclinical asymmetry. "
            "<0.93 = clinical lameness threshold."
        ),
    ),
    OntologyProperty(
        canonical   = "limb_loading_asymmetry",
        uri         = "http://purl.obolibrary.org/obo/EQUITWIN_0000002",
        unit        = "%",
        aliases     = ["LLA", "lla", "load_asymmetry", "LimbAsymmetry"],
        description = "Percentage difference in vertical peak acceleration between left and right limb pairs",
    ),
    OntologyProperty(
        canonical   = "stance_duration_asymmetry_s",
        uri         = "http://purl.obolibrary.org/obo/EQUITWIN_0000003",
        unit        = "s",
        aliases     = ["SDA", "sda", "stance_asym"],
        description = "Absolute difference in stance phase duration between left and right forelimbs (seconds)",
    ),
    OntologyProperty(
        canonical   = "peak_grf_proxy_N_kg",
        uri         = "http://purl.obolibrary.org/obo/EQUITWIN_0000004",
        unit        = "N/kg",
        aliases     = ["GRF_proxy", "grf_proxy", "peak_grf"],
        description = "Estimated peak vertical Ground Reaction Force per kg body mass derived from peak acceleration",
    ),
    OntologyProperty(
        canonical   = "tendon_strain_proxy",
        uri         = "http://purl.obolibrary.org/obo/EQUITWIN_0000005",
        unit        = "1",
        aliases     = ["tendon_strain", "TendonStrain", "TSP", "tsp"],
        description = (
            "Dimensionless tendon strain proxy (0–1) computed from GRF proxy, "
            "speed, and surface hardness. "
            "Safe zone < 0.5. Elevated risk 0.5–0.75. Critical > 0.75."
        ),
    ),
    OntologyProperty(
        canonical   = "injury_risk_index",
        uri         = "http://purl.obolibrary.org/obo/EQUITWIN_0000006",
        unit        = "1",
        aliases     = ["IRI", "iri", "injury_risk", "InjuryRisk"],
        description = (
            "Composite injury risk index (0–1) weighting symmetry deficit, "
            "tendon strain proxy, and thermal stress. "
            "Low < 0.25. Moderate 0.25–0.5. High > 0.5. Critical > 0.75."
        ),
    ),
    OntologyProperty(
        canonical   = "forelimb_vertical_acc_LF",
        uri         = "http://purl.obolibrary.org/obo/UBERON_0002103",
        unit        = "m/s2",
        aliases     = ["acc_LF", "LF_acc", "left_fore_acc", "LeftForeAcc"],
        description = "Peak vertical acceleration at left forelimb hoof during stance phase (m/s²)",
    ),
    OntologyProperty(
        canonical   = "forelimb_vertical_acc_RF",
        uri         = "http://purl.obolibrary.org/obo/UBERON_0002103",
        unit        = "m/s2",
        aliases     = ["acc_RF", "RF_acc", "right_fore_acc", "RightForeAcc"],
        description = "Peak vertical acceleration at right forelimb hoof during stance phase (m/s²)",
    ),
    OntologyProperty(
        canonical   = "hindlimb_vertical_acc_LH",
        uri         = "http://purl.obolibrary.org/obo/UBERON_0002104",
        unit        = "m/s2",
        aliases     = ["acc_LH", "LH_acc", "left_hind_acc", "LeftHindAcc"],
        description = "Peak vertical acceleration at left hindlimb hoof during stance phase (m/s²)",
    ),
    OntologyProperty(
        canonical   = "hindlimb_vertical_acc_RH",
        uri         = "http://purl.obolibrary.org/obo/UBERON_0002104",
        unit        = "m/s2",
        aliases     = ["acc_RH", "RH_acc", "right_hind_acc", "RightHindAcc"],
        description = "Peak vertical acceleration at right hindlimb hoof during stance phase (m/s²)",
    ),
    OntologyProperty(
        canonical   = "stance_duration_LF_s",
        uri         = "http://purl.obolibrary.org/obo/EQUITWIN_0000010",
        unit        = "s",
        aliases     = ["stance_LF", "LF_stance", "left_fore_stance"],
        description = "Stance phase duration for left forelimb in seconds",
    ),
    OntologyProperty(
        canonical   = "stance_duration_RF_s",
        uri         = "http://purl.obolibrary.org/obo/EQUITWIN_0000011",
        unit        = "s",
        aliases     = ["stance_RF", "RF_stance", "right_fore_stance"],
        description = "Stance phase duration for right forelimb in seconds",
    ),
]


def register_gait_vocabulary() -> None:
    """Register all gait canonical properties into the DigitalSoma vocabulary."""
    for prop in _GAIT_PROPERTIES:
        register_property(prop)
        logger.info("GaitVocab: registered '%s'", prop.canonical)


# ─────────────────────────────────────────────────────────────────────────────
# 2.  SOLVER 1 — equine_stride_kinematics
#     Computes stride frequency and velocity from raw stride duration and length.
#     Sits first in the gait DAG; provides inputs to solvers 2 and 3.
# ─────────────────────────────────────────────────────────────────────────────

def solver_equine_stride_kinematics(params: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Solver 1 of 3: Stride kinematics.

    Derives stride frequency and locomotion velocity from the two primary
    kinematic measurements: stride duration (s) and stride length (m).

    Inputs consumed from state
    ──────────────────────────
    stride_duration_s   : float  — duration of one complete stride cycle (s)
    stride_length_m     : float  — distance covered per stride (m)
    stride_velocity_m_s : float  — (optional) GPS/radar speed override (m/s)

    Outputs produced
    ──────────────────────────
    stride_frequency_Hz    : float  — strides per second
    stride_velocity_m_s    : float  — locomotion velocity (m/s)

    Physiological reference ranges (Thoroughbred gallop)
    ─────────────────────────────────────────────────────
    stride_duration_s  : 0.42–0.55 s  (walk: 0.8–1.2 s, trot: 0.55–0.75 s)
    stride_length_m    : 5.5–7.5 m    (elite Thoroughbred at race pace)
    stride_frequency_Hz: 2.1–2.4 Hz   (gallop)
    stride_velocity_m_s: 14–18 m/s    (gallop, elite Thoroughbred)
    """
    stride_dur = state.get("stride_duration_s")
    stride_len = state.get("stride_length_m")

    result: Dict[str, Any] = {}

    if stride_dur is not None and stride_dur > 0:
        result["stride_frequency_Hz"] = 1.0 / stride_dur

    # Velocity: prefer GPS/radar if already in state; otherwise compute from
    # stride length × frequency
    if state.get("stride_velocity_m_s") is None:
        if stride_len is not None and stride_dur is not None and stride_dur > 0:
            result["stride_velocity_m_s"] = stride_len / stride_dur
    else:
        # GPS override already in state — keep it, don't overwrite
        pass

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 3.  SOLVER 2 — equine_gait_symmetry
#     Core lameness detection solver.
#     Computes bilateral symmetry indices from forelimb and hindlimb
#     peak vertical accelerations and stance phase durations.
#
#     Scientific basis
#     ─────────────────
#     The Symmetry Index (SI) is the standard metric in equine lameness research
#     (Buchner et al. 1996; Keegan et al. 2007):
#
#         SI_acc = 1 − |acc_L − acc_R| / (0.5 × (acc_L + acc_R))
#
#     SI = 1.0  → perfect symmetry
#     SI < 0.97 → subclinical asymmetry (below human visual detection threshold)
#     SI < 0.93 → clinical lameness threshold
#
#     Stance duration asymmetry independently validates the acceleration-based SI:
#     a lame limb has a shorter stance duration to offload pain.
# ─────────────────────────────────────────────────────────────────────────────

# Clinical thresholds (Keegan 2007; Ross & Dyson 2010)
_SUBCLINICAL_SI_THRESHOLD = 0.97   # below this → pre-pathological alert
_CLINICAL_SI_THRESHOLD    = 0.93   # below this → clinical lameness flag
_STANCE_ASYM_THRESHOLD_S  = 0.020  # >20 ms stance asymmetry → significant


def _symmetry_index(a: float, b: float) -> float:
    """
    Bilateral symmetry index from two non-negative measurements a and b.
    Returns 1.0 if both are zero (undefined but no asymmetry implied).
    """
    mean = 0.5 * (a + b)
    if mean < 1e-9:
        return 1.0
    return 1.0 - abs(a - b) / mean


def solver_equine_gait_symmetry(params: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Solver 2 of 3: Gait symmetry and lameness detection.

    Inputs consumed from state
    ──────────────────────────
    forelimb_vertical_acc_LF   : float  — peak vert. acc left forelimb (m/s²)
    forelimb_vertical_acc_RF   : float  — peak vert. acc right forelimb (m/s²)
    hindlimb_vertical_acc_LH   : float  — peak vert. acc left hindlimb (m/s²)
    hindlimb_vertical_acc_RH   : float  — peak vert. acc right hindlimb (m/s²)
    stance_duration_LF_s       : float  — stance duration left forelimb (s)
    stance_duration_RF_s       : float  — stance duration right forelimb (s)

    Outputs produced
    ──────────────────────────
    forelimb_symmetry_index    : float  — SI for forelimb pair (0–1)
    hindlimb_symmetry_index    : float  — SI for hindlimb pair (0–1)
    stride_symmetry_index      : float  — composite SI (min of fore/hind)
    limb_loading_asymmetry     : float  — % asymmetry of forelimb pair
    stance_duration_asymmetry_s: float  — |LF_stance − RF_stance| in seconds
    subclinical_deviation_flag : bool   — True if SI < subclinical threshold
    lameness_detection_flag    : bool   — True if SI < clinical threshold
    lame_limb_side             : str    — "left_fore" | "right_fore" |
                                          "left_hind" | "right_hind" | "none"
    """
    acc_LF = state.get("forelimb_vertical_acc_LF")
    acc_RF = state.get("forelimb_vertical_acc_RF")
    acc_LH = state.get("hindlimb_vertical_acc_LH")
    acc_RH = state.get("hindlimb_vertical_acc_RH")
    stance_LF = state.get("stance_duration_LF_s")
    stance_RF = state.get("stance_duration_RF_s")

    result: Dict[str, Any] = {}

    # ── Forelimb symmetry ──────────────────────────────────────────────────
    if acc_LF is not None and acc_RF is not None:
        si_fore = _symmetry_index(acc_LF, acc_RF)
        result["forelimb_symmetry_index"] = si_fore

        # Limb loading asymmetry as percentage
        mean_fore = 0.5 * (acc_LF + acc_RF)
        if mean_fore > 1e-9:
            result["limb_loading_asymmetry"] = abs(acc_LF - acc_RF) / mean_fore * 100.0

    # ── Hindlimb symmetry ─────────────────────────────────────────────────
    if acc_LH is not None and acc_RH is not None:
        si_hind = _symmetry_index(acc_LH, acc_RH)
        result["hindlimb_symmetry_index"] = si_hind

    # ── Composite stride symmetry index ───────────────────────────────────
    si_values = [
        result.get("forelimb_symmetry_index"),
        result.get("hindlimb_symmetry_index"),
    ]
    si_values = [v for v in si_values if v is not None]
    if si_values:
        composite_si = min(si_values)   # most asymmetric pair dominates
        result["stride_symmetry_index"] = composite_si

        result["subclinical_deviation_flag"] = composite_si < _SUBCLINICAL_SI_THRESHOLD
        result["lameness_detection_flag"]    = composite_si < _CLINICAL_SI_THRESHOLD

        # ── Lame limb identification ───────────────────────────────────────
        # The lame limb has LOWER peak acceleration (reduced loading = offloading pain)
        lame_limb = "none"
        if composite_si < _SUBCLINICAL_SI_THRESHOLD:
            candidates = []
            if acc_LF is not None and acc_RF is not None:
                if acc_LF < acc_RF:
                    candidates.append(("left_fore",  acc_RF - acc_LF))
                else:
                    candidates.append(("right_fore", acc_LF - acc_RF))
            if acc_LH is not None and acc_RH is not None:
                if acc_LH < acc_RH:
                    candidates.append(("left_hind",  acc_RH - acc_LH))
                else:
                    candidates.append(("right_hind", acc_LH - acc_RH))
            if candidates:
                # Most asymmetric limb pair
                lame_limb = max(candidates, key=lambda x: x[1])[0]
        result["lame_limb_side"] = lame_limb

    # ── Stance duration asymmetry ──────────────────────────────────────────
    if stance_LF is not None and stance_RF is not None:
        sda = abs(stance_LF - stance_RF)
        result["stance_duration_asymmetry_s"] = sda

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 4.  SOLVER 3 — equine_injury_risk
#     Composite injury risk index.
#     Combines:
#       - Gait symmetry deficit (from solver 2)
#       - Tendon strain proxy derived from estimated GRF and speed
#       - Physiological stress component (from DigitalSoma built-in stress solver)
#       - Thermal stress component (from DigitalSoma thermoregulation solver)
#
#     Tendon strain proxy
#     ─────────────────────
#     Peak vertical GRF in horses is ≈ 1.1–1.4 × BW at walk,
#     rising to 2.5–3.5 × BW at trot and 3.0–5.0 × BW at gallop
#     (Weishaupt et al. 2006).
#     We estimate GRF from peak acceleration (Newton's 2nd law):
#         F_peak = m × a_peak   → F_peak/kg = a_peak (N/kg)
#     Normalised against a species-specific safe threshold to give
#     a dimensionless strain proxy (0–1).
# ─────────────────────────────────────────────────────────────────────────────

# GRF reference: safe peak for equine forelimb at working gallop (N/kg body mass)
# Derived from Weishaupt 2006 + safety margin
_GRF_SAFE_PEAK_N_KG   = 35.0   # ~3.5 × BW (N/kg) — working gallop threshold
_GRF_CRITICAL_N_KG    = 50.0   # ~5.0 × BW (N/kg) — elite race / injury risk
_SPEED_GALLOP_M_S     = 12.0   # transition speed (m/s) above which GRF scaling applies
_SURFACE_HARD_DEFAULT = 0.3    # default surface hardness modifier (0=soft, 1=firm)


def solver_equine_injury_risk(params: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Solver 3 of 3: Composite injury risk index.

    Inputs consumed from state
    ──────────────────────────
    forelimb_vertical_acc_LF    : float  — peak left forelimb acc (m/s²)
    forelimb_vertical_acc_RF    : float  — peak right forelimb acc (m/s²)
    stride_symmetry_index       : float  — composite SI from solver 2
    stride_velocity_m_s         : float  — locomotion speed (m/s)
    physiological_stress_index  : float  — HPA stress index from DigitalSoma
    thermal_comfort_index       : float  — TCI from DigitalSoma thermoregulation
    surface_hardness_index      : float  — (optional) 0=soft 1=firm, from TrackTwin

    Outputs produced
    ──────────────────────────
    peak_grf_proxy_N_kg   : float  — estimated peak GRF per kg body mass
    tendon_strain_proxy   : float  — normalised dimensionless tendon strain (0–1)
    injury_risk_index     : float  — composite injury risk (0–1)
    injury_risk_grade     : str    — "low" | "moderate" | "elevated" | "critical"
    """
    result: Dict[str, Any] = {}

    acc_LF  = state.get("forelimb_vertical_acc_LF")
    acc_RF  = state.get("forelimb_vertical_acc_RF")
    si      = state.get("stride_symmetry_index")
    speed   = state.get("stride_velocity_m_s")
    psi     = state.get("physiological_stress_index", 0.0)
    tci     = state.get("thermal_comfort_index", 0.0)
    surface = state.get("surface_hardness_index", _SURFACE_HARD_DEFAULT)

    # ── GRF proxy ─────────────────────────────────────────────────────────
    # Use peak forelimb acc (forelimbs carry ~60% of body mass load)
    if acc_LF is not None and acc_RF is not None:
        peak_acc = max(acc_LF, acc_RF)     # worst-case limb
        result["peak_grf_proxy_N_kg"] = peak_acc

        # Speed-adjusted GRF scaling: higher speed → higher impact multiplier
        speed_factor = 1.0
        if speed is not None and speed > _SPEED_GALLOP_M_S:
            speed_factor = 1.0 + 0.05 * (speed - _SPEED_GALLOP_M_S)

        # Surface hardness amplifies GRF (firm surface = less energy absorption)
        # surface_hardness_index: 0=soft, 1=firm
        surface_factor = 1.0 + 0.3 * surface

        adjusted_grf = peak_acc * speed_factor * surface_factor

        # Normalise to [0, 1] against critical threshold
        tendon_strain = min(adjusted_grf / _GRF_CRITICAL_N_KG, 1.0)
        result["tendon_strain_proxy"] = tendon_strain
    else:
        tendon_strain = None

    # ── Symmetry deficit component ────────────────────────────────────────
    # SI deficit: 0 at perfect symmetry, 1 at maximum asymmetry
    if si is not None:
        symmetry_deficit = max(0.0, (1.0 - si) / (1.0 - _CLINICAL_SI_THRESHOLD + 1e-9))
        symmetry_deficit = min(symmetry_deficit, 1.0)
    else:
        symmetry_deficit = 0.0

    # ── Thermal stress component ───────────────────────────────────────────
    # TCI > 0.15 → heat stress beginning to compromise musculoskeletal integrity
    thermal_component = min(max(abs(tci) - 0.15, 0.0) / 0.85, 1.0)

    # ── Composite injury risk ──────────────────────────────────────────────
    # Weighted sum — tendon strain is primary driver, symmetry is secondary
    components: List[float] = []
    weights:    List[float] = []

    if tendon_strain is not None:
        components.append(tendon_strain);  weights.append(0.45)
    components.append(symmetry_deficit);   weights.append(0.30)
    if psi is not None:
        components.append(psi);            weights.append(0.15)
    components.append(thermal_component);  weights.append(0.10)

    total_weight = sum(weights)
    if total_weight > 0:
        iri = sum(c * w for c, w in zip(components, weights)) / total_weight
        iri = min(max(iri, 0.0), 1.0)
    else:
        iri = 0.0

    result["injury_risk_index"] = iri

    # ── Risk grade ────────────────────────────────────────────────────────
    if iri < 0.25:
        grade = "low"
    elif iri < 0.50:
        grade = "moderate"
    elif iri < 0.75:
        grade = "elevated"
    else:
        grade = "critical"
    result["injury_risk_grade"] = grade

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 5.  TES ALARM CONFIGURATION
#     Four new threshold alarms added to the DigitalSoma Threshold Event System.
# ─────────────────────────────────────────────────────────────────────────────

GAIT_ALARMS: Dict[str, Any] = {
    "stride_symmetry_index": {
        "low":   _SUBCLINICAL_SI_THRESHOLD,   # 0.97 — pre-pathological
        "high":  None,
        "label": "subclinical_gait_asymmetry",
    },
    "limb_loading_asymmetry": {
        "low":   None,
        "high":  8.0,                          # > 8% forelimb loading difference
        "label": "forelimb_loading_asymmetry",
    },
    "tendon_strain_proxy": {
        "low":   None,
        "high":  0.50,                         # entering elevated risk zone
        "label": "elevated_tendon_strain",
    },
    "injury_risk_index": {
        "low":   None,
        "high":  0.50,                         # moderate → elevated transition
        "label": "elevated_injury_risk",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# 6.  REGISTRATION HELPER
#     Single function to wire the entire gait pipeline into a DigitalSoma twin.
# ─────────────────────────────────────────────────────────────────────────────

def register_gait_pipeline(ds: Any) -> None:
    """
    Register the complete EquiTwin gait biomechanics pipeline into an
    existing DigitalSoma instance.

    Actions performed
    ─────────────────
    1. Register 15 gait canonical properties into the shared vocabulary
    2. Register 3 gait solvers into the Model Zoo (in DAG order)
    3. Register 4 gait-specific TES alarms

    Parameters
    ──────────
    ds : DigitalSoma
        A fully built DigitalSoma instance (build_soma() already called).

    Example
    ───────
    >>> from digitalsoma import build_soma, SomaConfig
    >>> from equitwin.gait_biomechanics import register_gait_pipeline
    >>> ds = build_soma(SomaConfig(animal_type="equine_adult"))
    >>> register_gait_pipeline(ds)
    >>> print(ds.solvers)
    ['cardiovascular_baseline', 'metabolic_rate', 'thermoregulation',
     'respiratory_gas_exchange', 'neuroendocrine_stress', 'adverse_event_screen',
     'equine_stride_kinematics', 'equine_gait_symmetry', 'equine_injury_risk']
    """
    # 1. Vocabulary
    register_gait_vocabulary()

    # 2. Solvers (order matters — kinematics → symmetry → injury risk)
    ds.register_method("equine_stride_kinematics", solver_equine_stride_kinematics)
    ds.register_method("equine_gait_symmetry",     solver_equine_gait_symmetry)
    ds.register_method("equine_injury_risk",        solver_equine_injury_risk)

    # 3. TES alarms
    ds._tes._thresholds.update(GAIT_ALARMS)

    logger.info(
        "EquiTwin gait pipeline registered: 15 vocab properties, "
        "3 solvers, 4 TES alarms"
    )
