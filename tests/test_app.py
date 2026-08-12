"""
Automatisierte Tests für die 3D-Packungsoptimierung-Demo.

Zwei Ebenen, wie in der Tourenplanung-Demo:
1. UI-Tests über streamlit.testing.v1.AppTest.
2. Unit-Tests der reinen Geometrie-/Heuristik-/Bewertungsfunktionen (normale
   Imports, da die Logik in eigenen Modulen ohne Streamlit-UI-Code liegt).

Ausführen mit: pytest tests/ -v
"""

import os
import sys

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

APP_DIR = os.path.join(os.path.dirname(__file__), "..")
APP_PATH = os.path.join(APP_DIR, "app.py")
TIMEOUT = 90

sys.path.insert(0, os.path.abspath(APP_DIR))


def fresh_app():
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=TIMEOUT)
    return at


def assert_ok(at):
    assert not at.exception, f"Unerwartete Exception(s): {[e.message for e in at.exception]}"


# ==========================================================================
# 1. UI-Tests (AppTest)
# ==========================================================================

def test_default_load():
    at = fresh_app()
    assert_ok(at)
    assert len(at.tabs) == 4  # Schichten-basiert, Extreme-Point, Beam Search, Vergleich


@pytest.mark.parametrize("label", ["Gleichmäßige Kartons", "Gemischte Ladung", "Viele kleine Pakete"])
def test_presets_apply_without_crash(label):
    at = fresh_app()
    btn = [b for b in at.button if label in b.label][0]
    btn.click().run(timeout=TIMEOUT)
    assert_ok(at)


def test_regenerate_button():
    at = fresh_app()
    at.sidebar.button[0].click().run(timeout=TIMEOUT)
    assert_ok(at)


@pytest.mark.parametrize("slider_idx,value", [(0, 300), (0, 50), (3, 60), (3, 5)])
def test_slider_extremes(slider_idx, value):
    at = fresh_app()
    at.sidebar.slider[slider_idx].set_value(value).run(timeout=TIMEOUT)
    assert_ok(at)


def test_worst_case_settings_no_crash():
    """Größter Container + meiste Boxen + kleinste Boxen (viele Platzierungsversuche)."""
    at = fresh_app()
    at.sidebar.slider[0].set_value(300).run(timeout=TIMEOUT)
    at.sidebar.slider[1].set_value(300).run(timeout=TIMEOUT)
    at.sidebar.slider[2].set_value(300).run(timeout=TIMEOUT)
    at.sidebar.slider[3].set_value(60).run(timeout=TIMEOUT)
    at.sidebar.slider[4].set_value(5).run(timeout=TIMEOUT)
    assert_ok(at)


@pytest.mark.parametrize("prefix", ["layer", "extreme", "beam"])
def test_animation_toggle(prefix):
    at = fresh_app()
    cb = [c for c in at.checkbox if c.key == f"{prefix}_auto"]
    assert cb, f"Auto-Play-Checkbox für {prefix} nicht gefunden"
    cb[0].check().run(timeout=TIMEOUT)
    assert_ok(at)


def test_pdf_download_buttons_present():
    at = fresh_app()
    assert_ok(at)
    labels = [d.label for d in at.download_button]
    assert len(labels) == 3
    assert all("PDF" in l for l in labels)


def test_feedback_buttons_present_and_work():
    at = fresh_app()
    up = [b for b in at.button if b.key == "feedback_up_btn"]
    assert up
    up[0].click().run(timeout=TIMEOUT)
    assert_ok(at)
    assert any("Danke" in str(s.value) for s in at.success)


def test_comparison_tab_has_all_three_methods():
    at = fresh_app()
    assert_ok(at)
    comparison_dfs = [d for d in at.dataframe if "Methode" in d.value.columns]
    assert comparison_dfs, "Vergleichstabelle nicht gefunden"
    methods = comparison_dfs[0].value["Methode"].tolist()
    assert "Schichten-basiert" in methods
    assert "Extreme-Point" in methods
    assert "Beam Search" in methods


def test_permalink_writes_and_restores():
    at = fresh_app()
    assert_ok(at)
    qp = dict(at.query_params)
    for key in ["cl", "cw", "ch", "n_boxes", "min_size", "max_size", "seed", "cost"]:
        assert key in qp

    at2 = AppTest.from_file(APP_PATH)
    at2.query_params["n_boxes"] = "18"
    at2.run(timeout=TIMEOUT)
    assert_ok(at2)
    assert at2.sidebar.slider[3].value == 18


@pytest.mark.parametrize("param,value,label", [
    ("n_boxes", "9999", "n_boxes weit über Maximum"),
    ("n_boxes", "-50", "n_boxes negativ"),
    ("cl", "99999", "Container-Länge weit über Maximum"),
    ("cost", "nan", "cost=nan"),
    ("cost", "inf", "cost=inf"),
    ("seed", "-42", "seed negativ"),
    ("min_size", "not_a_number", "min_size ungültiger Text"),
])
def test_permalink_handles_bad_values_without_crash(param, value, label):
    """Regressionstest übernommen aus der Tourenplanung-Demo: Permalink-Werte
    außerhalb des Wertebereichs oder ungültigen Typs dürfen die App nie zum
    Absturz bringen. Hier von Anfang an über SETTING_SPECS/bounds() korrekt
    umgesetzt statt erst nachträglich gefunden."""
    at = AppTest.from_file(APP_PATH)
    at.query_params[param] = value
    at.run(timeout=TIMEOUT)
    assert_ok(at)


def test_slider_bounds_match_setting_specs():
    """Wartbarkeits-Schutz analog zur Tourenplanung-Demo: Slider-Wertebereiche
    dürfen nicht von SETTING_SPECS abweichen, aus dem auch die
    Permalink-Begrenzung liest."""
    import pack_presets

    at = fresh_app()
    assert_ok(at)
    by_key = {s.key: s for s in at.sidebar.slider if s.key}
    checked = 0
    for state_key, spec in pack_presets.SETTING_SPECS.items():
        if spec.lo is None or state_key not in by_key:
            continue
        slider = by_key[state_key]
        assert slider.min == pytest.approx(spec.lo)
        assert slider.max == pytest.approx(spec.hi)
        checked += 1
    assert checked >= 5


# ==========================================================================
# 2. Unit-Tests der reinen Funktionen
# ==========================================================================

from pack_evaluation import box_volume, estimate_extra_containers, evaluate_packing, volume_to_business
from pack_geometry import any_overlap, box_rotations, boxes_overlap, fits_in_container
from pack_heuristics import beam_search_packing, extreme_point_packing, layer_based_packing
from pack_visualization import _BOX_TRIANGLES_I, _BOX_TRIANGLES_J, _BOX_TRIANGLES_K


def _random_boxes(n, seed, lo=10, hi=50):
    rng = np.random.default_rng(seed)
    return [tuple(x) for x in rng.uniform(lo, hi, size=(n, 3)).round(1)]


def _validate_packing(placements, boxes, container_dim, unplaced):
    """Gemeinsame Korrektheitsprüfung für beide Heuristiken: keine
    Mehrfachplatzierung, alle Boxen erfasst, alles innerhalb der
    Containergrenzen, keine Überlappungen, Volumen-Konsistenz."""
    placed_idxs = [p["box_idx"] for p in placements]
    assert len(placed_idxs) == len(set(placed_idxs)), "Box mehrfach platziert"
    all_idxs = set(range(len(boxes)))
    assert set(placed_idxs) | set(unplaced) == all_idxs, "Boxen fehlen in platziert+unplaced"
    assert not (set(placed_idxs) & set(unplaced)), "Box gleichzeitig platziert und unplaced"
    for p in placements:
        assert fits_in_container(p["pos"], p["dim"], container_dim), f"Box {p['box_idx']} außerhalb"
    for i in range(len(placements)):
        for j in range(i + 1, len(placements)):
            assert not boxes_overlap(
                placements[i]["pos"], placements[i]["dim"], placements[j]["pos"], placements[j]["dim"]
            ), f"Überlappung zwischen Box {placements[i]['box_idx']} und {placements[j]['box_idx']}"
    placed_vol = sum(box_volume(p["dim"]) for p in placements)
    assert placed_vol <= box_volume(container_dim) + 1e-6


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
@pytest.mark.parametrize("heuristic", [layer_based_packing, extreme_point_packing, beam_search_packing])
def test_heuristics_produce_valid_packing(heuristic, seed):
    boxes = _random_boxes(25, seed)
    container_dim = (120.0, 80.0, 100.0)
    placements, unplaced = heuristic(boxes, container_dim)
    _validate_packing(placements, boxes, container_dim, unplaced)


def test_extreme_point_generally_beats_layer_based():
    """Kein Korrektheits-, sondern ein Qualitäts-Sanity-Check: Die
    fortgeschrittenere Heuristik sollte im Schnitt über mehrere Instanzen
    eine bessere Raumnutzung erreichen als die einfache Schichten-Heuristik."""
    container_dim = (120.0, 80.0, 100.0)
    wins = 0
    total = 0
    for seed in range(1, 8):
        boxes = _random_boxes(25, seed)
        p_layer, u_layer = layer_based_packing(boxes, container_dim)
        p_ep, u_ep = extreme_point_packing(boxes, container_dim)
        util_layer = sum(box_volume(p["dim"]) for p in p_layer) / box_volume(container_dim)
        util_ep = sum(box_volume(p["dim"]) for p in p_ep) / box_volume(container_dim)
        if util_ep >= util_layer:
            wins += 1
        total += 1
    assert wins == total, "Extreme-Point sollte in jedem Testfall mindestens gleich gut wie Schichten-basiert sein"


def test_empty_box_list_handled_gracefully():
    for heuristic in [layer_based_packing, extreme_point_packing, beam_search_packing]:
        placements, unplaced = heuristic([], (120.0, 80.0, 100.0))
        assert placements == []
        assert unplaced == []


def test_single_box_too_large_for_container_is_unplaced():
    boxes = [(200.0, 200.0, 200.0)]  # größer als der Container in jeder Dimension
    for heuristic in [layer_based_packing, extreme_point_packing, beam_search_packing]:
        placements, unplaced = heuristic(boxes, (120.0, 80.0, 100.0))
        assert placements == []
        assert unplaced == [0]


def test_beam_search_generally_at_least_as_good_as_extreme_point():
    """Qualitäts-Sanity-Check, analog zum Extreme-Point-vs-Schichten-Test.
    Im Benchmark (siehe README) gewinnt Beam Search in 6 von 10 Instanzen,
    verliert nur 2 (jeweils um <1 Prozentpunkt) - im Schnitt +0,9
    Prozentpunkte. Dieser Test prüft die Richtung des Effekts über eine
    kleinere Stichprobe, nicht die exakten Werte (die hängen vom Zufalls-Seed
    ab)."""
    container_dim = (120.0, 80.0, 100.0)
    net_deltas = []
    for seed in range(1, 6):
        rng = np.random.default_rng(seed)
        n_boxes = rng.integers(15, 35)
        boxes = _random_boxes(n_boxes, seed)
        p_ep, _ = extreme_point_packing(boxes, container_dim)
        p_bs, _ = beam_search_packing(boxes, container_dim)
        util_ep = sum(box_volume(p["dim"]) for p in p_ep)
        util_bs = sum(box_volume(p["dim"]) for p in p_bs)
        net_deltas.append(util_bs - util_ep)
    assert sum(net_deltas) >= 0, "Beam Search sollte im Schnitt nicht schlechter als Extreme-Point sein"


def test_beam_search_worst_case_completes_within_budget():
    """Regressionstest für einen beim Bauen gefundenen ehrlichen Befund:
    Beam Search bringt bei großen, dünn besiedelten Containern manchmal
    exakt keine Verbesserung gegenüber Extreme-Point, ist dabei aber 6-7x
    langsamer. Kein Korrektheits-, sondern ein Performance-Schutztest -
    stellt sicher, dass der Worst Case (großer Container, viele Boxen)
    innerhalb eines für die automatische (nicht Button-gesteuerte)
    Neuberechnung bei jeder UI-Interaktion vertretbaren Zeitrahmens bleibt."""
    import time

    boxes = _random_boxes(60, seed=1, lo=8, hi=100)
    container_dim = (300.0, 300.0, 300.0)
    t0 = time.time()
    beam_search_packing(boxes, container_dim)
    elapsed = time.time() - t0
    assert elapsed < 5.0, f"Beam Search Worst Case dauerte {elapsed:.1f}s - zu langsam für automatische Neuberechnung"


def test_box_rotations_count_and_volume_preserved():
    rotations = box_rotations(10, 20, 30)
    assert 1 <= len(rotations) <= 6
    for r in rotations:
        assert sorted(r) == [10, 20, 30]


def test_box_rotations_deduplicates_cube():
    # Ein Würfel hat nur 1 eindeutige "Rotation" (alle Permutationen gleich)
    rotations = box_rotations(15, 15, 15)
    assert len(rotations) == 1


def test_boxes_overlap_detects_true_overlap():
    assert boxes_overlap((0, 0, 0), (10, 10, 10), (5, 5, 5), (10, 10, 10))


def test_boxes_overlap_touching_faces_not_overlap():
    """Zwei Boxen, die sich nur an einer Fläche berühren (kein Volumen
    gemeinsam), gelten NICHT als überlappend."""
    assert not boxes_overlap((0, 0, 0), (10, 10, 10), (10, 0, 0), (10, 10, 10))


def test_any_overlap_against_multiple_boxes():
    placed = [((0, 0, 0), (10, 10, 10)), ((20, 0, 0), (10, 10, 10))]
    assert any_overlap((5, 5, 5), (2, 2, 2), placed)
    assert not any_overlap((15, 0, 0), (2, 2, 2), placed)


def test_fits_in_container_rejects_negative_and_overflow():
    assert fits_in_container((0, 0, 0), (10, 10, 10), (20, 20, 20))
    assert not fits_in_container((-1, 0, 0), (10, 10, 10), (20, 20, 20))
    assert not fits_in_container((15, 0, 0), (10, 10, 10), (20, 20, 20))


def test_box_mesh_triangles_cover_all_six_faces_exactly():
    """Regressionstest für einen beim Bau gefundenen Bug: Eine falsch
    geschriebene Dreiecksliste ließ eine Seitenfläche des 3D-Box-Meshs
    unbedeckt (sichtbares Loch), während eine andere Fläche ein
    überzähliges/falsches Dreieck hatte. Prüft geometrisch, dass alle 6
    Flächen eines Einheitswürfels von genau 2 Dreiecken lückenlos und ohne
    Überlappung abgedeckt werden."""
    from collections import defaultdict

    verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
    triangles = list(zip(_BOX_TRIANGLES_I, _BOX_TRIANGLES_J, _BOX_TRIANGLES_K))
    assert len(triangles) == 12

    def tri_area_on_face(p1, p2, p3, axis):
        others = [i for i in range(3) if i != axis]
        a, b, c = (p1[others[0]], p1[others[1]]), (p2[others[0]], p2[others[1]]), (p3[others[0]], p3[others[1]])
        return abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2

    covered = defaultdict(list)
    for (i, j, k) in triangles:
        p1, p2, p3 = verts[i], verts[j], verts[k]
        const_axis = next(axis for axis in range(3) if len({p1[axis], p2[axis], p3[axis]}) == 1)
        const_val = p1[const_axis]
        covered[(const_axis, const_val)].append(tri_area_on_face(p1, p2, p3, const_axis))

    for face in [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1)]:
        areas = covered.get(face, [])
        assert len(areas) == 2, f"Fläche {face}: {len(areas)} Dreiecke statt 2"
        assert sum(areas) == pytest.approx(1.0), f"Fläche {face}: Gesamtfläche {sum(areas)} statt 1.0"


def test_evaluate_packing_utilization_and_unplaced():
    boxes = _random_boxes(20, seed=1)
    container_dim = (120.0, 80.0, 100.0)
    placements, unplaced = extreme_point_packing(boxes, container_dim)
    stats = evaluate_packing(placements, boxes, container_dim, unplaced)
    assert 0 <= stats["utilization_pct"] <= 100
    assert stats["n_placed"] + stats["n_unplaced"] == len(boxes)
    assert stats["placed_volume"] + stats["unplaced_volume"] == pytest.approx(
        sum(box_volume(b) for b in boxes), rel=1e-6
    )


def test_estimate_extra_containers_zero_when_nothing_unplaced():
    assert estimate_extra_containers(0.0, 960000.0) == 0


def test_estimate_extra_containers_rounds_up():
    # 0.3 Container Bedarf -> es wird trotzdem 1 ganzer Container gebraucht
    assert estimate_extra_containers(300000.0, 1000000.0) == 1


def test_volume_to_business_cost_scales_with_containers():
    containers, cost = volume_to_business(2_000_000.0, 1_000_000.0, cost_per_container=50.0)
    assert containers == 2
    assert cost == pytest.approx(100.0)


def test_generate_pack_plan_pdf_produces_valid_pdf():
    from pack_pdf_export import generate_pack_plan_pdf

    boxes = _random_boxes(10, seed=2)
    ids = list(range(1, 11))
    container_dim = (120.0, 80.0, 100.0)
    placements, unplaced = extreme_point_packing(boxes, container_dim)
    pdf_bytes = generate_pack_plan_pdf("Extreme-Point", placements, boxes, ids, unplaced, container_dim, 50.0)
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 500


def test_feedback_log_and_count_roundtrip(tmp_path):
    from pack_feedback import get_feedback_counts, log_feedback

    log_file = str(tmp_path / "feedback_test.csv")
    assert get_feedback_counts(log_file) == (0, 0)
    assert log_feedback("up", log_file) is True
    assert log_feedback("down", log_file) is True
    assert log_feedback("up", log_file) is True
    assert get_feedback_counts(log_file) == (2, 1)
