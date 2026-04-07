"""
E1. Build and describe a DigitalSoma twin.

Mirrors DP E1 (GPS initialization) — here we initialise from an animal
type template rather than GPS coordinates, producing a fully parameterised
digital twin in a single function call.

Run: python examples/e1_build_and_describe.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from digitalsoma import build_soma, SomaConfig

print("=" * 60)
print("E1. DigitalSoma — build and structural layer inspection")
print("=" * 60)

animal_types = [
    ("bovine_adult",   "Dairy farm, Manitoba"),
    ("ovine_adult",    "Upland farm, Wales"),
    ("canine_adult",   "Veterinary clinic, Leuven"),
    ("salmonid_adult", "Aquaculture pen, Norway"),
    ("equine_adult",   "Equestrian centre, Ghent"),
]

print(f"\n{'Animal type':<20} {'Taxa':<32} {'Mass (kg)':<12} "
      f"{'HR normal':<12} {'Temp normal'}")
print("-" * 90)

for atype, site in animal_types:
    ds = build_soma(SomaConfig(animal_type=atype, site_name=site))
    sl = ds.structural_layer
    temp = sl.get("core_temp_normal_C")
    temp_str = f"{temp:.1f} °C" if temp else "ectotherm"
    print(f"{atype:<20} {sl['taxa']:<32} {sl['body_mass_kg']:<12.1f} "
          f"{sl['hr_normal_bpm']:<12.0f} {temp_str}")

print()
print("Solvers registered in Model Zoo (bovine twin):")
ds_bovine = build_soma(SomaConfig(animal_type="bovine_adult"))
for i, s in enumerate(ds_bovine.solvers, 1):
    print(f"  {i}. {s}")
