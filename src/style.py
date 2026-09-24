"""Shared chart style: clean, research-note look (navy / teal / grey)."""
import matplotlib.pyplot as plt
import matplotlib as mpl

NAVY, TEAL, GREY, ORANGE, RED = "#0B2545", "#13A89E", "#8D99AE", "#F29E4C", "#D1495B"
PALETTE = [NAVY, TEAL, ORANGE, GREY, RED, "#5E60CE"]

def apply():
    mpl.rcParams.update({
        "figure.figsize": (9, 4.8), "figure.dpi": 130, "savefig.bbox": "tight",
        "font.family": "DejaVu Sans", "font.size": 10,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.alpha": 0.25, "grid.linestyle": "-",
        "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlelocation": "left",
        "axes.prop_cycle": mpl.cycler(color=PALETTE), "legend.frameon": False,
    })

def finish(fig, path, source):
    fig.text(0.01, -0.01, f"Source: {source}. Author: Manoj Kumar Sen", fontsize=8, color=GREY, ha="left")
    fig.savefig(path)
    plt.close(fig)
    # store as compact WebP for the repo
    from PIL import Image
    from pathlib import Path
    path = Path(path)
    im = Image.open(path).convert("RGB")
    w = 820
    im = im.resize((w, int(im.height * w / im.width)), Image.LANCZOS)
    im.save(path.with_suffix(".webp"), "WEBP", quality=60, method=6)
    path.unlink()
