"""
Experiment 3 — Threshold Event System (TES) alarms.

Simulates a 24-hour continuous monitoring window for a bovine animal
with three distinct alarm episodes:
  Episode A (t=4–6h)   — mild hyperthermia + mild tachycardia
  Episode B (t=10–13h) — severe heat stress: hyperthermia + tachycardia + hypoxia
  Episode C (t=18–20h) — hypoglycaemia episode (blood glucose drop)

TES callbacks capture every fired alarm event with its timestamp and label.

Plotted:
  Top row    — raw physiological signals (core_temp, HR, SpO2, glucose)
  Bottom row — alarm event timeline as a raster / event plot per alarm type
"""

import sys
sys.path.insert(0, "/home/claude")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

from digitalsoma import build_soma, SomaConfig

# ── Build twin with alarm handler ────────────────────────────────────────────

ds = build_soma(SomaConfig(animal_type="bovine_adult", site_name="Continuous monitoring — 24h"))

alarm_log = []   # list of (step, label)

def alarm_handler(key, value, label):
    alarm_log.append({"key": key, "value": value, "label": label,
                      "step": alarm_handler._current_step})
alarm_handler._current_step = 0
ds._tes.register_handler(alarm_handler)

# ── Synthetic 24h signal (48 steps = 30 min intervals) ───────────────────────

np.random.seed(42)
steps = 48
t_hours = np.linspace(0, 24, steps)

def baseline_with_noise(base, noise=0.15):
    return base + np.random.normal(0, noise, steps)

core_temp = baseline_with_noise(38.5, 0.12)
heart_rate = baseline_with_noise(62, 1.5)
spo2       = baseline_with_noise(98.2, 0.2)
glucose    = baseline_with_noise(4.5, 0.15)

# Episode A: t=4–6h (steps 8–12) — mild hyperthermia
for i in range(8, 13):
    core_temp[i]  += 1.8 + (i - 8) * 0.2
    heart_rate[i] += 18 + (i - 8) * 3

# Episode B: t=10–13h (steps 20–26) — severe heat stress
for i in range(20, 27):
    core_temp[i]  += 2.5 + (i - 20) * 0.15
    heart_rate[i] += 40 + (i - 20) * 5
    spo2[i]       -= 4 + (i - 20) * 0.8

# Episode C: t=18–20h (steps 36–40) — hypoglycaemia
for i in range(36, 41):
    glucose[i] -= 2.2 + (i - 36) * 0.2

# ── Run twin through 24h ──────────────────────────────────────────────────────

states = []
for i in range(steps):
    alarm_handler._current_step = i
    state = ds.update_sync({
        "core_temp_C":          float(core_temp[i]),
        "heart_rate_bpm":       float(heart_rate[i]),
        "spo2_pct":             float(np.clip(spo2[i], 80, 100)),
        "blood_glucose_mmol_L": float(np.clip(glucose[i], 1.0, 10.0)),
    })
    states.append(state)

# ── Organise alarm events ─────────────────────────────────────────────────────

alarm_types = {
    "hyperthermia/hypothermia": ("#D85A30", "Hyperthermia / hypothermia"),
    "bradycardia/tachycardia":  ("#7F77DD", "Tachycardia / bradycardia"),
    "hypoxaemia":               ("#1D9E75", "Hypoxaemia (SpO2)"),
    "hypoglycaemia/hyperglycaemia": ("#BA7517", "Hypoglycaemia / hyperglycaemia"),
}

events_by_type = {k: [] for k in alarm_types}
for ev in alarm_log:
    lbl = ev["label"]
    if lbl in events_by_type:
        events_by_type[lbl].append(t_hours[ev["step"]])

print(f"Total alarm events fired: {len(alarm_log)}")
for lbl, evts in events_by_type.items():
    print(f"  {lbl}: {len(evts)} events")

# ── Plot ──────────────────────────────────────────────────────────────────────

fig = plt.figure(figsize=(14, 10))
fig.patch.set_facecolor("#fafaf8")
gs = gridspec.GridSpec(2, 4, hspace=0.5, wspace=0.35,
                       height_ratios=[3, 1.6])

signals = [
    (core_temp,  "Core temperature (°C)",       "#D85A30", (37.0, 42.0)),
    (heart_rate, "Heart rate (bpm)",             "#7F77DD", (30,   140)),
    (np.clip(spo2, 80, 100), "SpO2 (%)",         "#1D9E75", (82,   100)),
    (np.clip(glucose, 1.0, 10.0), "Blood glucose (mmol/L)", "#BA7517", (1.5, 7.0)),
]

thresholds = {
    "Core temperature (°C)":  [(38.5, "--", "#888780", "normal"), (40.5, "-.", "#D85A30", "alarm hi")],
    "Heart rate (bpm)":       [(62,   "--", "#888780", "normal"), (120,  "-.", "#7F77DD", "alarm hi")],
    "SpO2 (%)":               [(98.0, "--", "#888780", "normal"), (90,   "-.", "#1D9E75", "alarm lo")],
    "Blood glucose (mmol/L)": [(4.5,  "--", "#888780", "normal"), (2.5,  "-.", "#BA7517", "alarm lo")],
}

episode_spans = [
    (t_hours[8],  t_hours[12], "A", "#D85A30"),
    (t_hours[20], t_hours[26], "B", "#7F77DD"),
    (t_hours[36], t_hours[40], "C", "#BA7517"),
]

for si, (sig, label, color, ylim) in enumerate(signals):
    ax = fig.add_subplot(gs[0, si])
    ax.set_facecolor("#f4f3ee")

    for t_start, t_end, ep_label, ep_color in episode_spans:
        ax.axvspan(t_start, t_end, alpha=0.08, color=ep_color, linewidth=0)
        mid = (t_start + t_end) / 2
        ax.text(mid, ylim[1] * 0.985, f"Ep {ep_label}",
                ha="center", va="top", fontsize=7, color=ep_color, alpha=0.8)

    ax.plot(t_hours, sig, color=color, linewidth=1.5)
    ax.fill_between(t_hours, sig, ylim[0], alpha=0.08, color=color)

    for thresh_val, ls, tc, tlabel in thresholds[label]:
        ax.axhline(thresh_val, linestyle=ls, color=tc, linewidth=0.8, alpha=0.7)

    ax.set_xlim(0, 24)
    ax.set_ylim(ylim)
    ax.set_xlabel("Time (h)", fontsize=8)
    ax.set_ylabel(label, fontsize=8)
    ax.tick_params(labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#cccccc")
    ax.grid(axis="y", linewidth=0.3, color="#dddddd")
    ax.set_xticks([0, 6, 12, 18, 24])

# Alarm event raster — bottom row spanning all 4 columns
ax_raster = fig.add_subplot(gs[1, :])
ax_raster.set_facecolor("#f4f3ee")

for yi, (alarm_key, (color, display_label)) in enumerate(alarm_types.items()):
    event_times = events_by_type[alarm_key]
    if event_times:
        ax_raster.vlines(event_times, yi - 0.35, yi + 0.35,
                         color=color, linewidth=2.5, alpha=0.85)
    ax_raster.text(-0.4, yi, display_label, ha="right", va="center",
                   fontsize=8.5, color=color)

for t_start, t_end, ep_label, ep_color in episode_spans:
    ax_raster.axvspan(t_start, t_end, alpha=0.07, color=ep_color, linewidth=0)
    ax_raster.text((t_start + t_end) / 2, len(alarm_types) - 0.1,
                   f"Episode {ep_label}", ha="center", va="bottom",
                   fontsize=8, color=ep_color, fontweight="medium")

ax_raster.set_xlim(0, 24)
ax_raster.set_ylim(-0.7, len(alarm_types) - 0.3)
ax_raster.set_yticks([])
ax_raster.set_xlabel("Time (h)", fontsize=9)
ax_raster.set_xticks([0, 3, 6, 9, 12, 15, 18, 21, 24])
ax_raster.spines[["top", "right", "left"]].set_visible(False)
ax_raster.spines["bottom"].set_color("#cccccc")
ax_raster.set_title("TES alarm event timeline", fontsize=10,
                     fontweight="medium", pad=6)

plt.suptitle("E3 — DigitalSoma threshold event system: 24h continuous monitoring (bovine)",
             fontsize=13, fontweight="medium", y=1.01)

plt.savefig("/mnt/user-data/outputs/exp3_tes_alarms.png", dpi=150,
            bbox_inches="tight", facecolor=fig.get_facecolor())
plt.close()
print("Saved: exp3_tes_alarms.png")
