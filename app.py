"""
3D-Packungsoptimierung (Container-/Palettenstauung) – interaktive Demo
Sebastian Hanisch - Operations Research und Machine Learning

Bewusst schlanker gehalten als die Tourenplanung-Demo (drei Heuristiken statt
fünf, kein externer Solver), aber mit denselben Komfortfunktionen für gutes
Verständnis: Erklärung, Beispielszenarien, Animation, PDF-Export, Permalink,
Feedback-Mechanismus.

Lauffähig mit: streamlit run app.py
"""

import numpy as np
import pandas as pd
import streamlit as st

from pack_evaluation import box_volume, classify_comparison, volume_to_business
from pack_feedback import log_feedback
from pack_heuristics import extreme_point_packing, layer_based_packing, monobeam_packing
from pack_presets import apply_preset, bounds, init_session_state_defaults, load_permalink_settings, randomize_seed, sync_query_params
from pack_ui_panel import render_packing_panel
from pack_visualization import build_3d_figure

st.set_page_config(page_title="3D-Packungsoptimierung – Sebastian Hanisch", layout="wide")


@st.cache_data(show_spinner=False)
def _run_heuristics(boxes, container_dim):
    """Cacht alle drei Heuristiken über (boxes, container_dim) - ohne das
    würden layer_based_packing/extreme_point_packing/monobeam_packing bei
    JEDEM Rerun neu laufen, auch wenn ein völlig unbeteiligter Widget-Klick
    (z. B. der Animations-Schritt-Slider eines anderen Tabs) den Rerun
    ausgelöst hat."""
    return (
        layer_based_packing(boxes, container_dim),
        extreme_point_packing(boxes, container_dim),
        monobeam_packing(boxes, container_dim),
    )

st.title("📦 3D-Packungsoptimierung (Container-/Palettenstauung)")
st.markdown(
    """
Interaktive Demo zur dreidimensionalen Beladung eines Containers oder einer Palette.
Drei selbst implementierte Heuristiken – eine **schichtenweise** Vorgehensweise (wie man
intuitiv von Hand packen würde, ohne Rotation), eine fortgeschrittene **Extreme-Point**-
Methode (füllt Lücken zwischen unterschiedlich großen Boxen gezielt) und **Beam Search**
(verfolgt mehrere Teil-Packungen parallel, nachweislich monoton in der Beam-Breite) –
werden direkt verglichen.
"""
)

st.caption("🎯 Schnellstart – ein Beispielszenario laden:")
preset_col1, preset_col2, preset_col3, preset_col4 = st.columns(4)
with preset_col1:
    st.button(
        "📐 Gleichmäßige Kartons", use_container_width=True,
        on_click=apply_preset, args=(20, 25, 35, 120.0, 80.0, 100.0, 1),
        help="20 ähnlich große Kartons – hier landen Extreme-Point und Beam Search bei praktisch identischer Raumnutzung.",
    )
with preset_col2:
    st.button(
        "📦 Gemischte Ladung", use_container_width=True,
        on_click=apply_preset, args=(30, 10, 60, 120.0, 80.0, 100.0, 7),
        help="30 stark unterschiedlich große Boxen – zeigt den Unterschied zwischen den Heuristiken deutlich.",
    )
with preset_col3:
    st.button(
        "🧩 Viele kleine Pakete", use_container_width=True,
        on_click=apply_preset, args=(60, 8, 25, 70.0, 60.0, 50.0, 1),
        help="60 kleine Pakete bei knapper Kapazität (131% des Containervolumens) – echter Stresstest, bei dem nicht alle Pakete hineinpassen und die Packqualität wirklich zählt.",
    )
with preset_col4:
    st.button(
        "📡 Enges Puzzle", use_container_width=True,
        on_click=apply_preset, args=(30, 8, 70, 120.0, 80.0, 100.0, 10),
        help="30 stark gemischte Boxen bei knapper Kapazität – hier liegt Beam Search deutlich vor Extreme-Point, und größere Beam-Breite hilft hier sogar sichtbar weiter (empirisch gefunden, kein Zufall).",
    )

st.caption(
    "🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, "
    "um ein Szenario zu teilen. Hinweis: manuell in der Box-Tabelle bearbeitete Maße sind "
    "darin nicht enthalten, nur die Einstellungen, aus denen die Boxen erzeugt werden."
)

load_permalink_settings()
init_session_state_defaults()

with st.sidebar:
    st.header("⚙️ Einstellungen")
    st.markdown("**Container-Maße (cm)**")
    container_l = st.slider("Länge", *bounds("container_l_slider"), key="container_l_slider")
    container_w = st.slider("Breite", *bounds("container_w_slider"), key="container_w_slider")
    container_h = st.slider("Höhe", *bounds("container_h_slider"), key="container_h_slider")

    st.markdown("**Ladung**")
    n_boxes = st.slider("Anzahl Boxen", *bounds("n_boxes_slider"), key="n_boxes_slider")
    min_size = st.slider("Min. Kantenlänge (cm)", *bounds("min_size_slider"), key="min_size_slider")
    max_size = st.slider("Max. Kantenlänge (cm)", *bounds("max_size_slider"), key="max_size_slider")
    seed = st.number_input("Zufalls-Seed", *bounds("seed_input"), step=1, key="seed_input")

    st.markdown("**Geschäftliche Kennzahl**")
    cost_per_container = st.slider(
        "Kosten pro Zusatzcontainer (€)", *bounds("cost_slider"), step=5.0, key="cost_slider",
        help="Geschätzte Kosten, falls nicht alle Boxen in einen Container passen und ein weiterer nötig wird.",
    )

    st.button(
        "🎲 Neue Boxen generieren", use_container_width=True, on_click=randomize_seed,
        help="Würfelt einen neuen Zufalls-Seed und erzeugt damit komplett neue Boxen - "
        "praktisch, ohne selbst eine neue Seed-Zahl eintippen zu müssen.",
    )

sync_query_params(container_l, container_w, container_h, n_boxes, min_size, max_size, seed, cost_per_container)

if "force_regen" not in st.session_state:
    st.session_state.force_regen = False

# Alle Box-Generierungs-relevanten Parameter erfassen - nicht nur n_boxes.
# (Bug gefunden und behoben: vorher wurde nur n_boxes geprüft, wodurch reine
# Änderungen an Min./Max.-Kantenlänge oder Seed die Boxen NICHT neu erzeugt
# haben, obwohl die Sidebar bereits die neuen Werte anzeigte - verwirrend und
# funktional falsch. Siehe test_all_generation_params_trigger_regeneration.)
gen_key = (n_boxes, min_size, max_size, int(seed))
needs_init = (
    "boxes" not in st.session_state or st.session_state.force_regen
    or st.session_state.get("gen_key_cache") != gen_key
)
if needs_init:
    lo = min(min_size, max_size)
    hi = max(min_size, max_size)
    rng = np.random.default_rng(int(seed))
    dims = rng.uniform(lo, hi, size=(n_boxes, 3)).round(1)
    st.session_state.boxes = pd.DataFrame(
        {"id": range(1, n_boxes + 1), "laenge": dims[:, 0], "breite": dims[:, 1], "hoehe": dims[:, 2]}
    )
    st.session_state.gen_key_cache = gen_key
    st.session_state.force_regen = False

st.subheader("📋 Boxen (direkt editierbar)")
edited = st.data_editor(
    st.session_state.boxes,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "id": st.column_config.NumberColumn("ID", disabled=True),
        "laenge": st.column_config.NumberColumn("Länge (cm)", min_value=1.0, max_value=250.0, step=1.0),
        "breite": st.column_config.NumberColumn("Breite (cm)", min_value=1.0, max_value=250.0, step=1.0),
        "hoehe": st.column_config.NumberColumn("Höhe (cm)", min_value=1.0, max_value=250.0, step=1.0),
    },
)
n_before_dropna = len(edited)
edited = edited.dropna(subset=["laenge", "breite", "hoehe"]).reset_index(drop=True)
if len(edited) < n_before_dropna:
    st.caption(
        f"ℹ️ {n_before_dropna - len(edited)} unvollständige Zeile(n) ignoriert, bis "
        "Länge, Breite und Höhe ausgefüllt sind."
    )
if edited["id"].isna().any():
    edited["id"] = range(1, len(edited) + 1)
st.session_state.boxes = edited

if len(edited) == 0:
    st.warning("Bitte mindestens eine Box anlegen.")
    st.stop()

boxes = list(zip(edited["laenge"].to_numpy(dtype=float), edited["breite"].to_numpy(dtype=float), edited["hoehe"].to_numpy(dtype=float)))
ids = edited["id"].to_numpy()
container_dim = (float(container_l), float(container_w), float(container_h))

total_box_volume = sum(box_volume(b) for b in boxes)
container_volume = box_volume(container_dim)
if total_box_volume > container_volume:
    st.info(
        f"ℹ️ Das Gesamtvolumen aller Boxen ({total_box_volume/1000:.0f} Liter) übersteigt das "
        f"Containervolumen ({container_volume/1000:.0f} Liter) – nicht alle Boxen werden hineinpassen. "
        f"Genau das macht den Unterschied zwischen den Heuristiken sichtbar."
    )

(layer_placements, layer_unplaced), (ep_placements, ep_unplaced), (beam_placements, beam_unplaced) = _run_heuristics(
    boxes, container_dim
)

METHODS = [
    ("layer", "Schichten-basiert", "📚 Schichten-basiert", "Baut die Ladung schichtweise auf, wie man intuitiv von Hand packen würde. Dient als Baseline für den Vergleich.", layer_placements, layer_unplaced),
    ("extreme", "Extreme-Point", "🎯 Extreme-Point", "Verfolgt konkurrierende Eckpunkte und füllt Lücken zwischen unterschiedlich großen Boxen gezielt.", ep_placements, ep_unplaced),
    ("beam", "Beam Search", "📡 Beam Search", "Verfolgt mehrere Teil-Packungen parallel statt nur einer - eine größere Beam-Breite kann die Raumnutzung nachweislich nie verschlechtern (monobeam-Verfahren, siehe README) und ist bei Standardbreite nie schlechter als Extreme-Point.", beam_placements, beam_unplaced),
]

tab_labels = [m[2] for m in METHODS] + ["📊 Vergleich"]
tabs = st.tabs(tab_labels)

summaries = {}
for (key, label, _tab_label, caption, placements, unplaced), tab in zip(METHODS, tabs[: len(METHODS)]):
    with tab:
        st.caption(caption)
        summaries[key] = render_packing_panel(key, label, placements, unplaced, boxes, ids, container_dim, cost_per_container)

with tabs[len(METHODS)]:
    st.markdown("### Heuristik-Vergleich")
    candidates = [summaries["layer"], summaries["extreme"], summaries["beam"]]
    comp_rows = []
    for s in candidates:
        extra_containers, extra_cost = volume_to_business(s["unplaced_volume"], s["container_volume"], cost_per_container)
        comp_rows.append({
            "Methode": s["label"],
            "Raumnutzung": f"{s['final_utilization_pct']:.1f}%",
            "Platziert": f"{s['n_placed']} / {s['n_placed'] + s['n_unplaced']}",
            "Zusatzcontainer nötig": extra_containers,
            "Geschätzte Zusatzkosten": f"{extra_cost:.0f} €",
        })
    st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True)

    comparison = classify_comparison(candidates)
    ranked, best, worst = comparison["ranked"], comparison["best"], comparison["worst"]
    all_tied, top_two_tied, is_tied = comparison["all_tied"], comparison["top_two_tied"], comparison["is_tied"]
    if all_tied:
        st.markdown(
            "➡️ Alle Methoden erreichen hier praktisch dieselbe Raumnutzung – vermutlich passen "
            "bei dieser Instanz ohnehin alle Boxen hinein, wodurch sich Unterschiede in der "
            "Packqualität nicht in dieser Kennzahl widerspiegeln."
        )
    elif top_two_tied:
        tied_labels = " und ".join(s["label"] for s in ranked[:2])
        st.markdown(f"➡️ **{tied_labels}** liegen hier praktisch gleichauf vorn.")
    else:
        st.markdown(f"➡️ **{best['label']}** erreicht hier die bessere Raumnutzung.")

    if not is_tied and best["label"] != worst["label"]:
        best_ec, best_cost = volume_to_business(best["unplaced_volume"], best["container_volume"], cost_per_container)
        worst_ec, worst_cost = volume_to_business(worst["unplaced_volume"], worst["container_volume"], cost_per_container)
        containers_saved = worst_ec - best_ec
        cost_saved = worst_cost - best_cost
        if containers_saved > 0:
            st.info(
                f"💶 Im Vergleich zu {worst['label']} spart **{best['label']}** hier ca. "
                f"**{containers_saved} zusätzliche(n) Container** (~{cost_saved:.0f} €) – bei einer "
                f"einzelnen Beladung. Hochgerechnet auf regelmäßige Sendungen summiert sich das schnell."
            )

    st.markdown("**Finale Packungen im direkten Vergleich**")
    cols = st.columns(len(candidates))
    for col, s in zip(cols, candidates):
        with col:
            st.caption(f"{s['label']} (final, {s['final_utilization_pct']:.1f}%)")
            fig_c = build_3d_figure(s["placements"], boxes, ids, container_dim)
            st.plotly_chart(fig_c, use_container_width=True, key=f"compare_{s['label']}")


with st.expander("Wie funktioniert diese Demo?"):
    st.markdown(
        """
**Drei eigene Packheuristiken:**
- *Schichten-basiert:* Boxen werden nach Höhe sortiert und in Reihen/Schichten angeordnet -
  einfach und schnell, verschwendet aber Raum, wenn Boxen innerhalb einer Schicht
  unterschiedlich hoch sind (die Schichthöhe richtet sich nach der höchsten Box). Nutzt
  bewusst **keine Rotation** (Boxen bleiben in ihrer gegebenen Ausrichtung) - Teil der
  Einfachheit, die diese Heuristik als Baseline auszeichnet.
- *Extreme-Point:* Verfolgt eine Liste konkurrierender Eckpunkte, an denen die nächste Box
  platziert werden könnte, und probiert dort alle 6 Rotationen durch - füllt Lücken
  zwischen unterschiedlich großen Boxen gezielter und erreicht dadurch meist deutlich
  bessere Raumnutzung als die Baseline.
- *Beam Search:* Verfolgt mehrere Teil-Packungen parallel statt nur einer - als
  geordnete, nummerierte "Slots", die nacheinander gefüllt werden. Jeder Slot wählt
  sofort das beste Element aus einem mit allen Slots geteilten Kandidatenpool, bevor der
  nächste Slot überhaupt an der Reihe ist (monobeam-Verfahren, Lemons et al. 2022) -
  dadurch kann eine größere Beam-Breite die Raumnutzung **nachweislich nie
  verschlechtern**, nur gleich gut oder besser machen. Breite 1 entspricht dabei exakt
  Extreme-Point (dieselbe Positionswahl-Regel) - daraus folgt: Beam Search kann bei
  keiner Breite mehr schlechter als Extreme-Point sein, nur gleich gut oder besser. Bei
  großen, dünn besiedelten Containern manchmal ohne messbaren Zusatzvorteil und spürbar
  langsamer.

**Rotationen:** Extreme-Point und Beam Search dürfen jede Box in allen 6 achsparallelen
Ausrichtungen drehen (Schichten-basiert nicht, siehe oben) - in der Praxis wäre das nicht
für jede Ladung sinnvoll (z. B. bei "diese Seite oben"-Kennzeichnung), für die Demo aber
bewusst vereinfacht.

**Animation:** Zeigt, wie die jeweilige Heuristik den Container Box für Box befüllt -
mit Schritt-Regler und Auto-Play, analog zur Tourenplanung-Demo.

**Geschäftliche Kennzahl:** Passen nicht alle Boxen in einen Container, wird geschätzt,
wie viele zusätzliche Container (rein volumenbasiert) nötig wären und was das ungefähr
kostet - macht den Unterschied zwischen den Heuristiken konkret statt nur als Prozentzahl.

**In echten Projekten** kämen meist weitere Nebenbedingungen dazu (Gewichtsverteilung,
Stapelbarkeit, "diese Seite oben", mehrere Container/Paletten gleichzeitig optimieren) -
das Grundprinzip aus Konstruktion und Bewertung bleibt aber dasselbe.
"""
    )

st.markdown("---")

st.markdown("#### War diese Demo hilfreich für Sie?")
if st.session_state.get("feedback_given"):
    vote_text = "👍 positiv" if st.session_state["feedback_given"] == "up" else "👎 negativ"
    st.success(f"Danke für Ihr Feedback ({vote_text})! 🙏")
else:
    fb_col1, fb_col2 = st.columns(2)
    with fb_col1:
        if st.button("👍 Ja", key="feedback_up_btn", use_container_width=True):
            if log_feedback("up"):
                st.session_state["feedback_given"] = "up"
            else:
                st.session_state["feedback_save_failed"] = True
            st.rerun()
    with fb_col2:
        if st.button("👎 Nein", key="feedback_down_btn", use_container_width=True):
            if log_feedback("down"):
                st.session_state["feedback_given"] = "down"
            else:
                st.session_state["feedback_save_failed"] = True
            st.rerun()
    if st.session_state.get("feedback_save_failed"):
        st.warning("⚠️ Feedback konnte leider nicht gespeichert werden. Bitte versuchen Sie es erneut.")

st.caption(
    "Diese Demo ist Teil des Portfolios von Sebastian Hanisch – Operations Research "
    "und Machine Learning. Interesse an einer maßgeschneiderten Lösung für Ihr "
    "Unternehmen? [Kontakt aufnehmen](#)"
)
