"""
CAPM estimate for Norwegian Air Shuttle versus the OSEBX market index.

# Notes for instructors:
# - Reads Reuters/Refinitiv Excel exports (same layout as the other airline files).
# - Computes daily returns, excess returns, and runs an OLS regression on the estimation window.
# - Reports Jensen's alpha and beta alongside the usual regression summary.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

# --- Configuration ---------------------------------------------------------

DATA_DIR = Path("data/european_airlines")
NAS_FILE = "nas.xlsx"
OSEBX_FILE = "oslo_bors.xlsx"
RF_FILE = "nowa_rf.xlsx"
DAY_COUNT = 252  # switch to 360 if you prefer the money-market convention
SAMPLE_START = "2019-09-26"
SAMPLE_END = "2020-02-19"


# --- Helper functions ------------------------------------------------------


def read_price_history(path: Path) -> pd.Series:
    """Return the closing-price series from a Reuters export."""
    preview = pd.read_excel(path, header=None, nrows=80)
    header_row = int(
        preview.index[preview.iloc[:, 0].astype(str).str.contains("Exchange Date")][0]
    )
    df = pd.read_excel(path, header=header_row)[["Exchange Date", "Close"]].dropna()
    df["Exchange Date"] = pd.to_datetime(df["Exchange Date"])
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    return df.dropna().set_index("Exchange Date").sort_index()["Close"]


def load_risk_free(path: Path, day_count: int) -> pd.Series:
    """Load NOWA and convert the percentage quote into a daily decimal rate."""
    rf = pd.read_excel(path)
    rf = rf.rename(columns={rf.columns[0]: "Date", rf.columns[1]: "rate"})
    rf["Date"] = pd.to_datetime(rf["Date"])
    rf["rate"] = pd.to_numeric(rf["rate"], errors="coerce")
    rf = rf.dropna(subset=["rate"]).set_index("Date").sort_index()
    rf = rf[(rf.index >= SAMPLE_START) & (rf.index <= SAMPLE_END)]
    rf["rf_daily"] = rf["rate"] / 100 / day_count
    return rf["rf_daily"]


# --- Analysis ---------------------------------------------------------------

nas_prices = read_price_history(DATA_DIR / NAS_FILE)
osebx_prices = read_price_history(DATA_DIR / OSEBX_FILE)
rf_daily = load_risk_free(DATA_DIR / RF_FILE, day_count=DAY_COUNT)

returns = pd.concat(
    [
        nas_prices.pct_change().rename("norwegian_return"),
        osebx_prices.pct_change().rename("osebx_return"),
        rf_daily.rename("rf"),
    ],
    axis=1,
).dropna()

returns = returns.loc[SAMPLE_START:SAMPLE_END]
returns["norwegian_excess"] = returns["norwegian_return"] - returns["rf"]
returns["osebx_excess"] = returns["osebx_return"] - returns["rf"]

X = sm.add_constant(returns["osebx_excess"])
y = returns["norwegian_excess"]
capm_model = sm.OLS(y, X).fit()

alpha = capm_model.params["const"]
beta = capm_model.params["osebx_excess"]

print(f"Observations used in the regression: {len(returns):d}")
print(f"Alpha (daily Jensen's alpha): {alpha:.6f}")
print(f"Beta (CAPM beta): {beta:.4f}")
print("\n--- OLS summary ---")
print(capm_model.summary())
