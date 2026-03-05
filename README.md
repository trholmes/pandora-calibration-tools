# pandora-calibration-tools

Standalone scripts to produce and validate ECAL/HCAL theta-energy calibration tables for mid-Pandora cluster energy correction studies.

## Contents

- `scripts/make_ecal_theta_energy_calibration.py`
- `scripts/make_hcal_theta_energy_calibration.py`
- `scripts/validate_theta_energy_calibration.py`
- `scripts/build_theta_energy_steering_payload.py`
- `scripts/calibration_lib.py`
- `config/example_ecal_calibration_config.txt`
- `config/example_hcal_calibration_config.txt`
- `docs/theta_energy_cluster_calibration_spec.md`

## Requirements

- Python 3.8+
- `pyLCIO` in runtime environment
- Input `.slcio` files from your simulation/reconstruction workflow

## Quick start

### 1) Build ECAL calibration table (pass A)

```bash
python3 scripts/make_ecal_theta_energy_calibration.py \
  --inputs /scratch/trholmes/mucol/data/reco/photonGun_E_0_50 \
  --theta-bins 0,0.35,0.7,1.05,1.4,1.75,2.1,2.45,2.8,3.14159 \
  --energy-bins 0,5,10,20,50,100,200,500,1000,5000 \
  --pdg-ids 22 \
  --output calib/ecal_theta_energy_calib.json
```

### 2) Build HCAL calibration table with ECAL fixed (pass B)

```bash
python3 scripts/make_hcal_theta_energy_calibration.py \
  --inputs /scratch/trholmes/mucol/data/reco/neutronGun_E_250_1000 \
  --theta-bins 0,0.35,0.7,1.05,1.4,1.75,2.1,2.45,2.8,3.14159 \
  --energy-bins 0,5,10,20,50,100,200,500,1000,5000 \
  --pdg-ids 2112,211,111 \
  --ecal-calibration calib/ecal_theta_energy_calib.json \
  --output calib/hcal_theta_energy_calib.json
```

### 3) Generate DDMarlinPandora steering payload

```bash
python3 scripts/build_theta_energy_steering_payload.py \
  --ecal-calibration calib/ecal_theta_energy_calib.json \
  --hcal-calibration calib/hcal_theta_energy_calib.json \
  --output-json calib/theta_energy_ddmarlin_params.json \
  --output-python calib/theta_energy_ddmarlin_params.py
```

### 4) Validate closure (pass C)

```bash
python3 scripts/validate_theta_energy_calibration.py \
  --inputs /scratch/trholmes/mucol/data/reco \
  --ecal-calibration calib/ecal_theta_energy_calib.json \
  --hcal-calibration calib/hcal_theta_energy_calib.json \
  --output calib/calibration_closure_summary.json
```
