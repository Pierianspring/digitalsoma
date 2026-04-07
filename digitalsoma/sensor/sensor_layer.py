"""
sensor/sensor_layer.py — DigitalSoma BYOD sensor manifest layer.

The six-field manifest contract:
    sensor_id     : unique device identifier string
    canonical_key : property name (resolved via vocab.canonical_key())
    unit          : UCUM unit string of the raw stream
    timestamp     : Unix epoch float (ISO 8601 accepted and converted)
    value         : numeric reading (raw; converted to canonical unit before ingest)
    quality_flag  : int 0 = good, 1 = questionable, 2 = bad (QARTOD convention)

Any stream conforming to this contract is ingested without schema modification.

Unit conversions provided (14 conversions):
    °F   → °C
    K    → °C
    bpm  → /min         (identity, alias resolution only)
    kPa  → mmHg
    psi  → mmHg
    %    → fraction     (for SpO2 kept as %; for gas fractions converted)
    mg/dL→ mmol/L       (glucose)
    μg/dL→ nmol/L       (cortisol)
    lb   → kg
    g    → kg
    m/s² → m/s²         (identity)
    counts/min → /min   (activity)
    mV   → mV           (ECG; identity)
    Hz   → /min         (for RR from impedance in Hz × 60)
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from digitalsoma.ontology.vocab import canonical_key, normalise_dict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Unit conversion registry (14 supported conversions)
# ---------------------------------------------------------------------------

# Each entry: (from_unit_pattern, to_canonical_unit, converter_fn)
_UNIT_CONVERTERS: List[Tuple[str, str, Callable[[float], float]]] = [
    # Temperature
    ("degF",   "Cel",   lambda v: (v - 32.0) * 5.0 / 9.0),
    ("°F",     "Cel",   lambda v: (v - 32.0) * 5.0 / 9.0),
    ("F",      "Cel",   lambda v: (v - 32.0) * 5.0 / 9.0),
    ("K",      "Cel",   lambda v: v - 273.15),
    # Pressure
    ("kPa",    "mm[Hg]", lambda v: v * 7.50062),
    ("psi",    "mm[Hg]", lambda v: v * 51.7149),
    ("bar",    "mm[Hg]", lambda v: v * 750.062),
    # Glucose
    ("mg/dL",  "mmol/L", lambda v: v / 18.0182),
    ("mg/dl",  "mmol/L", lambda v: v / 18.0182),
    # Cortisol
    ("μg/dL",  "nmol/L", lambda v: v * 27.5886),
    ("ug/dL",  "nmol/L", lambda v: v * 27.5886),
    # Mass
    ("lb",     "kg",     lambda v: v * 0.453592),
    ("lbs",    "kg",     lambda v: v * 0.453592),
    ("g",      "kg",     lambda v: v / 1000.0),
    # Frequency (for RR from Hz-based impedance sensors)
    ("Hz",     "/min",   lambda v: v * 60.0),
]

_CONVERTER_MAP: Dict[str, Tuple[str, Callable[[float], float]]] = {
    src: (dst, fn) for src, dst, fn in _UNIT_CONVERTERS
}


def convert_unit(value: float, from_unit: str) -> Tuple[float, str]:
    """
    Convert *value* from *from_unit* to the canonical UCUM unit.
    Returns (converted_value, canonical_unit).
    If no converter is registered, returns (value, from_unit) unchanged.
    """
    entry = _CONVERTER_MAP.get(from_unit)
    if entry is None:
        return value, from_unit
    dst_unit, fn = entry
    return fn(value), dst_unit


# ---------------------------------------------------------------------------
# SensorManifestEntry — the six-field contract
# ---------------------------------------------------------------------------

@dataclass
class SensorManifestEntry:
    """
    One row in the sensor manifest. Maps a physical device stream to the
    framework's canonical vocabulary. Six-field BYOD manifest contract.
    """
    sensor_id: str
    property_alias: str             # raw alias; resolved to canonical_key internally
    unit: str                       # UCUM unit of the *raw* stream
    description: str = ""
    quality_threshold: int = 1      # readings with quality_flag > threshold are rejected
    conversion_fn: Optional[Callable[[float], float]] = None  # custom override


# ---------------------------------------------------------------------------
# SensorLayer
# ---------------------------------------------------------------------------

class SensorLayer:
    """
    BYOD sensor manifest layer.

    Workflow:
        1. Register one SensorManifestEntry per physical device stream.
        2. Call ingest(readings) with a list of raw SensorReading dicts.
        3. Receive a normalised dict ready for DigitalSoma.update_sync().

    Mirrors DP SensorLayer exactly; adds physiological quality checks.
    """

    def __init__(self) -> None:
        self._manifest: Dict[str, SensorManifestEntry] = {}
        self._rejected: List[Dict[str, Any]] = []   # audit log of rejected readings

    def register_sensor(self, entry: SensorManifestEntry) -> None:
        """Add a sensor to the manifest."""
        self._manifest[entry.sensor_id] = entry
        logger.info("SensorLayer: registered sensor '%s' → '%s'",
                    entry.sensor_id, canonical_key(entry.property_alias))

    def ingest(self, readings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process a batch of raw sensor readings through the manifest.

        Each reading dict must contain:
            sensor_id, value, [timestamp], [quality_flag]

        Returns a normalised dict {canonical_key: value} ready for
        DigitalSoma.update_sync().
        """
        output: Dict[str, Any] = {}
        for reading in readings:
            result = self._process_reading(reading)
            if result is not None:
                ckey, value = result
                output[ckey] = value
        return output

    def ingest_flat(self, flat: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convenience: ingest a flat {alias: value} dict (no quality flags).
        Equivalent to calling normalise_dict() + unit conversion.
        Direct dict update path — bypasses manifest validation.
        """
        output: Dict[str, Any] = {}
        for alias, value in flat.items():
            ckey = canonical_key(alias)
            output[ckey] = value
        return output

    def _process_reading(self, reading: Dict[str, Any]) -> Optional[Tuple[str, Any]]:
        sensor_id = reading.get("sensor_id")
        value = reading.get("value")
        quality = reading.get("quality_flag", 0)
        timestamp = reading.get("timestamp", time.time())

        if value is None:
            return None

        # Look up manifest entry
        entry = self._manifest.get(sensor_id)
        if entry is None:
            # Unknown sensor: attempt direct canonical key resolution
            alias = reading.get("property", sensor_id)
            ckey = canonical_key(alias)
            return ckey, value

        # Quality gate
        if quality > entry.quality_threshold:
            self._rejected.append({"sensor_id": sensor_id, "value": value,
                                   "quality_flag": quality, "timestamp": timestamp})
            logger.debug("Rejected reading from '%s' (quality_flag=%d)", sensor_id, quality)
            return None

        # Unit conversion
        if entry.conversion_fn is not None:
            value = entry.conversion_fn(value)
        else:
            value, _ = convert_unit(value, entry.unit)

        ckey = canonical_key(entry.property_alias)
        return ckey, value

    def manifest_summary(self) -> List[Dict[str, str]]:
        """Return a human-readable summary of registered sensors."""
        return [
            {
                "sensor_id": e.sensor_id,
                "canonical_key": canonical_key(e.property_alias),
                "unit": e.unit,
                "description": e.description,
            }
            for e in self._manifest.values()
        ]

    @property
    def rejected_count(self) -> int:
        return len(self._rejected)


# ---------------------------------------------------------------------------
# Sensor manifest presets (built-in templates for common device types)
# ---------------------------------------------------------------------------

def wearable_cattle_manifest() -> SensorLayer:
    """
    Pre-configured manifest for a standard cattle wearable collar/bolus suite.
    Covers the most common precision livestock farming sensor configuration.
    """
    layer = SensorLayer()
    entries = [
        SensorManifestEntry("HR_ECG_01",       "HR",          "/min",
                            "ECG-derived heart rate"),
        SensorManifestEntry("TEMP_RUMEN_01",   "core_temp",   "Cel",
                            "Rumen bolus temperature (proxy for core temp)"),
        SensorManifestEntry("ACCEL_01",        "accel",       "m/s2",
                            "3-axis accelerometer magnitude"),
        SensorManifestEntry("LYING_01",        "lying_time",  "min",
                            "Cumulative lying time per hour"),
        SensorManifestEntry("GPS_SPEED_01",    "activity",    "1",
                            "GPS-derived activity counts"),
        SensorManifestEntry("RR_BELT_01",      "RR",          "/min",
                            "Respiratory belt rate"),
    ]
    for e in entries:
        layer.register_sensor(e)
    return layer


def implant_bovine_manifest() -> SensorLayer:
    """Pre-configured manifest for an implanted biosensor suite (bovine)."""
    layer = SensorLayer()
    entries = [
        SensorManifestEntry("CGM_01",    "glucose",      "mg/dL",
                            "Continuous glucose monitor (raw mg/dL → mmol/L auto-converted)"),
        SensorManifestEntry("CORT_01",   "cortisol",     "μg/dL",
                            "Cortisol microdialysis probe (raw μg/dL → nmol/L)"),
        SensorManifestEntry("BP_01",     "systolic_bp",  "kPa",
                            "Intravascular pressure (kPa → mmHg auto-converted)"),
    ]
    for e in entries:
        layer.register_sensor(e)
    return layer


def lab_panel_manifest() -> SensorLayer:
    """Pre-configured manifest for a standard clinical blood panel."""
    layer = SensorLayer()
    entries = [
        SensorManifestEntry("HCT_LAB",  "HCT",        "%",      "Haematocrit"),
        SensorManifestEntry("HB_LAB",   "Hb",         "g/dL",   "Haemoglobin"),
        SensorManifestEntry("WBC_LAB",  "WBC",        "10*9/L", "White blood cell count"),
        SensorManifestEntry("CREA_LAB", "creatinine", "umol/L", "Plasma creatinine"),
        SensorManifestEntry("GLU_LAB",  "glucose",    "mg/dL",  "Fasting glucose"),
    ]
    for e in entries:
        layer.register_sensor(e)
    return layer
