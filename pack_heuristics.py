"""
Drei selbst implementierte Heuristiken für das 3D-Bin-Packing-Problem
(Container-/Palettenstauung):

- layer_based_packing: baut die Ladung schichtweise auf, wie man intuitiv
  von Hand packen würde. Einfach und schnell, verschwendet aber Raum, wenn
  Boxen innerhalb einer Schicht unterschiedlich hoch sind. Dient als feste
  Baseline für den Vergleich.

- extreme_point_packing: verfolgt eine Liste konkurrierender Eckpunkte
  (Crainic, Perboli, Tadei 2008) und füllt Lücken zwischen unterschiedlich
  großen Boxen gezielter. In der Regel deutlich bessere Raumnutzung als die
  Baseline, kostet aber mehr Rechenzeit.

- beam_search_packing: verfolgt mehrere Teil-Packungen parallel (wie die
  Beam-Search-Heuristik in der Tourenplanung-Demo). Bei jeder Box werden pro
  Teilzustand mehrere Kandidaten erzeugt statt nur der eine beste; die
  insgesamt besten Teilzustände werden weiterverfolgt. Im Benchmark im
  Schnitt +0,9 Prozentpunkte Raumnutzung gegenüber Extreme-Point, bei dicht
  gepackten Instanzen teils deutlich mehr - bei großen, dünn besiedelten
  Containern dagegen manchmal exakt keine Verbesserung, obwohl 6-7x langsamer
  (siehe README für die vollständige, ehrlich dokumentierte Abwägung).

Alle drei geben (placements, unplaced) zurück:
- placements: Liste von Dicts {"pos": (x,y,z), "dim": (l,w,h), "box_idx": i}
- unplaced: Liste der Box-Indizes, die nicht platziert werden konnten
"""

from pack_constants import BEAM_CANDIDATES_PER_STATE, BEAM_WIDTH, EPS
from pack_geometry import any_overlap, box_rotations, fits_in_container


def layer_based_packing(boxes, container_dim):
    """Schichten-Heuristik: Boxen werden nach Höhe absteigend sortiert und in
    Reihen/Schichten angeordnet - neue Reihe, wenn die Breite nicht mehr
    reicht, neue Schicht, wenn die Tiefe nicht mehr reicht. Keine Rotation,
    keine Lückenfüllung - bewusst die einfachere der beiden Heuristiken."""
    CL, CW, CH = container_dim
    order = sorted(range(len(boxes)), key=lambda i: -boxes[i][2])

    placements = []
    unplaced = []
    x = y = z = 0.0
    row_depth = 0.0
    layer_height = 0.0

    for idx in order:
        l, w, h = boxes[idx]
        placed_this_box = False

        # bis zu 3 Versuche: aktuelle Reihe -> neue Reihe -> neue Schicht
        for _attempt in range(3):
            if x + l <= CL + EPS and y + w <= CW + EPS and z + h <= CH + EPS:
                placements.append({"pos": (x, y, z), "dim": (l, w, h), "box_idx": idx})
                x += l
                row_depth = max(row_depth, w)
                layer_height = max(layer_height, h)
                placed_this_box = True
                break
            if x + l > CL + EPS:
                x = 0.0
                y += row_depth
                row_depth = 0.0
                continue
            if y + w > CW + EPS:
                x = 0.0
                y = 0.0
                z += layer_height
                layer_height = 0.0
                row_depth = 0.0
                continue
            break  # passt auch nach Schichtwechsel nicht (z. B. zu hoch)

        if not placed_this_box:
            unplaced.append(idx)

    return placements, unplaced


def extreme_point_packing(boxes, container_dim):
    """Extreme-Point-Heuristik: hält eine Liste von Kandidatenpunkten, an
    denen die nächste Box platziert werden könnte. Für jede Box (nach Volumen
    absteigend sortiert) wird die "tiefste, unterste, am weitesten links
    liegende" zulässige Position über alle Punkte und alle 6 Rotationen
    gesucht. Nach jeder Platzierung entstehen aus den drei "fernen" Ecken der
    Box neue Kandidatenpunkte."""
    CL, CW, CH = container_dim
    container_dim_t = (CL, CW, CH)
    order = sorted(range(len(boxes)), key=lambda i: -(boxes[i][0] * boxes[i][1] * boxes[i][2]))

    points = [(0.0, 0.0, 0.0)]
    placed_boxes = []  # (pos, dim) - für Overlap-Prüfung
    placements = []
    unplaced = []

    for idx in order:
        dims = boxes[idx]
        best = None  # (sort_key, point_index, pos, dim)
        for pi, p in enumerate(points):
            for rd in box_rotations(*dims):
                if not fits_in_container(p, rd, container_dim_t):
                    continue
                if any_overlap(p, rd, placed_boxes):
                    continue
                key = (p[2], p[1], p[0])  # z, y, x - unten/hinten/links bevorzugt
                if best is None or key < best[0]:
                    best = (key, pi, p, rd)

        if best is None:
            unplaced.append(idx)
            continue

        _, pi, pos, rd = best
        placed_boxes.append((pos, rd))
        placements.append({"pos": pos, "dim": rd, "box_idx": idx})
        points.pop(pi)

        x, y, z = pos
        dx, dy, dz = rd
        for candidate in [(x + dx, y, z), (x, y + dy, z), (x, y, z + dz)]:
            if candidate not in points:
                points.append(candidate)

    return placements, unplaced


def beam_search_packing(boxes, container_dim, beam_width=BEAM_WIDTH, candidates_per_state=BEAM_CANDIDATES_PER_STATE):
    """Beam Search: verfolgt mehrere Teil-Packungen parallel statt nur einer
    (wie Extreme-Point). Feste Box-Reihenfolge (nach Volumen absteigend, wie
    bei Extreme-Point) - der Suchraum liegt darin, WELCHE Position/Rotation
    pro Box gewählt wird, nicht in welcher Reihenfolge Boxen platziert
    werden. Pro Teilzustand werden die `candidates_per_state` besten
    Positionen erzeugt (statt nur der einen besten); die insgesamt
    `beam_width` besten neuen Teilzustände - zuerst nach Anzahl platzierter
    Boxen, dann nach Kompaktheit (niedrigste erreichte Höhe) - werden
    weiterverfolgt."""
    order = sorted(range(len(boxes)), key=lambda i: -(boxes[i][0] * boxes[i][1] * boxes[i][2]))

    init_state = {"placed": [], "points": [(0.0, 0.0, 0.0)], "unplaced": [], "max_z": 0.0}
    beam = [init_state]

    for idx in order:
        dims = boxes[idx]
        all_candidates = []
        for state in beam:
            placed_pairs = [(p["pos"], p["dim"]) for p in state["placed"]]
            local_candidates = []
            for pi, p in enumerate(state["points"]):
                for rd in box_rotations(*dims):
                    if not fits_in_container(p, rd, container_dim):
                        continue
                    if any_overlap(p, rd, placed_pairs):
                        continue
                    key = (p[2], p[1], p[0])  # unten/hinten/links bevorzugt
                    local_candidates.append((key, pi, p, rd))
            local_candidates.sort(key=lambda c: c[0])

            if not local_candidates:
                all_candidates.append({
                    "placed": state["placed"], "points": state["points"],
                    "unplaced": state["unplaced"] + [idx], "max_z": state["max_z"],
                })
                continue

            for key, pi, p, rd in local_candidates[:candidates_per_state]:
                new_placed = state["placed"] + [{"pos": p, "dim": rd, "box_idx": idx}]
                new_points = state["points"][:pi] + state["points"][pi + 1:]
                x, y, z = p
                dx, dy, dz = rd
                for cand_pt in [(x + dx, y, z), (x, y + dy, z), (x, y, z + dz)]:
                    if cand_pt not in new_points:
                        new_points = new_points + [cand_pt]
                all_candidates.append({
                    "placed": new_placed, "points": new_points,
                    "unplaced": state["unplaced"], "max_z": max(state["max_z"], z + dz),
                })

        all_candidates.sort(key=lambda c: (-len(c["placed"]), c["max_z"]))
        # Deduplizieren: identische Nachfolgezustände nicht mehrfach im Beam behalten
        seen = set()
        deduped = []
        for c in all_candidates:
            fingerprint = tuple(sorted((p["box_idx"], p["pos"], p["dim"]) for p in c["placed"]))
            if fingerprint not in seen:
                seen.add(fingerprint)
                deduped.append(c)
        beam = deduped[:beam_width]

    best = max(beam, key=lambda c: len(c["placed"]))
    return best["placed"], best["unplaced"]
