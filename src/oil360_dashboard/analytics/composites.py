from __future__ import annotations

import numpy as np
import pandas as pd

from ..catalog import COMPOSITE_DEFINITIONS


def _component_score(series: pd.Series, invert: bool) -> float:
    sample = series.dropna().tail(60)
    if sample.empty:
        return 50.0
    std = sample.std(ddof=0)
    zscore = 0.0 if std == 0 or np.isnan(std) else (sample.iloc[-1] - sample.mean()) / std
    normalized = float(np.clip(50 + (zscore * 15), 0, 100))
    return 100 - normalized if invert else normalized


def compute_composites(wide: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    scores = []
    components = []

    for composite_name, rules in COMPOSITE_DEFINITIONS.items():
        weighted_scores = []
        absolute_weights = []
        for component, weight, invert in rules:
            if component not in wide.columns:
                component_score = 50.0
                latest_value = np.nan
            else:
                component_score = _component_score(wide[component], invert)
                latest_value = wide[component].dropna().iloc[-1] if not wide[component].dropna().empty else np.nan

            weighted_scores.append(component_score * weight)
            absolute_weights.append(abs(weight))
            components.append(
                {
                    "composite": composite_name,
                    "component": component,
                    "weight": weight,
                    "invert": invert,
                    "component_score": round(component_score, 2),
                    "latest_value": latest_value,
                }
            )

        score = float(sum(weighted_scores) / sum(absolute_weights))
        regime = "Red" if score >= 67 else "Amber" if score >= 45 else "Green"
        scores.append({"composite": composite_name, "score": round(score, 2), "traffic_light": regime})

    return pd.DataFrame(scores), pd.DataFrame(components)
