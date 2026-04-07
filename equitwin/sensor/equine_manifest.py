"""
equitwin/sensor/equine_manifest.py
===============================================================================
EquiTwin — Equine Sensor Manifest

Pre-configured BYOD manifests for the three main EnergyTag sensor suites
used in EquiTwin's HorseTwin.

    equine_energytag_manifest()   Full EnergyTag collar + limb IMU suite
    equine_force_plate_manifest() Stationary force plate (lab / starting gate)
    equine_race_manifest()        Lightweight race-day minimal sensor set

All manifests follow the DigitalSoma six-field contract and are passed
directly to ds.update_sync() after calling manifest.read_batch(raw_data).
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from digitalsoma.sensor.sensor_layer import SensorManifestEntry, SensorLayer


def equine_energytag_manifest() -> SensorLayer:
    """
    Full EnergyTag collar + limb-mounted IMU suite.

    Covers all inputs required by the three gait biomechanics solvers
    plus the six DigitalSoma built-in solvers.

    Sensor placement
    ────────────────
    COLLAR_IMU   Dorsal neck / withers IMU (vertical + lateral + fore-aft accel)
    LF_IMU       Left forelimb cannon bone IMU
    RF_IMU       Right forelimb cannon bone IMU
    LH_IMU       Left hindlimb cannon bone IMU
    RH_IMU       Right hindlimb cannon bone IMU
    HEART_SENSOR EnergyTag HR / SpO2 / core temp sensor
    GPS_01       GPS speed and position
    STRIKE_01    Hoof strike timing sensor (piezo, left forelimb reference)

    Returns
    -------
    SensorLayer
        Fully configured manifest ready for read_batch().
    """
    layer = SensorLayer()
    entries = [
        # ── EnergyTag physiological (collar-mounted) ──────────────────────
        SensorManifestEntry("HEART_01",    "HR",           "/min",
                            "EnergyTag heart rate (beats per minute)"),
        SensorManifestEntry("SPO2_01",     "SpO2",         "%",
                            "EnergyTag peripheral oxygen saturation"),
        SensorManifestEntry("TEMP_01",     "core_temp_C",  "Cel",
                            "EnergyTag infrared core temperature estimate"),
        SensorManifestEntry("RESP_01",     "RR",           "/min",
                            "EnergyTag respiratory rate from thoracic impedance"),
        SensorManifestEntry("CORT_01",     "cortisol_nmol_L", "nmol/L",
                            "Salivary cortisol (intermittent assay; nmol/L)"),

        # ── GPS / speed ───────────────────────────────────────────────────
        SensorManifestEntry("GPS_01",      "speed_m_s",    "m/s",
                            "GPS speed over ground (m/s)"),

        # ── Stride timing ─────────────────────────────────────────────────
        SensorManifestEntry("STRIKE_01",   "strike_interval_s", "s",
                            "Left forelimb hoof strike interval (stride sensor)"),

        # ── Withers / collar IMU (3-axis) ──────────────────────────────────
        SensorManifestEntry("COLLAR_IMU_V", "acceleration_m_s2",          "m/s2",
                            "Collar IMU — dorsal-ventral (vertical) acceleration"),
        SensorManifestEntry("COLLAR_IMU_L", "acceleration_lateral_m_s2",  "m/s2",
                            "Collar IMU — mediolateral acceleration"),
        SensorManifestEntry("COLLAR_IMU_F", "acceleration_fore_m_s2",     "m/s2",
                            "Collar IMU — fore-aft (craniocaudal) acceleration"),

        # ── Limb load (% total bodyweight per limb) ───────────────────────
        SensorManifestEntry("LF_LOAD",     "limb_lf_load_pct",  "%",
                            "Left forelimb load (% of total bodyweight)"),
        SensorManifestEntry("RF_LOAD",     "limb_rf_load_pct",  "%",
                            "Right forelimb load (% of total bodyweight)"),
        SensorManifestEntry("LH_LOAD",     "limb_lh_load_pct",  "%",
                            "Left hindlimb load (% of total bodyweight)"),
        SensorManifestEntry("RH_LOAD",     "limb_rh_load_pct",  "%",
                            "Right hindlimb load (% of total bodyweight)"),

        # ── Stance time per limb (from limb-mounted IMU) ──────────────────
        SensorManifestEntry("LF_IMU_ST",   "stance_time_lf_s",  "s",
                            "Left forelimb stance duration per stride (s)"),
        SensorManifestEntry("RF_IMU_ST",   "stance_time_rf_s",  "s",
                            "Right forelimb stance duration per stride (s)"),
        SensorManifestEntry("LH_IMU_ST",   "stance_time_lh_s",  "s",
                            "Left hindlimb stance duration per stride (s)"),
        SensorManifestEntry("RH_IMU_ST",   "stance_time_rh_s",  "s",
                            "Right hindlimb stance duration per stride (s)"),

        # ── Ambient environment (feeds TrackTwin coupling) ─────────────────
        SensorManifestEntry("ENV_TEMP",    "ambient_temp_C",     "Cel",
                            "Ambient air temperature (°C)"),
        SensorManifestEntry("ENV_RH",      "relative_humidity_pct", "%",
                            "Relative humidity (%)"),
    ]
    for entry in entries:
        layer.register_sensor(entry)
    return layer


def equine_force_plate_manifest() -> SensorLayer:
    """
    Stationary force plate configuration for lab or starting-gate assessment.

    Force plates provide direct ground reaction force measurements —
    the ground truth inputs for the GRF solver (to be built in Phase 2).
    This manifest covers the four-plate system (one per hoof).

    Returns
    -------
    SensorLayer
    """
    layer = SensorLayer()
    entries = [
        # ── Direct GRF from four-plate system ────────────────────────────
        SensorManifestEntry("FP_LF_Fz",  "limb_lf_load_pct",  "N",
                            "Left forelimb vertical GRF (N; normalised to BW% internally)",
                            conversion_fn=lambda v: v / 500.0 / 9.81 * 100.0),
        SensorManifestEntry("FP_RF_Fz",  "limb_rf_load_pct",  "N",
                            "Right forelimb vertical GRF (N)",
                            conversion_fn=lambda v: v / 500.0 / 9.81 * 100.0),
        SensorManifestEntry("FP_LH_Fz",  "limb_lh_load_pct",  "N",
                            "Left hindlimb vertical GRF (N)",
                            conversion_fn=lambda v: v / 500.0 / 9.81 * 100.0),
        SensorManifestEntry("FP_RH_Fz",  "limb_rh_load_pct",  "N",
                            "Right hindlimb vertical GRF (N)",
                            conversion_fn=lambda v: v / 500.0 / 9.81 * 100.0),

        # ── Stance time from force plate threshold crossing ───────────────
        SensorManifestEntry("FP_LF_ST",  "stance_time_lf_s",  "s",
                            "Left forelimb stance time from FP threshold (s)"),
        SensorManifestEntry("FP_RF_ST",  "stance_time_rf_s",  "s",
                            "Right forelimb stance time from FP threshold (s)"),
        SensorManifestEntry("FP_LH_ST",  "stance_time_lh_s",  "s",
                            "Left hindlimb stance time (s)"),
        SensorManifestEntry("FP_RH_ST",  "stance_time_rh_s",  "s",
                            "Right hindlimb stance time (s)"),

        # ── IMU on withers (same as EnergyTag suite) ──────────────────────
        SensorManifestEntry("IMU_V",  "acceleration_m_s2",         "m/s2",
                            "Withers vertical acceleration"),
        SensorManifestEntry("IMU_L",  "acceleration_lateral_m_s2", "m/s2",
                            "Withers lateral acceleration"),
        SensorManifestEntry("IMU_F",  "acceleration_fore_m_s2",    "m/s2",
                            "Withers fore-aft acceleration"),
        SensorManifestEntry("TREAD_SPEED", "speed_m_s",            "m/s",
                            "Treadmill or walkway speed"),
        SensorManifestEntry("TREAD_ST",    "strike_interval_s",    "s",
                            "Stride interval from treadmill sensor"),
    ]
    for entry in entries:
        layer.register_sensor(entry)
    return layer


def equine_race_manifest() -> SensorLayer:
    """
    Lightweight race-day manifest — minimal sensor set for real-time
    monitoring during competition where sensor weight and interference
    constraints apply.

    Covers the essential inputs: speed (GPS), collar IMU (vertical accel
    only), heart rate, and temperature. Stride kinematics and basic
    symmetry index are still computed from the collar IMU lateral channel
    and strike sensor.

    Returns
    -------
    SensorLayer
    """
    layer = SensorLayer()
    entries = [
        SensorManifestEntry("GPS_RACE",     "speed_m_s",           "m/s",
                            "Race-day GPS speed"),
        SensorManifestEntry("HR_RACE",      "HR",                  "/min",
                            "Race-day heart rate"),
        SensorManifestEntry("TEMP_RACE",    "core_temp_C",         "Cel",
                            "Race-day core temperature (EnergyTag IR)"),
        SensorManifestEntry("SPO2_RACE",    "SpO2",                "%",
                            "Race-day SpO2"),
        SensorManifestEntry("IMU_V_RACE",   "acceleration_m_s2",         "m/s2",
                            "Withers vertical acceleration"),
        SensorManifestEntry("IMU_L_RACE",   "acceleration_lateral_m_s2", "m/s2",
                            "Withers lateral acceleration (lameness proxy)"),
        SensorManifestEntry("STRIKE_RACE",  "strike_interval_s",   "s",
                            "Hoof strike interval (lightweight piezo)"),
        SensorManifestEntry("ENV_T_RACE",   "ambient_temp_C",      "Cel",
                            "Race-day ambient temperature"),
    ]
    for entry in entries:
        layer.register_sensor(entry)
    return layer
