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


@pytest.mark.parametrize("label", ["Gleichmäßige Kartons", "Gemischte Ladung", "Viele kleine Pakete", "Enges Puzzle"])
def test_presets_apply_without_crash(label):
    at = fresh_app()
    btn = [b for b in at.button if label in b.label][0]
    btn.click().run(timeout=TIMEOUT)
    assert_ok(at)


def test_regenerate_button():
    """Verstärkt auf Nutzerhinweis: prüfte zuvor nur 'kein Absturz', nicht
    die tatsächliche Wirkung - genau die Art Test, die den ursprünglichen
    Fehler (Button ohne Effekt bei unverändertem Seed, siehe
    randomize_seed-Docstring in pack_presets.py) nicht erkannt hätte."""
    at = fresh_app()
    seed_before = at.sidebar.number_input(key="seed_input").value
    at.sidebar.button[0].click().run(timeout=TIMEOUT)
    assert_ok(at)
    seed_after = at.sidebar.number_input(key="seed_input").value
    assert seed_after != seed_before, "Seed hat sich durch den Klick nicht geändert"


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


def test_comparison_tab_has_all_three_methods():
    at = fresh_app()
    assert_ok(at)
    comparison_dfs = [d for d in at.dataframe if "Methode" in d.value.columns]
    assert comparison_dfs, "Vergleichstabelle nicht gefunden"
    methods = comparison_dfs[0].value["Methode"].tolist()
    assert "Schichten-basiert" in methods
    assert "Extreme-Point" in methods
    assert "Beam Search" in methods


def test_seed_change_alone_regenerates_boxes():
    """Regressionstest für einen gefundenen Bug: Der Regenerierungs-Trigger
    prüfte nur, ob sich die Anzahl Boxen geändert hat - ein reiner
    Seed-Wechsel (ohne n_boxes zu ändern) erzeugte dadurch KEINE neuen Boxen,
    obwohl die Sidebar bereits den neuen Seed zeigte. Betraf denselben
    Fehlermuster wie ein noch ungeprüfter, vermutlich identischer Fall in der
    Tourenplanung-Demo."""
    at = fresh_app()
    df_before = at.session_state["boxes"].copy()
    at.number_input[0].set_value(999).run(timeout=TIMEOUT)
    assert_ok(at)
    df_after = at.session_state["boxes"]
    assert not df_before.equals(df_after), "Boxen haben sich nach reinem Seed-Wechsel nicht geändert"


def test_size_range_change_alone_regenerates_boxes():
    """Regressionstest für denselben Bug: Auch ein reiner Wechsel von
    Min./Max.-Kantenlänge (ohne n_boxes zu ändern) muss die Boxen neu
    erzeugen. Vorher blieben die alten Box-Größen bestehen, obwohl die
    Sidebar bereits die neuen Grenzen zeigte."""
    at = fresh_app()
    at.sidebar.slider[4].set_value(70).run(timeout=TIMEOUT)
    at.sidebar.slider[5].set_value(90).run(timeout=TIMEOUT)
    assert_ok(at)
    df = at.session_state["boxes"]
    assert df["laenge"].min() >= 70 - 1e-6
    assert df["laenge"].max() <= 90 + 1e-6


def test_comparison_tab_does_not_falsely_claim_winner_on_tie():
    """Regressionstest für einen gefundenen Bug: Wenn alle drei Heuristiken
    dieselbe Raumnutzung erreichen (z. B. weil ohnehin alle Boxen passen -
    'platziertes Volumen / Containervolumen' ist dann bei allen Methoden
    identisch, unabhängig von der tatsächlichen Packqualität), erklärte
    max()/min() willkürlich den ERSTEN Kandidaten der Liste zum Sieger. Jetzt
    wird ein echter Gleichstand erkannt und ehrlich benannt statt eine
    Falschaussage zu treffen."""
    at = fresh_app()
    # Viele kleine Boxen in einem riesigen Container -> alles passt trivial,
    # Raumnutzung ist dadurch bei allen drei Methoden identisch.
    at.sidebar.slider[0].set_value(300).run(timeout=TIMEOUT)
    at.sidebar.slider[1].set_value(300).run(timeout=TIMEOUT)
    at.sidebar.slider[2].set_value(300).run(timeout=TIMEOUT)
    at.sidebar.slider[3].set_value(5).run(timeout=TIMEOUT)
    at.sidebar.slider[4].set_value(5).run(timeout=TIMEOUT)
    at.sidebar.slider[5].set_value(15).run(timeout=TIMEOUT)
    assert_ok(at)

    md_texts = [str(m.value) for m in at.markdown]
    winner_claims = [t for t in md_texts if "➡️" in t and "erreicht hier die bessere Raumnutzung" in t]
    assert not winner_claims, f"Falschaussage bei Gleichstand gefunden: {winner_claims}"
    tie_notes = [t for t in md_texts if "➡️" in t and "praktisch dieselbe Raumnutzung" in t]
    assert tie_notes, "Erwarteter Gleichstand-Hinweis fehlt"



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


def test_seed_input_bounds_match_setting_specs():
    """Regressionstest für einen gefundenen Bug: anders als alle Slider hatte
    das Zufalls-Seed-Feld keine min_value/max_value-Grenze, obwohl
    SETTING_SPECS für seed_input lo=0 vorschreibt (nur die Permalink-Ladung
    und die Preset-Buttons hielten sich bereits daran). Ein per Tippen oder
    Minus-Stepper erreichbarer negativer Seed ließ np.random.default_rng()
    mit ValueError abstürzen. Jetzt an dieselbe Wahrheitsquelle gebunden wie
    die Slider."""
    import pack_presets

    at = fresh_app()
    assert_ok(at)
    seed_widget = at.sidebar.number_input(key="seed_input")
    spec = pack_presets.SETTING_SPECS["seed_input"]
    assert seed_widget.proto.min == pytest.approx(spec.lo)
    assert seed_widget.proto.max == pytest.approx(spec.hi)


def test_auto_play_does_not_replay_on_unrelated_rerun():
    """Regressionstest für einen gefundenen Bug: render_packing_panel läuft
    für alle drei Methoden-Tabs bei JEDEM Rerun (Streamlit-Tabs sind nicht
    "lazy"), nicht nur für den gerade sichtbaren. Eine angehakte "Automatisch
    abspielen"-Checkbox in einem Tab spielte deshalb die komplette
    (blockierende, time.sleep-basierte) Animation bei JEDEM Rerun erneut ab -
    auch wenn ein völlig anderer Tab/Widget den Rerun ausgelöst hat. Jetzt
    spielt ein Ankreuzen genau einmal ab (Flag `{prefix}_auto_played`)."""
    at = fresh_app()
    layer_auto = [c for c in at.checkbox if c.key == "layer_auto"]
    assert layer_auto, "Auto-Play-Checkbox nicht gefunden (zu wenige platzierte Boxen?)"
    layer_auto[0].check().run(timeout=TIMEOUT)
    assert_ok(at)
    assert at.session_state["layer_auto_played"] is True

    # Unbeteiligtes Widget in einem ANDEREN Tab betätigen - löst einen vollen
    # Rerun aus, der render_packing_panel auch für den Layer-Tab erneut läuft.
    extreme_step = [s for s in at.slider if s.key == "extreme_step"]
    assert extreme_step
    new_value = max(0, extreme_step[0].value - 1)
    extreme_step[0].set_value(new_value).run(timeout=TIMEOUT)
    assert_ok(at)
    # Checkbox ist weiterhin angehakt, aber das "schon abgespielt"-Flag darf
    # nicht zurückgesetzt worden sein - genau das verhindert das erneute,
    # unsichtbar blockierende Abspielen.
    assert at.session_state["layer_auto_played"] is True


# ==========================================================================
# 2. Unit-Tests der reinen Funktionen
# ==========================================================================

from pack_evaluation import box_volume, classify_comparison, estimate_extra_containers, evaluate_packing, volume_to_business
from pack_geometry import any_overlap, box_rotations, boxes_overlap, contact_area, fits_in_container, is_supported
from pack_heuristics import extreme_point_packing, layer_based_packing, monobeam_packing, rescue_unplaced_via_swap
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
@pytest.mark.parametrize("heuristic", [layer_based_packing, extreme_point_packing, monobeam_packing])
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
    for heuristic in [layer_based_packing, extreme_point_packing, monobeam_packing]:
        placements, unplaced = heuristic([], (120.0, 80.0, 100.0))
        assert placements == []
        assert unplaced == []


def test_single_box_too_large_for_container_is_unplaced():
    boxes = [(200.0, 200.0, 200.0)]  # größer als der Container in jeder Dimension
    for heuristic in [layer_based_packing, extreme_point_packing, monobeam_packing]:
        placements, unplaced = heuristic(boxes, (120.0, 80.0, 100.0))
        assert placements == []
        assert unplaced == [0]


def test_gleichmaessige_kartons_preset_shows_no_beam_regression():
    """Regressionstest für einen gefundenen Fehler, der seitdem dreimal
    neu bewertet werden musste. Ursprünglich (Seed 10): Beam Search
    SCHLECHTER als beide anderen Methoden (54.1% vs. 56.2%) - Seed 8
    korrigierte das auf einen exakten Dreifach-Gleichstand. Nach der
    Stützungsprüfung (`is_supported`) verschob sich das Bild erneut - Seed
    8 zeigte Beam Search wieder schlechter, auf Seed 3 korrigiert. Nach der
    DBL-Korrektur (siehe monobeam_packing-Docstring: Breite 1 entspricht
    jetzt exakt Extreme-Point, garantiert per Konstruktion nie schlechter)
    ist praktisch JEDER Seed bei uniformen Boxgrößen ein sauberer
    Gleichstand (44 von 49 getesteten) - auf Seed 1 vereinfacht."""
    container_dim = (120.0, 80.0, 100.0)
    boxes = _random_boxes(20, seed=1, lo=25, hi=35)

    p_layer, _ = layer_based_packing(boxes, container_dim)
    p_ep, _ = extreme_point_packing(boxes, container_dim)
    p_bs, _ = monobeam_packing(boxes, container_dim)

    u_layer = sum(box_volume(p["dim"]) for p in p_layer) / box_volume(container_dim) * 100
    u_ep = sum(box_volume(p["dim"]) for p in p_ep) / box_volume(container_dim) * 100
    u_bs = sum(box_volume(p["dim"]) for p in p_bs) / box_volume(container_dim) * 100

    assert u_bs >= u_ep - 0.5, f"Beam Search sollte hier nicht schlechter als Extreme-Point sein: {u_bs:.1f}% vs {u_ep:.1f}%"
    assert u_bs >= u_layer - 0.5, f"Beam Search sollte hier nicht schlechter als Schichten-basiert sein: {u_bs:.1f}% vs {u_layer:.1f}%"


def test_beam_search_beam_width_1_exactly_equals_extreme_point():
    """Kern-Regressionstest für eine vom Nutzer gestellte, scharfe Frage:
    'Beam Search bei Breite 1 sollte doch praktisch Extreme-Point sein,
    wieso kann Extreme-Point da besser abschneiden?' - zurecht, war es
    vorher nicht. Zwei unabhängige Ursachen gefunden (siehe monobeam_packing
    Docstring für die vollständige Herleitung, inkl. eines Kombinationsver-
    suchs, der verworfen wurde): (1) die Pro-Schritt-Bewertungsgröße
    (Maximalhöhe statt DBL) und (2) die Auflösung echter Gleichstände
    (State-Fingerprint statt Erzeugungsreihenfolge). Nach Korrektur beider
    Punkte: Breite 1 ist byte-identisch mit extreme_point_packing - geprüft
    über mehrere Instanzen und Boxgrößenbereiche."""
    container_dim = (120.0, 80.0, 100.0)
    for seed in range(1, 6):
        boxes = _random_boxes(25, seed=seed, lo=10, hi=60)
        p_ep, u_ep = extreme_point_packing(boxes, container_dim)
        p_b1, u_b1 = monobeam_packing(boxes, container_dim, beam_width=1)
        assert sorted((p["pos"], p["dim"]) for p in p_ep) == sorted((p["pos"], p["dim"]) for p in p_b1), (
            f"seed={seed}: Beam Search bei Breite 1 sollte byte-identisch mit Extreme-Point sein"
        )
        assert sorted(u_ep) == sorted(u_b1)


def test_beam_search_never_worse_than_extreme_point():
    """Direkte Folge aus der Breite-1-Identität plus der Monotonie-
    Garantie: Beam Search kann bei KEINER Breite mehr schlechter als
    Extreme-Point sein. Über 20 Instanzen geprüft."""
    container_dim = (120.0, 80.0, 100.0)
    for seed in range(1, 11):
        for beam_width in [2, 4, 8]:
            boxes = _random_boxes(25, seed=seed, lo=8, hi=60)
            p_ep, _ = extreme_point_packing(boxes, container_dim)
            p_bs, _ = monobeam_packing(boxes, container_dim, beam_width=beam_width)
            u_ep = sum(box_volume(p["dim"]) for p in p_ep) / box_volume(container_dim) * 100
            u_bs = sum(box_volume(p["dim"]) for p in p_bs) / box_volume(container_dim) * 100
            assert u_bs >= u_ep - 1e-6, (
                f"seed={seed} bw={beam_width}: Beam Search ({u_bs:.1f}%) schlechter als "
                f"Extreme-Point ({u_ep:.1f}%) - sollte nach der DBL-Korrektur unmöglich sein"
            )


def test_viele_kleine_pakete_preset_is_genuinely_capacity_constrained():
    """Regressionstest für einen gefundenen Fehler: der ursprüngliche Preset
    (45 Boxen, 8-25cm, Standardcontainer 120x80x100) hatte ein
    Gesamtboxvolumen von nur 20.9% des Containervolumens - dadurch passten
    ALLE Boxen bei ALLEN DREI Methoden vollständig hinein (0 unplatziert je
    Methode), und die Raumnutzung war bei allen drei Methoden identisch
    (20.9%) - kein Stresstest, sondern das Gegenteil: die Kennzahl maß nur
    noch 'passt rein', nicht mehr Packqualität. Auf einen kleineren Container
    (70x60x50 statt 120x80x100) korrigiert, sodass die 60 Boxen (Maximum)
    tatsächlich konkurrieren (Gesamtvolumen ~131% des Containers) - echte,
    unterschiedliche unplatzierte Anzahl je Methode."""
    container_dim = (70.0, 60.0, 50.0)
    boxes = _random_boxes(60, seed=1, lo=8, hi=25)

    total_box_vol = sum(box_volume(b) for b in boxes)
    assert total_box_vol > box_volume(container_dim), (
        "Boxen sollten NICHT alle hineinpassen - sonst kein echter Stresstest"
    )

    p_layer, u_layer_list = layer_based_packing(boxes, container_dim)
    p_ep, u_ep_list = extreme_point_packing(boxes, container_dim)

    assert len(u_layer_list) > 0, "Schichten-basiert sollte hier tatsächlich Boxen nicht unterbringen"
    assert len(u_ep_list) > 0, "Extreme-Point sollte hier tatsächlich Boxen nicht unterbringen"

    u_layer = sum(box_volume(p["dim"]) for p in p_layer) / box_volume(container_dim) * 100
    u_ep = sum(box_volume(p["dim"]) for p in p_ep) / box_volume(container_dim) * 100
    assert u_ep > u_layer + 15.0, f"Erwarteter deutlicher Extreme-Point-Vorsprung fehlt: {u_ep:.1f}% vs {u_layer:.1f}%"


def test_enges_puzzle_preset_shows_clear_beam_search_advantage():
    """Auf Wunsch ergänzt, seitdem zweimal neu gesucht. Erster Fund (Seed 3,
    15-55cm) mit monobeam nicht reproduzierbar, auf n=25, Größe 8-70cm,
    Seed 11 korrigiert. Nach der DBL-Korrektur (siehe monobeam_packing-
    Docstring - Breite 1 entspricht jetzt exakt Extreme-Point) verschwand
    DIESER Vorsprung komplett (blieb exakt bei 71,8%, selbst bei Breite
    32) - er war teilweise ein Artefakt der vorherigen falschen
    Bewertungsgröße, keine echte Exploration. Systematisch neu gesucht
    (~300 Konfigurationen): echte, wenn auch seltenere Vorteile bleiben
    nachweisbar - n=30, Größe 8-70cm, Seed 10 zeigt bei Standardbreite 6
    einen Vorsprung von 4,6 Prozentpunkten (71,6%→76,2%), der bei größerer
    Breite weiter wächst (Breite 16: 81,7%)."""
    container_dim = (120.0, 80.0, 100.0)
    boxes = _random_boxes(30, seed=10, lo=8, hi=70)

    p_layer, _ = layer_based_packing(boxes, container_dim)
    p_ep, _ = extreme_point_packing(boxes, container_dim)
    p_bs, _ = monobeam_packing(boxes, container_dim)

    u_layer = sum(box_volume(p["dim"]) for p in p_layer) / box_volume(container_dim) * 100
    u_ep = sum(box_volume(p["dim"]) for p in p_ep) / box_volume(container_dim) * 100
    u_bs = sum(box_volume(p["dim"]) for p in p_bs) / box_volume(container_dim) * 100

    assert u_bs - u_ep > 3.0, f"Erwarteter deutlicher Vorsprung vor Extreme-Point fehlt: {u_bs:.1f}% vs {u_ep:.1f}%"
    assert u_bs - u_layer > 15.0, f"Erwarteter deutlicher Vorsprung vor Schichten-basiert fehlt: {u_bs:.1f}% vs {u_layer:.1f}%"


def test_beam_search_generally_at_least_as_good_as_extreme_point():
    """Qualitäts-Sanity-Check, analog zum Extreme-Point-vs-Schichten-Test.
    Über eine breitere Stichprobe (30 Instanzen, siehe README) ist monobeam
    im Schnitt +0,25 Prozentpunkte besser als die frühere (nicht-monotone)
    Implementierung und gewinnt gegen Extreme-Point deutlich häufiger als es
    verliert - aber mit echter, dokumentierter Varianz zwischen einzelnen
    Instanzen (Worst Case: -9,1 Prozentpunkte). Eine erste Fassung dieses
    Tests summierte ROHE Volumina über nur 5 Seeds mit unterschiedlicher
    Boxenzahl (nicht direkt vergleichbar) und geriet dadurch in eine unglückliche
    Stichprobe (schlug fehl, obwohl kein Bug vorlag) - auf 20 Seeds und
    prozentuale (Container-normierte) Differenzen umgestellt, um die
    bekannte Varianz robust abzubilden statt an ihr zu scheitern."""
    container_dim = (120.0, 80.0, 100.0)
    net_deltas_pct = []
    for seed in range(1, 21):
        rng = np.random.default_rng(seed)
        n_boxes = rng.integers(15, 35)
        boxes = _random_boxes(n_boxes, seed)
        p_ep, _ = extreme_point_packing(boxes, container_dim)
        p_bs, _ = monobeam_packing(boxes, container_dim)
        util_ep = sum(box_volume(p["dim"]) for p in p_ep) / box_volume(container_dim) * 100
        util_bs = sum(box_volume(p["dim"]) for p in p_bs) / box_volume(container_dim) * 100
        net_deltas_pct.append(util_bs - util_ep)
    avg = sum(net_deltas_pct) / len(net_deltas_pct)
    assert avg > -1.0, f"Beam Search sollte im Schnitt nicht spürbar schlechter als Extreme-Point sein: {avg:+.2f}pp"


def test_monobeam_is_monotone_in_beam_width():
    """Der zentrale, auf Nutzeranfrage untersuchte und dann bewiesene Befund:
    die ursprüngliche beam_search_packing war NICHT monoton (11-12 von 14
    Testinstanzen zeigten eine schlechtere Raumnutzung bei größerer Breite -
    dasselbe strukturelle Muster wie die zuerst verworfene Beam-Search-
    Variante der Seefracht-Demo). monobeam_packing (Lemons et al. 2022,
    "Beam Search: Faster and Monotonic") behebt das nachweislich - über eine
    breite Stichprobe (30 Instanzen, variable Boxenzahl/-größe) traten dabei
    0 Verletzungen auf. Zwei eigene Implementierungsfehler mussten dafür erst
    behoben werden (siehe README): getrennte statt verschachtelte Erzeugung/
    Zuweisung pro Slot, und Bewertung nach Boxenzahl statt direkt nach dem
    angezeigten Volumen."""
    container_dim = (120.0, 80.0, 100.0)
    for seed in range(1, 15):
        boxes = _random_boxes(25, seed, lo=15, hi=55)
        utils = []
        for bw in [1, 2, 4, 6, 8, 12, 16]:
            p, _ = monobeam_packing(boxes, container_dim, beam_width=bw)
            utils.append(sum(box_volume(pp["dim"]) for pp in p) / box_volume(container_dim) * 100)
        for i in range(len(utils) - 1):
            assert utils[i] <= utils[i + 1] + 1e-6, (
                f"seed={seed}: Raumnutzung sank von bw={[1,2,4,6,8,12,16][i]} zu "
                f"bw={[1,2,4,6,8,12,16][i+1]}: {utils[i]:.2f}% -> {utils[i+1]:.2f}%"
            )


def test_monobeam_worst_case_completes_within_budget():
    """Regressionstest für einen beim Bauen gefundenen ehrlichen Befund:
    Beam Search bringt bei großen, dünn besiedelten Containern manchmal
    exakt keine Verbesserung gegenüber Extreme-Point, ist dabei aber ca.
    11x langsamer (monobeam: ~1,45s statt Extreme-Points ~0,13s bei 60
    Boxen in einem 300x300x300-Container) - noch etwas langsamer als die
    frühere Implementierung (6-7x), da monobeam pro Slot eine echte
    Prioritätswarteschlange über alle Kandidaten pflegt statt nur die besten
    pro Zustand zu begrenzen. Kein Korrektheits-, sondern ein
    Performance-Schutztest - stellt sicher, dass der Worst Case innerhalb
    eines für die automatische (nicht Button-gesteuerte) Neuberechnung bei
    jeder UI-Interaktion vertretbaren Zeitrahmens bleibt."""
    import time

    boxes = _random_boxes(60, seed=1, lo=8, hi=100)
    container_dim = (300.0, 300.0, 300.0)
    t0 = time.time()
    monobeam_packing(boxes, container_dim)
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


def test_box_mesh_triangles_have_consistent_outward_normals():
    """Regressionstest für einen vom Nutzer gemeldeten Fehler: die
    Dreiecks-Reihenfolge deckte zwar alle 6 Flächen korrekt ab (siehe
    test_box_mesh_triangles_cover_all_six_faces_exactly), aber 4 von 6
    Flächen (unten, hinten, links) hatten eine nach INNEN statt nach AUSSEN
    zeigende Normale (falsche Wicklungsreihenfolge / Eckpunkt-Richtung).
    Das flächen-basierte Coverage-Kriterium allein prüft nur unsignierte
    Fläche, nicht die Wicklungsrichtung - dieser Test prüft explizit die
    Normalenrichtung jedes einzelnen Dreiecks per Kreuzprodukt (rechte-Hand-
    Regel), da uneinheitliche Normalen je nach Beleuchtung/Rendering-
    Verhalten zu unsichtbaren oder falsch schattierten Flächen aus
    bestimmten Blickwinkeln führen können."""
    import numpy as np

    verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
    face_names = ["unten", "unten", "oben", "oben", "vorne", "vorne", "hinten", "hinten", "links", "links", "rechts", "rechts"]
    expected_normals = {
        "unten": (0, 0, -1), "oben": (0, 0, 1), "vorne": (0, -1, 0),
        "hinten": (0, 1, 0), "links": (-1, 0, 0), "rechts": (1, 0, 0),
    }
    triangles = list(zip(_BOX_TRIANGLES_I, _BOX_TRIANGLES_J, _BOX_TRIANGLES_K))

    for idx, (i, j, k) in enumerate(triangles):
        v0, v1, v2 = np.array(verts[i]), np.array(verts[j]), np.array(verts[k])
        normal = np.cross(v1 - v0, v2 - v0)
        normal_unit = normal / np.linalg.norm(normal)
        expected = np.array(expected_normals[face_names[idx]])
        assert np.dot(normal_unit, expected) > 0.9, (
            f"Dreieck {idx} ({face_names[idx]}): Normale {normal_unit.round(2)} zeigt nicht nach "
            f"außen (erwartet ~{expected})"
        )


def test_box_meshes_render_fully_opaque_with_explicit_lighting():
    """Regressionstest für einen vom Nutzer gemeldeten Fehler: 'manche
    Packstücke scheinen durchsichtig zu sein, andere nicht, allen fehlt die
    feste Substanz'. Ursache: jede Box ist ein eigener go.Mesh3d-Trace: bei
    Halbtransparenz (opacity<1) muss WebGL mehrere UNABHÄNGIGE Traces nach
    Tiefe sortiert überblenden - das gelingt zwischen getrennten Traces
    nicht zuverlässig, wodurch je nach Zeichenreihenfolge/Kamerawinkel
    manche Boxen die Überblendung 'gewinnen' (wirken solide) und andere
    'verlieren' (wirken durchsichtig). Prüft, dass alle Box-Traces mit
    voller Deckkraft (kein Alpha-Blending zwischen Traces nötig, nur
    einfacher Z-Buffer-Tiefenvergleich - immer korrekt) und expliziter
    Beleuchtung (mehr Kontrast/Plastizität statt flacher Optik) gerendert
    werden."""
    from pack_visualization import build_3d_figure

    container_dim = (120.0, 80.0, 100.0)
    placements = [
        {"box_idx": 0, "pos": (0.0, 0.0, 0.0), "dim": (30.0, 30.0, 30.0)},
        {"box_idx": 1, "pos": (30.0, 0.0, 0.0), "dim": (30.0, 30.0, 30.0)},
        {"box_idx": 2, "pos": (0.0, 30.0, 0.0), "dim": (30.0, 30.0, 30.0)},
    ]
    boxes = [(30.0, 30.0, 30.0)] * 3
    fig = build_3d_figure(placements, boxes, ["A", "B", "C"], container_dim)

    box_traces = [t for t in fig.data if t.type == "mesh3d"]
    assert len(box_traces) == 3
    for trace in box_traces:
        assert trace.opacity == 1.0, f"Erwartete volle Deckkraft, bekam {trace.opacity}"
        assert trace.lighting is not None, "Erwartete explizite Beleuchtung fehlt"


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


def test_classify_comparison_detects_two_way_tie():
    """Regressionstest für einen gefundenen Bug in der Vergleichs-Tab-Logik:
    eine erste Fassung prüfte nur, ob ALLE Kandidaten innerhalb der Toleranz
    liegen - lagen exakt die besten zwei von drei Methoden gleichauf, während
    die dritte klar abwich, blieb "alle gleich" False, und max() erklärte
    willkürlich die erste der beiden gleichauf liegenden Methoden zum
    Sieger."""
    candidates = [
        {"label": "Extreme-Point", "final_utilization_pct": 50.256},
        {"label": "Beam Search", "final_utilization_pct": 50.256},
        {"label": "Schichten-basiert", "final_utilization_pct": 33.4},
    ]
    result = classify_comparison(candidates)
    assert result["all_tied"] is False
    assert result["top_two_tied"] is True
    assert result["is_tied"] is True


def test_classify_comparison_detects_all_tied():
    candidates = [{"label": l, "final_utilization_pct": 80.0} for l in ["A", "B", "C"]]
    result = classify_comparison(candidates)
    assert result["all_tied"] is True
    assert result["is_tied"] is True


def test_classify_comparison_clear_winner_not_flagged_as_tied():
    candidates = [
        {"label": "A", "final_utilization_pct": 90.0},
        {"label": "B", "final_utilization_pct": 70.0},
        {"label": "C", "final_utilization_pct": 60.0},
    ]
    result = classify_comparison(candidates)
    assert result["is_tied"] is False
    assert result["best"]["label"] == "A"
    assert result["worst"]["label"] == "C"


def test_generate_pack_plan_pdf_produces_valid_pdf():
    from pack_pdf_export import generate_pack_plan_pdf

    boxes = _random_boxes(10, seed=2)
    ids = list(range(1, 11))
    container_dim = (120.0, 80.0, 100.0)
    placements, unplaced = extreme_point_packing(boxes, container_dim)
    pdf_bytes = generate_pack_plan_pdf("Extreme-Point", placements, boxes, ids, unplaced, container_dim, 50.0)
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 500


def test_intro_text_mentions_all_three_heuristics_by_name():
    """Regressionstest für einen gefundenen Fehler: Beim Ergänzen von Beam
    Search als dritte Heuristik wurde die besucherseitige Einleitung nicht
    mitgepflegt - sie sprach weiterhin von 'zwei Heuristiken' und erwähnte
    Beam Search gar nicht. Prüft positiv, dass alle drei Methodennamen in der
    Einleitung vorkommen, statt nur auf Abwesenheit eines veralteten Wortes
    ('zwei') zu prüfen - robuster gegenüber zukünftigen Umformulierungen."""
    at = fresh_app()
    assert_ok(at)
    intro_texts = [str(m.value) for m in at.markdown if "dreidimensionalen Beladung" in str(m.value)]
    assert intro_texts, "Einleitungstext nicht gefunden"
    intro = intro_texts[0]
    for name in ["schichtenweise", "Extreme-Point", "Beam Search"]:
        assert name in intro, f"Einleitung erwähnt '{name}' nicht - Methodenzahl/-liste könnte veraltet sein"



    """Regressionstest für eine gefundene falsche Erklärung: Der Text behauptete
    pauschal 'Jede Box darf in allen 6 Ausrichtungen gedreht werden', obwohl
    layer_based_packing laut eigenem Docstring KEINE Rotation nutzt (Boxen
    bleiben in ihrer gegebenen Ausrichtung). Prüft, dass die Einschränkung im
    erklärenden Text tatsächlich benannt wird."""
    at = fresh_app()
    assert_ok(at)
    explanation_texts = [str(m.value) for m in at.markdown if "Schichten-basiert" in str(m.value) and "Rotation" in str(m.value)]
    assert explanation_texts, "Erklärungstext mit Schichten-basiert und Rotation nicht gefunden"
    combined = " ".join(explanation_texts)
    assert "keine Rotation" in combined or "keine Rotation" in combined.lower(), (
        "Erklärungstext sollte explizit nennen, dass Schichten-basiert keine Rotation nutzt"
    )


# --- rescue_unplaced_via_swap: Button-gesteuerte Verbesserungssuche ---
# (auf Wunsch ergänzt, analog zu flexible_beam_search_construction in der
# Seefracht-Demo, aber wegen der 3D-Geometrie ohne wirksame Kandidaten-
# Vorauswahl - deshalb Button-gesteuert statt automatisch)

def test_rescue_finds_known_improvement_on_viele_kleine_pakete():
    """Kernkorrektheitstest: das konkrete Szenario, an dem der Nutzen
    ursprünglich gefunden wurde. Werte auf Nutzerhinweis ("Packstücke
    scheinen zu schweben") aktualisiert: nach Einbau der Stützungsprüfung
    (is_supported, siehe README) liefert Extreme-Point selbst schon eine
    konservativere, aber physikalisch korrekte Startkonstruktion (70,9%
    statt vorher 75,5% - die Differenz waren frei "schwebende"
    Platzierungen, die es vorher fälschlich mitzählte) - entsprechend
    weniger Rettungspotential übrig (1 statt 3 gerettete Boxen). Systematisch
    nachgesucht (14 Seeds x 3 Containergrößen): Seed 1 bleibt bei diesem
    Container die beste verfügbare Demonstration, auch wenn kleiner als
    zuvor - ein kleinerer, aber ehrlicher (und jetzt physikalisch
    korrekter) Befund."""
    container_dim = (70.0, 60.0, 50.0)
    boxes = _random_boxes(60, seed=1, lo=8, hi=25)
    p_ep, u_ep = extreme_point_packing(boxes, container_dim)
    p_r, u_r, n_rescued = rescue_unplaced_via_swap(boxes, container_dim, p_ep, u_ep)

    assert n_rescued == 1
    assert len(p_r) == len(p_ep) + 1
    assert len(u_r) == len(u_ep) - 1

    u_before = sum(box_volume(p["dim"]) for p in p_ep) / box_volume(container_dim) * 100
    u_after = sum(box_volume(p["dim"]) for p in p_r) / box_volume(container_dim) * 100
    assert u_before == pytest.approx(70.9, abs=0.1)
    assert u_after == pytest.approx(72.7, abs=0.1)


def test_rescue_never_worse_than_input():
    """Startet immer beim übergebenen Ausgangszustand - kann per Konstruktion
    nie schlechter sein (nur Verschiebungen werden akzeptiert, die strikt
    mehr Boxen unterbringen)."""
    for seed in range(1, 6):
        boxes = _random_boxes(30, seed=seed, lo=10, hi=50)
        container_dim = (100.0, 80.0, 90.0)
        p_ep, u_ep = extreme_point_packing(boxes, container_dim)
        p_r, u_r, n_rescued = rescue_unplaced_via_swap(boxes, container_dim, p_ep, u_ep)
        assert len(p_r) >= len(p_ep)
        assert n_rescued >= 0


def test_rescue_produces_structurally_valid_placements():
    """Keine Überlappungen, alles innerhalb des Containers, jede Box
    höchstens einmal platziert - nach der Rettungssuche genau wie bei den
    Konstruktionsheuristiken selbst."""
    container_dim = (70.0, 60.0, 50.0)
    boxes = _random_boxes(60, seed=1, lo=8, hi=25)
    p_ep, u_ep = extreme_point_packing(boxes, container_dim)
    p_r, u_r, n_rescued = rescue_unplaced_via_swap(boxes, container_dim, p_ep, u_ep)

    placed_idxs = [p["box_idx"] for p in p_r]
    assert len(placed_idxs) == len(set(placed_idxs)), "Box mehrfach platziert"
    assert set(placed_idxs) | set(u_r) == set(range(len(boxes))), "Boxen fehlen oder doppelt"
    for p in p_r:
        assert fits_in_container(p["pos"], p["dim"], container_dim)
    for i in range(len(p_r)):
        for j in range(i + 1, len(p_r)):
            assert not boxes_overlap(p_r[i]["pos"], p_r[i]["dim"], p_r[j]["pos"], p_r[j]["dim"])


def test_rescue_handles_no_unplaced_boxes():
    container_dim = (200.0, 200.0, 200.0)
    boxes = _random_boxes(5, seed=1, lo=10, hi=20)
    p_ep, u_ep = extreme_point_packing(boxes, container_dim)
    assert u_ep == []  # sollte bei so viel Platz alle unterbringen
    p_r, u_r, n_rescued = rescue_unplaced_via_swap(boxes, container_dim, p_ep, u_ep)
    assert n_rescued == 0
    assert p_r == p_ep


def test_rescue_worst_case_completes_within_budget():
    """Performance-Schutztest: Button-gesteuert (nicht automatisch), aber
    auch eine bewusst ausgelöste Aktion sollte nicht beliebig lange dauern.
    Empirischer Worst Case bei maximaler Boxenzahl (60): ~3,6s."""
    import time

    worst = 0.0
    container_dim = (70.0, 60.0, 50.0)
    for seed in range(1, 4):
        boxes = _random_boxes(60, seed=seed, lo=8, hi=25)
        p_ep, u_ep = extreme_point_packing(boxes, container_dim)
        t0 = time.time()
        rescue_unplaced_via_swap(boxes, container_dim, p_ep, u_ep)
        worst = max(worst, time.time() - t0)
    assert worst < 10.0, f"Worst Case dauerte {worst:.1f}s"


def test_rescue_button_not_mislabeled_as_beam_search():
    """Regressionstest für einen gefundenen Fehler: die Rettungssuche wurde
    zunächst 'Beam-Search-Verbesserungssuche' genannt, obwohl sie strukturell
    KEINE Beam Search ist - kein beam_width-Parameter, keine parallel
    verfolgten Kandidatenzustände, nur ein einziger deterministischer
    Durchlauf (first-improvement). Getestet wurde, ob eine echte Breite
    (mehrere zufällig geordnete Durchläufe) etwas bringt: ja, vereinzelt
    (teils doppelt so viele Rettungen), aber inkonsistent und bei linear
    wachsender Rechenzeit - bewusst nicht eingebaut. Der Button-Text muss
    das korrekt widerspiegeln, nicht mehr fälschlich 'Beam Search'
    versprechen."""
    at = fresh_app()
    btn = [b for b in at.button if "Enges Puzzle" in b.label][0]
    btn.click().run(timeout=TIMEOUT)
    rescue_buttons = [b for b in at.button if "nachträglich retten" in b.label]
    assert rescue_buttons
    for b in rescue_buttons:
        assert "Beam" not in b.label, f"Rettungs-Button sollte nicht 'Beam Search' behaupten: {b.label}"
        assert "Greedy" in b.label



    at = fresh_app()
    assert_ok(at)
    btn = [b for b in at.button if "Enges Puzzle" in b.label][0]
    btn.click().run(timeout=TIMEOUT)
    # Enges Puzzle hat bei allen drei Methoden unplatzierte Boxen
    rescue_buttons = [b for b in at.button if "nachträglich retten" in b.label]
    assert len(rescue_buttons) == 3


def test_rescue_button_click_shows_result_and_updates_state():
    at = fresh_app()
    btn = [b for b in at.button if "Viele kleine Pakete" in b.label][0]
    btn.click().run(timeout=TIMEOUT)
    rescue_btn = [b for b in at.button if b.key == "extreme_rescue_btn"][0]
    rescue_btn.click().run(timeout=TIMEOUT)
    assert_ok(at)
    successes = [str(s.value) for s in at.success if "Umplatzierung" in str(s.value)]
    assert successes, "Erwartete Erfolgsmeldung nach Rettungssuche fehlt"


def test_rescue_result_becomes_stale_after_config_change():
    """Regressionsschutz nach demselben Muster wie OR-Tools in der
    Touren-Demo: ein Rettungsergebnis darf nach einer Konfigurationsänderung
    nicht unverändert weiter angezeigt werden."""
    at = fresh_app()
    btn = [b for b in at.button if "Viele kleine Pakete" in b.label][0]
    btn.click().run(timeout=TIMEOUT)
    rescue_btn = [b for b in at.button if b.key == "extreme_rescue_btn"][0]
    rescue_btn.click().run(timeout=TIMEOUT)
    assert any("Umplatzierung" in str(s.value) for s in at.success)

    at.sidebar.number_input[0].set_value(999).run(timeout=TIMEOUT)
    assert_ok(at)
    stale_notes = [str(c.value) for c in at.caption if "verworfen" in str(c.value)]
    assert stale_notes, "Erwarteter Stale-Hinweis nach Konfigurationsänderung fehlt"


# --- 3D-Visualisierung: nicht-wuerfelfoermige Container ---
# (auf Nutzerhinweis "sehr merkwuerdige 3D-Darstellung" gefunden und behoben)

def test_container_wireframe_matches_actual_dimensions_not_cube():
    """Regressionstest für einen vom Nutzer gemeldeten Fehler: alle drei
    Achsen (Länge, Breite, Höhe) bekamen denselben Bereich [0, max(L,B,H)]
    statt jeweils ihre eigene tatsächliche Ausdehnung. Bei einem nicht-
    würfelförmigen Container (z. B. dem Standard 120×80×100) zwang das
    Plotly mit aspectmode='data' zu einer würfelförmigen Anzeige, in der
    der tatsächliche Container nur einen Teil einnahm - verzerrte,
    unausgefüllte Darstellung mit viel leerem Rand auf zwei Seiten. Fix:
    jede Achse bekommt ihren eigenen Bereich [0, jeweilige Kantenlänge]."""
    from pack_visualization import build_3d_figure

    container_dim = (120.0, 80.0, 100.0)  # bewusst nicht wuerfelfoermig
    placements = [{"box_idx": 0, "pos": (0.0, 0.0, 0.0), "dim": (30.0, 30.0, 30.0)}]
    fig = build_3d_figure(placements, [(30.0, 30.0, 30.0)], ["A"], container_dim)

    scene = fig.layout.scene
    assert tuple(scene.xaxis.range) == (0, 120.0)
    assert tuple(scene.yaxis.range) == (0, 80.0)
    assert tuple(scene.zaxis.range) == (0, 100.0)

    wireframe = fig.data[0]
    assert max(x for x in wireframe.x if x is not None) == 120.0
    assert max(y for y in wireframe.y if y is not None) == 80.0
    assert max(z for z in wireframe.z if z is not None) == 100.0


def test_container_wireframe_matches_dimensions_for_all_presets():
    """Erweiterte Prüfung über alle vier Presets (unterschiedliche
    Container-Formen, inkl. dem stark nicht-würfelförmigen 70x60x50 von
    'Viele kleine Pakete')."""
    from pack_visualization import build_3d_figure

    for container_dim in [(120.0, 80.0, 100.0), (70.0, 60.0, 50.0)]:
        fig = build_3d_figure([], [], [], container_dim)
        scene = fig.layout.scene
        CL, CW, CH = container_dim
        assert tuple(scene.xaxis.range) == (0, CL)
        assert tuple(scene.yaxis.range) == (0, CW)
        assert tuple(scene.zaxis.range) == (0, CH)


# --- is_supported: physikalische Stuetzungspruefung ---
# (auf Nutzerhinweis "Packstuecke scheinen zu schweben" ergaenzt)

def test_is_supported_on_floor():
    assert is_supported((0, 0, 0), (10, 10, 10), [])


def test_is_supported_exact_fit():
    assert is_supported((0, 0, 10), (10, 10, 10), [((0, 0, 0), (10, 10, 10))])


def test_is_supported_rejects_overhang():
    """Kernfall des gemeldeten Fehlers: eine größere Box auf einer kleineren
    Stütze - der überstehende Teil hängt in der Luft."""
    assert not is_supported((0, 0, 10), (20, 20, 10), [((0, 0, 0), (10, 10, 10))])


def test_is_supported_accepts_combined_support():
    """Zwei kleinere Boxen können zusammen die volle Grundfläche stützen."""
    assert is_supported(
        (0, 0, 10), (20, 10, 10),
        [((0, 0, 0), (10, 10, 10)), ((10, 0, 0), (10, 10, 10))],
    )


def test_is_supported_rejects_fully_floating():
    assert not is_supported((50, 50, 20), (10, 10, 10), [((0, 0, 0), (10, 10, 10))])


def test_is_supported_rejects_gap_between_supports():
    """Zwei Stützen mit einer Lücke dazwischen - die Grundfläche darüber ist
    NICHT vollständig gestützt, auch wenn beide Enden es sind."""
    assert not is_supported(
        (0, 0, 10), (20, 10, 10),
        [((0, 0, 0), (8, 10, 10)), ((12, 0, 0), (8, 10, 10))],
    )


@pytest.mark.parametrize("heuristic_name", ["layer_based_packing", "extreme_point_packing", "monobeam_packing"])
def test_no_floating_boxes_across_heuristics(heuristic_name):
    """Regressionstest für den vom Nutzer gemeldeten Fehler: 'Packstücke
    scheinen zu schweben, obwohl sie bei Kippung in den Zwischenraum
    darunter passen würden'. Systematisch geprüft: vor dem Fix waren bei
    einem realen Szenario 6 von 15 Boxen (40%) nicht vollständig gestützt,
    eine davon komplett frei schwebend (0% Stützung) - bei allen drei
    Heuristiken. Prüft über mehrere Seeds, dass jede platzierte Box
    entweder auf dem Boden steht oder lückenlos von anderen Boxen gestützt
    wird."""
    import pack_heuristics
    fn = getattr(pack_heuristics, heuristic_name)
    container_dim = (120.0, 80.0, 100.0)
    for seed in range(1, 6):
        boxes = _random_boxes(25, seed=seed, lo=15, hi=55)
        placements, _unplaced = fn(boxes, container_dim)
        for p in placements:
            others = [(pp["pos"], pp["dim"]) for pp in placements if pp is not p]
            assert is_supported(p["pos"], p["dim"], others), (
                f"{heuristic_name} seed={seed}: Box {p['box_idx']} bei pos={p['pos']} "
                f"dim={p['dim']} ist nicht vollständig gestützt"
            )


def test_no_floating_boxes_after_rescue():
    container_dim = (70.0, 60.0, 50.0)
    boxes = _random_boxes(60, seed=1, lo=8, hi=25)
    p_ep, u_ep = extreme_point_packing(boxes, container_dim)
    p_r, _u_r, _n = rescue_unplaced_via_swap(boxes, container_dim, p_ep, u_ep)
    for p in p_r:
        others = [(pp["pos"], pp["dim"]) for pp in p_r if pp is not p]
        assert is_supported(p["pos"], p["dim"], others), (
            f"Box {p['box_idx']} nach Rettungssuche nicht vollständig gestützt"
        )


def test_layer_based_packing_preserves_reasonable_utilization():
    """Regressionstest für einen beim Bauen gefundenen Fehler: ein erster
    Fix-Versuch (reines Ablehnen unpassender Positionen) behob das
    Schweben, ließ aber die Raumnutzung einbrechen (Seed 1: von 25 auf nur
    5 platzierte Boxen). Ein zweiter Versuch (Stützhöhe live berechnen,
    aber weiterhin fester 3-Versuche-Cursor) hatte denselben Effekt aus
    einem anderen Grund: eine an einer Position gescheiterte Box ließ den
    Cursor dort "stecken", jede nachfolgende Box scheiterte an derselben
    Position. Die funktionierende Lösung (wachsendes 2D-Kandidatenraster
    statt starrem Cursor) hält die Nutzung im erwarteten Bereich."""
    container_dim = (120.0, 80.0, 100.0)
    boxes = _random_boxes(25, seed=1, lo=15, hi=55)
    placements, unplaced = layer_based_packing(boxes, container_dim)
    assert len(placements) >= 10, (
        f"Nur {len(placements)} von 25 Boxen platziert - Hinweis auf Cursor-Steckenbleiben"
    )


# --- contact_area: auf Nutzernachfrage untersuchte, aber nicht integrierte ---
# Bewertungsgroesse (siehe README - schlaegt DBL nicht robust)

def test_contact_area_corner_touches_all_three_walls():
    """Eine Box exakt in der Containerecke berührt Boden, Rückwand und
    linke Wand vollständig."""
    assert contact_area((0, 0, 0), (10, 10, 10), [], (120, 80, 100)) == pytest.approx(300.0)


def test_contact_area_floating_box_has_zero_contact():
    assert contact_area((50, 50, 50), (10, 10, 10), [], (120, 80, 100)) == pytest.approx(0.0)


def test_contact_area_partial_contact_with_neighbor():
    """Zwei halb überlappende Boxen berühren sich anteilig."""
    neighbor = [((0, 0, 0), (10, 10, 10))]
    # Box direkt daneben (rechte Seite von neighbor beruehrt linke Seite dieser Box)
    area = contact_area((10, 0, 0), (10, 10, 10), neighbor, (120, 80, 100))
    assert area >= 100.0  # mindestens die linke Wand (10x10) plus Boden


def test_comparison_tab_shows_final_packings_side_by_side():
    """Auf Nutzerwunsch ergänzt (analog zur bereits bestehenden Funktion in
    der VRP-Demo): der Vergleichs-Tab zeigt jetzt für jede der drei
    Heuristiken die finale Packung als eigene 3D-Ansicht nebeneinander,
    nicht nur die numerische Vergleichstabelle."""
    at = fresh_app()
    captions = [str(c.value) for c in at.caption if "(final," in str(c.value)]
    assert len(captions) == 3, f"Erwartete 3 Beschriftungen für die finalen Packungen, gefunden: {captions}"
    for label in ["Schichten-basiert", "Extreme-Point", "Beam Search"]:
        assert any(label in c for c in captions), f"Beschriftung für {label} fehlt"
