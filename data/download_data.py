"""Download the raw data used in the notes (run once before run_all.py)."""
import subprocess, shutil, urllib.request
from pathlib import Path

D = Path(__file__).resolve().parent
urllib.request.urlretrieve("https://raw.githubusercontent.com/datasets/finance-vix/main/data/vix-daily.csv", D / "vix_daily.csv")
urllib.request.urlretrieve("https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv", D / "shiller_monthly.csv")

# NIFTY 50 constituents, daily OHLCV 2012-2022 (public GitHub dataset)
tmp = D / "_nifty_tmp"
subprocess.run(["git", "clone", "--depth", "1",
                "https://github.com/Ram9219/NIFTY-50-Stock-Market-Data-2000---2022-.git", str(tmp)], check=True)
(D / "nifty50").mkdir(exist_ok=True)
for f in tmp.glob("*.csv"):
    shutil.copy(f, D / "nifty50" / f.name)
shutil.rmtree(tmp)
print("Data ready. S&P 500 daily and Fama-French RF ship with the `arch` package.")
