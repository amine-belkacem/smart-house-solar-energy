"""Checks every result of sizing.py against values I computed by hand.

Each expected value has its hand calculation next to it, so a reader can
redo it with a calculator. If a value is off, the message says ECHEC with
what the code gave and what was expected.

Run:  pytest -v
"""

import pytest

import sizing

TOL = 1e-3  # relative tolerance


def check(name, got, expected, rel=TOL):
    assert got == pytest.approx(expected, rel=rel), (
        f"ECHEC {name}: obtenu {got:.6g}, attendu {expected:.6g}"
    )


@pytest.fixture(scope="module")
def full_scale():
    return sizing.read_csv("loads_full_scale.csv")


@pytest.fixture(scope="module")
def model():
    return sizing.model_power_by_subsystem(sizing.read_csv("loads_scale_model.csv"))


@pytest.fixture(scope="module")
def measures():
    return sizing.load_measurements()


# ------------------------------------------------ full-scale house (II.1-II.3)

def test_dc_daily_energy(full_scale):
    # lamps: 2*25*4 + 2*25*4 + 3*(1*25*4) + 2*(4*25*4) + 2*(2*25*2)
    #      = 200 + 200 + 300 + 800 + 200 = 1700 Wh/day
    check("energie DC", sizing.daily_energy(full_scale, "DC"), 1700)


def test_ac_daily_energy(full_scale):
    # (400*4 + 45*1 + 35*1 + 100*3 + 250*24) * 0.95
    # = (1600 + 45 + 35 + 300 + 6000) * 0.95 = 7980 * 0.95 = 7581 Wh/day
    check("energie AC", sizing.daily_energy(full_scale, "AC"), 7581)


def test_total_daily_energy(full_scale):
    # 1700 + 7581 = 9281 Wh/day (same as table II.1)
    check("energie totale", sizing.daily_energy(full_scale), 9281)


def test_unit_power_sums(full_scale):
    # 9 lamp lines * 25 W = 225 W (the report printed 235 W in table II.2)
    check("somme puissances DC", sizing.sum_unit_power(full_scale, "DC"), 225)
    # 225 + 400 + 45 + 35 + 100 + 250 = 1055 W (table II.1)
    check("somme puissances", sizing.sum_unit_power(full_scale), 1055)


def test_peak_power():
    # K * Ir = 0.65 * 5 = 3.25 h
    # DC: 1700 / 3.25 = 523.077 Wc (the report printed 532.076)
    check("puissance crete DC", sizing.peak_power(1700), 523.077)
    # AC: 7581 / 3.25 = 2332.615 Wc
    check("puissance crete AC", sizing.peak_power(7581), 2332.615)


# ------------------------------------------------- scale model (II.4-II.6)

def test_lighting_power(model):
    # 2*0.2145 + 0.0495 + 1.419 + 10*0.01 + 10*0.088 + 0.5
    # = 0.429 + 0.0495 + 1.419 + 0.1 + 0.88 + 0.5 = 3.3775 W
    check("eclairage", model["lighting"], 3.3775)


def test_security_power(model):
    # 0.75 + 0.01 + 2*0.088 + 2*0.15 + 0.05 + 0.25 + 0.72 + 1.419 + 0.105 + 0.75
    # = 0.75 + 0.01 + 0.176 + 0.30 + 0.05 + 0.25 + 0.72 + 1.419 + 0.105 + 0.75
    # = 4.53 W (the report counted one buzzer only and got 4.38 W)
    check("securite", model["security"], 4.53)


def test_temperature_power(model):
    # 1.419 + 0.0075 + 0.75 + 0.01 + 0.72 + 0.1 + 220*0.04^2 (= 0.352)
    # = 3.3585 W
    check("temperature", model["temperature"], 3.3585)


def test_model_total(model):
    # 3.3775 + 4.53 + 3.3585 = 11.266 W
    check("maquette totale", sum(model.values()), 11.266)


# --------------------------------------------------- prototype measurements

def test_measured_balance(measures):
    b = sizing.measured_balance(measures)
    # 5.72 V * 0.585 A = 3.3462 W
    check("puissance panneau", b["panel_power_w"], 3.3462)
    # 3.79 V * 0.585 A = 2.21715 W
    check("puissance stockee", b["stored_power_w"], 2.21715)
    # 2.21715 / 3.3462 = 0.66259 (= 3.79 / 5.72, linear charger)
    check("rendement chargeur", b["charger_efficiency"], 0.66259)
    # 8.92 V * 0.058 A = 0.51736 W
    check("puissance charge", b["load_power_w"], 0.51736)


def test_estimated_capacity(measures):
    # load energy: 0.51736 W * 11.83 h = 6.12037 Wh
    # from the cell: 6.12037 / 0.85 = 7.20044 Wh
    # in Ah:        7.20044 / 3.7  = 1.94606 Ah
    check("capacite estimee", sizing.estimated_capacity_ah(measures), 1.94606)


def test_battery_is_below_label(measures):
    # The point of the measurement: the cell gives far less than its 5 Ah label
    cap = sizing.estimated_capacity_ah(measures)
    assert cap < 0.5 * sizing.BATTERY_LABEL_AH, (
        f"ECHEC capacite: obtenu {cap:.3f} Ah, attendu moins de la moitie de "
        f"{sizing.BATTERY_LABEL_AH} Ah"
    )


def test_uno_regulator_loss():
    # (8.92 - 5) / 8.92 = 3.92 / 8.92 = 0.43946
    check("perte regulateur Uno", sizing.uno_regulator_loss(8.92), 0.43946)


def test_runtime_full_model():
    # 5 Ah * 3.7 V * 0.85 / 11.266 W = 15.725 / 11.266 = 1.39580 h
    check("autonomie 5 Ah", sizing.runtime_h(5.0, 11.266), 1.39580)
    # 1.94606 * 3.7 * 0.85 / 11.266 = 6.12036 / 11.266 = 0.54326 h
    check("autonomie mesuree", sizing.runtime_h(1.94606, 11.266), 0.54326)


def test_main_runs(capsys):
    # The script prints its report without crashing
    sizing.main()
    out = capsys.readouterr().out
    assert "523.08 Wc" in out, "ECHEC main: la puissance crete DC 523.08 Wc n'apparait pas"
