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

- monobeam_packing: Monobeam-Adaption (Lemons, Linares López, Holte & Ruml,
  "Beam Search: Faster and Monotonic", ICAPS 2022) - verfolgt mehrere
  Teil-Packungen parallel, mit der bewiesenen Garantie, dass eine größere
  Beam-Breite die Raumnutzung nie verschlechtern kann (siehe Docstring der
  Funktion für die ausführliche Herleitung). Löste eine frühere, nicht
  monotone beam_search_packing-Implementierung ab, die auf ausdrücklichen
  Wunsch inzwischen ganz aus dem Code entfernt wurde - ihr Verhalten und die
  Gründe für die Ablösung sind im README dokumentiert.

Alle drei geben (placements, unplaced) zurück:
- placements: Liste von Dicts {"pos": (x,y,z), "dim": (l,w,h), "box_idx": i}
- unplaced: Liste der Box-Indizes, die nicht platziert werden konnten
"""

import heapq

from pack_constants import BEAM_WIDTH, EPS
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


def _best_placement(points, dims, placed_pairs, container_dim):
    """Sucht über alle Kandidatenpunkte und alle Rotationen einer Box die
    "tiefste, hinterste, am weitesten linke" (DBL) zulässige Platzierung.
    Gibt (key, point_index, pos, dim) der besten gefundenen Platzierung
    zurück, oder None. War zuvor identisch dupliziert in extreme_point_packing
    und _try_place_one - hier zusammengeführt.

    NICHT für monobeam_packing verwendet: die braucht pro Box mehrere
    Kandidaten (nicht nur den einen besten) und ein zusätzliches, fein
    austariertes Tie-Break über eine Erzeugungsreihenfolge, an dem die
    dokumentierte Monotonie-Garantie hängt (siehe dessen Docstring) - eine
    gemeinsame Schleife dafür wäre kein reines Zusammenführen von Duplikat
    mehr, sondern ein Umbau mit echtem Risiko für diese Garantie, deshalb
    bewusst nicht angefasst."""
    best = None
    for pi, p in enumerate(points):
        for rd in box_rotations(*dims):
            if not fits_in_container(p, rd, container_dim):
                continue
            if any_overlap(p, rd, placed_pairs):
                continue
            if not is_supported(p, rd, placed_pairs):
                continue
            key = (p[2], p[1], p[0])  # z, y, x - unten/hinten/links bevorzugt
            if best is None or key < best[0]:
                best = (key, pi, p, rd)
    return best


def _new_extreme_points(pos, dim, existing_points):
    """Leitet aus den drei "fernen" Ecken einer neu platzierten Box neue
    Kandidatenpunkte ab und hängt noch nicht vorhandene an eine NEUE Liste an
    - verändert existing_points nicht, wichtig für monobeam_packing, wo
    derselbe points-Zustand von mehreren Nachfolgezuständen aus verzweigt
    wird. War zuvor identisch dupliziert in extreme_point_packing und
    monobeam_packing - hier zusammengeführt."""
    x, y, z = pos
    dx, dy, dz = dim
    new_points = list(existing_points)
    for candidate in [(x + dx, y, z), (x, y + dy, z), (x, y, z + dz)]:
        if candidate not in new_points:
            new_points.append(candidate)
    return new_points


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
        best = _best_placement(points, dims, placed_boxes, container_dim_t)

        if best is None:
            unplaced.append(idx)
            continue

        _, pi, pos, rd = best
        placed_boxes.append((pos, rd))
        placements.append({"pos": pos, "dim": rd, "box_idx": idx})
        points.pop(pi)
        points = _new_extreme_points(pos, rd, points)

    return placements, unplaced


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
    best = _best_placement(points, box_dims, placed_pairs, container_dim)
    return (best[2], best[3]) if best else None


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

    PRO-SCHRITT-BEWERTUNG (welcher Kandidat je Slot beansprucht wird): DBL
    ("tiefste, hinterste, am weitesten linke" Position - z, y, x der
    Kandidatenposition), exakt wie extreme_point_packing. Auf scharfe
    Nutzerfrage hin korrigiert - eine frühere Fassung bewertete stattdessen
    nach (-Volumen, resultierende Maximalhöhe): da das Volumen für EIN
    bestimmtes Packstück bei jeder gültigen Position gleich ist, reduzierte
    sich das faktisch auf "minimiere die resultierende Maximalhöhe" - ein
    ANDERES Kriterium als DBL. Dadurch war Breite 1 NICHT identisch mit
    extreme_point_packing, obwohl das naheliegend erschien ("Breite 1 sollte
    doch praktisch Extreme-Point sein") - Extreme-Point konnte dadurch sogar
    BESSER als Beam Search abschneiden (z. B. "Gemischte Ladung"-Preset:
    81,4% vs. 78,8%), was der Monotonie-Garantie widersprach: eine größere
    Breite sollte nie schlechter sein als Breite 1, aber wenn Breite 1 nicht
    einmal Extreme-Point erreicht, hilft die Garantie an dieser Stelle nicht.

    Zwei Ursachen, nicht nur eine: (1) die Bewertungsgröße selbst
    (DBL vs. Maximalhöhe) UND (2) die Auflösung ECHTER Gleichstände (mehrere
    gültige Rotationen an derselben Position) - Extreme-Point löst diese
    über die Erzeugungsreihenfolge auf ("zuerst gefunden gewinnt", da
    `points` außen, Rotationen innen durchlaufen werden), monobeam vorher
    über den State-Fingerprint (eine andere, unabhängige Regel). Erst nach
    Korrektur BEIDER Punkte (DBL als Score, `gen_order`-Zähler als Tie-Break
    in derselben Reihenfolge wie Extreme-Point) war Breite 1 byte-identisch
    mit extreme_point_packing, über 9 getestete Instanzen verifiziert.

    Versucht, aber verworfen: die resultierende Maximalhöhe als ZUSÄTZLICHEN
    Tie-Break NACH DBL zu verwenden (statt der reinen Erzeugungsreihenfolge)
    - naheliegend, um "das Beste aus beiden Bewertungsgrößen zu kombinieren".
    Ergebnis: Breite 1 wich dadurch wieder in 12 von 14 Fällen von
    Extreme-Point ab, in 6 davon sogar SCHLECHTER - die Kombination brach
    die Übereinstimmung erneut auf, weil Extreme-Points eigene Tie-Break-
    Regel nicht höhenbasiert ist. Auch als Test, ob eine höhenbasierte
    Tie-Break-Regel Extreme-Point SELBST verbessern würde (dann könnten
    beide synchron auf das bessere Kriterium umgestellt werden): über 20
    Instanzen fast ausgeglichen (9 besser, 8 schlechter) - keine der beiden
    Regeln ist objektiv überlegen, nur unterschiedlich. Die eigentliche
    "Kombination", die funktioniert, ist keine cleverere Pro-Schritt-Formel,
    sondern die saubere Aufgabentrennung: DBL lenkt die Suche (bewährt,
    exakt wie Extreme-Point), eine deterministische Reihenfolge löst echte
    Gleichstände auf (ebenfalls wie Extreme-Point), und erst die
    FINAL-AUSWAHL zwischen den am Ende verbliebenen Beam-Zuständen nutzt das
    tatsächlich interessierende PLATZIERTE VOLUMEN (siehe unten) - der
    eigentliche Nutzen einer größeren Breite kommt daher, mehrere
    unterschiedlich aufgelöste Gleichstands-Pfade parallel zu verfolgen und
    danach den besten zu übernehmen, nicht aus einer schlaueren
    Einzelentscheidung.

    Bewertungsgröße für die FINALE Auswahl zwischen verschiedenen
    Beam-Zuständen am Ende ist weiterhin das PLATZIERTE VOLUMEN (nicht die
    Anzahl platzierter Boxen) - wichtig, weil "mehr Boxen" nicht dasselbe
    ist wie "mehr Volumen" (viele kleine vs. wenige große Boxen). Eine noch
    frühere Fassung optimierte hier nach Boxenzahl, dann Kompaktheit - dabei
    blieben 2 von 14 winzige (~0,1 Prozentpunkt) Verletzungen der
    RAUMNUTZUNG übrig, obwohl die Boxenzahl selbst bereits perfekt monoton
    war (nachgeprüft) - ein Nebeneffekt davon, dass eine andere Größe als
    die tatsächlich angezeigte optimiert wurde. Nach Umstellung auf Volumen:
    exakt 0 Verletzungen, weil jetzt genau die angezeigte Kennzahl selbst
    optimiert wird.

    ERGEBNIS DER DBL-KORREKTUR: da Breite 1 jetzt exakt Extreme-Point
    entspricht UND die Monotonie-Garantie gilt, folgt zwingend: Beam Search
    kann bei KEINER Breite mehr schlechter als Extreme-Point sein - über 30
    Testinstanzen verifiziert (5 besser, 0 schlechter, 25 gleich). Das war
    vorher nicht garantiert. Eine Nebenwirkung: der zuvor demonstrierte
    "Enges Puzzle"-Vorsprung (71,8%→80,7%) verschwand bei diesem konkreten
    Seed komplett (blieb exakt bei 71,8%, selbst bei Breite 32) - er war
    teilweise ein Artefakt der falschen Bewertungsgröße, keine echte
    Exploration. Echte, wenn auch seltenere und kleinere Vorteile durch
    Breite bleiben nachweisbar (systematisch neu gesucht: 41 von ~300
    getesteten Konfigurationen zeigen >1 Prozentpunkt Vorsprung, bester Fund
    +6,3 Prozentpunkte) - siehe README für den neu gefundenen Preset."""
    order = sorted(range(len(boxes)), key=lambda i: -_box_volume(boxes[i]))

    init_state = {"placed": [], "points": [(0.0, 0.0, 0.0)], "unplaced": [], "max_z": 0.0, "vol": 0.0}
    beam = [None] * beam_width
    beam[0] = init_state

    for idx in order:
        dims = boxes[idx]
        candidates = []  # heapq: (score, Erzeugungsreihenfolge, fingerprint, state) - gemeinsam ueber alle Slots dieser Ebene
        next_beam = [None] * beam_width
        gen_order = 0  # gleiche Tie-Break-Regel wie Extreme-Point: zuerst gefunden gewinnt bei Gleichstand

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
                        new_points = _new_extreme_points(p, rd, new_points)
                        x, y, z = p
                        dx, dy, dz = rd
                        new_state = {
                            "placed": new_placed, "points": new_points,
                            "unplaced": state["unplaced"], "max_z": max(state["max_z"], z + dz),
                            "vol": state["vol"] + _box_volume(rd),
                        }
                        score = (p[2], p[1], p[0])  # DBL: unten/hinten/links, wie Extreme-Point
                        heapq.heappush(candidates, (score, gen_order, _state_fingerprint(new_placed), new_state))
                        gen_order += 1
                if not found_any:
                    new_state = {
                        "placed": state["placed"], "points": state["points"],
                        "unplaced": state["unplaced"] + [idx], "max_z": state["max_z"], "vol": state["vol"],
                    }
                    score = (float("inf"), float("inf"), float("inf"))
                    heapq.heappush(candidates, (score, gen_order, _state_fingerprint(new_state["placed"]), new_state))
                    gen_order += 1

            # KRITISCH: sofort nach der Erweiterung von Slot c beanspruchen,
            # BEVOR Slot c+1 angefasst wird - siehe Docstring fuer den Fehler,
            # der beim Trennen dieser beiden Schritte entstand.
            if candidates:
                _score, _order, _fp, best_state = heapq.heappop(candidates)
                next_beam[c] = best_state

        beam = next_beam

    valid_states = [s for s in beam if s is not None]
    best = max(valid_states, key=lambda s: (s["vol"], -s["max_z"]))
    return best["placed"], best["unplaced"]
