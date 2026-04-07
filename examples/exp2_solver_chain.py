"""
Experiment 2 — Solver chain: multi-species physiological scenarios.

Three realistic scenarios, one per species:
  Bovine  — summer heat stress ramp (ambient 22 → 40 °C, 12 steps)
  Ovine   — transport stress cycle (loading, transit, unloading, recovery)
  Equine  — exercise and recovery (rest → warm-up → peak → cool-down)

For each species the full solver chain runs on every step.
Plotted derived variables:
  - cardiac_output_L_min
  - rmr_W
  - thermal_comfort_index
  - physiological_stress_index
  - adverse_event_score
"""

import sys
sys.path.insert(0, "/home/claude")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

from digitalsoma import build_soma, SomaConfig

# ── Scenario definitions ─────────────────────────────────────────────────────

# Bovine: heat stress ramp — 12 time steps
# (core_temp_C, heart_rate_bpm, respiratory_rate_bpm, spo2_pct, ambient_temp_C)
bovine_steps = [
    (38.5, 60,  20, 98.5, 22),
    (38.6, 62,  22, 98.5, 24),
    (38.8, 65,  25, 98.2, 27),
    (39.1, 70,  28, 98.0, 30),
    (39.4, 75,  33, 97.8, 33),
    (39.8, 82,  38, 97.5, 35),
    (40.2, 90,  44, 97.0, 37),
    (40.6, 98,  50, 96.5, 39),
    (41.0, 108, 56, 95.5, 40),
    (40.4, 94,  46, 96.8, 37),
    (39.5, 76,  30, 97.8, 31),
    (38.7, 63,  21, 98.4, 24),
]
bovine_labels = [f"t{i+1}" for i in range(len(bovine_steps))]

# Ovine: transport stress — 10 steps
# (core_temp_C, heart_rate_bpm, respiratory_rate_bpm, spo2_pct, cortisol_nmol_L)
ovine_steps = [
    (39.0, 75,  24, 98.0, 28),   # baseline
    (39.2, 82,  28, 97.8, 45),   # loading begins
    (39.5, 96,  36, 97.2, 90),   # transit — moderate stress
    (39.8, 108, 44, 96.5, 140),  # transit — peak stress
    (40.1, 118, 52, 95.8, 180),  # transit — severe stress
    (40.3, 122, 56, 95.2, 200),  # peak transit
    (39.9, 110, 48, 96.0, 160),  # unloading
    (39.4, 92,  36, 97.0, 100),  # pen recovery 1h
    (39.1, 80,  27, 97.8, 55),   # pen recovery 3h
    (39.0, 76,  24, 98.0, 30),   # recovered
]
ovine_labels = ["Baseline","Loading","Transit 1","Transit 2",
                "Transit 3","Peak","Unloading","Recov 1h","Recov 3h","Recovered"]

# Equine: exercise and recovery — 10 steps
# (core_temp_C, heart_rate_bpm, respiratory_rate_bpm, spo2_pct, ambient_temp_C)
equine_steps = [
    (37.8, 36,  12, 98.5, 18),   # rest
    (38.0, 60,  18, 98.2, 18),   # walk
    (38.4, 100, 30, 97.8, 18),   # trot
    (38.9, 150, 50, 97.2, 18),   # canter
    (39.5, 190, 70, 96.5, 18),   # gallop peak
    (39.8, 200, 80, 95.8, 18),   # max effort
    (39.2, 155, 55, 96.8, 18),   # cool-down 1
    (38.7, 100, 32, 97.5, 18),   # cool-down 2
    (38.2, 60,  18, 98.2, 18),   # walk out
    (37.9, 38,  13, 98.5, 18),   # recovered
]
equine_labels = ["Rest","Walk","Trot","Canter","Gallop","Max",
                 "Cool 1","Cool 2","Walk out","Recovered"]

# ── Run solver chains ─────────────────────────────────────────────────────────

def run_scenario(animal_type, steps, keys_in):
    ds = build_soma(SomaConfig(animal_type=animal_type))
    records = []
    for step in steps:
        reading = dict(zip(keys_in, step))
        state = ds.update_sync(reading)
        records.append(state)
    return records

bovine_keys = ["core_temp_C","heart_rate_bpm","respiratory_rate_bpm","spo2_pct","ambient_temp_C"]
bovine_records = run_scenario("bovine_adult", bovine_steps, bovine_keys)

ovine_keys = ["core_temp_C","heart_rate_bpm","respiratory_rate_bpm","spo2_pct","cortisol_nmol_L"]
ovine_records = run_scenario("ovine_adult", ovine_steps, ovine_keys)

equine_keys = ["core_temp_C","heart_rate_bpm","respiratory_rate_bpm","spo2_pct","ambient_temp_C"]
equine_records = run_scenario("equine_adult", equine_steps, equine_keys)

# ── Extract series ────────────────────────────────────────────────────────────

def series(records, key):
    return [r.get(key, float("nan")) for r in records]

VARS = [
    ("cardiac_output_L_min",      "Cardiac output (L/min)",      "#1D9E75"),
    ("rmr_W",                     "Metabolic rate (W)",           "#BA7517"),
    ("thermal_comfort_index",     "Thermal comfort index",        "#D85A30"),
    ("physiological_stress_index","Physiological stress index",   "#7F77DD"),
    ("adverse_event_score",       "Adverse event score",          "#A32D2D"),
]

scenarios = [
    ("Bovine — heat stress",    bovine_records,  bovine_labels),
    ("Ovine — transport stress",ovine_records,   ovine_labels),
    ("Equine — exercise/recovery",equine_records,equine_labels),
]

# ── Plot ──────────────────────────────────────────────────────────────────────

fig = plt.figure(figsize=(16, 12))
fig.patch.set_facecolor("#fafaf8")

gs = gridspec.GridSpec(len(VARS), len(scenarios), hspace=0.55, wspace=0.35)

for vi, (var_key, var_label, color) in enumerate(VARS):
    for si, (title, records, labels) in enumerate(scenarios):
        ax = fig.add_subplot(gs[vi, si])
        ax.set_facecolor("#f4f3ee")

        vals = series(records, var_key)
        x = range(len(vals))

        ax.plot(x, vals, color=color, linewidth=2, marker="o",
                markersize=4, markerfacecolor="white", markeredgecolor=color,
                markeredgewidth=1.2)
        ax.fill_between(x, vals, alpha=0.12, color=color)

        # shade adverse event zone for stress/AE vars
        if var_key in ("physiological_stress_index","adverse_event_score"):
            ax.axhline(0.5, color="#A32D2D", linewidth=0.6,
                       linestyle="--", alpha=0.5)

        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=7)
        ax.tick_params(axis="y", labelsize=8)
        ax.spines[["top","right"]].set_visible(False)
        ax.spines[["left","bottom"]].set_color("#cccccc")
        ax.grid(axis="y", linewidth=0.4, color="#dddddd")

        if vi == 0:
            ax.set_title(title, fontsize=10, fontweight="medium", pad=8)
        if si == 0:
            ax.set_ylabel(var_label, fontsize=8)

plt.suptitle("E2 — DigitalSoma solver chain: multi-species physiological scenarios",
             fontsize=13, fontweight="medium", y=1.01)

plt.savefig("/mnt/user-data/outputs/exp2_solver_chain.png", dpi=150,
            bbox_inches="tight", facecolor=fig.get_facecolor())
plt.close()
print("Saved: exp2_solver_chain.png")
