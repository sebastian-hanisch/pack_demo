"""
Ein-Klick-Beispielszenarien und Permalink-Logik - dasselbe SETTING_SPECS-
Muster wie in der Touren-Demo (vrp_presets.py): eine Wahrheitsquelle für
Wertebereiche, aus der sowohl die Slider als auch die Permalink-Begrenzung
lesen. Vermeidet von Anfang an die Absturzklasse, die in der Touren-Demo erst
nachträglich gefunden und behoben werden musste (Permalink-Wert außerhalb der
Slider-Grenzen).
"""

import math
import random
from dataclasses import dataclass
from typing import Callable, Optional

import streamlit as st

from pack_constants import DEFAULT_CONTAINER_H, DEFAULT_CONTAINER_L, DEFAULT_CONTAINER_W, DEFAULT_COST_PER_CONTAINER


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: Callable
    default: object
    lo: Optional[float] = None
    hi: Optional[float] = None


SETTING_SPECS = {
    "container_l_slider": SettingSpec("cl", float, DEFAULT_CONTAINER_L, 50.0, 300.0),
    "container_w_slider": SettingSpec("cw", float, DEFAULT_CONTAINER_W, 50.0, 300.0),
    "container_h_slider": SettingSpec("ch", float, DEFAULT_CONTAINER_H, 50.0, 300.0),
    "n_boxes_slider": SettingSpec("n_boxes", int, 25, 5, 60),
    "min_size_slider": SettingSpec("min_size", int, 10, 5, 80),
    "max_size_slider": SettingSpec("max_size", int, 50, 5, 100),
    "seed_input": SettingSpec("seed", int, 42, 0, 2_000_000_000),
    "cost_slider": SettingSpec("cost", float, DEFAULT_COST_PER_CONTAINER, 5.0, 500.0),
}


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def apply_preset(n_boxes_val, min_size_val, max_size_val, cl_val, cw_val, ch_val, seed_val):
    st.session_state["n_boxes_slider"] = n_boxes_val
    st.session_state["min_size_slider"] = min_size_val
    st.session_state["max_size_slider"] = max_size_val
    st.session_state["container_l_slider"] = cl_val
    st.session_state["container_w_slider"] = cw_val
    st.session_state["container_h_slider"] = ch_val
    st.session_state["seed_input"] = seed_val
    st.session_state["force_regen"] = True


def randomize_seed():
    """on_click-Callback für den 'Neue Boxen generieren'-Button.

    Auf Nutzerhinweis korrigiert (identischer Fehler wie beim analogen VRP-,
    Fracht- und Transit-Button, siehe dortige Historie): der Button rief
    zuvor nur ein normales st.button() auf, dessen Wert zwar in die
    gen_key-Neuberechnung einfloss, aber bei UNVERÄNDERTEM Seed erzeugt die
    deterministische Zufallserzeugung dieselben Werte erneut - ein Klick
    bewirkte sichtbar GAR NICHTS, wenn man nicht zusätzlich selbst eine
    neue Seed-Zahl eintippte. Jetzt würfelt der Klick selbst einen neuen,
    zufälligen Seed - ein Klick liefert garantiert neue Boxen."""
    st.session_state["seed_input"] = random.randint(0, 2_000_000_000)
    st.session_state["force_regen"] = True


def load_permalink_settings():
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    applied_any = False
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            try:
                value = spec.caster(qp[spec.url_param])
                if isinstance(value, float) and not math.isfinite(value):
                    continue
                if spec.lo is not None:
                    value = max(spec.lo, value)
                if spec.hi is not None:
                    value = min(spec.hi, value)
                st.session_state[state_key] = value
                applied_any = True
            except (ValueError, TypeError):
                pass
    if applied_any:
        st.session_state["force_regen"] = True
    st.session_state["permalink_loaded"] = True


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def sync_query_params(container_l, container_w, container_h, n_boxes, min_size, max_size, seed, cost_per_container):
    try:
        st.query_params["cl"] = str(container_l)
        st.query_params["cw"] = str(container_w)
        st.query_params["ch"] = str(container_h)
        st.query_params["n_boxes"] = str(n_boxes)
        st.query_params["min_size"] = str(min_size)
        st.query_params["max_size"] = str(max_size)
        st.query_params["seed"] = str(int(seed))
        st.query_params["cost"] = str(cost_per_container)
    except Exception:
        pass
