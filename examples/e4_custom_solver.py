"""
E4. User-defined solver extension + VeDDRA adverse event report.

Mirrors DP E4 (Crank-Nicolson heat conduction via register_method()) —
here a custom Heart Rate Variability (HRV) solver is registered via
register_method() without modifying the core codebase.

The HRV solver:
  - Consumes cardiac_output_L_min (from built-in cardiovascular_baseline)
  - Consumes physiological_stress_index (from built-in neuroendocrine_stress)
  - Estimates RMSSD (root mean square of successive RR-interval differences)
    as a proxy for autonomic nervous system status
  - Annotates low HRV as a VeDDRA-mappable clinical sign

Demonstrates solver compositionality: user solver inherits built-in outputs
within the same update() cycle — exactly as E4 demonstrates in DP.

Run: python examples/e4_custom_solver.py
"""

import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from digitalsoma import build_soma, SomaConfig

# ---------------------------------------------------------------------------
# Custom solver: HRV estimator (RMSSD proxy)
# ---------------------------------------------------------------------------

def solver_hrv_estimator(params: dict, state: dict) -> dict:
    """
    Estimate RMSSD (ms) from heart rate and stress index.
    RMSSD ≈ 1000 / HR * scaling_factor(1 - stress_index)
    This is a physiological approximation; real HRV requires beat-to-beat RR data.

    Consumes:
        heart_rate_bpm              (built-in: cardiovascular_baseline)
        physiological_stress_index  (built-in: neuroendocrine_stress)
    Produces:
        hrv_rmssd_ms                 Approximate RMSSD in milliseconds
        hrv_status                   "normal" | "reduced" | "suppressed"
    """
    hr = state.get("heart_rate_bpm")
    psi = state.get("physiological_stress_index", 0.0)
    if hr is None or hr <= 0:
        return {}

    # RR interval in ms
    rr_ms = (60.0 / hr) * 1000.0

    # RMSSD scales inversely with stress; typical bovine RMSSD ~30-80 ms
    hrv_rmssd = rr_ms * 0.065 * (1.0 - 0.85 * psi)
    hrv_rmssd = max(hrv_rmssd, 2.0)  # physiological floor

    if hrv_rmssd >= 30.0:
        status = "normal"
    elif hrv_rmssd >= 15.0:
        status = "reduced"
    else:
        status = "suppressed"

    return {
        "hrv_rmssd_ms": hrv_rmssd,
        "hrv_status": status,
    }


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

ds = build_soma(SomaConfig(animal_type="bovine_adult",
                           site_name="HRV extensibility demo"))

# Register custom solver — no core code modification
ds.register_method("hrv_estimator", solver_hrv_estimator)

print("=" * 70)
print("E4. DigitalSoma — user-defined HRV solver via register_method()")
print("=" * 70)
print("\nRegistered solvers:")
for i, s in enumerate(ds.solvers, 1):
    marker = " ← custom" if s == "hrv_estimator" else ""
    print(f"  {i}. {s}{marker}")

# Drive through a stress progression
scenarios = [
    ("Baseline",        {"core_temp_C": 38.5, "heart_rate_bpm": 60,  "spo2_pct": 98.5, "respiratory_rate_bpm": 20}),
    ("Moderate stress", {"core_temp_C": 39.5, "heart_rate_bpm": 82,  "spo2_pct": 97.0, "respiratory_rate_bpm": 35}),
    ("Severe stress",   {"core_temp_C": 40.8, "heart_rate_bpm": 108, "spo2_pct": 93.5, "respiratory_rate_bpm": 55}),
    ("Recovery",        {"core_temp_C": 38.8, "heart_rate_bpm": 65,  "spo2_pct": 98.0, "respiratory_rate_bpm": 22}),
]

print(f"\n{'Scenario':<20} {'HR':<6} {'Stress':<8} {'RMSSD(ms)':<12} "
      f"{'HRV status':<14} {'AE score':<10}")
print("-" * 72)

for label, readings in scenarios:
    state = ds.update_sync(readings)
    hr    = state.get("heart_rate_bpm", 0)
    psi   = state.get("physiological_stress_index", 0)
    rmssd = state.get("hrv_rmssd_ms", 0)
    hvs   = state.get("hrv_status", "—")
    ae    = state.get("adverse_event_score", 0)
    print(f"{label:<20} {hr:<6.0f} {psi:<8.3f} {rmssd:<12.1f} {hvs:<14} {ae:<10.3f}")

# VeDDRA report from the final (severe stress) state
print()
print("VeDDRA adverse event report (severe stress scenario):")
# Re-run severe stress to ensure it's the current state
ds.update_sync({"core_temp_C": 40.8, "heart_rate_bpm": 108,
                "spo2_pct": 93.5, "respiratory_rate_bpm": 55})
report = ds.veddra_report()
print(f"  Report ID   : {report['report_id']}")
print(f"  Taxa        : {report['taxa']}")
print(f"  AE score    : {report['adverse_event_score']:.3f}")
print(f"  Standard    : {report['reporting_standard']}")
print(f"  Clinical signs flagged:")
for sign in report["clinical_signs"]:
    print(f"    [{sign['veddra_id']}] {sign['veddra_term']}"
          f" ({sign['state_key']}={sign['value']:.3g})")
