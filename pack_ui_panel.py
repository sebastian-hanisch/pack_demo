"""
Wiederverwendbares Streamlit-UI-Panel für eine einzelne Packheuristik:
Platzierungs-Schritt-Slider (+ Auto-Play als Animation), Metriken, 3D-Ansicht,
PDF-Export. Wird einmal pro Heuristik-Tab in app.py aufgerufen - analog zu
render_heuristic_panel in der Touren-Demo.
"""

import time

import streamlit as st

from pack_evaluation import box_volume, volume_to_business
from pack_pdf_export import generate_pack_plan_pdf
from pack_visualization import build_3d_figure


def render_packing_panel(prefix, label, placements, unplaced, boxes, ids, container_dim, cost_per_container):
    n_placed = len(placements)
    n_total = len(boxes)
    container_volume = box_volume(container_dim)

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
