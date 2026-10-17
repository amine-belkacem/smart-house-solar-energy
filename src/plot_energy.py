"""Draws docs/energy_budget.png from the same numbers as sizing.py.

Run:  python src/plot_energy.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import sizing

OUT = Path(__file__).resolve().parent.parent / "docs" / "energy_budget.png"

BLUE = "#2a78d6"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"


def bar_panel(ax, labels, values, title, fmt):
    y = range(len(labels))[::-1]
    ax.barh(list(y), values, color=BLUE, height=0.55)
    ax.set_yticks(list(y), labels, color=INK)
    ax.set_title(title, loc="left", color=INK, fontsize=11, pad=10)
    ax.set_xlabel("Power (W)", color=INK_2)
    for yi, v in zip(y, values):
        ax.text(v + max(values) * 0.02, yi, fmt.format(v), va="center", color=INK_2, fontsize=9)
    ax.set_xlim(0, max(values) * 1.18)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_2, length=0)
    ax.set_facecolor(SURFACE)


def main():
    m = sizing.load_measurements()
    b = sizing.measured_balance(m)
    model = sizing.model_power_by_subsystem(sizing.read_csv("loads_scale_model.csv"))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 3.8), facecolor=SURFACE)

    bar_panel(
        ax1,
        ["Panels, rated (2 x 3 W)", "Taken from panels", "Stored in battery", "Arduino + DHT11 + LED"],
        [sizing.PANEL_COUNT * sizing.PANEL_VOLTAGE * sizing.PANEL_CURRENT,
         b["panel_power_w"], b["stored_power_w"], b["load_power_w"]],
        "Measured power flow on the prototype",
        "{:.2f} W",
    )
    bar_panel(
        ax2,
        ["Lighting (est.)", "Security (est.)", "Temperature (est.)", "Whole model (est.)", "Measured load"],
        [model["lighting"], model["security"], model["temperature"],
         sum(model.values()), b["load_power_w"]],
        "Scale model: datasheet estimate vs measured",
        "{:.2f} W",
    )

    fig.tight_layout(w_pad=3)
    fig.savefig(OUT, dpi=150, facecolor=SURFACE)
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
