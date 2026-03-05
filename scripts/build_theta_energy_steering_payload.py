#!/usr/bin/env python3
"""Build DDMarlinPandora steering payload from ECAL/HCAL calibration JSON tables."""

from __future__ import annotations

import argparse
import json

from calibration_lib import combine_ddmarlin_params, load_table_json


def render_python_update_block(params: dict) -> str:
    lines = []
    lines.append("theta_energy_calibration_params = {")
    for key in sorted(params.keys()):
        values = ", ".join([f"\"{v}\"" for v in params[key]])
        lines.append(f"    \"{key}\": [{values}],")
    lines.append("}")
    lines.append("DDMarlinPandora.Parameters.update(theta_energy_calibration_params)")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ecal-calibration", required=True, help="ECAL calibration JSON.")
    parser.add_argument("--hcal-calibration", required=True, help="HCAL calibration JSON.")
    parser.add_argument("--plugin-name", default="ThetaEnergyBinned")
    parser.add_argument("--output-json", help="Write merged DDMarlin parameter payload JSON.")
    parser.add_argument("--output-python", help="Write ready-to-paste python block for steer_reco.py.")
    args = parser.parse_args()

    ecal = load_table_json(args.ecal_calibration)
    hcal = load_table_json(args.hcal_calibration)
    if ecal.domain.upper() != "ECAL":
        raise RuntimeError(f"Expected ECAL domain table, got {ecal.domain}")
    if hcal.domain.upper() != "HCAL":
        raise RuntimeError(f"Expected HCAL domain table, got {hcal.domain}")

    params = combine_ddmarlin_params(ecal, hcal, plugin_name=args.plugin_name)

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(params, f, indent=2, sort_keys=True)
        print(f"Wrote JSON payload: {args.output_json}")

    py_block = render_python_update_block(params)
    if args.output_python:
        with open(args.output_python, "w", encoding="utf-8") as f:
            f.write(py_block)
        print(f"Wrote python payload block: {args.output_python}")
    else:
        print(py_block)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
