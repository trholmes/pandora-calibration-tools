#!/usr/bin/env python3
"""Validate ECAL/HCAL theta-energy calibration tables with closure summaries."""

from __future__ import annotations

import argparse
import json
import statistics
import time

from calibration_lib import (
    expand_input_paths,
    find_single_primary,
    load_table_json,
    mcp_theta,
    parse_int_list,
    setup_lcio_reader,
    sum_collection_energy,
)


def summarize(values):
    if not values:
        return {"n": 0, "mean": None, "median": None, "stdev": None}
    return {
        "n": len(values),
        "mean": sum(values) / float(len(values)),
        "median": statistics.median(values),
        "stdev": statistics.pstdev(values),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--file-glob", default="*.slcio")
    parser.add_argument("--max-events", type=int, default=-1)
    parser.add_argument("--eta-max", type=float, default=2.436)
    parser.add_argument("--require-single-primary", action="store_true")
    parser.add_argument("--mc-collection", default="MCParticle")
    parser.add_argument("--ecal-barrel-collection", default="ECalBarrelCollection")
    parser.add_argument("--ecal-endcap-collection", default="ECalEndcapCollection")
    parser.add_argument("--hcal-barrel-collection", default="HCalBarrelCollection")
    parser.add_argument("--hcal-endcap-collection", default="HCalEndcapCollection")
    parser.add_argument("--ecal-pdg-ids", default="22")
    parser.add_argument("--hcal-pdg-ids", default="2112,211,111")
    parser.add_argument("--ecal-calibration", required=True)
    parser.add_argument("--hcal-calibration", required=True)
    parser.add_argument("--output", required=True, help="Output JSON summary")
    args = parser.parse_args()

    files = expand_input_paths(args.inputs, args.file_glob)
    if not files:
        raise RuntimeError("No input files found.")

    ecal_table = load_table_json(args.ecal_calibration)
    hcal_table = load_table_json(args.hcal_calibration)
    ecal_pdgs = parse_int_list(args.ecal_pdg_ids)
    hcal_pdgs = parse_int_list(args.hcal_pdg_ids)

    reader = setup_lcio_reader(
        [
            args.mc_collection,
            args.ecal_barrel_collection,
            args.ecal_endcap_collection,
            args.hcal_barrel_collection,
            args.hcal_endcap_collection,
        ]
    )

    events_total = 0
    ecal_closure = []
    hcal_closure = []
    total_closure = []
    t0 = time.time()

    for fname in files:
        reader.open(fname)
        for event in reader:
            if args.max_events > 0 and events_total >= args.max_events:
                break
            events_total += 1

            ecal_measured = (
                sum_collection_energy(event, args.ecal_barrel_collection)
                + sum_collection_energy(event, args.ecal_endcap_collection)
            )
            hcal_measured = (
                sum_collection_energy(event, args.hcal_barrel_collection)
                + sum_collection_energy(event, args.hcal_endcap_collection)
            )

            mcp_ecal = find_single_primary(
                event.getCollection(args.mc_collection),
                pdg_ids=ecal_pdgs,
                eta_max=args.eta_max,
                require_single=args.require_single_primary,
            )
            if mcp_ecal is not None and ecal_measured > 0.0:
                truth_e = mcp_ecal.getEnergy()
                theta = mcp_theta(mcp_ecal)
                ecal_corr = ecal_table.lookup(theta, truth_e) * ecal_measured
                if ecal_corr > 0.0:
                    ecal_closure.append(truth_e / ecal_corr)

            mcp_hcal = find_single_primary(
                event.getCollection(args.mc_collection),
                pdg_ids=hcal_pdgs,
                eta_max=args.eta_max,
                require_single=args.require_single_primary,
            )
            if mcp_hcal is not None and hcal_measured > 0.0:
                truth_e = mcp_hcal.getEnergy()
                theta = mcp_theta(mcp_hcal)
                ecal_corr = ecal_table.lookup(theta, truth_e) * ecal_measured
                target_hcal = truth_e - ecal_corr
                if target_hcal > 0.0:
                    hcal_corr = hcal_table.lookup(theta, target_hcal) * hcal_measured
                    if hcal_corr > 0.0:
                        hcal_closure.append(target_hcal / hcal_corr)
                total_corr = ecal_corr + hcal_table.lookup(theta, truth_e) * hcal_measured
                if total_corr > 0.0:
                    total_closure.append(truth_e / total_corr)
        reader.close()
        if args.max_events > 0 and events_total >= args.max_events:
            break

    summary = {
        "created_unix": int(time.time()),
        "runtime_sec": round(time.time() - t0, 3),
        "events_total": events_total,
        "files": len(files),
        "ecal_closure_truth_over_corrected": summarize(ecal_closure),
        "hcal_closure_target_over_corrected": summarize(hcal_closure),
        "total_closure_truth_over_corrected": summarize(total_closure),
        "inputs": {
            "ecal_calibration": args.ecal_calibration,
            "hcal_calibration": args.hcal_calibration,
            "ecal_pdg_ids": ecal_pdgs,
            "hcal_pdg_ids": hcal_pdgs,
        },
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    print(f"Wrote validation summary: {args.output}")
    print(json.dumps(summary["ecal_closure_truth_over_corrected"], indent=2))
    print(json.dumps(summary["hcal_closure_target_over_corrected"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
