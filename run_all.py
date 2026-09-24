"""Rebuild every chart and results table in the repo."""
import subprocess, sys
for script in ["src/covered_calls.py", "src/factor_momentum_india.py"]:
    print(f"Running {script} ...")
    subprocess.run([sys.executable, script], check=True)
print("Done. Charts in /charts, tables in /results.")
