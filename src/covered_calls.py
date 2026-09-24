"""
Research Note 01 - Covered Calls: Income Machine or Upside Tax?

Monthly covered-call overlay on the S&P 500, Jan 1999 - Dec 2018.
- Buy the index, sell a 1-month call on the first trading day of each month,
  hold to the first trading day of the next month (cash-settled at intrinsic value).
- Strikes: ATM, 2% OTM, 5% OTM.
- Option priced with Black-Scholes. Implied vol proxy = VIX minus a simple skew
  haircut (2 vol pts for ATM, +0.7 vol pt per 1% OTM). This is an assumption,
  documented in the note, and tested in a sensitivity table.
- Dividends added to both legs from Shiller monthly data. Risk-free from Ken French.
- Cost: 5% of option premium lost to bid/ask each month.
"""
import numpy as np
import pandas as pd
from scipy.stats import norm
from pathlib import Path
import matplotlib.pyplot as plt
from arch.data import sp500, frenchdata
import style

ROOT = Path(__file__).resolve().parents[1]
CH = ROOT / "charts"
style.apply()
SRC = "S&P 500 (Yahoo via arch), CBOE VIX (datahub), Shiller dividends, Ken French RF"


def bs_call(S, K, T, r, q, vol):
    d1 = (np.log(S / K) + (r - q + 0.5 * vol ** 2) * T) / (vol * np.sqrt(T))
    d2 = d1 - vol * np.sqrt(T)
    return S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)


def load():
    px = sp500.load()["Adj Close"].rename("spx")
    vix = pd.read_csv(ROOT / "data/vix_daily.csv", parse_dates=["DATE"]).set_index("DATE")["CLOSE"].rename("vix")
    sh = pd.read_csv(ROOT / "data/shiller_monthly.csv", parse_dates=["Date"]).set_index("Date")
    dy = (sh["Dividend"] / sh["SP500"]).rename("dy")            # annual dividend yield
    ff = frenchdata.load()
    rf = ff["RF"] / 100.0
    rf.index = pd.period_range("1926-07", periods=len(rf), freq="M")
    d = pd.concat([px, vix], axis=1, sort=True).dropna()
    return d, dy, rf


def backtest(skew_per_pct=0.7, atm_haircut=2.0, cost=0.05):
    d, dy, rf = load()
    first = d.groupby(d.index.to_period("M")).head(1)             # first trading day each month
    first = pd.concat([first, d.iloc[[-1]]])                        # close final month on last data day
    rows = []
    for i in range(len(first) - 1):
        t0, t1 = first.index[i], first.index[i + 1]
        S0, S1, vix0 = first.spx.iloc[i], first.spx.iloc[i + 1], first.vix.iloc[i]
        per = t0.to_period("M")
        rf_m = rf.get(per, rf.iloc[-1])                               # French data ends Nov-2018: carry last value
        r = rf_m * 12
        q = dy.asof(t0)
        T = (t1 - t0).days / 365.0
        div = S0 * q * T
        rec = {"date": t0, "spx_ret": (S1 + div) / S0 - 1, "vix": vix0, "rf": rf_m}
        for name, otm in [("ATM", 0.0), ("OTM 2%", 0.02), ("OTM 5%", 0.05)]:
            K = S0 * (1 + otm)
            vol = max(vix0 - atm_haircut - skew_per_pct * otm * 100, 5.0) / 100
            prem = bs_call(S0, K, T, r, q, vol) * (1 - cost)
            payoff = max(S1 - K, 0.0)
            rec[name] = (S1 + div + prem - payoff) / S0 - 1
            rec[name + "_prem"] = prem / S0
        rows.append(rec)
    return pd.DataFrame(rows).set_index("date")


def stats(r, rf):
    ex = r - rf
    eq = (1 + r).cumprod()
    return pd.Series({
        "CAGR": eq.iloc[-1] ** (12 / len(r)) - 1,
        "Volatility": r.std() * np.sqrt(12),
        "Sharpe": ex.mean() / ex.std() * np.sqrt(12),
        "Max Drawdown": (eq / eq.cummax() - 1).min(),
        "Worst Month": r.min(),
        "Best Month": r.max(),
    })


def main():
    bt = backtest()
    strats = ["spx_ret", "ATM", "OTM 2%", "OTM 5%"]
    names = {"spx_ret": "S&P 500", "ATM": "Covered Call ATM", "OTM 2%": "Covered Call 2% OTM", "OTM 5%": "Covered Call 5% OTM"}
    tbl = pd.DataFrame({names[s]: stats(bt[s], bt.rf) for s in strats})

    # upside / downside capture
    up, dn = bt.spx_ret > 0, bt.spx_ret < 0
    cap = pd.DataFrame({names[s]: {"Upside Capture": bt.loc[up, s].mean() / bt.loc[up, "spx_ret"].mean(),
                                    "Downside Capture": bt.loc[dn, s].mean() / bt.loc[dn, "spx_ret"].mean()} for s in strats})
    tbl = pd.concat([tbl, cap])

    # --- Chart 1: growth of $1
    fig, ax = plt.subplots()
    for s in strats:
        ax.plot((1 + bt[s]).cumprod(), label=names[s], lw=1.6 if s != "spx_ret" else 2.2)
    ax.set_title("Covered calls won 1999-2018, helped by a start between two crashes")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.1f}x")); ax.yaxis.set_minor_formatter(plt.NullFormatter())
    ax.set_ylabel("Growth of $1"); ax.legend()
    style.finish(fig, CH / "cc_01_growth.png", SRC)

    # --- Chart 2: annualised premium vs VIX
    fig, ax = plt.subplots()
    ax.plot(bt["ATM_prem"] * 12, label="ATM premium (annualised)", color=style.NAVY)
    ax.plot(bt["OTM 5%_prem"] * 12, label="5% OTM premium (annualised)", color=style.TEAL)
    ax.set_title("The income is real, but it spikes when markets crash")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}")); ax.legend()
    style.finish(fig, CH / "cc_02_premium.png", SRC)

    # --- Chart 3: avg excess return vs S&P by market bucket
    buckets = pd.cut(bt.spx_ret, [-1, -0.05, -0.02, 0, 0.02, 0.05, 1],
                     labels=["< -5%", "-5% to -2%", "-2% to 0%", "0% to 2%", "2% to 5%", "> 5%"])
    g = bt.groupby(buckets, observed=True)[["ATM", "OTM 2%", "OTM 5%"]].mean().sub(
        bt.groupby(buckets, observed=True)["spx_ret"].mean(), axis=0)
    fig, ax = plt.subplots()
    g.columns = ["Covered Call ATM", "Covered Call 2% OTM", "Covered Call 5% OTM"]
    g.plot.bar(ax=ax, rot=0, width=0.8)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("Small cushion in down months, big upside tax in rallies")
    ax.set_xlabel("S&P 500 monthly return"); ax.set_ylabel("Avg. return vs. S&P 500")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.1%}"))
    ax.legend()
    style.finish(fig, CH / "cc_03_buckets.png", SRC)

    # --- Chart 4: rolling 36m excess return
    roll = lambda s: (1 + s).rolling(36).apply(np.prod, raw=True) ** (12 / 36) - 1
    fig, ax = plt.subplots()
    for s in ["ATM", "OTM 5%"]:
        ax.plot(roll(bt[s]) - roll(bt.spx_ret), label=names[s])
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("Rolling 3-year return vs. S&P 500: a regime bet on sideways markets")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}")); ax.legend()
    style.finish(fig, CH / "cc_04_rolling.png", SRC)

    # --- Sensitivity: skew assumption (modern add-on: robustness)
    sens = []
    for sk in [0.4, 0.7, 1.0]:
        for hc in [0.0, 1.0, 2.0]:
            b = backtest(skew_per_pct=sk, atm_haircut=hc)
            sens.append({"Skew (vol pts per 1% OTM)": sk, "ATM haircut vs VIX": hc,
                         "Sharpe S&P": stats(b.spx_ret, b.rf)["Sharpe"],
                         "Sharpe ATM": stats(b["ATM"], b.rf)["Sharpe"],
                         "Sharpe 5% OTM": stats(b["OTM 5%"], b.rf)["Sharpe"]})
    sens = pd.DataFrame(sens)

    # --- Regimes
    reg = {"Dot-com bust (2000-02)": ("2000", "2002"), "Bull (2003-07)": ("2003", "2007"),
           "GFC (2008)": ("2008", "2008"), "QE bull (2009-17)": ("2009", "2017"), "Vol shocks (2018)": ("2018", "2018")}
    regt = pd.DataFrame({k: {names[s]: (1 + bt.loc[a:b, s]).prod() ** (12 / len(bt.loc[a:b])) - 1 for s in strats}
                         for k, (a, b) in reg.items()}).T

    out = ROOT / "results" / "cc_results.md"
    with open(out, "w") as f:
        f.write(tbl.to_markdown(floatfmt=".2f") + "\n\n" + regt.to_markdown(floatfmt=".1%") + "\n\n" + sens.to_markdown(index=False, floatfmt=".2f"))
    print(tbl.round(3)); print(regt.round(3)); print(sens.round(2))
    print("avg ATM prem annual", (bt.ATM_prem * 12).mean(), "OTM5", (bt["OTM 5%_prem"] * 12).mean())


if __name__ == "__main__":
    main()
