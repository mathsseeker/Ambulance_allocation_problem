"""Prepare all processed data and generated instances.

Run from the project root:
    python scripts/prepare_data.py                 # uses config/default.yaml
    python scripts/prepare_data.py --config my.yaml
Steps follow docs/data_guide.md ("Preparing the data").
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ambulance.data import loader, prepare  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config" / "default.yaml"))
    cfg = yaml.safe_load(Path(ap.parse_args().config).read_text())

    raw = ROOT / cfg["raw_file"]
    processed = ROOT / cfg["processed_dir"]
    period, T = cfg["period"], cfg["T"]

    # Step 2: areas and d_v (shared by all cases)
    areas = prepare.build_areas(raw)
    assert abs(areas["d_v"].sum() - 1) < 1e-12, "d_v must sum to 1"
    processed.mkdir(parents=True, exist_ok=True)
    loader.read_fleet_options(raw).to_csv(processed / "fleet_options_table8.csv", index=False)
    print(f"areas: {len(areas)}, population {areas['population'].sum():,}, sum d_v = {areas['d_v'].sum():.6f}")

    for case in cfg["cases"]:
        # Steps 1 and 3: bases, travel times, a_jv
        cd = prepare.load_case(raw, case, areas)
        s = prepare.write_case(cd, processed, period, T, cfg["T_sensitivity"])
        print(f"\ncase {case}: {s['n_bases']} bases | T={T}: {s['areas_without_base_within_T']} areas "
              f"have no base within T ({1 - s['demand_share_covered']:.1%} of demand)")
        for row in s["coverage_by_T"]:
            print(f"   T={row['T']:>3}: uncovered areas {row['areas_uncovered']:>3}, demand covered {row['demand_covered']:.1%}")

    print("\nAmbulance states are generated on the fly: see src/ambulance/instance.py")


if __name__ == "__main__":
    main()
