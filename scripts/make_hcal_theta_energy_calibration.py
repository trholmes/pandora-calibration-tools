#!/usr/bin/env python3
"""Produce HCAL theta-energy calibration table with ECAL correction fixed."""

from __future__ import annotations

import argparse
import time

from calibration_lib import (
    add_common_args,
    build_table_from_ratios,
    expand_input_paths,
    find_bin,
    find_single_primary,
    flatten_index,
    load_table_json,
    mcp_theta,
    parse_float_list,
    parse_int_list,
    save_table_json,
    setup_lcio_reader,
    sum_collection_energy,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    parser.add_argument("--pdg-ids", default="2112,211,111", help="Comma-separated PDG IDs for HCAL training.")
    parser.add_argument("--mc-collection", default="MCParticle")
    parser.add_argument("--ecal-barrel-collection", default="ECalBarrelCollection")
    parser.add_argument("--ecal-endcap-collection", default="ECalEndcapCollection")
    parser.add_argument("--hcal-barrel-collection", default="HCalBarrelCollection")
    parser.add_argument("--hcal-endcap-collection", default="HCalEndcapCollection")
    parser.add_argument("--ecal-calibration", required=True, help="ECAL calibration JSON from pass A.")
    parser.add_argument(
        "--ecal-lookup-energy",
        choices=["truth", "measured"],
        default="measured",
        help="Energy argument used for ECAL table lookup.",
    )
    parser.add_argument(
        "--hcal-energy-axis",
        choices=["target", "truth", "measured"],
        default="target",
        help="Energy value used for HCAL theta-energy binning.",
    )
    parser.add_argument(
        "--negative-target-policy",
        choices=["skip", "clip0"],
        default="skip",
        help="How to handle E_target_hcal <= 0.",
    )
    parser.add_argument("--output", required=True, help="Output HCAL calibration JSON path.")
    args = parser.parse_args()

    theta_edges = parse_float_list(args.theta_bins)
    energy_edges = parse_float_list(args.energy_bins)
    pdg_ids = parse_int_list(args.pdg_ids)
    files = expand_input_paths(args.inputs, args.file_glob)
    if not files:
        raise RuntimeError("No input files found.")

    ecal_table = load_table_json(args.ecal_calibration)
    n_theta = len(theta_edges) - 1
    n_energy = len(energy_edges) - 1
    ratios_per_bin = [[] for _ in range(n_theta * n_energy)]

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
    events_used = 0
    t0 = time.time()

    for fname in files:
        reader.open(fname)
        for event in reader:
            if args.max_events > 0 and events_total >= args.max_events:
                break
            events_total += 1

            mcp = find_single_primary(
                event.getCollection(args.mc_collection),
                pdg_ids=pdg_ids,
                eta_max=args.eta_max,
                require_single=args.require_single_primary,
            )
            if mcp is None:
                continue

            truth_e = mcp.getEnergy()
            theta = mcp_theta(mcp)
            ecal_measured = (
                sum_collection_energy(event, args.ecal_barrel_collection)
                + sum_collection_energy(event, args.ecal_endcap_collection)
            )
            hcal_measured = (
                sum_collection_energy(event, args.hcal_barrel_collection)
                + sum_collection_energy(event, args.hcal_endcap_collection)
            )
            if hcal_measured <= 0.0:
                continue

            ecal_lookup_energy = truth_e if args.ecal_lookup_energy == "truth" else ecal_measured
            ecal_scale = ecal_table.lookup(theta, ecal_lookup_energy)
            ecal_corrected = ecal_scale * ecal_measured
            target_hcal = truth_e - ecal_corrected
            if target_hcal <= 0.0:
                if args.negative_target_policy == "skip":
                    continue
                target_hcal = 0.0
            if target_hcal <= 0.0:
                continue

            ratio = target_hcal / hcal_measured
            if args.hcal_energy_axis == "target":
                energy_axis_value = target_hcal
            elif args.hcal_energy_axis == "truth":
                energy_axis_value = truth_e
            else:
                energy_axis_value = hcal_measured

            i_theta = find_bin(theta_edges, theta)
            i_energy = find_bin(energy_edges, energy_axis_value)
            if i_theta < 0 or i_energy < 0:
                continue
            ratios_per_bin[flatten_index(i_theta, i_energy, n_energy)].append(ratio)
            events_used += 1
        reader.close()
        if args.max_events > 0 and events_total >= args.max_events:
            break

    table = build_table_from_ratios(
        domain="HCAL",
        theta_edges=theta_edges,
        energy_edges=energy_edges,
        ratios_per_bin=ratios_per_bin,
        min_bin_count=args.min_bin_count,
        estimator=args.estimator,
        trim_fraction=args.trim_fraction,
        metadata={
            "created_unix": int(time.time()),
            "files": len(files),
            "events_total": events_total,
            "events_used": events_used,
            "pdg_ids": pdg_ids,
            "mc_collection": args.mc_collection,
            "ecal_collections": [args.ecal_barrel_collection, args.ecal_endcap_collection],
            "hcal_collections": [args.hcal_barrel_collection, args.hcal_endcap_collection],
            "ecal_calibration": args.ecal_calibration,
            "ecal_lookup_energy": args.ecal_lookup_energy,
            "hcal_energy_axis": args.hcal_energy_axis,
            "negative_target_policy": args.negative_target_policy,
            "runtime_sec": round(time.time() - t0, 3),
        },
    )
    save_table_json(table, args.output)
    print(f"Wrote HCAL calibration table: {args.output}")
    print(f"Events total/used: {events_total}/{events_used}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
