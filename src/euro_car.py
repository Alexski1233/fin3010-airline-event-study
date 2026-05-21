"""
Daily event study for European airlines measured in NOK.

Method:
1) Estimate a simple market model (CAPM) in [-105, -5] business days pre-event.
2) Compute abnormal returns (AR).
3) Aggregate to AAR/CAAR over firms.
4) Test CAAR across firms with a t-test.

Notes:
- All returns are in NOK.
- Risk-free rate is NOK (NOWA daily fixing), converted to a daily rate using 252.
"""

from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

# ------------------------------- Config ------------------------------------ #

DATA_DIR = Path("data/european_airlines")

AIRLINE_FILES: List[str] = [
    "aeg_greece.xlsx",
    "air_france.xlsx",
    "easyjet_uk.xlsx",
    "iceland_air.xlsx",
    "lufthansa.xlsx",
    "nas.xlsx",
    "ryanair.xlsx",
    "sas.xlsx",
    "tui.xlsx",
    "wizz_air_uk.xlsx",
]

MARKET_FILE = "europa_index.xlsx"  # Europe index expressed in NOK (prefer TR)
RF_FILE = "nowa_rf.xlsx"           # NOWA daily fixing: (Date, Value) in % p.a.

EVENT_DATE = pd.Timestamp("2020-03-11")  # WHO announcement (t = 0)

# Estimation window: [-105, -5] business days before the event (avoid leakage)
ESTIMATION_OFFSETS: Tuple[int, int] = (-105, -5)

# Event windows to report (relative to t=0)s
EVENT_WINDOWS: Dict[str, Tuple[int, int]] = {
    "±10": (-10, 10),
    "±5": (-5, 5),
    "±3": (-3, 3),
    "±1": (-1, 1),
}

DAY_COUNT = 252  # Daily conversion from annualized rates (market convention)


# ----------------------------- IO Utilities -------------------------------- #

def read_exchange_history(path: Path) -> pd.Series:
    """
    Read a LSEG/Reuters-style Excel with 'Exchange Date' and 'Close' columns.

    The header row may not be the first row (typical RIC exports).
    Returns
    -------
    pd.Series
        Close prices, indexed by pandas Timestamp, sorted ascending.
    """
    preview = pd.read_excel(path, header=None, nrows=80)
    header_row = int(
        preview.index[
            preview.iloc[:, 0].astype(str).str.contains("Exchange Date")
        ][0]
    )
    df = pd.read_excel(path, header=header_row)[["Exchange Date", "Close"]].dropna()
    df["Exchange Date"] = pd.to_datetime(df["Exchange Date"])
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    return (
        df.dropna()
        .set_index("Exchange Date")
        .sort_index()["Close"]
    )


def load_risk_free(path: Path, day_count: int = DAY_COUNT) -> pd.Series:
    """
    Load NOK risk-free series (NOWA daily fixing) and convert % p.a. to daily.

    Expected Excel layout: first column = Date, second = Value (% p.a.).
    Returns
    -------
    pd.Series
        Daily risk-free rate aligned by date (no calendar mapping yet).
    """
    rf = pd.read_excel(path)
    rf = rf.rename(columns={rf.columns[0]: "date", rf.columns[1]: "rate"})
    rf = rf.dropna(subset=["date", "rate"])
    rf["date"] = pd.to_datetime(rf["date"])
    rf["rate"] = pd.to_numeric(rf["rate"], errors="coerce")
    rf = rf.dropna().set_index("date").sort_index()
    # Simple daily rate; for short windows this is equivalent to compounding
    rf["rf_daily"] = rf["rate"] / 100 / day_count
    return rf["rf_daily"]


# ----------------------------- Core Methods -------------------------------- #

def compute_capm_abnormal(
    close: pd.Series,
    market_returns: pd.Series,
    rf_series: pd.Series,
    event_date: pd.Timestamp,
    est_offsets: Tuple[int, int],
) -> pd.DataFrame:
    """
    Estimate CAPM in the estimation window and compute abnormal returns (AR).

    Parameters
    ----------
    close : pd.Series
        Stock close prices (NOK).
    market_returns : pd.Series
        Market returns (NOK).
    rf_series : pd.Series
        Daily NOK risk-free rate.
    event_date : pd.Timestamp
        Event date (t = 0).
    est_offsets : (int, int)
        Business-day offsets relative to event_date, e.g. (-105, -5).

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: stock_return, market_return, rf,
        excess_stock, excess_market, abnormal. Index is trading dates.
    """
    stock_ret = close.pct_change().dropna().rename("stock_return")
    aligned = (
        pd.concat(
            [stock_ret, market_returns.rename("market_return"),
             rf_series.rename("rf")],
            axis=1,
            join="inner",
        )
        .dropna()
    )

    aligned["excess_stock"] = aligned["stock_return"] - aligned["rf"]
    aligned["excess_market"] = aligned["market_return"] - aligned["rf"]

    # Estimation window by calendar (works if calendars are aligned).
    est_start = event_date + pd.offsets.BDay(est_offsets[0])
    est_end = event_date + pd.offsets.BDay(est_offsets[1])
    estimation = aligned.loc[est_start:est_end]

    X = sm.add_constant(estimation["excess_market"])
    model = sm.OLS(estimation["excess_stock"], X).fit()
    alpha = float(model.params["const"])
    beta = float(model.params["excess_market"])

    aligned["abnormal"] = (
        aligned["excess_stock"] - (alpha + beta * aligned["excess_market"])
    )
    return aligned


def extract_window(
    series: pd.Series,
    event_date: pd.Timestamp,
    start: int,
    end: int,
) -> pd.Series:
    """
    Extract an event window using business-day calendar around event_date.

    Returns a series indexed by event time τ ∈ [start, end] with τ=0 at event.
    """
    idx = pd.bdate_range(
        event_date + pd.offsets.BDay(start),
        event_date + pd.offsets.BDay(end),
    )
    window = series.reindex(idx)
    window.index = range(start, end + 1)
    return window


# ------------------------------- Pipeline ---------------------------------- #

def main() -> None:
    # Market: price series → daily returns (NOK)
    market_prices = read_exchange_history(DATA_DIR / MARKET_FILE)
    market_returns = market_prices.pct_change().dropna()

    # Risk-free: NOWA daily → align to market calendar to avoid uneven joins
    rf_daily = load_risk_free(DATA_DIR / RF_FILE, day_count=DAY_COUNT)
    rf_daily = rf_daily.reindex(market_returns.index).ffill()

    window_panels: Dict[str, List[pd.Series]] = {k: [] for k in EVENT_WINDOWS}
    aar_curves: Dict[str, pd.Series] = {}
    caar_curves: Dict[str, pd.Series] = {}
    skipped: Dict[str, str] = {}

    # Firm-level AR computation and window extraction
    for fname in AIRLINE_FILES:
        try:
            close = read_exchange_history(DATA_DIR / fname)
            abnormal_df = compute_capm_abnormal(
                close,
                market_returns,
                rf_daily,
                EVENT_DATE,
                ESTIMATION_OFFSETS,
            )
            firm = Path(fname).stem
            for label, (start, end) in EVENT_WINDOWS.items():
                window_panels[label].append(
                    extract_window(
                        abnormal_df["abnormal"], EVENT_DATE, start, end
                    ).rename(firm)
                )
        except Exception as exc:  # keep going and report which series failed
            skipped[fname] = str(exc)

    # Cross-sectional AAR/CAAR and t-tests on CAR
    summary_rows: List[Dict[str, float]] = []
    for label, series_list in window_panels.items():
        window_df = pd.concat(series_list, axis=1)

        # Average across firms each event day (AAR), then cumulative (CAAR curve)
        aar = window_df.mean(axis=1)
        aar_curves[label] = aar
        caar_curves[label] = aar.cumsum()

        # Firm CARs over the window → CAAR (mean of CARs) and t-test
        car = window_df.sum(axis=0)  # CAR per firm
        n = car.count()
        caar_mean = car.mean()
        std = car.std(ddof=1)
        t_stat = np.nan if n < 2 or std == 0 else caar_mean / (std / np.sqrt(n))
        p_val = np.nan if n < 2 or std == 0 else stats.t.sf(abs(t_stat), df=n - 1) * 2

        summary_rows.append(
            {
                "window": label,
                "firms": int(n),
                "CAAR": float(caar_mean),
                "t": float(t_stat) if pd.notna(t_stat) else np.nan,
                "p": float(p_val) if pd.notna(p_val) else np.nan,
                "event_AAR": float(aar.loc[0]),
            }
        )
        # store concatenated frame for later inspection/printing
        window_panels[label] = window_df

    summary = pd.DataFrame(summary_rows).set_index("window").sort_index()

    if skipped:
        print("Skipped series:", skipped)

    # Pretty print (percent for CAAR and event-day AAR)
    summary_view = summary.copy()
    summary_view[["CAAR", "event_AAR"]] *= 100
    summary_view = summary_view.round({"CAAR": 2, "event_AAR": 2, "t": 3, "p": 3})

    print("CAAR t-tests (values in % where noted):")
    print(summary_view)

    print("\nEvent-day abnormal returns (%):")
    event_day = window_panels["±10"].loc[[0]].T.rename(columns={0: "AR_t0"})
    event_day["AR_t0"] = (event_day["AR_t0"] * 100).round(2)
    print(event_day.sort_values("AR_t0"))


if __name__ == "__main__":
    main()
