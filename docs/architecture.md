# Build Plan

## App architecture

The dashboard is built as a modular Streamlit app with one shared backend and two presentation modes:

- `Analyst mode`
  Full-density interface with spreads, tables, rolling correlations, divergences, and composite breakdowns.
- `Beginner mode`
  Same data, storage, and heuristics layer, but reduced chart density and more plain-English interpretation.
- `Helper/tutorial toggle`
  Cross-cuts both modes and exposes additional context without changing the underlying analytics.

## Module layout

```text
oil360_dashboard/
  app.py
  docs/
    architecture.md
    data_dictionary.md
  runtime/
    imports/
      manual/
      public/
      premium/
      freight/
  src/oil360_dashboard/
    catalog.py
    config.py
    models.py
    pipeline.py
    adapters/
      base.py
      csv_manual.py
      ibkr.py
      public_data.py
      premium_physical.py
      freight_flow.py
      placeholder.py
    analytics/
      metrics.py
      composites.py
      narrative.py
      transmission.py
    storage/
      history_store.py
    ui/
      helpers.py
      sections.py
```

## Data-source map

| Layer | Primary v1 path | Expected status | Fallback |
| --- | --- | --- | --- |
| Exchange / broker | TradingView or IBKR CSV exports; later IBKR direct | delayed/manual | placeholder scaffold |
| Physical pricing | Premium vendor CSV exports | manual | AUB, OQD, or placeholder |
| Freight / flows | Baltic, AIS, war-risk CSV exports | manual | placeholder scaffold |
| Public inventories | Public CSV imports | delayed | placeholder scaffold |
| Derived metrics | Local analytics engine | local | n/a |
| Historical analytics | SQLite local history store | local | n/a |

## Why this stays usable with partial data

- Every series in the framework is defined in the catalog from day one.
- Each series is tagged with an expected source, fallback proxy, and plain-English explanation.
- If a live or CSV source is missing, the UI still renders the slot and labels it as a placeholder.
- The relationship map and composite heuristics never hide missing-data limitations.
- Historical storage lets imported or delayed data accumulate into a more useful local history over time.

## Fallback strategy

- `Dated Brent` unavailable: use `AUB` or placeholder.
- `Dubai / East-of-Suez` premium feed unavailable: use `OQD`, `DBI`, `ADM` placeholders as needed.
- `Freight / AIS` unavailable: use placeholders and show the path as scaffold-only.
- `Public inventory` unavailable: use placeholder inventory series and keep quality flags visible.
- `TradingView / IBKR direct` unavailable: use CSV imports first, placeholders second.

## Historical storage choice

SQLite is used because it is:
- local
- simple to inspect
- easy to append to
- enough for v1 correlation, z-score, and regime logic

This is the main reason v1 can support rolling analytics, divergence detection, and composite stress scores without depending on external platforms to retain long lookback history.
