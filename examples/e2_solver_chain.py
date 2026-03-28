"""
E2. Dynamic solver chain — physiological stress cycle.

Mirrors DP E2 (drying-wetting cycle) — here we drive a bovine twin
through a heat-stress and recovery cycle, demonstrating that all six
built-in solvers run automatically on each update_sync() call and
that derived variables (cardiac output, metabolic rate, stress index,
VeDDRA flags) respond correctly.

Run: python examples/e2_solver_chain.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from digitalsoma import build_soma, SomaConfig

ds = build_soma(SomaConfig(animal_type="bovine_adult", site_name="Heat stress trial"))

# Simulate a heat-stress ramp: core temp 38.5 → 41.5 °C, HR rises, SpO2 drops
stress_ramp = [
    # (core_temp_C, heart_rate_bpm, respiratory_rate_bpm, spo2_pct, ambient_temp_C)
    (38.5, 60,  20, 98.5, 22),   # thermoneutral baseline
    (39.0, 68,  24, 98.0, 28),   # mild heat load
    (39.8, 78,  32, 97.5, 34),   # moderate heat stress
    (40.6, 92,  44, 96.0, 38),   # severe heat stress — alarms expected
    (41.2, 110, 58, 93.0, 40),   # critical — tachycardia + hypoxia flags
    (40.0, 85,  38, 96.5, 35),   # recovery begins
    (38.9, 65,  22, 98.0, 25),   # near-normal recovery
    (38.5, 61,  20, 98.5, 22),   # baseline restored
]

print("=" * 80)
print("E2. DigitalSoma — solver chain across a heat-stress/recovery cycle")
print("=" * 80)
print(f"\n{'Step':<6} {'Temp(°C)':<10} {'HR':<6} {'RR':<6} {'SpO2':<7} "
      f"{'CO(L/min)':<11} {'RMR(W)':<9} {'Stress':<8} {'AE_score':<10} {'Flags'}")
print("-" * 100)

for step, (temp, hr, rr, spo2, t_amb) in enumerate(stress_ramp, 1):
    state = ds.update_sync({
        "core_temp_C":          temp,
        "heart_rate_bpm":       hr,
        "respiratory_rate_bpm": rr,
        "spo2_pct":             spo2,
        "ambient_temp_C":       t_amb,
    })
    co   = state.get("cardiac_output_L_min", float("nan"))
    rmr  = state.get("rmr_W", float("nan"))
    psi  = state.get("physiological_stress_index", float("nan"))
    ae   = state.get("adverse_event_score", 0.0)
    flags = [f["veddra_term"] for f in state.get("ae_flags", [])]
    flag_str = ", ".join(flags) if flags else "—"
    print(f"{step:<6} {temp:<10.1f} {hr:<6} {rr:<6} {spo2:<7.1f} "
          f"{co:<11.2f} {rmr:<9.1f} {psi:<8.3f} {ae:<10.3f} {flag_str}")

print()
print("Time-series for heart_rate_bpm (last 5 readings):")
for rec in ds.query_history("heart_rate_bpm", limit=5):
    print(f"  t={rec['timestamp']:.2f}  HR={rec['value']} bpm")
