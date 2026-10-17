"""Energy sizing for the Smart House solar supply.

Reproduces the calculations of my licence thesis (chapter II) from the CSV
tables in data/, then compares them with what I measured on the prototype.

A few numbers differ from the printed report on purpose. The report had
small mistakes that I only caught when redoing everything in code:
  - DC peak power: 1700 / (0.65 * 5) = 523.08 Wc, the report printed 532.076
  - Table II.2: the unit powers of the 9 lamps add up to 225 W, not 235 W
  - Table II.5: two buzzers at 0.15 W each are 0.30 W, the report kept 0.15 W

Run:  python src/sizing.py
"""

import csv
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

# Values used in the thesis for Algiers
SUN_HOURS = 5.0      # average daily sunshine, between 2 and 8 h/day
K_FACTOR = 0.65      # correction factor, usually 0.55 to 0.75

# Prototype parts
PANEL_COUNT = 2
PANEL_VOLTAGE = 6.0      # V, rated
PANEL_CURRENT = 0.5      # A, rated (the two panels are wired in parallel)
BATTERY_NOMINAL_V = 3.7
BATTERY_LABEL_AH = 5.0   # what is printed on the 18650
UNO_REGULATED_V = 5.0

# Assumption, not measured: XL6009 efficiency around 85 % when boosting
# from a single Li-ion cell to 9 V.
BOOST_EFFICIENCY = 0.85


def read_csv(name):
    with open(DATA / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------- full scale

def daily_energy(loads, supply=None):
    """Daily energy in Wh/day, corrected by the converter efficiency.

    The thesis multiplies the AC energy by 0.95 (it calls it "énergie
    corrigée du rendement"). I kept the same convention so the totals match.
    """
    total = 0.0
    for row in loads:
        if supply and row["supply"] != supply:
            continue
        e = int(row["count"]) * float(row["unit_power_w"]) * float(row["hours_per_day"])
        total += e * float(row["conversion_efficiency"])
    return total


def sum_unit_power(loads, supply=None):
    return sum(float(r["unit_power_w"]) for r in loads
               if supply is None or r["supply"] == supply)


def peak_power(energy_wh, k=K_FACTOR, sun_hours=SUN_HOURS):
    """Peak power of the PV field, Pc = Ec / (K * Ir)  (eq. II.1)."""
    return energy_wh / (k * sun_hours)


# --------------------------------------------------------------- scale model

def model_power_by_subsystem(rows):
    totals = {}
    for r in rows:
        p = int(r["quantity"]) * float(r["unit_power_w"])
        totals[r["subsystem"]] = totals.get(r["subsystem"], 0.0) + p
    return totals


# -------------------------------------------------------------- measurements

def load_measurements():
    return {r["quantity"]: float(r["value"]) for r in read_csv("measurements.csv")}


def measured_balance(m):
    """Power flow on the prototype, from the multimeter readings."""
    i_charge = m["battery_charge_current"] / 1000
    p_panel = m["panel_voltage_under_load"] * i_charge
    # Charge current measured with the battery at 3.79 V
    p_stored = 3.79 * i_charge
    p_load = m["boost_output_voltage_loaded"] * m["load_current"] / 1000
    return {
        "panel_power_w": p_panel,
        "stored_power_w": p_stored,
        # TP4056 is a linear charger, so efficiency ~ Vbat / Vin
        "charger_efficiency": p_stored / p_panel,
        "load_power_w": p_load,
    }


def estimated_capacity_ah(m, boost_eff=BOOST_EFFICIENCY):
    """Battery capacity actually delivered during the discharge test.

    Energy seen by the Arduino over the test, divided by the boost
    efficiency, gives the energy taken from the cell. Dividing by the
    nominal 3.7 V gives Ah. The test stopped at 3.45 V and a Li-ion cell can
    go down to about 3.0 V, so this is a lower bound.
    """
    p_load = m["boost_output_voltage_loaded"] * m["load_current"] / 1000
    e_battery = p_load * m["runtime_on_battery"] / boost_eff
    return e_battery / BATTERY_NOMINAL_V


def uno_regulator_loss(v_in):
    """Fraction of the power burnt in the Uno's linear regulator (Vin -> 5 V)."""
    return (v_in - UNO_REGULATED_V) / v_in


def runtime_h(capacity_ah, load_w, boost_eff=BOOST_EFFICIENCY):
    return capacity_ah * BATTERY_NOMINAL_V * boost_eff / load_w


def main():
    loads = read_csv("loads_full_scale.csv")
    e_dc = daily_energy(loads, "DC")
    e_ac = daily_energy(loads, "AC")
    print("== Full-scale house (thesis tables II.1 to II.3) ==")
    print(f"DC lamps energy         : {e_dc:8.2f} Wh/day")
    print(f"AC appliances energy    : {e_ac:8.2f} Wh/day")
    print(f"Total                   : {e_dc + e_ac:8.2f} Wh/day")
    print(f"Sum of DC unit powers   : {sum_unit_power(loads, 'DC'):8.2f} W")
    print(f"Sum of all unit powers  : {sum_unit_power(loads):8.2f} W")
    print(f"Peak power DC           : {peak_power(e_dc):8.2f} Wc")
    print(f"Peak power AC           : {peak_power(e_ac):8.2f} Wc")

    model = model_power_by_subsystem(read_csv("loads_scale_model.csv"))
    print("\n== Scale model, estimated from datasheets (tables II.4 to II.6) ==")
    for name, p in model.items():
        print(f"{name:<24}: {p:8.4f} W")
    p_model = sum(model.values())
    print(f"{'Total':<24}: {p_model:8.4f} W")

    m = load_measurements()
    b = measured_balance(m)
    cap = estimated_capacity_ah(m)
    print("\n== Prototype, measured ==")
    print(f"Rated panel power       : {PANEL_COUNT * PANEL_VOLTAGE * PANEL_CURRENT:8.2f} W")
    print(f"Power taken from panel  : {b['panel_power_w']:8.2f} W")
    print(f"Power stored in battery : {b['stored_power_w']:8.2f} W")
    print(f"Charger efficiency      : {b['charger_efficiency'] * 100:8.1f} %")
    print(f"Arduino+DHT11+LED load  : {b['load_power_w']:8.2f} W")
    print(f"Uno regulator loss @Vin : {uno_regulator_loss(m['boost_output_voltage_loaded']) * 100:8.1f} %")
    print(f"Capacity delivered      : {cap * 1000:8.0f} mAh (label {BATTERY_LABEL_AH * 1000:.0f} mAh)")
    print(f"Runtime, full model     : {runtime_h(cap, p_model):8.2f} h with measured capacity")
    print(f"Runtime, full model     : {runtime_h(BATTERY_LABEL_AH, p_model):8.2f} h if the label were true")


if __name__ == "__main__":
    main()
