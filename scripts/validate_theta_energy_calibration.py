#!/usr/bin/env python3
"""Validate ECAL/HCAL theta-energy calibration tables with closure summaries."""

from __future__ import annotations

import argparse
from array import array
import json
import os
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


def _make_root_hist2(name, title, x_edges, y_edges):
    import ROOT  # type: ignore

    return ROOT.TH2F(
        name,
        title,
        len(x_edges) - 1,
        array("d", x_edges),
        len(y_edges) - 1,
        array("d", y_edges),
    )


def _make_root_hist1(name, title, x_edges):
    import ROOT  # type: ignore

    return ROOT.TH1F(name, title, len(x_edges) - 1, array("d", x_edges))


def _plot_table(table, out_dir):
    import ROOT  # type: ignore

    ROOT.gROOT.SetBatch(True)
    ROOT.gStyle.SetOptStat(0)
    os.makedirs(out_dir, exist_ok=True)

    n_theta = len(table.theta_edges) - 1
    n_energy = len(table.energy_edges) - 1
    tag = table.domain.lower()

    h_scale = _make_root_hist2(
        f"{tag}_scale_map",
        f"{table.domain} calibration scale;theta [rad];energy [GeV]",
        table.theta_edges,
        table.energy_edges,
    )
    h_count = _make_root_hist2(
        f"{tag}_count_map",
        f"{table.domain} calibration bin counts;theta [rad];energy [GeV]",
        table.theta_edges,
        table.energy_edges,
    )

    h_theta_mean = _make_root_hist1(
        f"{tag}_theta_mean_scale",
        f"{table.domain} mean scale vs theta;theta [rad];scale",
        table.theta_edges,
    )
    h_theta_weighted = _make_root_hist1(
        f"{tag}_theta_weighted_scale",
        f"{table.domain} count-weighted scale vs theta;theta [rad];scale",
        table.theta_edges,
    )

    for i_theta in range(n_theta):
        weighted_sum = 0.0
        count_sum = 0.0
        mean_sum = 0.0
        for i_energy in range(n_energy):
            idx = i_theta * n_energy + i_energy
            scale = table.scales[idx]
            count = table.counts[idx]
            h_scale.SetBinContent(i_theta + 1, i_energy + 1, scale)
            h_count.SetBinContent(i_theta + 1, i_energy + 1, count)
            mean_sum += scale
            weighted_sum += scale * count
            count_sum += count
        h_theta_mean.SetBinContent(i_theta + 1, mean_sum / float(n_energy))
        if count_sum > 0:
            h_theta_weighted.SetBinContent(i_theta + 1, weighted_sum / count_sum)
        else:
            h_theta_weighted.SetBinContent(i_theta + 1, 1.0)

    root_path = os.path.join(out_dir, f"{tag}_calibration_plots.root")
    fout = ROOT.TFile(root_path, "RECREATE")
    for h in (h_scale, h_count, h_theta_mean, h_theta_weighted):
        h.Write()
    fout.Close()

    c1 = ROOT.TCanvas(f"c_{tag}_scale", "", 900, 700)
    c1.SetRightMargin(0.15)
    h_scale.Draw("COLZ")
    c1.SaveAs(os.path.join(out_dir, f"{tag}_scale_map.png"))

    c2 = ROOT.TCanvas(f"c_{tag}_count", "", 900, 700)
    c2.SetRightMargin(0.15)
    c2.SetLogz()
    h_count.Draw("COLZ")
    c2.SaveAs(os.path.join(out_dir, f"{tag}_count_map.png"))

    c3 = ROOT.TCanvas(f"c_{tag}_theta", "", 900, 700)
    h_theta_weighted.SetLineColor(ROOT.kBlue + 1)
    h_theta_weighted.SetLineWidth(3)
    h_theta_weighted.Draw("HIST")
    h_theta_mean.SetLineColor(ROOT.kRed + 1)
    h_theta_mean.SetLineWidth(2)
    h_theta_mean.SetLineStyle(2)
    h_theta_mean.Draw("HIST SAME")
    leg = ROOT.TLegend(0.58, 0.76, 0.89, 0.89)
    leg.AddEntry(h_theta_weighted, "weighted mean", "l")
    leg.AddEntry(h_theta_mean, "simple mean", "l")
    leg.Draw()
    c3.SaveAs(os.path.join(out_dir, f"{tag}_theta_profiles.png"))

    return {
        "root": root_path,
        "scale_map_png": os.path.join(out_dir, f"{tag}_scale_map.png"),
        "count_map_png": os.path.join(out_dir, f"{tag}_count_map.png"),
        "theta_profiles_png": os.path.join(out_dir, f"{tag}_theta_profiles.png"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--file-glob", default="*.slcio")
    parser.add_argument("--recursive", action="store_true")
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
    parser.add_argument(
        "--plot-dir",
        default="",
        help="If set, write ECAL/HCAL calibration plots (.png + .root) to this directory.",
    )
    args = parser.parse_args()

    files = expand_input_paths(args.inputs, args.file_glob, recursive=args.recursive)
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

    if args.plot_dir:
        summary["plot_outputs"] = {
            "ecal": _plot_table(ecal_table, args.plot_dir),
            "hcal": _plot_table(hcal_table, args.plot_dir),
        }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    print(f"Wrote validation summary: {args.output}")
    print(json.dumps(summary["ecal_closure_truth_over_corrected"], indent=2))
    print(json.dumps(summary["hcal_closure_target_over_corrected"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
