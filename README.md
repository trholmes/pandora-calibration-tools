# pandora-calibration-tools

Standalone tools for producing Pandora theta-energy calibration payloads and diagnostic plots for the MAIA reconstruction workflow.

The current workflow targets the `v2.11` MAIA setup and the calibration branches in:

- `trholmes/LCContent`: `codex/photon-em-nonlinearity`
- `trholmes/DDMarlinPandora`: `codex/photon-em-theta-energy`
- `trholmes/SteeringMacros`: `codex/photon-em-steering`
- `trholmes/pandora-calibration-tools`: `codex/photon-em-payload`

The logical workflow is:

1. Use reconstructed single-particle samples to create calibration factors with this repository.
2. Use the matching runtime branches above to apply those calibrations during reconstruction.
3. Use switches in `PandoraSettingsDefault.xml` to control whether corrected energies are used in selected internal decisions, such as cluster merging and the E/p comparison in ElectronID (output energies are always calibrated if you hand reconstruction the payload files).

If you just want to **use** existing calibrations, you only need [Ready-to-use calibrations](#ready-to-use-calibrations) and [Applying calibrations in reconstruction](#applying-calibrations-in-reconstruction). If you want to **make or improve** calibrations, see [Producing calibration factors](#producing-calibration-factors).

## Ready-to-use calibrations

The latest calibration payloads live in `calib/` and are ready to pass to `k4run`:

| File | Made from | Use for |
|---|---|---|
| `calib/photon_em_calib_payload_final.json` | Photon gun samples, E = 0–5000 GeV (v6 central production + dedicated transition-region samples) | EM (photon/electron) energy correction |
| `calib/hadronic_calib_payload_Final.json` | Pion gun samples, E = 0–5000 GeV | Hadronic energy correction |

The intermediate calibration tables and closure summaries used to build these are also in `calib/` (`ecal_theta_energy_calib_final.json`, `hadronic_theta_energy_calib_Final.json`, `ecal_closure_summary_final.json`, `hadronic_closure_summary_Final.json`).

**How they were made:** the EM table was derived from single photons (PDG 22) in the Pandora EM energy basis, using the v6 central photon gun productions (E = 0–5000 GeV) plus dedicated samples generated in the barrel/endcap transition region, with theta bins refined around the transition. The hadronic table was derived from single charged pions (PDG 211) in the Pandora hadronic energy basis, using pion gun samples spanning 0–5000 GeV. Both were produced with the workflow in [Producing calibration factors](#producing-calibration-factors), using the bin edges shown there.

## Applying calibrations in reconstruction

### 1) Enter the container

The `-B /ospool/...:/data` bind mounts the central sample area. If you are only running over your own samples in `/scratch`, you can drop that line.

```bash
apptainer run \
  -B /ospool/uc-shared/project/futurecolliders/data/:/data \
  -B /scratch:/scratch \
  /cvmfs/unpacked.cern.ch/ghcr.io/muoncollidersoft/mucoll-sim-ubuntu24:v2.11-amd64
```

### 2) Point the runtime at the local builds

The calibration-aware code lives in local builds of `LCContent` and `DDMarlinPandora` (see [Set up from scratch](#set-up-from-scratch) if you don't have these built yet). Before running `k4run`, put those builds first in the library search path:

```bash
export MUCOL_BASE="/scratch/<user>/mucol/v2.11"    # your software area
export LD_LIBRARY_PATH="${MUCOL_BASE}/LCContent/install/lib:${MUCOL_BASE}/DDMarlinPandora/install/lib:${LD_LIBRARY_PATH}"
export MARLIN_DLL="${MUCOL_BASE}/DDMarlinPandora/install/lib/libDDMarlinPandora.so:${MARLIN_DLL}"
```

The container environment may already contain a stale `DDMarlinPandora` entry in `MARLIN_DLL`. Only your local build should be loaded, so check for duplicates:

```bash
echo "$MARLIN_DLL" | tr ':' '\n'
```

You should see exactly one `libDDMarlinPandora.so`, pointing at `${MUCOL_BASE}/DDMarlinPandora/install/lib/`. If a second (container-default or relative-path) entry appears, strip it:

```bash
export MARLIN_DLL=$(python3 -c "import os; print(':'.join(p for p in os.environ['MARLIN_DLL'].split(':') if 'DDMarlinPandora' not in p or p.startswith('${MUCOL_BASE}')))")
```

### 3) Run `k4run` with the payloads

```bash
k4run "${MUCOL_BASE}/SteeringMacros/k4Reco/steer_reco.py" \
  --code "${MUCOL_BASE}" \
  --data "${MUCOL_BASE}" \
  --TypeEvent <sample_tag> \
  --InFileName 0 \
  --inputFile /path/to/your_sim_file.slcio \
  --outputFile /path/to/your_output_reco.slcio \
  --photonEMCalibPayload "${MUCOL_BASE}/pandora-calibration-tools/calib/photon_em_calib_payload_final.json" \
  --hadronicCalibPayload "${MUCOL_BASE}/pandora-calibration-tools/calib/hadronic_calib_payload_Final.json"
```

Notes on the steering arguments:

- `--inputFile` / `--outputFile`: point these at your own simulated `.slcio` file and wherever you want the reconstructed output written. For example: `--inputFile ${MUCOL_BASE}/sim/electronGun_pT_0_50/electronGun_pT_0_50_sim_0.slcio --outputFile ${MUCOL_BASE}/reco/electronGun_pT_0_50/electronGun_pT_0_50_reco_newcalib_0.slcio`.
- `--TypeEvent` is a sample tag used to auto-build file paths (e.g. `electronGun_pT_0_50`). If you do **not** pass `--inputFile`/`--outputFile`, the macro reads `{data}/sim/{TypeEvent}/{TypeEvent}_sim_{InFileName}.slcio` and writes `{data}/reco/{TypeEvent}/{TypeEvent}_reco_{InFileName}.slcio`. If you pass explicit input/output files (as above), `--TypeEvent` only affects the lctuple output name.
- The example above uses the shipped final payloads; if you made your own (see [Producing calibration factors](#producing-calibration-factors)), point the flags at your own payload files instead.
- Both payloads should be passed for standard reconstruction — each one only enables its own correction, and omitting one leaves that energy scale uncalibrated. Passing a single payload is only appropriate for dedicated studies of one correction in isolation.

### 4) Check the log

You should see all of the following, otherwise the calibration is not active:

1. From the steering macro, one line per payload you passed:
   - `Loaded photon EM calibration payload: <path>`
   - `Loaded hadronic calibration payload: <path>`
2. In the Marlin processor parameter dump for `DDPandoraPFANewProcessor`, the correction parameters set from the payloads:
   - `ElectromagneticThetaEnergyCorrectionEnabled` = `true` with plugin name `PhotonEMNonLinearity`
   - `HadronicThetaEnergyCorrectionEnabled` = `true` with plugin name `HadronicThetaEnergyBinned`
3. The **local** `libDDMarlinPandora.so` path (under `${MUCOL_BASE}`), not the container default.

If the payload lines are missing, the steering macro didn't receive the `--photonEMCalibPayload` / `--hadronicCalibPayload` flags. If the parameters show `false` or the container's library path appears instead of yours, the local runtime override is not active — re-check the exports in step 2.

### 5) Optional: use corrected energies in Pandora's internal decisions

Passing the payloads calibrates the **output** energies. Whether the corrected energies are also used in Pandora's internal decisions is controlled by switches in `${MUCOL_BASE}/SteeringMacros/PandoraSettings/PandoraSettingsDefault.xml`, which all default to `false`:

- `<UseCorrectedElectromagneticEnergyForEOverP>` (in the `<LCElectronId>` block): if `true`, the E/p check in ElectronID uses corrected EM cluster energy.
- `<UseCorrectedHadronicEnergyForTrackComparison>` (5 occurrences: inside `ProximityBasedMerging`, `ConeBasedMerging`, and `TrackPreparation`'s `TrackClusterAssociation`, at both the inner-algorithm and algorithm level): if `true`, track-cluster energy comparisons and chi checks during cluster merging use corrected hadronic energy.

To turn these on, edit the XML and set the relevant switches to `true` — flip all occurrences of `UseCorrectedHadronicEnergyForTrackComparison` together for consistent behavior. The steering macro copies this file to a temporary XML at the start of each run (`Running using temporary PandoraSettings XML: ...` in the log), so edits to the original take effect on the next `k4run`.

The plugin registration at the top of the same file (`<HadronicEnergyCorrectionPlugins>HadronicThetaEnergyBinned</HadronicEnergyCorrectionPlugins>` and `<ElectromagneticEnergyCorrectionPlugins>PhotonEMNonLinearity</ElectromagneticEnergyCorrectionPlugins>`) should already be present on the calibration branch and does not need editing.

## Producing calibration factors

This section is a recipe for making your own calibration. Prerequisites:

- **Only this repository is needed** — the local `LCContent`/`DDMarlinPandora` builds are required for *applying* calibrations, not for making them.
- A Python environment with `pyLCIO`, which is easiest inside the container ([step 1 above](#1-enter-the-container)), with `MUCOL_BASE` set as in step 2.
- Reconstructed single-particle gun samples: photons for the EM calibration, charged pions for the hadronic one. Use the central productions (mounted at `/data`) or produce your own with the standard MAIA sim + reco chain.

Each calibration (EM and hadronic) follows the same three steps:

1. **Make** the theta-energy table from your reconstructed single-particle samples.
2. **Validate** closure (corrected energy / true energy ≈ 1 in every bin) and produce diagnostic plots.
3. **Build** the steering payload JSON for `k4run`.

All scripts run over `.slcio` reco files and default to **cluster-based** energies (`PandoraClusters`) using the cluster subdetector energy split (ECAL index 0, HCAL index 1). `--inputs` accepts any mix of directories and individual `.slcio` files, space-separated. Run everything from the repo root with a `calib/` output directory:

```bash
cd "${MUCOL_BASE}/pandora-calibration-tools"
mkdir -p calib
```

**Note on ordering:** the EM closure validation (step A2) takes a hadronic table as input, so if you are making both calibrations, make the hadronic table (B1) before running the EM validation. If you are only remaking the EM table, you can pass the shipped `calib/hadronic_theta_energy_calib_Final.json` instead.

### A) EM calibration (photons)

#### A1) Make the ECAL table

The table is built in the Pandora EM energy basis: raw ECAL subdetector energy is multiplied by the same `ECalToEMGeVCalibration` factor `DDMarlinPandora` uses before ratios and energy-axis binning are computed. Point `--inputs` at your reconstructed single-photon samples — ideally covering the full energy range and all of theta, with extra events in the barrel/endcap transition region where the response varies fastest. The theta binning below is the most optimized so far for the MAIA geometry — fine bins across the barrel/endcap transition — but it can still be improved with more statistics (see [Improving the calibration](#improving-the-calibration)):

```bash
python3 scripts/make_ecal_theta_energy_calibration.py \
  --inputs /path/to/photon/gun/reco/samples \
  --recursive \
  --energy-source clusters \
  --cluster-collection PandoraClusters \
  --skip-missing-subdet-split \
  --ecal-fraction-min 0.7 \
  --energy-basis em \
  --ecal-to-em-gev 1.02373335516 \
  --theta-bins 0.15,0.40,0.577,0.61,0.635,0.66,0.71,0.77,0.86,1.00,1.20,1.5708,1.9416,2.1416,2.2816,2.3716,2.4316,2.4816,2.5066,2.5316,2.5646,2.7416,2.9916 \
  --energy-bins 30,50,100,250,500,1000,2000,5000 \
  --pdg-ids 22 \
  --output calib/ecal_theta_energy_calib.json
```

#### A2) Validate closure

This mode validates the ECAL and HCAL components together, so it takes separate `--ecal-inputs` (photons) and `--hcal-inputs` (pions):

```bash
python3 scripts/validate_theta_energy_calibration.py \
  --ecal-inputs /path/to/photon/gun/reco/samples \
  --hcal-inputs /path/to/pion/gun/reco/samples \
  --recursive \
  --energy-source clusters \
  --cluster-collection PandoraClusters \
  --skip-missing-subdet-split \
  --ecal-calibration calib/ecal_theta_energy_calib.json \
  --hcal-calibration calib/hadronic_theta_energy_calib.json \
  --plot-dir calib/plots \
  --output calib/ecal_closure_summary.json
```

When `--plot-dir` is provided this writes quick-look plots (`ecal_scale_map.png`, `ecal_count_map.png`, `ecal_theta_profiles.png`, HCAL equivalents, plus ROOT files with the same histograms). Check that corrected/true energy is flat and centered at 1 across theta and energy. The 2D `*_count_map.png` plots are the best way to see whether each (theta, energy) bin has enough statistics — low-count bins produce unstable scale factors or fall back to scale `1.0` (no correction), so if a bin looks sparse, either add events there or merge it with a neighbor. The `*_scale_map.png` plots show where the correction varies sharply, which is where finer binning pays off. Note that validating on the same samples used to derive the table confirms self-consistency; for a stricter test, derive the table on half your events and validate on the other half.

#### A3) Build the payload

```bash
python3 scripts/build_theta_energy_steering_payload.py \
  --photon-em-calibration calib/ecal_theta_energy_calib.json \
  --output-json calib/photon_em_calib_payload.json
```

This payload is what reconstruction consumes — pass it to `k4run` via `--photonEMCalibPayload` (see [Applying calibrations in reconstruction](#applying-calibrations-in-reconstruction)).

### B) Hadronic calibration (pions)

#### B1) Make the hadronic table

The table is built in the Pandora hadronic energy basis: raw ECAL and HCAL subdetector energies are converted with the `ECalToHadGeVCalibration` / `HCalToHadGeVCalibration` factors before ratios and binning. Point `--inputs` at your reconstructed single-pion samples covering the full energy range and all of theta. The binning below is the most optimized so far, but coarser than the EM table — with more pion statistics it could be refined further, particularly around the transition region (see [Improving the calibration](#improving-the-calibration)):

```bash
python3 scripts/make_hcal_theta_energy_calibration.py \
  --inputs /path/to/pion/gun/reco/samples \
  --recursive \
  --energy-source clusters \
  --cluster-collection PandoraClusters \
  --skip-missing-subdet-split \
  --hcal-fraction-min 0.1 \
  --energy-basis hadronic \
  --ecal-to-had-gev 1.38 \
  --hcal-to-had-gev 1.25 \
  --theta-bins 0.0,0.35,0.577,0.70,0.86,1.00,1.5708,2.1416,2.2816,2.4416,2.5646,2.7916,3.14159 \
  --energy-bins 10,25,50,100,175,250,500,1000,5000 \
  --pdg-ids 211 \
  --output calib/hadronic_theta_energy_calib.json
```

#### B2) Validate closure

When validating a single hadronic table (rather than the combined ECAL+HCAL mode in A2), the script takes plain `--inputs`:

```bash
python3 scripts/validate_theta_energy_calibration.py \
  --inputs /path/to/pion/gun/reco/samples \
  --recursive \
  --energy-source clusters \
  --cluster-collection PandoraClusters \
  --skip-missing-subdet-split \
  --hadronic-calibration calib/hadronic_theta_energy_calib.json \
  --plot-dir calib/plots \
  --output calib/hadronic_closure_summary.json
```

#### B3) Build the payload

```bash
python3 scripts/build_theta_energy_steering_payload.py \
  --hadronic-calibration calib/hadronic_theta_energy_calib.json \
  --output-json calib/hadronic_calib_payload.json
```

This payload is what reconstruction consumes — pass it to `k4run` via `--hadronicCalibPayload` (see [Applying calibrations in reconstruction](#applying-calibrations-in-reconstruction)).

### Key options explained

- `--energy-basis em` / `hadronic` with `--ecal-to-em-gev`, `--ecal-to-had-gev`, `--hcal-to-had-gev`: convert raw subdetector energies into the same energy basis Pandora uses internally, so derived factors compose correctly with the base calibration constants. **These values must match your reconstruction settings** — compare against `ECalToEMGeVCalibration`, `ECalToHadGeVCalibrationBarrel`/`EndCap`, and `HCalToHadGeVCalibration` in `steer_reco.py` before running.
- `--ecal-fraction-min 0.7` (EM) / `--hcal-fraction-min 0.1` (HAD): require the cluster to deposit at least this fraction of its energy in the relevant calorimeter, selecting well-contained showers.
- `--theta-bins` / `--energy-bins`: comma-separated bin edges. Binning is the main tuning knob — see [Improving the calibration](#improving-the-calibration).
- `--pdg-ids`: truth-match to these particle types (22 = photon for EM, 211 = charged pion for HAD).
- `--min-bin-count`: minimum entries required in a (theta, energy) bin to derive a scale factor; bins below it fall back to scale `1.0` (no correction).
- `--skip-missing-subdet-split`: skip clusters whose collection doesn't provide the ECAL/HCAL subdetector energy split, instead of failing.
- `--recursive`: search input directories for `.slcio` files in nested subdirectories.

## Improving the calibration

The current tables close well, but there is room to improve. Two directions matter most:

1. **More statistics.** Every (theta, energy) bin needs enough events for a stable fit; sparse bins fall back to scale `1.0` (i.e., no correction). More single-particle events — particularly at high energy and in the transition region — directly improves bin-by-bin precision and allows finer binning.
2. **Binning optimized for the detector geometry.** The response changes rapidly wherever the geometry changes: the barrel/endcap transition, cracks, and the edges of coverage. The current EM theta binning is already refined around the transition region (see the bin edges in A1), but further optimization — finer bins where the response gradient is large, merged bins where statistics are thin — would ensure every particle, at every energy and every theta, gets a properly tailored correction. The `*_scale_map.png` and `*_count_map.png` plots from the validation step are the tool for this: look for bins where the scale varies sharply between neighbors (split them) or where counts are low (merge them or add statistics).

Other possible extensions: dedicated samples for additional particle types, energy-bin refinement at the low-energy end where nonlinearity is strongest, and iterating make → validate until closure is flat everywhere.

## Set up from scratch

Use this for a clean checkout in a new MAIA software area.

```bash
export MUCOL_BASE=/scratch/<user>/mucol/v2.11
mkdir -p "${MUCOL_BASE}"
cd "${MUCOL_BASE}"
```

Clone the runtime repositories and this calibration-tool repository:

```bash
git clone git@github.com:PandoraPFA/LCContent.git
git clone git@github.com:MuonColliderSoft/DDMarlinPandora.git
git clone https://github.com/madbaron/SteeringMacros.git
git clone git@github.com:trholmes/pandora-calibration-tools.git
```

Add the fork remotes used by the calibration branches:

```bash
cd "${MUCOL_BASE}/LCContent"
git remote add trholmes git@github.com:trholmes/LCContent.git

cd "${MUCOL_BASE}/DDMarlinPandora"
git remote add trholmes git@github.com:trholmes/DDMarlinPandora.git

cd "${MUCOL_BASE}/SteeringMacros"
git remote add trholmes git@github.com:trholmes/SteeringMacros.git
```

Check out the calibration branches:

```bash
cd "${MUCOL_BASE}/LCContent"
git fetch trholmes codex/photon-em-nonlinearity
git checkout codex/photon-em-nonlinearity

cd "${MUCOL_BASE}/DDMarlinPandora"
git fetch trholmes codex/photon-em-theta-energy
git checkout codex/photon-em-theta-energy

cd "${MUCOL_BASE}/SteeringMacros"
git fetch trholmes codex/photon-em-steering
git checkout codex/photon-em-steering

cd "${MUCOL_BASE}/pandora-calibration-tools"
git fetch origin codex/photon-em-payload
git checkout codex/photon-em-payload
```

Build and install local `LCContent` and `DDMarlinPandora` (run inside the container so the compiler/CMake environment is consistent):

```bash
cd "${MUCOL_BASE}/LCContent"
rm -rf build install
mkdir -p build install
cd build
cmake .. -DCMAKE_INSTALL_PREFIX="${MUCOL_BASE}/LCContent/install"
cmake --build . -j"$(nproc)"
cmake --install .

cd "${MUCOL_BASE}/DDMarlinPandora"
rm -rf build install
mkdir -p build install
cd build
cmake .. \
  -DCMAKE_INSTALL_PREFIX="${MUCOL_BASE}/DDMarlinPandora/install" \
  -DLCContent_DIR="${MUCOL_BASE}/LCContent/install/lib/cmake/LCContent"
cmake --build . -j"$(nproc)"
cmake --install .
```

If your environment installs to `lib64` instead of `lib`, adjust `LCContent_DIR`, `LD_LIBRARY_PATH`, and `MARLIN_DLL` paths accordingly.

Then set the runtime environment as in [Applying calibrations in reconstruction](#applying-calibrations-in-reconstruction) — the same three exports, including the `MARLIN_DLL` duplicate check.

## Set up upon return

Coming back to an existing area (or after updating any of the runtime repos):

1. Enter the container (see above).
2. Pull the current branches:

```bash
cd "${MUCOL_BASE}/LCContent"
git fetch trholmes codex/photon-em-nonlinearity
git checkout codex/photon-em-nonlinearity
git pull --ff-only trholmes codex/photon-em-nonlinearity

cd "${MUCOL_BASE}/DDMarlinPandora"
git fetch trholmes codex/photon-em-theta-energy
git checkout codex/photon-em-theta-energy
git pull --ff-only trholmes codex/photon-em-theta-energy

cd "${MUCOL_BASE}/SteeringMacros"
git fetch trholmes codex/photon-em-steering
git checkout codex/photon-em-steering
git pull --ff-only trholmes codex/photon-em-steering
```

3. If `LCContent` or `DDMarlinPandora` changed, rebuild them (see the build block above — if the build cache is from an older branch, remove `build/` first and reconfigure).
4. Re-export the runtime environment (`LD_LIBRARY_PATH`, `MARLIN_DLL`) — this must be done in every new shell.

## Repository contents

- `scripts/make_ecal_theta_energy_calibration.py` — build the EM (ECAL) theta-energy table
- `scripts/make_hcal_theta_energy_calibration.py` — build the hadronic theta-energy table
- `scripts/validate_theta_energy_calibration.py` — closure validation + diagnostic plots
- `scripts/build_theta_energy_steering_payload.py` — convert tables to `k4run` payloads
- `scripts/calibration_lib.py` — shared library
- `scripts/plot_shower_profile_diagnostics.py` — shower-profile diagnostics (see below)
- `config/example_ecal_calibration_config.txt`, `config/example_hcal_calibration_config.txt`
- `docs/theta_energy_cluster_calibration_spec.md` — full design/specification (read after this README for design + integration details)
- `calib/` — current final calibration tables and payloads

## Runtime requirements

- Python 3.8+ with `pyLCIO` available (source the MuonCollider environment / run inside the container)
- `.slcio` reco files
- Write access to an output directory (e.g. `calib/`)

## Shower-profile diagnostics (work in progress)

**These diagnostics are not finalized** — the plots, cuts, and interface are still being developed and may change. Treat the outputs as exploratory rather than final results.

`scripts/plot_shower_profile_diagnostics.py` plots `showerProfileStart` and `showerProfileDiscrepancy` with the current `LCElectronId` cuts overlaid:

```bash
python3 scripts/plot_shower_profile_diagnostics.py reco.log \
  --format dump-pfos-log \
  --output-dir shower_profile_diagnostics
```

This log-parsing mode reads neutral PFO rows printed by `DumpPfosMonitoringAlgorithm` (columns `sStart`, `sDisc`). Charged PFO rows do not currently print these quantities, so for electron-specific studies either add those columns to the monitoring output or provide a CSV with columns `energy,sStart,sDisc,theta,label` (`theta` and `label` optional). Outputs: `shower_profile_vs_energy.png`, `shower_profile_distributions.png`, `shower_profile_vs_theta.png` (when `theta` present), `shower_profile_summary.txt`.

## Troubleshooting

1. `ImportError: pyLCIO` — source your MuonCollider/ILCSoft environment (or enter the container) before running scripts.
2. `No input files found` — check `--inputs` paths and `--file-glob`; add `--recursive` for nested subdirectories; for closure validation use `--ecal-inputs` / `--hcal-inputs` when the samples live in different places.
3. Too many bins with scale `1.0` — increase statistics, reduce bin granularity, or lower `--min-bin-count`.
4. Cluster split not available — if `PandoraClusters` in your file doesn't provide the subdetector split, remove `--skip-missing-subdet-split` and test, or temporarily switch to `--energy-source hits` for debugging.
5. Calibration messages missing from the `k4run` log — the local runtime override isn't active: re-check `LD_LIBRARY_PATH` and `MARLIN_DLL` (exactly one `libDDMarlinPandora.so`, pointing at your local install) and confirm you rebuilt after checking out the calibration branches.
