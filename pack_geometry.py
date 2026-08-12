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
