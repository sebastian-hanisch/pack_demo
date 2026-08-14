"""
Geometrische Grundfunktionen für die 3D-Packung: Rotationen einer Box,
Überlappungs- und Bounds-Prüfung (Axis-Aligned Bounding Box, AABB).
Bewusst einfach gehalten und unabhängig von den Packheuristiken, damit sie
isoliert getestet werden können.
"""

from pack_constants import EPS


def box_rotations(l, w, h):
    """Alle 6 möglichen achsparallelen Ausrichtungen einer Box (Permutationen
    der drei Kantenlängen). Doppelte werden entfernt (z. B. bei einem Würfel
    oder gleich langen Kanten)."""
    dims = (l, w, h)
    perms = [(0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)]
    seen = set()
    rotations = []
    for p in perms:
        r = (dims[p[0]], dims[p[1]], dims[p[2]])
        if r not in seen:
            seen.add(r)
            rotations.append(r)
    return rotations


def boxes_overlap(pos1, dim1, pos2, dim2, eps=EPS):
    """AABB-Überlappungstest: Zwei Quader überlappen genau dann, wenn sie
    sich auf ALLEN drei Achsen gleichzeitig überschneiden. Berühren sich zwei
    Boxen nur an einer Fläche/Kante (kein Overlap, nur Kontakt), zählt das
    NICHT als Überlappung."""
    for i in range(3):
        if pos1[i] + dim1[i] <= pos2[i] + eps or pos2[i] + dim2[i] <= pos1[i] + eps:
            return False
    return True


def fits_in_container(pos, dim, container_dim, eps=EPS):
    """Prüft, ob eine Box an gegebener Position vollständig innerhalb der
    Containergrenzen liegt (keine negativen Koordinaten, kein Überstand)."""
    for i in range(3):
        if pos[i] < -eps or pos[i] + dim[i] > container_dim[i] + eps:
            return False
    return True


def any_overlap(pos, dim, placed_boxes, eps=EPS):
    """Prüft, ob eine Box mit irgendeiner bereits platzierten Box überlappt.
    `placed_boxes` ist eine Liste von (pos, dim)-Tupeln."""
    return any(boxes_overlap(pos, dim, pp, pd, eps) for pp, pd in placed_boxes)


def is_supported(pos, dim, placed_boxes, eps=EPS):
    """Prüft, ob eine Box an gegebener Position vollständig unterstützt ist -
    entweder sie steht auf dem Containerboden (z≈0), oder ihre gesamte
    Grundfläche liegt lückenlos auf den Oberseiten bereits platzierter Boxen
    auf. Auf Nutzerhinweis ergänzt ("Packstücke scheinen zu schweben, obwohl
    sie in den Zwischenraum darunter passen würden") - vorher wurde nur auf
    Überlappung und Containergrenzen geprüft, nie auf physikalisch
    plausible Stützung. Eine Box konnte dadurch an einem Extrempunkt
    (typischerweise die Oberseite einer KLEINEREN bereits platzierten Box)
    platziert werden, obwohl ihre Grundfläche größer war als die stützende
    Fläche darunter - der überstehende Teil hing dann buchstäblich in der
    Luft.

    Exakte Flächenabdeckung per Koordinatenkompression (kein Stichproben-
    Raster) - jede stützende Box, deren Oberseite exakt auf Höhe der
    Unterseite der neuen Box liegt, trägt ihre (x,y)-Grundfläche als
    Stützrechteck bei; die Vereinigung dieser Stützrechtecke muss die
    gesamte Grundfläche der neuen Box lückenlos abdecken."""
    x0, y0, z0 = pos
    dx, dy, _dz = dim
    if z0 <= eps:
        return True  # steht auf dem Boden

    support_rects = []
    for ppos, pdim in placed_boxes:
        px, py, pz = ppos
        pdx, pdy, pdz = pdim
        if abs((pz + pdz) - z0) > eps:
            continue  # Oberseite dieser Box liegt nicht auf der noetigen Hoehe
        rx0, ry0 = max(px, x0), max(py, y0)
        rx1, ry1 = min(px + pdx, x0 + dx), min(py + pdy, y0 + dy)
        if rx1 - rx0 > eps and ry1 - ry0 > eps:
            support_rects.append((rx0, ry0, rx1, ry1))

    if not support_rects:
        return False

    xs = sorted({x0, x0 + dx} | {r[0] for r in support_rects} | {r[2] for r in support_rects})
    ys = sorted({y0, y0 + dy} | {r[1] for r in support_rects} | {r[3] for r in support_rects})

    for i in range(len(xs) - 1):
        cx0, cx1 = xs[i], xs[i + 1]
        if cx1 - cx0 <= eps or cx0 < x0 - eps or cx1 > x0 + dx + eps:
            continue
        for j in range(len(ys) - 1):
            cy0, cy1 = ys[j], ys[j + 1]
            if cy1 - cy0 <= eps or cy0 < y0 - eps or cy1 > y0 + dy + eps:
                continue
            cell_covered = any(
                r[0] <= cx0 + eps and r[2] >= cx1 - eps and r[1] <= cy0 + eps and r[3] >= cy1 - eps
                for r in support_rects
            )
            if not cell_covered:
                return False
    return True


def contact_area(pos, dim, placed_boxes, container_dim, eps=EPS):
    """Wie viel Fläche einer Box (Boden, Rückwand, linke Wand) tatsächlich
    an etwas Festem anliegt - Containerwänden ODER anderen Boxen. Aus der
    Container-Loading-Literatur (Crainic, Perboli, Tadei 2008, "Extreme
    Point-Based Heuristics for Three-Dimensional Bin Packing"): eine Box,
    die an mehreren Seiten satt anliegt, sitzt kompakter als eine, die nur
    zufällig eine tiefe Koordinate hat, aber eigentlich frei zwischen
    Lücken schwebt (positionsbezogen statt geometrisch).

    HINWEIS: auf Nutzernachfrage implementiert und in vier Varianten gegen
    DBL getestet (siehe README) - keine schlägt DBL robust, deshalb NICHT
    in die Konstruktionsheuristiken integriert. Als eigenständige,
    getestete Funktion belassen (Reproduzierbarkeit der Untersuchung,
    falls jemand später weiter experimentieren möchte)."""
    x0, y0, z0 = pos
    dx, dy, dz = dim
    total = 0.0

    # Boden-Kontakt: Containerboden (z=0) ODER Oberseiten anderer Boxen bei z0
    if z0 <= eps:
        total += dx * dy
    else:
        for ppos, pdim in placed_boxes:
            px, py, pz = ppos
            pdx, pdy, pdz = pdim
            if abs((pz + pdz) - z0) > eps:
                continue
            ox = max(0.0, min(px + pdx, x0 + dx) - max(px, x0))
            oy = max(0.0, min(py + pdy, y0 + dy) - max(py, y0))
            total += ox * oy

    # Rueckwand-Kontakt: Containerwand (y=0) ODER Vorderseiten anderer Boxen bei y0
    if y0 <= eps:
        total += dx * dz
    else:
        for ppos, pdim in placed_boxes:
            px, py, pz = ppos
            pdx, pdy, pdz = pdim
            if abs((py + pdy) - y0) > eps:
                continue
            ox = max(0.0, min(px + pdx, x0 + dx) - max(px, x0))
            oz = max(0.0, min(pz + pdz, z0 + dz) - max(pz, z0))
            total += ox * oz

    # Linke-Wand-Kontakt: Containerwand (x=0) ODER rechte Seiten anderer Boxen bei x0
    if x0 <= eps:
        total += dy * dz
    else:
        for ppos, pdim in placed_boxes:
            px, py, pz = ppos
            pdx, pdy, pdz = pdim
            if abs((px + pdx) - x0) > eps:
                continue
            oy = max(0.0, min(py + pdy, y0 + dy) - max(py, y0))
            oz = max(0.0, min(pz + pdz, z0 + dz) - max(pz, z0))
            total += oy * oz

    return total
