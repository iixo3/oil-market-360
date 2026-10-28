# Oil Market 360

A Streamlit dashboard that reads stress across the oil market in one place: paper benchmarks, physical prices, U.S. export grades, sour and heavy crude, refined products, freight and logistics, and inventory hubs. It blends these into composite stress scores and short plain-English readings.

## What it does

- **Ten sections**: Executive Overview, Paper vs Physical, U.S. Export-Barrel / Location Stress, Sour / Heavy Substitution, Refined Products and Cracks, Freight / Flows / Logistics, Inventories and Absorption, Correlation and Transmission Map, Composite Indices and Narratives, Source Health and Data Quality.
- **Six composite stress scores**: Paper vs Physical, East-of-Suez, U.S. Inland Dislocation, Product Stress, Sour/Heavy Substitution, Logistics Constraint. Each score shows the components it is built from.
- **Relationships**: rolling correlations, lagged relationships, divergence detection, and a map of how stress is expected to pass from one market to another.
- **Two views of the same data**: Analyst (full detail) and Beginner (fewer charts, more explanation), plus an optional helper layer that explains each panel.
- **Honest about its data**: every series is labelled live, delayed, public, manual or placeholder, and the Source Health page lists where each one came from.

## How it works

```text
data adapters  ->  local history (SQLite)  ->  analytics  ->  Streamlit pages
```

1. **Adapters** (`src/oil360_dashboard/adapters/`) collect data: public web pages (EIA, GME, CME bulletin, Fujairah FOIZ), CSV files you drop into `runtime/imports/`, and an optional direct link to Interactive Brokers (IBKR).
2. **History store** (`storage/`) keeps every observation in a local SQLite file, so history builds up over time.
3. **Placeholders**: any series with no data gets clearly labelled synthetic values, so the full framework stays visible with partial data.
4. **Analytics** (`analytics/`) computes spreads, crack spreads, z-scores, correlations, divergences and the composite scores.
5. **UI** (`ui/`) draws the pages with Plotly charts.

More detail: [`docs/architecture.md`](docs/architecture.md) (module layout, data-source map, fallbacks) and [`docs/data_dictionary.md`](docs/data_dictionary.md) (every series and why it matters).

## What is real on a first launch

Without your own data, most series are placeholders. Out of the box:

- **Cushing crude stocks**: real weekly history from 2021 (sample file, see below), plus the latest week fetched from the EIA on each launch.
- **Oman crude (OQD)**: the latest daily marker price, fetched from GME's public page.
- **Everything else** (WTI, Brent, products, freight, other inventories): placeholders until you add CSV files or connect IBKR.

Two public sources no longer answer as of October 2026: the CME daily bulletin refuses automated downloads, and the Fujairah FOIZ statistics page has moved. The app reports both on the Source Health page and falls back to placeholders.

## How to run

Requires Python 3.11 or newer. Tested with Python 3.13 and Streamlit 1.66.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
streamlit run app.py
```

The app creates its local history file and import folders under `runtime/` on first launch.

### Adding your own data

Drop CSV files into these folders, or upload them from the sidebar:

| Folder | For |
| --- | --- |
| `runtime/imports/manual/` | Broker or charting exports (e.g. TradingView, IBKR) |
| `runtime/imports/public/` | Public inventory data (Cushing, Fujairah, Singapore, ARA) |
| `runtime/imports/premium/` | Paid physical price assessments (e.g. Platts, Argus, OPIS) |
| `runtime/imports/freight/` | Freight, tanker tracking (AIS) or war-risk data |

Each file needs a date column (`timestamp`, `datetime`, `date` or `time`) and a value column (`value`, `close`, `price`, `last`, `settle` or `index_value`). The series comes from a `series_id`/`symbol`/`ticker` column, or from the file name (e.g. `CL.csv`, `BDTI.csv`). Common aliases are mapped, for example `BZ` or `COIL` to Brent and `OMOIL` to Oman crude.

### Optional: direct IBKR prices

```bash
pip install -e ".[ibkr]"
export OIL360_ENABLE_IBKR=1
python scripts/check_ibkr_connection.py   # optional connection test
```

This needs TWS or IB Gateway running (by default on the same computer) with API access enabled. Other environment variables, with example values in `.env.example`: `OIL360_IBKR_HOST`, `OIL360_IBKR_PORT`, `OIL360_IBKR_PORTS` (fallback list), `OIL360_IBKR_CLIENT_ID`, `OIL360_IBKR_TIMEOUT_SECONDS`, and `OIL360_CSV_IMPORT_DIR` to point the manual CSV folder elsewhere.

## Sample data

`runtime/imports/public/CUSHING.csv`: weekly crude oil stocks at Cushing, Oklahoma, in million barrels, from 1 January 2021 to 16 October 2026. Source: U.S. Energy Information Administration (EIA), public domain.

## Credits and use

Built by iixo3. The code is published to show the work: you're welcome to read it, but it is not licensed for reuse.
