# MIL-217 Reliability Analyzer

Flask web app for dual reliability analysis: **MIL-STD-217F Notice 2** and **manufacturer FIT data**.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

```powershell
.\.venv\Scripts\python.exe app.py
```

Open [http://127.0.0.1:5050](http://127.0.0.1:5050).

## Usage

1. Upload a BOM file (CSV or XLSX).
2. Set analysis conditions (temperature, environment, quality level).
3. Run analysis and compare MIL-217F vs manufacturer FIT rates.
4. Download a Word comparison report.

Sample BOM files are available under `uploads/` and via the **Sample BOM** button in the UI.
