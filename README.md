# pandora-calibration-tools

Standalone tooling to produce ECAL/HCAL theta-energy calibration tables and convert them into a `DDMarlinPandora.Parameters` payload.

This repo is intentionally independent from your larger software stack so you can clone and run it inside your remote container.

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

```bash
python3 scripts/make_ecal_theta_energy_calibration.py \
  --inputs /scratch/trholmes/mucol/data/reco/photonGun_E_0_50 \
  --recursive \
  --theta-bins 0,0.35,0.7,1.05,1.4,1.75,2.1,2.45,2.8,3.14159 \
  --energy-bins 0,5,10,20,50,100,200,500,1000,5000 \
  --pdg-ids 22 \
  --output calib/ecal_theta_energy_calib.json
```

### 2) Pass B: build HCAL table (ECAL fixed)

```bash
python3 scripts/make_hcal_theta_energy_calibration.py \
  --inputs /scratch/trholmes/mucol/data/reco/neutronGun_E_250_1000 \
  --recursive \
  --theta-bins 0,0.35,0.7,1.05,1.4,1.75,2.1,2.45,2.8,3.14159 \
  --energy-bins 0,5,10,20,50,100,200,500,1000,5000 \
  --pdg-ids 2112,211,111 \
  --ecal-calibration calib/ecal_theta_energy_calib.json \
  --output calib/hcal_theta_energy_calib.json
```

### 3) Pass C: closure summary

```bash
python3 scripts/validate_theta_energy_calibration.py \
  --ecal-inputs /data/fmeloni/DataMuC_MAIA_v0/v6/reco/photonGun_E_0_50 \
  --hcal-inputs /data/fmeloni/DataMuC_MAIA_v0/v6/reco/neutronGun_E_0_50 \
  --recursive \
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

## Integration Into SteeringMacros

In your fork of `SteeringMacros/k4Reco/steer_reco.py`:

1. Paste `theta_energy_calibration_params` near `DDMarlinPandora.Parameters`.
2. Add:
   - `DDMarlinPandora.Parameters.update(theta_energy_calibration_params)`

Note: these parameters become active only once corresponding support is added in your `DDMarlinPandora` + `LCContent` builds.

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
