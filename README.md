# pandora-calibration-tools

Standalone tooling to produce ECAL/HCAL theta-energy calibration tables and convert them into a `DDMarlinPandora.Parameters` payload.

This repo is intentionally independent from your larger software stack so you can clone and run it inside your remote container.

Default calibration source in scripts is **cluster-based** (`PandoraClusters`) using cluster subdetector energy split:
- ECAL subdetector index: `0`
- HCAL subdetector index: `1`

## Fresh MAIA Checkout For Calibration Development

Use this for a clean checkout in a new MAIA software area, e.g. `/scratch/trholmes/mucol/v2.11`.

```bash
export MUCOL_BASE=/scratch/trholmes/mucol/v2.11
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

Check out the photon EM calibration branches:

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

Build and install local `LCContent` and `DDMarlinPandora`:

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

Point runtime at those local builds before running `k4run`:

```bash
export LD_LIBRARY_PATH="${MUCOL_BASE}/LCContent/install/lib:${MUCOL_BASE}/DDMarlinPandora/install/lib:${LD_LIBRARY_PATH}"
export MARLIN_DLL="${MUCOL_BASE}/DDMarlinPandora/install/lib/libDDMarlinPandora.so:${MARLIN_DLL}"
```

If your CMake install uses `lib64`, replace `lib` with `lib64` in `LCContent_DIR`, `LD_LIBRARY_PATH`, and `MARLIN_DLL`.

## Included Spec

Full design/specification is included here:

- `docs/theta_energy_cluster_calibration_spec.md`

Recommended read order:
1. This README (operational workflow)
2. `docs/theta_energy_cluster_calibration_spec.md` (design + integration details)

## What This Repo Does

1. Produces ECAL calibration table (pass A) from photon samples.
2. Produces HCAL calibration table (pass B) using fixed ECAL table.
3. Produces closure summary (pass C).
4. Builds ready-to-paste steering payload for `DDMarlinPandora.Parameters`.

## What This Repo Does Not Do

1. It does not patch or build `DDMarlinPandora`/`LCContent`.
2. It does not automatically modify `SteeringMacros/k4Reco/steer_reco.py`.
3. It does not by itself enable mid-Pandora correction until matching code changes are merged in `LCContent` + `DDMarlinPandora`.

## Repository Contents

- `scripts/make_ecal_theta_energy_calibration.py`
- `scripts/make_hcal_theta_energy_calibration.py`
- `scripts/validate_theta_energy_calibration.py`
- `scripts/build_theta_energy_steering_payload.py`
- `scripts/calibration_lib.py`
- `config/example_ecal_calibration_config.txt`
- `config/example_hcal_calibration_config.txt`
- `docs/theta_energy_cluster_calibration_spec.md`

## Runtime Requirements

- Python 3.8+
- `pyLCIO` available in environment
- `.slcio` reco files
- Write access to output directory (e.g. `calib/`)

## Expected Remote Layout

Example (your current container layout):

- `/scratch/trholmes/mucol/v2.9.7/SteeringMacros`
- `/scratch/trholmes/mucol/v2.9.7/MyBIBUtils`
- `/scratch/trholmes/mucol/v2.9.7/pandora-calibration-tools` (this repo)

## End-to-End Workflow

### 0) Prepare output dir

```bash
cd /scratch/trholmes/mucol/v2.9.7/pandora-calibration-tools
mkdir -p calib
```

### 1) Pass A: build ECAL table

For photon EM corrections, build the ECAL table in the Pandora EM energy basis. The raw ECAL subdetector energy from `cluster.getSubdetectorEnergies()` is multiplied by the same `ECalToEMGeVCalibration` factor used by `DDMarlinPandora` before ratios and energy-axis binning are computed.

```bash
python3 scripts/make_ecal_theta_energy_calibration.py \
  --inputs /scratch/trholmes/mucol/data/reco/photonGun_E_0_50 \
  --recursive \
  --energy-source clusters \
  --cluster-collection PandoraClusters \
  --skip-missing-subdet-split \
  --ecal-fraction-min 0.7 \
  --energy-basis em \
  --ecal-to-em-gev 1.02373335516 \
  --theta-bins 0,0.35,0.7,1.05,1.4,1.75,2.1,2.45,2.8,3.14159 \
  --energy-bins 0,5,10,20,50,100,200,500,1000,5000 \
  --pdg-ids 22 \
  --output calib/ecal_theta_energy_calib.json
```

### 2) Pass B: build HCAL table (ECAL fixed)

For the first-pass hadronic branch test, train one branch-summed hadronic table. The raw ECAL and HCAL subdetector energies are converted to the Pandora HAD energy basis before ratios and energy-axis binning are computed.

```bash
python3 scripts/make_hcal_theta_energy_calibration.py \
  --inputs /scratch/trholmes/mucol/data/reco/neutronGun_E_250_1000 \
  --recursive \
  --energy-source clusters \
  --cluster-collection PandoraClusters \
  --skip-missing-subdet-split \
  --hcal-fraction-min 0.1 \
  --energy-basis hadronic \
  --ecal-to-had-gev 1.24223718397 \
  --hcal-to-had-gev 1.01799349172 \
  --theta-bins 0,0.35,0.7,1.05,1.4,1.75,2.1,2.45,2.8,3.14159 \
  --energy-bins 0,5,10,20,50,100,200,500,1000,5000 \
  --pdg-ids 2112,211,111 \
  --output calib/hadronic_theta_energy_calib.json
```

### 3) Pass C: closure summary

For the first-pass hadronic branch table, validate the single hadronic table directly:

```bash
python3 scripts/validate_theta_energy_calibration.py \
  --hcal-inputs /scratch/trholmes/mucol/data/reco/neutronGun_E_0_50 \
  --recursive \
  --energy-source clusters \
  --cluster-collection PandoraClusters \
  --skip-missing-subdet-split \
  --hadronic-calibration calib/hadronic_theta_energy_calib.json \
  --plot-dir calib/plots \
  --output calib/hadronic_closure_summary.json
```

The older ECAL+HCAL component-closure mode is still available:

```bash
python3 scripts/validate_theta_energy_calibration.py \
  --ecal-inputs /data/fmeloni/DataMuC_MAIA_v0/v6/reco/photonGun_E_0_50 \
  --hcal-inputs /data/fmeloni/DataMuC_MAIA_v0/v6/reco/neutronGun_E_0_50 \
  --recursive \
  --energy-source clusters \
  --cluster-collection PandoraClusters \
  --skip-missing-subdet-split \
  --ecal-calibration calib/ecal_theta_energy_calib.json \
  --hcal-calibration calib/hcal_theta_energy_calib.json \
  --plot-dir calib/plots \
  --output calib/calibration_closure_summary.json
```

This also writes quick-look calibration plots when `--plot-dir` is provided:
- `ecal_scale_map.png`, `hcal_scale_map.png`
- `ecal_count_map.png`, `hcal_count_map.png`
- `ecal_theta_profiles.png`, `hcal_theta_profiles.png`
- plus ROOT files with the same histograms

### 4) Build steering payload

```bash
python3 scripts/build_theta_energy_steering_payload.py \
  --ecal-calibration calib/ecal_theta_energy_calib.json \
  --hcal-calibration calib/hcal_theta_energy_calib.json \
  --output-json calib/theta_energy_ddmarlin_params.json \
  --output-python calib/theta_energy_ddmarlin_params.py
```

This produces:

- `calib/theta_energy_ddmarlin_params.json`
- `calib/theta_energy_ddmarlin_params.py`

`*.py` contains a block like:

```python
theta_energy_calibration_params = {...}
DDMarlinPandora.Parameters.update(theta_energy_calibration_params)
```

For the first-pass hadronic branch runtime test, build a single-table hadronic payload:

```bash
python3 scripts/build_theta_energy_steering_payload.py \
  --hadronic-calibration calib/hadronic_theta_energy_calib.json \
  --output-json calib/hadronic_calib_payload.json
```

Pass it to reconstruction with:

```bash
k4run /scratch/trholmes/mucol/v2.11/SteeringMacros/k4Reco/steer_reco.py \
  --code /scratch/trholmes/mucol/v2.11 \
  --data /scratch/trholmes/mucol/v2.11 \
  --TypeEvent neutronGun_E_0_50 \
  --InFileName 0 \
  --hadronicCalibPayload /scratch/trholmes/mucol/v2.11/pandora-calibration-tools/calib/hadronic_calib_payload.json
```

### Photon EM payload

For the photon-focused EM correction path, build a single-table payload from the ECAL/photon calibration:

```bash
python3 scripts/build_theta_energy_steering_payload.py \
  --photon-em-calibration calib/ecal_theta_energy_calib.json \
  --output-json calib/photon_em_calib_payload.json
```

Then pass it to reconstruction:

```bash
k4run /scratch/trholmes/mucol/v2.9.7/SteeringMacros/k4Reco/steer_reco.py \
  --code /scratch/trholmes/mucol/v2.9.7 \
  --data /scratch/trholmes/mucol/v2.9.7 \
  --TypeEvent photonGun_E_0_50 \
  --InFileName 0 \
  --photonEMCalibPayload /scratch/trholmes/mucol/v2.9.7/pandora-calibration-tools/calib/photon_em_calib_payload.json
```

## Rebuild And Run After Updates

Use this when you have updated any of the three runtime repos:

- `trholmes/LCContent`
- `trholmes/DDMarlinPandora`
- `trholmes/SteeringMacros`

The commands below assume this container layout:

- `/scratch/trholmes/mucol/v2.9.7/LCContent`
- `/scratch/trholmes/mucol/v2.9.7/DDMarlinPandora`
- `/scratch/trholmes/mucol/v2.9.7/SteeringMacros`
- `/scratch/trholmes/mucol/v2.9.7/pandora-calibration-tools`

### 1) Pull the current branches

```bash
cd /scratch/trholmes/mucol/v2.9.7/LCContent
git fetch trholmes codex/theta-energy-binned-plugin
git checkout codex/theta-energy-binned-plugin
git pull --ff-only trholmes codex/theta-energy-binned-plugin

cd /scratch/trholmes/mucol/v2.9.7/DDMarlinPandora
git fetch trholmes codex/theta-energy-params-plumbing
git checkout codex/theta-energy-params-plumbing
git pull --ff-only trholmes codex/theta-energy-params-plumbing

cd /scratch/trholmes/mucol/v2.9.7/SteeringMacros
git fetch trholmes codex/ecal-3d-precalib
git checkout codex/ecal-3d-precalib
git pull --ff-only trholmes codex/ecal-3d-precalib
```

### 2) Rebuild and install `LCContent`

```bash
cd /scratch/trholmes/mucol/v2.9.7/LCContent
mkdir -p build install
cd build

cmake .. \
  -DCMAKE_INSTALL_PREFIX=/scratch/trholmes/mucol/v2.9.7/LCContent/install
cmake --build . -j$(nproc)
cmake --install .
```

If you already have a build directory and CMake cache from an older branch, it is safer to remove `build/` and configure again before rebuilding.

### 3) Rebuild and install `DDMarlinPandora` against the local `LCContent`

```bash
cd /scratch/trholmes/mucol/v2.9.7/DDMarlinPandora
mkdir -p build install
cd build

cmake .. \
  -DCMAKE_INSTALL_PREFIX=/scratch/trholmes/mucol/v2.9.7/DDMarlinPandora/install \
  -DLCContent_DIR=/scratch/trholmes/mucol/v2.9.7/LCContent/install/lib/cmake/LCContent
cmake --build . -j$(nproc)
cmake --install .
```

If your environment installs to `lib64` instead of `lib`, adjust the `LCContent_DIR`, `LD_LIBRARY_PATH`, and `MARLIN_DLL` paths below accordingly.

### 4) Point runtime to the local libraries

```bash
export LD_LIBRARY_PATH=/scratch/trholmes/mucol/v2.9.7/LCContent/install/lib:/scratch/trholmes/mucol/v2.9.7/DDMarlinPandora/install/lib:$LD_LIBRARY_PATH
export MARLIN_DLL=/scratch/trholmes/mucol/v2.9.7/DDMarlinPandora/install/lib/libDDMarlinPandora.so:$MARLIN_DLL
```

Sanity checks:

```bash
echo "$LD_LIBRARY_PATH" | tr ':' '\n' | head -n 5
echo "$MARLIN_DLL" | tr ':' '\n' | head -n 10
```

In the `k4run` log, `MyAIDAProcessor` should show your local:

- `/scratch/trholmes/mucol/v2.9.7/DDMarlinPandora/install/lib/libDDMarlinPandora.so`

### 5) Run reconstruction with the payload

```bash
k4run /scratch/trholmes/mucol/v2.9.7/SteeringMacros/k4Reco/steer_reco.py \
  --code /scratch/trholmes/mucol/v2.9.7 \
  --data /scratch/trholmes/mucol/v2.9.7 \
  --TypeEvent photonGun_E_0_50 \
  --InFileName 0 \
  --thetaEnergyCalibPayload /scratch/trholmes/mucol/v2.9.7/pandora-calibration-tools/calib/theta_energy_ddmarlin_params.json \
  --writeClusterCalibrationComparison
```

This writes both:

- `PandoraClusters` for the uncalibrated comparison collection
- `PandoraClustersCalibrated` for the corrected comparison collection

## Shower-Profile Diagnostics

`scripts/plot_shower_profile_diagnostics.py` plots `showerProfileStart` and `showerProfileDiscrepancy` with the current `LCElectronId` cuts overlaid:

```bash
python3 scripts/plot_shower_profile_diagnostics.py reco.log \
  --format dump-pfos-log \
  --output-dir shower_profile_diagnostics
```

This log-parsing mode reads neutral PFO rows printed by `DumpPfosMonitoringAlgorithm`, where the columns are labelled `sStart` and `sDisc`. Charged PFO rows do not currently print these quantities, so for electron-specific studies either add those columns to the monitoring output or provide a CSV with columns:

```text
energy,sStart,sDisc,theta,label
```

`theta` and `label` are optional. The script writes:

- `shower_profile_vs_energy.png`
- `shower_profile_distributions.png`
- `shower_profile_vs_theta.png` when `theta` is present
- `shower_profile_summary.txt`

### 6) What to look for in the log

You should see all of the following:

1. `Loaded theta-energy calibration payload ...`
2. `Updated HadronicEnergyCorrectionPlugins in Pandora XML to include: ThetaEnergyBinned`
3. `DDPandoraPFANewProcessor: loaded theta-energy correction tables for plugin 'ThetaEnergyBinned' ...`

If those messages are missing, the local runtime override is usually not active.

## Recommended Companion Repos

To make this whole chain testable end-to-end on remote:

1. `pandora-calibration-tools` (this repo) for table production.
2. `trholmes/LCContent` fork for 2D ECAL/HCAL plugin implementation.
3. `trholmes/DDMarlinPandora` fork for steering parameter plumbing.
4. `trholmes/SteeringMacros` fork for runtime parameter injection.

## Quick Troubleshooting

1. `ImportError: pyLCIO`:
   - source your MuonCollider/ILCSoft environment before running scripts.
2. `No input files found`:
   - check `--inputs` path and `--file-glob`,
   - add `--recursive` when files are in nested subdirectories,
   - for closure use `--ecal-inputs` and `--hcal-inputs` when ECAL and HCAL validation samples are in different directories.
3. Too many bins with scale `1.0`:
   - increase statistics or reduce bin granularity,
   - lower `--min-bin-count`.
4. Cluster split not available:
   - if `PandoraClusters` in your file does not provide subdetector split, remove `--skip-missing-subdet-split` and test,
   - or temporarily switch to `--energy-source hits` for debugging.
