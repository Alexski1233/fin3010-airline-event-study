# --- Import libraries for data handling, date offsets, file paths, statistics ---
import pandas as pd
from pandas.tseries.offsets import BDay  # business-day window selection
from pathlib import Path
from math import sqrt
from scipy import stats  # two-sided t distribution for significance tests

# --- Model calibration and event definition ---
alpha = -0.0005  # intercept from the CAPM previously estimated
beta = 1.7795     # previously estimated market beta estimated over the estimation window
event_date = pd.Timestamp("2020-03-11")  # WHO pandemic announcement (Norwegian Air focus date)

# --- Data ingestion: Norwegian Air, OSEBX, and risk-free rate ---
data_dir = Path("data/norway")

# Norwegian Air share prices from Yahoo Finance export; rename 'Price' column to Date
nas = (
    pd.read_csv(data_dir / "norwegian.csv", skiprows=[1, 2])
    .rename(columns={"Price": "Date"})
    .assign(
        Date=lambda df: pd.to_datetime(df["Date"]),
        Close=lambda df: pd.to_numeric(df["Close"], errors="coerce"),
    )
    .dropna(subset=["Close"])
    .set_index("Date")
    .sort_index()
)

# Oslo Benchmark Index (OSEBX); same cleaning steps for consistency
osebx = (
    pd.read_csv(data_dir / "osebx_index.csv", skiprows=[1, 2])
    .rename(columns={"Price": "Date"})
    .assign(
        Date=lambda df: pd.to_datetime(df["Date"]),
        Close=lambda df: pd.to_numeric(df["Close"], errors="coerce"),
    )
    .dropna(subset=["Close"])
    .set_index("Date")
    .sort_index()
)

# Daily Norwegian risk-free rate (already in decimal form, e.g. 0.0003 = 0.03%)
rf = (
    pd.read_csv(data_dir / "Norway_Rf_daily.csv", skiprows=1)
    .rename(columns={"date": "Date", "Rf(1d)": "rf"})
    .assign(
        Date=lambda df: pd.to_datetime(df["Date"], format="%Y%m%d"),
        rf=lambda df: pd.to_numeric(df["rf"], errors="coerce"),
    )
    .dropna(subset=["rf"])
    .set_index("Date")
    .sort_index()
)

# --- Construct daily returns aligned on dates ---
returns = (
    pd.concat(
        [
            nas["Close"].pct_change().rename("norwegian_return"),
            osebx["Close"].pct_change().rename("osebx_return"),
            rf["rf"],
        ],
axis=1,).dropna())

# --- Event windows, abnormal returns, and significance testing ---
summary = []
for k in [10, 5, 3, 1]:  # evaluate several symmetric event windows
    win = returns.loc[event_date - BDay(k): event_date + BDay(k)].copy()

    # Excess returns over the risk-free rate
    win["norwegian_excess"] = win["norwegian_return"] - win["rf"]
    win["osebx_excess"] = win["osebx_return"] - win["rf"]

    # Expected return from CAPM and abnormal return (AR)
    win["expected_capm"] = alpha + beta * win["osebx_excess"]
    ar = win["norwegian_excess"] - win["expected_capm"]

    # Descriptive statistics and t-test of mean AR
    n = len(ar)
    mean_ar = ar.mean()
    std_ar = ar.std(ddof=1)
    t_stat = mean_ar / (std_ar / sqrt(n)) if std_ar > 0 else float("nan")
    p_val = 2 * stats.t.sf(abs(t_stat), df=n - 1) if std_ar > 0 else float("nan")

    summary.append(
        {
            "window": f"[-{k}, +{k}]",
            "n": n,
            "mean_AR": mean_ar,
            "std_AR": std_ar,
            "CAR": ar.sum(),
            "t_stat": t_stat,
            "p_value": p_val,
        }
    )

# --- Output results ---
results = pd.DataFrame(summary)
print(results)
