from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from oil360_dashboard.config import AppConfig
from oil360_dashboard.adapters.ibkr import ExchangeBrokerAdapter


def main() -> int:
    config = AppConfig.from_env(ROOT)
    config.ensure_runtime_dirs()

    if not config.ibkr_enabled:
        print("OIL360_ENABLE_IBKR is not set to 1.")
        return 1

    response = ExchangeBrokerAdapter(config).fetch(
        timeframe="Daily",
        start=pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=7),
        end=pd.Timestamp.utcnow().tz_localize(None),
    )

    print("Observations")
    if response.observations.empty:
        print("No direct/csv broker observations returned.")
    else:
        print(response.observations.sort_values(["series_id", "timestamp"]).tail(20).to_string(index=False))

    print("\nSource health")
    if response.source_health.empty:
        print("No broker health rows returned.")
    else:
        print(response.source_health.sort_values("series_id").to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
