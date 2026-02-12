
import numpy as np


def _safe_div(numerator, denominator, fill_value=0.0):
    numerator_arr = np.asarray(numerator, dtype=float)
    denominator_arr = np.asarray(denominator, dtype=float)
    out = np.full_like(numerator_arr, fill_value, dtype=float)
    np.divide(numerator_arr, denominator_arr, out=out, where=denominator_arr != 0)
    return out


def add_metrics(df):
    df["ctr"] = _safe_div(df["clicks"], df["impressions"])
    df["cvr"] = _safe_div(df["orders"], df["clicks"])
    df["roas"] = _safe_div(df["revenue"], df["cost"])
    df["cpc"] = _safe_div(df["cost"], df["clicks"])
    df["cpa"] = _safe_div(df["cost"], df["orders"], fill_value=np.nan)
    df["acos"] = _safe_div(df["cost"], df["revenue"])
    df["rpc"] = _safe_div(df["revenue"], df["clicks"])
    if "add_to_cart" in df.columns:
        df["atc_rate"] = _safe_div(df["add_to_cart"], df["clicks"])
        df["checkout_rate"] = _safe_div(df["orders"], df["add_to_cart"])
    return df
