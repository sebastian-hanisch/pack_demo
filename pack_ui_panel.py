"""
Wiederverwendbares Streamlit-UI-Panel für eine einzelne Packheuristik:
Platzierungs-Schritt-Slider (+ Auto-Play als Animation), Metriken, 3D-Ansicht,
PDF-Export, sowie eine Button-gesteuerte Greedy-Verbesserungssuche für
unplatzierte Boxen. Wird einmal pro Heuristik-Tab in app.py aufgerufen -
analog zu render_heuristic_panel in der Touren-Demo.
"""

import time

import streamlit as st

from pack_evaluation import box_volume, volume_to_business
from pack_heuristics import rescue_unplaced_via_swap
from pack_pdf_export import generate_pack_plan_pdf
from pack_visualization import build_3d_figure


def render_packing_panel(prefix, label, placements, unplaced, boxes, ids, container_dim, cost_per_container):
    n_placed = len(placements)
    n_total = len(boxes)
    container_volume = box_volume(container_dim)

    # Greedy-Verbesserungssuche (KEINE Beam Search - kein beam_width, ein
    # einziger deterministischer Durchlauf): Button-gesteuert statt automatisch bei
    # jeder UI-Interaktion, da sie im Worst Case ~3-4s dauert (siehe README)
    # - dieselbe Grundidee wie flexible_beam_search_construction in der
    # Seefracht-Demo, aber wegen der 3D-Geometrie rechenaufwändiger und ohne
    # wirksame Kandidaten-Vorauswahl, die das entschärfen würde.
    current_key = (
        tuple(sorted((p["box_idx"], p["pos"], p["dim"]) for p in placements)),
        tuple(sorted(unplaced)), container_dim,
    )
    rescue_state_key = f"{prefix}_rescue_result"

    if unplaced:
        rescue_clicked = st.button(
            f"🔧 {len(unplaced)} unplatzierte Boxen nachträglich retten (Greedy-Verbesserungssuche)",
            key=f"{prefix}_rescue_btn",
            help="Sucht gezielt nach Umplatzierungen bereits eingeräumter Boxen, um zusätzliche, bisher unplatzierte Boxen doch noch unterzubringen. Kann einige Sekunden dauern.",
        )
        if rescue_clicked:
            with st.spinner("Suche nach Umplatzierungen, die zusätzliche Boxen unterbringen..."):
                t0 = time.time()
                rescued_placements, rescued_unplaced, n_rescued = rescue_unplaced_via_swap(
                    boxes, container_dim, placements, unplaced
                )
                elapsed = time.time() - t0
            st.session_state[rescue_state_key] = {
                "placements": rescued_placements, "unplaced": rescued_unplaced,
                "n_rescued": n_rescued, "key": current_key, "elapsed": elapsed,
            }

        rescue_result = st.session_state.get(rescue_state_key)
        if rescue_result is not None and rescue_result["key"] == current_key:
            if rescue_result["n_rescued"] > 0:
                st.success(
                    f"✅ {rescue_result['n_rescued']} zusätzliche Box(en) durch gezielte Umplatzierung "
                    f"untergebracht ({rescue_result['elapsed']:.1f}s)."
                )
                placements = rescue_result["placements"]
                unplaced = rescue_result["unplaced"]
                n_placed = len(placements)
            else:
                st.info(f"Keine zusätzliche Box konnte durch Umplatzierung untergebracht werden ({rescue_result['elapsed']:.1f}s).")
        elif rescue_result is not None:
            st.caption("⚠️ Ergebnis der letzten Rettungssuche bezog sich auf eine andere Konfiguration und wurde verworfen.")

    if n_placed > 1:
        auto_play = st.checkbox("▶️ Automatisch abspielen", key=f"{prefix}_auto")
        step = st.slider(
            f"Platzierungs-Schritt ({label})", 0, n_placed, n_placed, key=f"{prefix}_step",
            help="0 = leerer Container, Maximum = alle platzierbaren Boxen eingeräumt.",
        )
    else:
        auto_play = False
        step = n_placed
        if n_placed == 0:
            st.info("Keine einzige Box konnte in diesem Container platziert werden.")

    subset = placements[:step]
    placed_volume = sum(box_volume(p["dim"]) for p in subset)
    utilization_pct = (placed_volume / container_volume * 100) if container_volume > 0 else 0.0

    m1, m2, m3 = st.columns(3)
    m1.metric("Raumnutzung (aktueller Schritt)", f"{utilization_pct:.1f}%")
    m2.metric("Platzierte Boxen", f"{step} / {n_total}")
    final_unplaced_shown = len(unplaced) if step == n_placed else None
    m3.metric("Nicht platzierbar", str(final_unplaced_shown) if final_unplaced_shown is not None else "–")

    if step == n_placed and unplaced:
        unplaced_volume = sum(box_volume(boxes[i]) for i in unplaced)
        extra_containers, extra_cost = volume_to_business(unplaced_volume, container_volume, cost_per_container)
        st.warning(
            f"⚠️ {len(unplaced)} Boxen ({unplaced_volume / 1000:.0f} Liter) passen nicht in diesen "
            f"Container – geschätzt {extra_containers} weitere Container nötig "
            f"(~{extra_cost:.0f} € bei {cost_per_container:.0f} €/Container)."
        )

    fig = build_3d_figure(subset, boxes, ids, container_dim)
    plot_slot = st.empty()
    plot_slot.plotly_chart(fig, use_container_width=True, key=f"{prefix}_plot_{step}")

    if auto_play:
        for s in range(n_placed + 1):
            f = build_3d_figure(placements[:s], boxes, ids, container_dim)
            plot_slot.plotly_chart(f, use_container_width=True, key=f"{prefix}_auto_{s}")
            time.sleep(0.15)

    pdf_bytes = generate_pack_plan_pdf(label, placements, boxes, ids, unplaced, container_dim, cost_per_container)
    st.download_button(
        "📄 Packplan als PDF herunterladen", data=pdf_bytes,
        file_name=f"packplan_{prefix}.pdf", mime="application/pdf", key=f"{prefix}_pdf_download",
    )

    unplaced_volume_final = sum(box_volume(boxes[i]) for i in unplaced)
    final_placed_volume = sum(box_volume(p["dim"]) for p in placements)
    final_utilization_pct = (final_placed_volume / container_volume * 100) if container_volume > 0 else 0.0
    return {
        "label": label, "final_utilization_pct": final_utilization_pct,
        "n_placed": n_placed, "n_unplaced": len(unplaced), "unplaced_volume": unplaced_volume_final,
        "container_volume": container_volume, "placements": placements,
    }
