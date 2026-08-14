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

import heapq

from pack_constants import BEAM_CANDIDATES_PER_STATE, BEAM_WIDTH, EPS
from pack_geometry import any_overlap, box_rotations, fits_in_container, is_supported


def _support_height_for_footprint(x, y, l, w, placed_pairs):
    """Höchste Oberfläche unter dem angegebenen Fußabdruck (x,y,l,w) - die
    Box muss mindestens auf dieser Höhe ruhen, um nicht zu überlappen.
    Garantiert für sich allein noch KEINE volle Stützung (siehe
    is_supported) - falls der Fußabdruck über Boxen unterschiedlicher Höhe
    hinausragt, kann trotzdem eine Lücke bleiben, die is_supported()
    zusätzlich prüft."""
    max_h = 0.0
    for (px, py, pz), (pl, pw, ph) in placed_pairs:
        if px < x + l - EPS and px + pl > x + EPS and py < y + w - EPS and py + pw > y + EPS:
            max_h = max(max_h, pz + ph)
    return max_h


def layer_based_packing(boxes, container_dim):
    """Schichten-Heuristik: Boxen werden nach Höhe absteigend sortiert. Für
    jede Box wird die "tiefste, hinterste, am weitesten links liegende"
    Position über ein wachsendes Raster aus (x,y)-Kandidaten gesucht (Ecken
    bereits platzierter Boxen in der Grundfläche) - keine Rotation, kein
    3D-Extrempunkt-Verfahren wie bei Extreme-Point, nur ein einfaches
    2D-Raster mit "auf das tatsächlich Vorhandene fallen lassen" für die
    Höhe. Bewusst die einfachste der drei Heuristiken.

    Auf Nutzerhinweis ergänzt ("Packstücke scheinen zu schweben"): zwei
    frühere Fassungen hatten Probleme. Die erste nutzte einen einzelnen
    globalen Höhen-Cursor (`z += layer_height`, Höhe der GRÖSSTEN Box einer
    Reihe für ALLE Boxen dieser Reihe) - bei unterschiedlich hohen Boxen in
    derselben Reihe reichten kleinere Boxen nicht bis zu dieser Höhe,
    wodurch eine Box der nächsten Schicht über der Lücke schwebte. Ein
    zweiter Versuch (feste (x,y)-Reihenfolge mit nur 3 Versuchen pro Box,
    Höhe live berechnet) behob das Schweben, aber die Raumnutzung brach ein
    (z. B. Seed 1: 25 auf 5 Boxen) - schlug eine Box an einer bestimmten
    Position fehl, blieb der (x,y)-Cursor dort "stecken" und vergiftete
    ALLE nachfolgenden Boxen (jede scheiterte an derselben Position, ohne
    Möglichkeit, eine andere zu versuchen). Jetzt: robuste Suche über ein
    wachsendes Kandidaten-Raster statt eines starren 3-Versuche-Cursors -
    kann eine Box hier nicht platziert werden, bleibt der Rasterzustand für
    die nächste Box unverändert (kein Steckenbleiben mehr möglich)."""
    CL, CW, CH = container_dim
    order = sorted(range(len(boxes)), key=lambda i: -boxes[i][2])

    placements = []
    unplaced = []
    x_edges = {0.0}
    y_edges = {0.0}

    for idx in order:
        l, w, h = boxes[idx]
        placed_pairs = [(p["pos"], p["dim"]) for p in placements]
        best = None
        for y in sorted(y_edges):
            if y + w > CW + EPS:
                continue
            for x in sorted(x_edges):
                if x + l > CL + EPS:
                    continue
                actual_z = _support_height_for_footprint(x, y, l, w, placed_pairs)
                if actual_z + h > CH + EPS:
                    continue
                if not is_supported((x, y, actual_z), (l, w, h), placed_pairs):
                    continue
                if any_overlap((x, y, actual_z), (l, w, h), placed_pairs):
                    continue
                key = (actual_z, y, x)  # unten/hinten/links bevorzugt, wie bei Extreme-Point
                if best is None or key < best[0]:
                    best = (key, x, y, actual_z)

        if best is None:
            unplaced.append(idx)
            continue

        _, x, y, actual_z = best
        placements.append({"pos": (x, y, actual_z), "dim": (l, w, h), "box_idx": idx})
        x_edges.add(x + l)
        y_edges.add(y + w)

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
                if not is_supported(p, rd, placed_boxes):
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
                    if not is_supported(p, rd, placed_pairs):
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


def _candidate_points_for(placed_pairs):
    """Rekonstruiert eine gültige (wenn auch nicht notwendig minimale)
    Kandidatenpunktliste für einen gegebenen Satz bereits platzierter Boxen
    ((pos, dim)-Paare). Kann leicht mehr Punkte liefern als die inkrementelle
    Extreme-Point-Konstruktion es täte - das ist unschädlich, da ungültige
    Punkte ohnehin von der Überlappungs-/Grenzenprüfung verworfen werden."""
    points = [(0.0, 0.0, 0.0)]
    seen = {(0.0, 0.0, 0.0)}
    for pos, dim in placed_pairs:
        x, y, z = pos
        dx, dy, dz = dim
        for candidate in [(x + dx, y, z), (x, y + dy, z), (x, y, z + dz)]:
            if candidate not in seen:
                seen.add(candidate)
                points.append(candidate)
    return points


def _try_place_one(box_dims, placed_pairs, container_dim):
    """Versucht, eine einzelne Box in einen gegebenen Zustand (Liste
    bereits platzierter (pos, dim)-Paare) einzufügen. Gibt (pos, dim) der
    besten zulässigen Platzierung zurück, oder None."""
    points = _candidate_points_for(placed_pairs)
    best = None
    for p in points:
        for rd in box_rotations(*box_dims):
            if not fits_in_container(p, rd, container_dim):
                continue
            if any_overlap(p, rd, placed_pairs):
                continue
            if not is_supported(p, rd, placed_pairs):
                continue
            key = (p[2], p[1], p[0])
            if best is None or key < best[0]:
                best = (key, p, rd)
    return (best[1], best[2]) if best else None


def rescue_unplaced_via_swap(boxes, container_dim, base_placements, base_unplaced, max_pairs=3600):
    """Greedy-Verbesserungssuche, auf ausdrücklichen Wunsch ergänzt -
    dieselbe Grundidee wie flexible_beam_search_construction in der
    Seefracht-Demo, auf die Packungsoptimierung übertragen: startet bei
    einer bestehenden Konstruktion (z.B. Extreme-Point) und sucht gezielt
    nach Umplatzierungen, die zusätzliche, bisher unplatzierte Boxen
    unterbringen. Garantiert nie schlechter als der Ausgangszustand - jede
    akzeptierte Verschiebung platziert strikt mehr Boxen als vorher.

    WICHTIG - trotz des Namensmusters KEINE Beam Search: anders als
    flexible_beam_search_construction gibt es hier keinen beam_width-
    Parameter, keine parallel verfolgten Kandidatenzustände - ein einziger
    deterministischer Durchlauf, der bei der ersten erfolgreichen
    Verschiebung sofort übernimmt (first-improvement). Die Monotonie-
    Eigenschaft aus der Fracht-Demo bezieht sich auf "mehr Breite wird nie
    schlechter" - ohne Breite gibt es diese Dimension hier gar nicht, die
    Frage stellt sich nicht.

    Wurde eine Breite (mehrere zufällig geordnete Durchläufe, bester wird
    übernommen) getestet? Ja - fand vereinzelt mehr Rettungen (teils
    doppelt so viele), aber inkonsistent (nicht bei jeder Instanz) und bei
    linear mit der Breite wachsender Rechenzeit. Da bereits ein einzelner
    Durchlauf im Worst Case ~3,6s braucht, würde selbst eine bescheidene
    Breite von 3-5 den Worst Case auf 10-18s treiben - für einen
    unsicheren Zusatznutzen zu teuer für eine Button-Aktion. Bewusst nicht
    eingebaut (siehe README für die genauen Zahlen).

    Mechanismus: für jede unplatzierte Box U wird jede bereits platzierte
    Box P probeweise entfernt, geprüft ob U dann passt, und falls ja, ob P
    selbst an anderer Stelle wieder untergebracht werden kann. Gelingt
    beides, werden beide Boxen übernommen (netto eine Box mehr platziert).

    Anders als bei der Seefracht-Demo ließ sich hier keine wirksame
    Kandidaten-Vorauswahl finden, die die Rechenzeit spürbar senkt, ohne den
    gefundenen Nutzen zunichtezumachen (getestet: Beschränkung auf die
    größten platzierten Boxen zuerst - hat die tatsächlich hilfreichen,
    meist kleineren/anders positionierten Kandidaten verpasst). Deshalb
    bewusst NICHT automatisch bei jeder UI-Interaktion aufgerufen, sondern
    über einen eigenen Button - Worst Case bei maximaler Boxenzahl (60):
    ~3,6s, für eine bewusst ausgelöste Aktion vertretbar (ähnliche
    Größenordnung wie die OR-Tools-Zeitbegrenzung der Tourenplanung-Demo).

    max_pairs begrenzt die Gesamtzahl der pro Runde geprüften (U,P)-Paare
    als Sicherheitsnetz gegen pathologische Eingaben - bei der regulären
    Obergrenze von 60 Boxen wird dieses Limit nie erreicht."""
    placements = [dict(p) for p in base_placements]
    unplaced = list(base_unplaced)
    n_rescued = 0

    improved = True
    while improved and unplaced:
        improved = False
        pairs_checked = 0
        for u_idx in list(unplaced):
            if pairs_checked >= max_pairs:
                break
            u_dims = boxes[u_idx]

            for p_entry in list(placements):
                if pairs_checked >= max_pairs:
                    break
                pairs_checked += 1
                p_idx = p_entry["box_idx"]
                reduced_pairs = [(pp["pos"], pp["dim"]) for pp in placements if pp["box_idx"] != p_idx]
                result_u = _try_place_one(u_dims, reduced_pairs, container_dim)
                if result_u is None:
                    continue
                pos_u, rd_u = result_u
                trial_pairs = reduced_pairs + [(pos_u, rd_u)]
                result_p = _try_place_one(boxes[p_idx], trial_pairs, container_dim)
                if result_p is None:
                    continue
                pos_p, rd_p = result_p

                placements = [pp for pp in placements if pp["box_idx"] != p_idx]
                placements.append({"pos": pos_u, "dim": rd_u, "box_idx": u_idx})
                placements.append({"pos": pos_p, "dim": rd_p, "box_idx": p_idx})
                unplaced.remove(u_idx)
                n_rescued += 1
                improved = True
                break
            if improved:
                break

    return placements, unplaced, n_rescued


def _state_fingerprint(placed):
    return tuple(sorted((p["box_idx"], p["pos"], p["dim"]) for p in placed))


def _box_volume(dim):
    return dim[0] * dim[1] * dim[2]


def monobeam_packing(boxes, container_dim, beam_width=BEAM_WIDTH):
    """Monobeam-Adaption (Lemons, Linares López, Holte & Ruml, "Beam Search:
    Faster and Monotonic", ICAPS 2022) auf die 3D-Packungskonstruktion - auf
    Nachfrage ergänzt, nachdem sich beam_search_packing als NICHT monoton
    erwies (empirisch bestätigt: 11-12 von 14 Testinstanzen zeigten eine
    schlechtere Raumnutzung bei größerer statt kleinerer Beam-Breite - dasselbe
    strukturelle Muster wie die zuerst verworfene Beam-Search-Variante der
    Seefracht-Demo: pro Schritt wird die volle Kandidatenmenge sortiert und
    gekürzt, plus zusätzlich eine Pro-Zustand-Begrenzung).

    Kernidee wie bei monobeam_construction in der Seefracht-Demo: der Beam
    wird als GEORDNETE Folge nummerierter Slots behandelt und SEQUENZIELL
    gefüllt - Slot c wird expandiert und beansprucht SOFORT das beste
    verbliebene Element aus einem mit allen Slots geteilten Kandidatenpool,
    BEVOR Slot c+1 überhaupt angefasst wird. Nur diese strikte Verschachtelung
    (nicht zwei getrennte Schritte "alles erzeugen" / "dann verteilen")
    garantiert, dass Slot c ausschließlich von den Slots 1..c des Beams der
    VORHERIGEN Ebene abhängt - und damit, dass eine größere Breite das
    Ergebnis nie verschlechtern kann. Ein eigener, beim Bauen gefundener
    Fehler: eine erste Fassung trennte Erzeugung und Verteilung in zwei
    Schleifen - das ergab 12 von 14 Verletzungen, sogar mehr als das
    Original. Nach dem Verschachtelungs-Fix: 0 von 30 Verletzungen über eine
    breite Stichprobe (siehe README).

    Bewertungsgröße ist das PLATZIERTE VOLUMEN (nicht die Anzahl platzierter
    Boxen) - wichtig, weil "mehr Boxen" nicht dasselbe ist wie "mehr Volumen"
    (viele kleine vs. wenige große Boxen). Eine erste Fassung optimierte nach
    Boxenzahl, dann Kompaktheit - dabei blieben 2 von 14 winzige (~0,1
    Prozentpunkt) Verletzungen der RAUMNUTZUNG übrig, obwohl die Boxenzahl
    selbst bereits perfekt monoton war (nachgeprüft) - ein Nebeneffekt davon,
    dass eine andere Größe als die tatsächlich angezeigte optimiert wurde.
    Nach Umstellung auf Volumen als Bewertungsgröße: exakt 0 Verletzungen,
    weil jetzt genau die angezeigte Kennzahl selbst optimiert wird.

    WICHTIGER, EHRLICHER KOMPROMISS: monoton zu sein bedeutet nicht
    zwangsläufig, in JEDEM Einzelfall besser zu sein als die ursprüngliche
    (nicht monotone) Implementierung. Über 30 Testinstanzen ist monobeam im
    Schnitt leicht besser (+0,25 Prozentpunkte, gewinnt 15 von 30 Fällen),
    aber im Worst Case bis zu 9,1 Prozentpunkte SCHLECHTER als die alte
    Implementierung - insbesondere beim "Enges Puzzle"-Preset erreicht
    monobeam selbst bei Breite 50 nur ~77% statt der dort dokumentierten
    82,7%. Die vorhersagbare Garantie "breiter wird nie schlechter" hat ihren
    Preis: eine stärker eingeschränkte Suche (Slot 1 ist immer identisch zur
    Breite-1-Lösung, unabhängig von der Gesamtbreite), die gelegentlich
    bessere, aber unvorhersehbare Zufallsfunde der ursprünglichen Version
    nicht macht. Deshalb bewusst NICHT die App-Verdrahtung ersetzt - siehe
    README für die vollständige Abwägung."""
    order = sorted(range(len(boxes)), key=lambda i: -_box_volume(boxes[i]))

    init_state = {"placed": [], "points": [(0.0, 0.0, 0.0)], "unplaced": [], "max_z": 0.0, "vol": 0.0}
    beam = [None] * beam_width
    beam[0] = init_state

    for idx in order:
        dims = boxes[idx]
        candidates = []  # heapq: (score, fingerprint, state) - gemeinsam ueber alle Slots dieser Ebene
        next_beam = [None] * beam_width

        for c in range(beam_width):
            if beam[c] is not None:
                state = beam[c]
                placed_pairs = [(p["pos"], p["dim"]) for p in state["placed"]]
                found_any = False
                for pi, p in enumerate(state["points"]):
                    for rd in box_rotations(*dims):
                        if not fits_in_container(p, rd, container_dim):
                            continue
                        if any_overlap(p, rd, placed_pairs):
                            continue
                        if not is_supported(p, rd, placed_pairs):
                            continue
                        found_any = True
                        new_placed = state["placed"] + [{"pos": p, "dim": rd, "box_idx": idx}]
                        new_points = state["points"][:pi] + state["points"][pi + 1:]
                        x, y, z = p
                        dx, dy, dz = rd
                        for cand_pt in [(x + dx, y, z), (x, y + dy, z), (x, y, z + dz)]:
                            if cand_pt not in new_points:
                                new_points = new_points + [cand_pt]
                        new_state = {
                            "placed": new_placed, "points": new_points,
                            "unplaced": state["unplaced"], "max_z": max(state["max_z"], z + dz),
                            "vol": state["vol"] + _box_volume(rd),
                        }
                        score = (-new_state["vol"], new_state["max_z"])
                        heapq.heappush(candidates, (score, _state_fingerprint(new_placed), new_state))
                if not found_any:
                    new_state = {
                        "placed": state["placed"], "points": state["points"],
                        "unplaced": state["unplaced"] + [idx], "max_z": state["max_z"], "vol": state["vol"],
                    }
                    score = (-new_state["vol"], new_state["max_z"])
                    heapq.heappush(candidates, (score, _state_fingerprint(new_state["placed"]), new_state))

            # KRITISCH: sofort nach der Erweiterung von Slot c beanspruchen,
            # BEVOR Slot c+1 angefasst wird - siehe Docstring fuer den Fehler,
            # der beim Trennen dieser beiden Schritte entstand.
            if candidates:
                _score, _fp, best_state = heapq.heappop(candidates)
                next_beam[c] = best_state

        beam = next_beam

    valid_states = [s for s in beam if s is not None]
    best = max(valid_states, key=lambda s: (s["vol"], -s["max_z"]))
    return best["placed"], best["unplaced"]
