"""
Erzeugt einen einsatzfähigen Packplan als downloadbares PDF (in-memory, kein
Zwischenspeichern auf Disk nötig) - Zusammenfassung + Positionsliste je Box.
"""

import time

from pack_constants import DEFAULT_COST_PER_CONTAINER
from pack_evaluation import evaluate_packing, volume_to_business


def generate_pack_plan_pdf(label, placements, boxes, ids, unplaced, container_dim, cost_per_container=DEFAULT_COST_PER_CONTAINER):
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    stats = evaluate_packing(placements, boxes, container_dim, unplaced)
    extra_containers, extra_cost = volume_to_business(stats["unplaced_volume"], stats["container_volume"], cost_per_container)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"Packplan - {label}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, f"Erstellt: {time.strftime('%d.%m.%Y %H:%M')} Uhr", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    CL, CW, CH = container_dim
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Zusammenfassung", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Container: {CL:.0f} x {CW:.0f} x {CH:.0f} cm", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, f"Raumnutzung: {stats['utilization_pct']:.1f}%", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, f"Platzierte Boxen: {stats['n_placed']} von {stats['n_placed']+stats['n_unplaced']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if stats["n_unplaced"] > 0:
        pdf.cell(0, 6, f"Nicht platziert: {stats['n_unplaced']} Boxen ({stats['unplaced_volume']/1000:.1f} Liter)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.cell(0, 6, f"Geschätzt zusätzlich benötigt: {extra_containers} Container (~{extra_cost:.0f} EUR)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Positionsliste (platzierte Boxen)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    headers = ["#", "Box-ID", "Position (x,y,z)", "Maße (L x B x H)"]
    widths = [10, 25, 65, 60]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(235, 235, 235)
    for h, w in zip(headers, widths):
        pdf.cell(w, 7, h, border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln(7)

    pdf.set_font("Helvetica", "", 9)
    sorted_placements = sorted(placements, key=lambda p: (p["pos"][2], p["pos"][1], p["pos"][0]))
    for i, entry in enumerate(sorted_placements):
        idx = entry["box_idx"]
        pos = entry["pos"]
        dim = entry["dim"]
        row = [
            str(i + 1), str(ids[idx]),
            f"({pos[0]:.0f}, {pos[1]:.0f}, {pos[2]:.0f}) cm",
            f"{dim[0]:.0f} x {dim[1]:.0f} x {dim[2]:.0f} cm",
        ]
        for val, w in zip(row, widths):
            pdf.cell(w, 6, val, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln(6)

    if unplaced:
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, "Nicht platzierte Boxen", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 9)
        for idx in unplaced:
            l, w, h = boxes[idx]
            pdf.cell(0, 6, f"Box {ids[idx]}: {l:.0f} x {w:.0f} x {h:.0f} cm", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())
