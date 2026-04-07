"""
Experiment 1 — Ontology alias resolution and JSON-LD export.

Tests that DigitalSoma correctly resolves device-specific aliases from
bovine, ovine, and equine sensor vocabularies to canonical keys, and
that the JSON-LD export carries valid Uberon / SNOMED / VeDDRA URIs.

Output: two-panel matplotlib figure
  Panel A — alias resolution pass/fail heatmap across three species
  Panel B — JSON-LD URI namespace breakdown pie chart
"""

import sys
sys.path.insert(0, "/home/claude")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from digitalsoma.ontology.vocab import canonical_key, normalise_dict, to_jsonld

# ── Alias test cases per species ────────────────────────────────────────────

TESTS = {
    "Bovine": [
        ("HR",              "heart_rate_bpm"),
        ("Tb",              "core_temp_C"),
        ("RR",              "respiratory_rate_bpm"),
        ("SpO2",            "spo2_pct"),
        ("BW",              "body_mass_kg"),
        ("glucose",         "blood_glucose_mmol_L"),
        ("cortisol",        "cortisol_nmol_L"),
        ("SBP",             "systolic_bp_mmHg"),
        ("accel",           "acceleration_m_s2"),
        ("lying_time",      "lying_time_min"),
    ],
    "Ovine": [
        ("heart_rate",      "heart_rate_bpm"),
        ("core_temp",       "core_temp_C"),
        ("breaths_per_min", "respiratory_rate_bpm"),
        ("oxygen_saturation","spo2_pct"),
        ("live_weight",     "body_mass_kg"),
        ("BloodGlucose",    "blood_glucose_mmol_L"),
        ("CORT",            "cortisol_nmol_L"),
        ("DBP",             "diastolic_bp_mmHg"),
        ("ACC",             "acceleration_m_s2"),
        ("HCT",             "haematocrit_pct"),
    ],
    "Equine": [
        ("ECG_HR",          "heart_rate_bpm"),
        ("rectal_temp",     "core_temp_C"),
        ("BreathRate",      "respiratory_rate_bpm"),
        ("pulse_ox",        "spo2_pct"),
        ("weight",          "body_mass_kg"),
        ("BGlucose",        "blood_glucose_mmol_L"),
        ("Cortisol",        "cortisol_nmol_L"),
        ("MAP",             "mean_arterial_pressure_mmHg"),
        ("activity",        "activity_counts"),
        ("Hb",              "haemoglobin_g_dL"),
    ],
}

# ── JSON-LD URI namespace check ──────────────────────────────────────────────

sample_state = {
    "heart_rate_bpm": 60, "core_temp_C": 38.5, "spo2_pct": 98.0,
    "respiratory_rate_bpm": 20, "blood_glucose_mmol_L": 4.2,
    "cortisol_nmol_L": 30.0, "body_mass_kg": 600.0,
    "systolic_bp_mmHg": 130, "diastolic_bp_mmHg": 85,
    "mean_arterial_pressure_mmHg": 100, "haematocrit_pct": 35.0,
    "haemoglobin_g_dL": 12.0, "acceleration_m_s2": 0.2,
    "adverse_event_score": 0.0,
}
doc = to_jsonld(sample_state)
ctx = doc["@context"]

namespace_counts = {"OBO (Uberon/CMO/PATO)": 0, "SNOMED CT": 0, "VeDDRA": 0, "Other": 0}
for key in sample_state:
    uri = ctx.get(key, {}).get("@id", "")
    if "snomed.info" in uri:
        namespace_counts["SNOMED CT"] += 1
    elif "ema.europa.eu" in uri:
        namespace_counts["VeDDRA"] += 1
    elif "purl.obolibrary.org" in uri:
        namespace_counts["OBO (Uberon/CMO/PATO)"] += 1
    else:
        namespace_counts["Other"] += 1

# ── Build result matrix ──────────────────────────────────────────────────────

species = list(TESTS.keys())
aliases = [a for a, _ in TESTS["Bovine"]]   # same positions across species
results = np.zeros((len(species), len(aliases)))

for si, sp in enumerate(species):
    for ai, (alias, expected) in enumerate(TESTS[sp]):
        results[si, ai] = 1 if canonical_key(alias) == expected else 0

total = int(results.sum())
total_tests = results.size
print(f"E1 alias resolution: {total}/{total_tests} PASS")

# ── Plot ─────────────────────────────────────────────────────────────────────

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
fig.patch.set_facecolor("#fafaf8")

# Panel A — heatmap
ax = axes[0]
ax.set_facecolor("#f4f3ee")
im = ax.imshow(results, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1, interpolation="none")

ax.set_yticks(range(len(species)))
ax.set_yticklabels(species, fontsize=11)
ax.set_xticks(range(len(aliases)))
ax.set_xticklabels([a for a, _ in TESTS["Bovine"]], rotation=40, ha="right", fontsize=9)

for si in range(len(species)):
    for ai in range(len(aliases)):
        alias_for_species = TESTS[species[si]][ai][0]
        label = "✓" if results[si, ai] == 1 else "✗"
        ax.text(ai, si, label, ha="center", va="center",
                fontsize=11, color="white" if results[si, ai] == 1 else "#8b0000",
                fontweight="bold")

ax.set_title(f"Alias resolution — {total}/{total_tests} PASS", fontsize=12, pad=12, fontweight="medium")
ax.set_xlabel("Sensor alias", fontsize=10)
ax.set_ylabel("Species", fontsize=10)

pass_patch  = mpatches.Patch(color="#4dac26", label="PASS")
fail_patch  = mpatches.Patch(color="#d01c8b", label="FAIL")
ax.legend(handles=[pass_patch, fail_patch], loc="lower right", fontsize=9)

# Panel B — namespace pie
ax2 = axes[1]
ax2.set_facecolor("#f4f3ee")
labels = [k for k, v in namespace_counts.items() if v > 0]
sizes  = [v for v in namespace_counts.values() if v > 0]
colors = ["#5DCAA5", "#7F77DD", "#D85A30", "#888780"][:len(labels)]
wedges, texts, autotexts = ax2.pie(
    sizes, labels=labels, colors=colors,
    autopct="%1.0f%%", startangle=140,
    textprops={"fontsize": 10},
    wedgeprops={"linewidth": 0.8, "edgecolor": "white"},
)
for at in autotexts:
    at.set_fontsize(9)
    at.set_color("white")
    at.set_fontweight("bold")

ax2.set_title("JSON-LD URI namespaces", fontsize=12, pad=12, fontweight="medium")

plt.suptitle("E1 — DigitalSoma ontology compliance", fontsize=13, fontweight="medium", y=1.01)
plt.tight_layout()
plt.savefig("/mnt/user-data/outputs/exp1_ontology.png", dpi=150, bbox_inches="tight",
            facecolor=fig.get_facecolor())
plt.close()
print("Saved: exp1_ontology.png")
