"""
Experiment 4 — VeDDRA adverse event detection and reporting.

Simulates a post-vaccination monitoring scenario across three species,
where a hypothetical drug reaction causes a progressive physiological
response that DigitalSoma detects and encodes in VeDDRA terms.

Scenario: 16-step post-administration monitoring window
  Phase 1 (t=0–3)   — baseline (pre-administration)
  Phase 2 (t=4–8)   — early reaction (fever onset, HR elevation)
  Phase 3 (t=9–12)  — peak reaction (hyperthermia, tachycardia, hypoxia)
  Phase 4 (t=13–15) — resolution / recovery

Plotted as a 4-panel dashboard:
  Panel A — adverse event score progression (all three species)
  Panel B — VeDDRA flag counts per species per phase
  Panel C — physiological stress index trajectory
  Panel D — VeDDRA clinical sign breakdown (stacked bar, peak phase)
"""

import sys
sys.path.insert(0, "/home/claude")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

from digitalsoma import build_soma, SomaConfig

# ── Scenario per species ──────────────────────────────────────────────────────
# (core_temp_C, heart_rate_bpm, respiratory_rate_bpm, spo2_pct)

SCENARIOS = {
    "Bovine": {
        "animal_type": "bovine_adult",
        "color": "#D85A30",
        "steps": [
            # Baseline
            (38.5, 60,  20, 98.5), (38.5, 61,  20, 98.4),
            (38.6, 62,  21, 98.3), (38.5, 60,  20, 98.5),
            # Early reaction
            (39.0, 68,  24, 98.0), (39.4, 74,  28, 97.6),
            (39.8, 82,  33, 97.2), (40.1, 90,  38, 96.8),
            (40.4, 98,  44, 96.2),
            # Peak reaction
            (40.8, 108, 50, 95.5), (41.0, 114, 55, 94.8),
            (41.2, 118, 58, 94.0), (41.0, 112, 54, 94.5),
            # Recovery
            (40.2, 92,  40, 96.0), (39.4, 74,  26, 97.5),
            (38.7, 63,  21, 98.2),
        ],
    },
    "Ovine": {
        "animal_type": "ovine_adult",
        "color": "#7F77DD",
        "steps": [
            (39.0, 75,  24, 98.0), (39.0, 76,  24, 97.9),
            (39.1, 77,  25, 97.8), (39.0, 75,  24, 98.0),
            (39.5, 85,  30, 97.5), (39.9, 95,  36, 97.0),
            (40.3, 106, 44, 96.4), (40.7, 115, 50, 95.8),
            (41.0, 124, 56, 95.0),
            (41.4, 132, 62, 94.0), (41.6, 138, 66, 93.2),
            (41.8, 140, 68, 92.5), (41.5, 134, 63, 93.5),
            (40.6, 108, 46, 95.5), (39.8, 88,  32, 97.2),
            (39.1, 77,  25, 97.9),
        ],
    },
    "Equine": {
        "animal_type": "equine_adult",
        "color": "#1D9E75",
        "steps": [
            (37.8, 36,  12, 98.5), (37.8, 37,  12, 98.4),
            (37.9, 38,  13, 98.3), (37.8, 36,  12, 98.5),
            (38.3, 48,  16, 98.0), (38.7, 58,  20, 97.6),
            (39.1, 70,  26, 97.2), (39.5, 82,  32, 96.7),
            (39.8, 94,  38, 96.0),
            (40.2, 108, 44, 95.2), (40.5, 116, 50, 94.5),
            (40.8, 122, 54, 93.8), (40.4, 114, 48, 94.5),
            (39.6, 88,  32, 96.5), (38.9, 64,  20, 97.8),
            (37.9, 40,  13, 98.4),
        ],
    },
}

phases = {
    "Baseline":    (0,  3),
    "Early":       (4,  8),
    "Peak":        (9,  12),
    "Recovery":    (13, 15),
}
phase_colors = {"Baseline": "#9FE1CB", "Early": "#FAC775",
                "Peak": "#F09595",     "Recovery": "#B5D4F4"}
t_labels = [f"t{i}" for i in range(16)]

# ── Run all scenarios ─────────────────────────────────────────────────────────

results = {}
for species, cfg in SCENARIOS.items():
    ds = build_soma(SomaConfig(animal_type=cfg["animal_type"]))
    ae_scores, psi_scores, ae_flag_counts = [], [], []
    veddra_terms_peak = {}

    for i, (temp, hr, rr, spo2) in enumerate(cfg["steps"]):
        state = ds.update_sync({
            "core_temp_C":          temp,
            "heart_rate_bpm":       hr,
            "respiratory_rate_bpm": rr,
            "spo2_pct":             spo2,
        })
        ae_scores.append(state.get("adverse_event_score", 0))
        psi_scores.append(state.get("physiological_stress_index", 0))
        ae_flag_counts.append(len(state.get("ae_flags", [])))

        if 9 <= i <= 12:
            for flag in state.get("ae_flags", []):
                term = flag["veddra_term"]
                veddra_terms_peak[term] = veddra_terms_peak.get(term, 0) + 1

    results[species] = {
        "ae_scores":       ae_scores,
        "psi_scores":      psi_scores,
        "ae_flag_counts":  ae_flag_counts,
        "veddra_peak":     veddra_terms_peak,
        "color":           cfg["color"],
    }

# ── VeDDRA peak breakdown ─────────────────────────────────────────────────────
all_veddra_terms = sorted({
    term for sp in results.values()
    for term in sp["veddra_peak"]
})

# ── Plot ──────────────────────────────────────────────────────────────────────

fig = plt.figure(figsize=(16, 11))
fig.patch.set_facecolor("#fafaf8")
gs = gridspec.GridSpec(2, 2, hspace=0.48, wspace=0.35)

x = np.arange(16)

# ── Panel A: AE score progression ────────────────────────────────────────────
ax_a = fig.add_subplot(gs[0, 0])
ax_a.set_facecolor("#f4f3ee")

for p_label, (p_start, p_end) in phases.items():
    ax_a.axvspan(p_start - 0.5, p_end + 0.5, alpha=0.12,
                 color=phase_colors[p_label], linewidth=0)
    mid = (p_start + p_end) / 2
    ax_a.text(mid, 1.02, p_label, ha="center", va="bottom",
              fontsize=7.5, color="#555", transform=ax_a.get_xaxis_transform())

for species, res in results.items():
    ax_a.plot(x, res["ae_scores"], color=res["color"], linewidth=2,
              marker="o", markersize=4, markerfacecolor="white",
              markeredgecolor=res["color"], markeredgewidth=1.2, label=species)
    ax_a.fill_between(x, res["ae_scores"], alpha=0.08, color=res["color"])

ax_a.axhline(0.5, color="#A32D2D", linewidth=0.7, linestyle="--", alpha=0.6)
ax_a.text(15.2, 0.51, "alert", fontsize=7, color="#A32D2D", va="bottom")
ax_a.set_xlim(-0.5, 15.5); ax_a.set_ylim(0, 1.1)
ax_a.set_xticks(x); ax_a.set_xticklabels(t_labels, rotation=45, ha="right", fontsize=7)
ax_a.set_ylabel("Adverse event score", fontsize=9)
ax_a.set_title("VeDDRA adverse event score", fontsize=10, fontweight="medium", pad=8)
ax_a.legend(fontsize=8, framealpha=0.7)
ax_a.spines[["top","right"]].set_visible(False)
ax_a.spines[["left","bottom"]].set_color("#cccccc")
ax_a.grid(axis="y", linewidth=0.3, color="#dddddd")

# ── Panel B: VeDDRA flag counts per phase ─────────────────────────────────────
ax_b = fig.add_subplot(gs[0, 1])
ax_b.set_facecolor("#f4f3ee")

species_list = list(results.keys())
n_species = len(species_list)
n_phases  = len(phases)
bar_w = 0.22
phase_list = list(phases.keys())

for pi, p_label in enumerate(phase_list):
    p_start, p_end = phases[p_label]
    for si, species in enumerate(species_list):
        counts = results[species]["ae_flag_counts"]
        avg_flags = np.mean(counts[p_start:p_end + 1])
        xpos = pi + (si - 1) * bar_w
        ax_b.bar(xpos, avg_flags, width=bar_w,
                 color=results[species]["color"], alpha=0.85,
                 linewidth=0.5, edgecolor="white")

ax_b.set_xticks(range(n_phases))
ax_b.set_xticklabels(phase_list, fontsize=9)
ax_b.set_ylabel("Mean VeDDRA flags fired", fontsize=9)
ax_b.set_title("VeDDRA flag counts per phase", fontsize=10,
               fontweight="medium", pad=8)

handles = [plt.Rectangle((0,0),1,1, color=results[sp]["color"], alpha=0.85)
           for sp in species_list]
ax_b.legend(handles, species_list, fontsize=8, framealpha=0.7)
ax_b.spines[["top","right"]].set_visible(False)
ax_b.spines[["left","bottom"]].set_color("#cccccc")
ax_b.grid(axis="y", linewidth=0.3, color="#dddddd")

# ── Panel C: Physiological stress index ───────────────────────────────────────
ax_c = fig.add_subplot(gs[1, 0])
ax_c.set_facecolor("#f4f3ee")

for p_label, (p_start, p_end) in phases.items():
    ax_c.axvspan(p_start - 0.5, p_end + 0.5, alpha=0.12,
                 color=phase_colors[p_label], linewidth=0)

for species, res in results.items():
    ax_c.plot(x, res["psi_scores"], color=res["color"], linewidth=2,
              marker="s", markersize=3.5, markerfacecolor="white",
              markeredgecolor=res["color"], markeredgewidth=1.2, label=species)

ax_c.axhline(0.7, color="#7F77DD", linewidth=0.7, linestyle="--", alpha=0.6)
ax_c.text(15.2, 0.71, "high", fontsize=7, color="#7F77DD", va="bottom")
ax_c.set_xlim(-0.5, 15.5); ax_c.set_ylim(0, 1.05)
ax_c.set_xticks(x); ax_c.set_xticklabels(t_labels, rotation=45, ha="right", fontsize=7)
ax_c.set_ylabel("Physiological stress index", fontsize=9)
ax_c.set_title("Physiological stress index", fontsize=10, fontweight="medium", pad=8)
ax_c.legend(fontsize=8, framealpha=0.7)
ax_c.spines[["top","right"]].set_visible(False)
ax_c.spines[["left","bottom"]].set_color("#cccccc")
ax_c.grid(axis="y", linewidth=0.3, color="#dddddd")

# ── Panel D: VeDDRA clinical sign breakdown — peak phase ─────────────────────
ax_d = fig.add_subplot(gs[1, 1])
ax_d.set_facecolor("#f4f3ee")

if all_veddra_terms:
    bar_w2 = 0.25
    veddra_colors = ["#D85A30","#7F77DD","#1D9E75","#BA7517","#A32D2D"]

    for si, species in enumerate(species_list):
        peak_counts = [results[species]["veddra_peak"].get(t, 0)
                       for t in all_veddra_terms]
        x_terms = np.arange(len(all_veddra_terms))
        xpos = x_terms + (si - 1) * bar_w2
        ax_d.bar(xpos, peak_counts, width=bar_w2,
                 color=results[species]["color"], alpha=0.85,
                 linewidth=0.5, edgecolor="white", label=species)

    ax_d.set_xticks(np.arange(len(all_veddra_terms)))
    ax_d.set_xticklabels(all_veddra_terms, rotation=30, ha="right", fontsize=8)
    ax_d.set_ylabel("Event count (peak phase)", fontsize=9)
    ax_d.set_title("VeDDRA clinical signs — peak phase", fontsize=10,
                   fontweight="medium", pad=8)
    ax_d.legend(fontsize=8, framealpha=0.7)
else:
    ax_d.text(0.5, 0.5, "No VeDDRA flags in peak phase",
              ha="center", va="center", transform=ax_d.transAxes, fontsize=10)

ax_d.spines[["top","right"]].set_visible(False)
ax_d.spines[["left","bottom"]].set_color("#cccccc")
ax_d.grid(axis="y", linewidth=0.3, color="#dddddd")

plt.suptitle("E4 — DigitalSoma VeDDRA adverse event detection: post-administration monitoring",
             fontsize=13, fontweight="medium", y=1.01)

plt.savefig("/mnt/user-data/outputs/exp4_veddra.png", dpi=150,
            bbox_inches="tight", facecolor=fig.get_facecolor())
plt.close()
print("Saved: exp4_veddra.png")

# ── Print VeDDRA report for peak bovine state ─────────────────────────────────
ds_bovine = build_soma(SomaConfig(animal_type="bovine_adult"))
ds_bovine.update_sync({"core_temp_C": 41.2, "heart_rate_bpm": 118,
                        "respiratory_rate_bpm": 58, "spo2_pct": 94.0})
report = ds_bovine.veddra_report()
print("\nVeDDRA adverse event report — bovine peak reaction:")
print(f"  Report ID    : {report['report_id']}")
print(f"  Taxa         : {report['taxa']}")
print(f"  AE score     : {report['adverse_event_score']:.3f}")
print(f"  Standard     : {report['reporting_standard']}")
print("  Clinical signs:")
for sign in report["clinical_signs"]:
    print(f"    [{sign['veddra_id']}] {sign['veddra_term']}"
          f"  ({sign['state_key']} = {sign['value']:.3g})")
