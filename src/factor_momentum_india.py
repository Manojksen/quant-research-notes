"""
Research Note 02 - Does Factor Momentum Work in Indian Large Caps?

Universe: the 50 stocks in the NIFTY 50 (daily, Oct-2012 to Oct-2022, Yahoo adjusted closes).
Monthly rebalance. Each factor = equal-weight top tercile minus bottom tercile.

Factors
  MOM   12-1 month price momentum
  LVOL  low minus high 60-day volatility
  LBETA low minus high 1-year beta vs. equal-weight universe
  STR   1-month losers minus winners (short-term reversal)
  HIGH  proximity to 52-week high (George & Hwang 2004)
  LIQ   low minus high 60-day average traded value (size proxy; no market-cap data)

Factor momentum (Ehsani & Linnainmaa 2022; Dickerson et al. 2025 style):
  TSFM  hold each factor only if its trailing 12-month return is positive
  VS    volatility-scaled version of each portfolio (target 10% p.a., 6-month realised vol)

Caveats (stated in the note): survivorship bias, 50 names only, no trading costs.
"""
import numpy as np
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
import style

ROOT = Path(__file__).resolve().parents[1]
CH = ROOT / "charts"
style.apply()
SRC = "NIFTY 50 constituents, Yahoo Finance adjusted prices"
NAMES = {"MOM": "Momentum", "LVOL": "Low Volatility", "LBETA": "Low Beta",
         "STR": "Short-Term Reversal", "HIGH": "52-Week High", "LIQ": "Low Liquidity (size proxy)"}


def load():
    px, vol = {}, {}
    for f in sorted((ROOT / "data/nifty50").glob("*.csv")):
        d = pd.read_csv(f)
        fmt = "%d-%m-%Y" if d["Date"].iloc[0][2] == "-" else "%Y-%m-%d"   # two files use dd-mm-yyyy
        d = d.assign(Date=pd.to_datetime(d["Date"], format=fmt)).set_index("Date")
        d = d[~d.index.duplicated()]
        px[f.stem] = d["Adj Close"]
        vol[f.stem] = d["Close"] * d["Volume"]
    return pd.DataFrame(px).sort_index(), pd.DataFrame(vol).sort_index()


def signals(px, tv):
    r = px.pct_change(fill_method=None)
    mkt = r.mean(axis=1)
    beta = r.rolling(252, min_periods=200).cov(mkt).div(mkt.rolling(252, min_periods=200).var(), axis=0)
    return {
        "MOM": px.shift(21) / px.shift(252) - 1,
        "LVOL": -r.rolling(60).std(),
        "LBETA": -beta,
        "STR": -(px / px.shift(21) - 1),
        "HIGH": px / px.rolling(252).max(),
        "LIQ": -tv.rolling(60).mean(),
    }


def build_factors(px, tv):
    sig = signals(px, tv)
    me = px.groupby(px.index.to_period("M")).tail(1).index         # month-end dates
    fwd = px.loc[me].pct_change(fill_method=None).shift(-1)         # next-month return
    out = {}
    for k, s in sig.items():
        s = s.loc[me]
        rets = []
        for dt in me[:-1]:
            x = s.loc[dt].dropna()
            y = fwd.loc[dt].reindex(x.index).dropna()
            x = x.reindex(y.index)
            if len(x) < 30:
                rets.append(np.nan); continue
            q = x.rank(pct=True)
            rets.append(y[q > 2 / 3].mean() - y[q <= 1 / 3].mean())
        out[k] = pd.Series(rets, index=me[1:])
    f = pd.DataFrame(out).dropna()
    mkt = fwd.mean(axis=1).shift(1).reindex(f.index)
    return f, mkt


def perf(r):
    r = r.dropna()
    eq = (1 + r).cumprod()
    return pd.Series({"Ann. Return": r.mean() * 12, "Volatility": r.std() * np.sqrt(12),
                      "Sharpe": r.mean() / r.std() * np.sqrt(12),
                      "Max Drawdown": (eq / eq.cummax() - 1).min(), "Hit Rate": (r > 0).mean()})


def vol_scale(r, target=0.10, lb=6):
    v = r.rolling(lb).std().shift(1) * np.sqrt(12)
    return (r * (target / v).clip(upper=2.0)).dropna()


def main():
    px, tv = load()
    f, mkt = build_factors(px, tv)
    ew = f.mean(axis=1)                                              # static equal-weight multi-factor
    trail = (1 + f).rolling(12).apply(np.prod, raw=True).shift(1) - 1
    on = (trail > 0).astype(float)
    tsfm = (f * on).sum(axis=1) / on.sum(axis=1).replace(0, np.nan)
    tsfm = tsfm.fillna(0.0)[trail.notna().all(axis=1)]
    ew_c = ew.reindex(tsfm.index)
    vs_ew, vs_tsfm = vol_scale(ew_c), vol_scale(tsfm)
    idx = vs_tsfm.index.intersection(vs_ew.index)

    # single-factor TS momentum: is each factor more profitable after an up year?
    cond = pd.DataFrame({NAMES[k]: {"After positive 12M": f[k][trail[k] > 0].mean() * 12,
                                    "After negative 12M": f[k][trail[k] <= 0].mean() * 12} for k in f}).T

    fac_tbl = pd.DataFrame({NAMES[k]: perf(f[k]) for k in f}).T
    strat = {"Equal-Weight Factors": ew_c.loc[idx], "Factor Momentum": tsfm.loc[idx],
             "EW, Vol-Scaled": vs_ew.loc[idx], "Factor Momentum, Vol-Scaled": vs_tsfm.loc[idx]}
    str_tbl = pd.DataFrame({k: perf(v) for k, v in strat.items()}).T

    # in-sample vs out-of-sample (modern add-on: split the sample, no re-fitting)
    split = "2018-12-31"
    oos = pd.DataFrame({k: {"Sharpe 2015-2018": perf(v[:split])["Sharpe"],
                            "Sharpe 2019-2022": perf(v[split:])["Sharpe"]} for k, v in strat.items()}).T

    # --- Chart 1: factor cumulative returns
    fig, ax = plt.subplots()
    for k in f:
        ax.plot((1 + f[k]).cumprod(), label=NAMES[k], lw=1.6)
    ax.axhline(1, color="black", lw=0.7)
    ax.set_title("Nifty 50 factors: defensive factors collapsed, reversal and momentum paid")
    ax.set_ylabel("Growth of 1 (long-short)"); ax.legend(ncol=2, fontsize=8)
    style.finish(fig, CH / "fm_01_factors.png", SRC)

    # --- Chart 2: conditional returns
    fig, ax = plt.subplots()
    cond.plot.barh(ax=ax, color=[style.TEAL, style.RED], width=0.75)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_title("Factor returns after a positive vs. negative trailing year")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.set_xlabel("Annualised next-month return"); ax.invert_yaxis()
    style.finish(fig, CH / "fm_02_conditional.png", SRC)

    # --- Chart 3: strategies
    fig, ax = plt.subplots()
    cols = [style.GREY, style.NAVY, style.ORANGE, style.TEAL]
    for (k, v), col in zip(strat.items(), cols):
        ax.plot((1 + v).cumprod(), label=k, color=col, lw=2.2 if "Momentum" in k else 1.4,
                ls="-" if "Vol" not in k else "--")
    ax.set_title("Timing factors by their own trend vs. holding them all")
    ax.set_ylabel("Growth of 1"); ax.legend(fontsize=8)
    style.finish(fig, CH / "fm_03_strategies.png", SRC)

    # --- Chart 4: correlation heatmap
    c = f.rename(columns=NAMES).corr()
    fig, ax = plt.subplots(figsize=(7, 5.5))
    im = ax.imshow(c, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(c)), c.columns, rotation=40, ha="right", fontsize=8)
    ax.set_yticks(range(len(c)), c.columns, fontsize=8); ax.grid(False)
    for i in range(len(c)):
        for j in range(len(c)):
            ax.text(j, i, f"{c.iloc[i, j]:.2f}", ha="center", va="center", fontsize=8)
    ax.set_title("Factor correlations: low vol and low beta are close cousins")
    fig.colorbar(im, ax=ax, shrink=0.8)
    style.finish(fig, CH / "fm_04_corr.png", SRC)

    with open(ROOT / "results" / "fm_results.md", "w") as fh:
        fh.write(fac_tbl.to_markdown(floatfmt=".2f") + "\n\n" + cond.to_markdown(floatfmt=".1%") + "\n\n"
                 + str_tbl.to_markdown(floatfmt=".2f") + "\n\n" + oos.to_markdown(floatfmt=".2f"))
    print(fac_tbl.round(2)); print(cond.round(3)); print(str_tbl.round(2)); print(oos.round(2))
    print(f.index[0], f.index[-1], len(f), "strategy months", len(idx), idx[0])
    print("avg active factors", on.sum(axis=1).loc[idx].mean())


if __name__ == "__main__":
    main()
