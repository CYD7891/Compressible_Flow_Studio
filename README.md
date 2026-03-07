# Compressible Flow Studio (CFS)

![Python](https://img.shields.io/badge/Python-3.13%2B-blue)
![Tests](https://img.shields.io/badge/tests-pytest-green)
![CI](https://img.shields.io/badge/CI-GitHub_Actions-success)

![CFS report preview](docs/report_preview.png)
![CFS report preview](docs/report_preview2.png)

Reliable compressible-flow calculator for isentropic flow, normal shocks, and oblique shocks — with batch CSV input, automated HTML reporting, optional PDF export, and test-backed engineering validation.

## Contents
- [Current capabilities](#current-capabilities)
- [Quickstart](#quickstart)
- [Example input format](#example-input-format)
- [Outputs](#outputs)
- [Example workflow](#example-workflow)
- [Engineering assumptions](#engineering-assumptions)
- [Known limitations / failure modes](#known-limitations--failure-modes)
- [Reliability features](#reliability-features)
- [Verification philosophy](#verification-philosophy)
- [Repository structure](#repository-structure)
- [Development roadmap](#development-roadmap)

## Why this project
Compressible-flow formulas are easy to find, but reliable engineering tools are harder to build well.

This project focuses on turning standard gas-dynamics relations into a more professional workflow:
- batch case execution from CSV
- validation-aware computation
- graceful handling of bad cases
- automated report generation
- reproducible tests and CI

Instead of being just a collection of formulas, CFS is designed as a small engineering toolchain.

## Current capabilities
- Isentropic flow
  - `T/T0`
  - `P/P0`
  - `rho/rho0`
  - `A/A*`
  - inverse `A/A* -> M` for subsonic and supersonic branches
- Normal shock
  - `M2`
  - `p2/p1`
  - `rho2/rho1`
  - `T2/T1`
  - `p02/p01`
- Oblique shock
  - weak / strong branch
  - shock angle `beta`
  - `Mn1`, `Mn2`, `M2`
  - `p2/p1`, `rho2/rho1`, `T2/T1`, `p02/p01`
  - attached-shock validity check through `theta_max`
- Batch runner from CSV
- HTML report generation
- Optional PDF generation with graceful fallback
- Error summary for failed cases
- pytest test suite
- GitHub Actions CI

## Quickstart

### 1. Create a virtual environment
Windows PowerShell:
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install
```bash
pip install -e ".[dev]"
```

### 3. Run the demo
```bash
python -m cfs demo --out build/demo
```

### 4. Run a batch case file
```bash
python -m cfs run examples/inputs_demo.csv --out build/run1
```

### 5. Attempt PDF generation
```bash
python -m cfs demo --out build/demo --pdf
```

### 6. open the generated report
Open:
```bash
build/demo/report.html
```

### 7. Run tests
```bash
pytest -q
```

## Example input format

**examples/inputs_demo.csv**

```csv
case_id,model,gamma,M,M1,theta_deg,branch
iso_1,isentropic,1.4,2.0,,,
ns_1,normal_shock,1.4,,2.0,,
os_1,oblique_shock,1.4,,3.0,15,weak
```

## Outputs

A typical run generates:
- `results.csv` with model-by-model computed quantities
- `report.html` with assumptions, limitations, tables, plots, and conclusions
- `assets/isentropic_area_ratio.png`
- optional `report.pdf` when PDF dependencies are available

The report also includes:
- successful case counts
- error case counts
- per-case error summaries for invalid inputs

## Example workflow

```bash
python -m cfs run examples/inputs_demo.csv --out build/run1
```

Then open:
- `build/run1/report.html`

## Engineering assumptions

CFS currently assumes:

- ideal gas behavior
- calorically perfect gas (`gamma` is constant)
- steady, inviscid, adiabatic flow
- quasi-1D relations for isentropic flow
- 1D normal-shock relations
- 2D attached oblique-shock modeling for wedge-type deflection cases

These assumptions are appropriate for many textbook and introductory engineering compressible-flow calculations, but they are not universal.

## Known limitations / failure modes

CFS does **not** currently model:

- real-gas effects
- variable-`gamma` thermodynamics
- high-temperature chemistry, dissociation, or ionization
- shock-boundary-layer interaction
- detached bow shocks beyond attached oblique-shock limits
- viscous duct effects such as Fanno flow
- heat-addition effects such as Rayleigh flow

Important numerical or physical rejection cases include:

- `M <= 0` for isentropic relations
- `M1 <= 1` for normal-shock calculations
- oblique-shock cases with `theta > theta_max(M1, gamma)`
- missing required CSV fields
- invalid numeric inputs
- unsupported model names

In batch runs, these cases are not allowed to crash the whole job. They are recorded as `ERROR` rows in the output instead.

## Reliability features

What makes this project more than a formula script:
- validation-aware functions
- branch-aware inverse area-ratio solver
- error isolation at the row level for batch jobs
- explicit reporting of failed cases
- unit tests for core relations and edge cases
- CI automation

## Verification philosophy

The project is verified through:
- closed-form compressible-flow relations
- regression-style numerical checks
- branch consistency checks
- batch workflow smoke tests
- report-generation smoke tests

## Repository structure

```
compressible-flow-studio/
  .github/workflows/ci.yml
  examples/
    inputs_demo.csv
  src/
    cfs/
      cli.py
      errors.py
      io/
      models/
      report/
  tests/
```

## Development roadmap

Planned next steps:
- better plots for oblique-shock behavior
- Fanno flow support
- Rayleigh flow support
- unit-aware user inputs with pint
- more formal golden-data validation tables
- richer report conclusions and comparison views