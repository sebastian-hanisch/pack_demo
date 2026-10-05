"""
Orakel-Tests (unabhängiger Rechenweg) für die Packgeometrie und die
Heuristiken: ein Voxel-Prüfer (Belegungsraster in Zehntel-Einheiten) statt der
AABB-/Koordinatenkompressions-Logik der Demo, plus Vollaufzählung auf
Mini-Instanzen. Klein und schnell gehalten (< 10 s).
"""

import math
import os
import random
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pack_evaluation import box_volume, estimate_extra_containers  # noqa: E402
from pack_geometry import any_overlap, box_rotations, contact_area, fits_in_container, is_supported  # noqa: E402
from pack_heuristics import (  # noqa: E402
    extreme_point_packing,
    layer_based_packing,
    monobeam_packing,
    rescue_unplaced_via_swap,
)

SC = 10  # Zehntel-Einheiten -> ganzzahliges Raster


def _vox(pos, dim):
    return tuple(round(c * SC) for c in pos) + tuple(round(c * SC) for c in dim)


def _occupancy(placed, shape):
    g = np.zeros(shape, dtype=np.int16)
    for pos, dim in placed:
        x, y, z, l, w, h = _vox(pos, dim)
        g[x:x + l, y:y + w, z:z + h] += 1
    return g


def voxel_check(placements, boxes, cdim, unplaced):
    """Unabhängiger Zulässigkeitsprüfer. Gibt einen Fehlertext oder None zurück."""
    shape = tuple(round(c * SC) for c in cdim)
    idx = [p["box_idx"] for p in placements]
    if len(idx) != len(set(idx)):
        return "doppelt platziert"
    if set(idx) | set(unplaced) != set(range(len(boxes))) or (set(idx) & set(unplaced)):
        return "Boxen fehlen oder doppelt"
    g = np.zeros(shape, dtype=np.int16)
    for p in placements:
        if sorted(round(c * SC) for c in p["dim"]) != sorted(round(c * SC) for c in boxes[p["box_idx"]]):
            return "keine Rotation der Originalbox"
        x, y, z, l, w, h = _vox(p["pos"], p["dim"])
        if min(x, y, z) < 0 or x + l > shape[0] or y + w > shape[1] or z + h > shape[2]:
            return "außerhalb des Containers"
        g[x:x + l, y:y + w, z:z + h] += 1
    if g.max(initial=0) > 1:
        return "Überlappung"
    for p in placements:
        x, y, z, l, w, h = _vox(p["pos"], p["dim"])
        if z > 0 and not (g[x:x + l, y:y + w, z - 1] > 0).all():
            return "schwebt"
    return None


def test_geometry_matches_voxel_oracle():
    rng = random.Random(7)
    for _ in range(300):
        cd = tuple(float(rng.randint(3, 8)) for _ in range(3))
        shape = tuple(round(c * SC) for c in cd)
        placed = []
        for _ in range(rng.randint(0, 5)):
            d = tuple(rng.randint(1, 4) / 2 for _ in range(3))
            pos = tuple(rng.randint(0, max(0, int(cd[i] * 2 - d[i] * 2))) / 2 for i in range(3))
            if all(pos[i] + d[i] <= cd[i] for i in range(3)) and not _occupancy(placed, shape)[
                _vox(pos, d)[0]:_vox(pos, d)[0] + _vox(pos, d)[3],
                _vox(pos, d)[1]:_vox(pos, d)[1] + _vox(pos, d)[4],
                _vox(pos, d)[2]:_vox(pos, d)[2] + _vox(pos, d)[5],
            ].any():
                placed.append((pos, d))
        d = tuple(rng.randint(1, 4) / 2 for _ in range(3))
        pos = tuple(rng.randint(-1, int(cd[i] * 2) + 1) / 2 for i in range(3))
        inside = all(pos[i] >= 0 and pos[i] + d[i] <= cd[i] for i in range(3))
        assert fits_in_container(pos, d, cd) == inside
        if not inside:
            continue
        occ = _occupancy(placed, shape)
        x, y, z, l, w, h = _vox(pos, d)
        overlaps = bool(occ[x:x + l, y:y + w, z:z + h].any())
        assert any_overlap(pos, d, placed) == overlaps
        if overlaps:
            continue
        supported = z == 0 or bool((occ[x:x + l, y:y + w, z - 1] > 0).all())
        assert is_supported(pos, d, placed) == supported
        contact = l * w if z == 0 else int((occ[x:x + l, y:y + w, z - 1] > 0).sum())
        contact += l * h if y == 0 else int((occ[x:x + l, y - 1, z:z + h] > 0).sum())
        contact += w * h if x == 0 else int((occ[x - 1, y:y + w, z:z + h] > 0).sum())
        assert contact_area(pos, d, placed, cd) * SC * SC == pytest.approx(contact)


HEURISTICS = [layer_based_packing, extreme_point_packing, monobeam_packing]


def test_heuristics_feasible_by_voxel_oracle():
    rng = random.Random(11)
    for _ in range(40):
        n = rng.randint(1, 14)
        cd = (rng.choice([4.0, 6.0, 8.0]), rng.choice([3.0, 5.0, 7.0]), rng.choice([3.0, 5.0]))
        boxes = [tuple(round(rng.uniform(0.5, 3.0), 1) for _ in range(3)) for _ in range(n)]
        for f in HEURISTICS:
            pl, un = f(boxes, cd)
            assert voxel_check(pl, boxes, cd, un) is None, f.__name__
        pl, un = extreme_point_packing(boxes, cd)
        plr, unr, n_res = rescue_unplaced_via_swap(boxes, cd, pl, un)
        assert voxel_check(plr, boxes, cd, unr) is None
        assert len(plr) == len(pl) + n_res


def test_rescue_does_not_leave_boxes_floating():
    """Regression (Orakel-Fund): P entfernen ließ eine auf P stehende Box
    schweben; die Rettung hat das nicht geprüft."""
    boxes = [(3.0, 2.0, 3.0), (4.0, 4.0, 2.0), (3.0, 2.0, 4.0), (1.0, 2.0, 4.0), (2.0, 4.0, 3.0)]
    cd = (6.0, 5.0, 4.0)
    pl, un = extreme_point_packing(boxes, cd)
    plr, unr, _n = rescue_unplaced_via_swap(boxes, cd, pl, un)
    assert voxel_check(plr, boxes, cd, unr) is None


def _brute_opt(boxes, cd):
    """Größtes platzierbares Volumen: Teilmenge, Rotation, ganzzahlige Position,
    Stützung im Endzustand."""
    cdi = tuple(int(c) for c in cd)
    options = []
    for b in boxes:
        o = []
        for rd in box_rotations(*b):
            l, w, h = (int(c) for c in rd)
            for x in range(cdi[0] - l + 1):
                for y in range(cdi[1] - w + 1):
                    for z in range(cdi[2] - h + 1):
                        o.append((x, y, z, l, w, h))
        options.append(o)
    best = 0

    def go(i, chosen, grid, vol):
        nonlocal best
        if vol + sum(math.prod(b) for b in boxes[i:]) <= best:
            return
        if i == len(boxes):
            for (x, y, z, l, w, h) in chosen:
                if z > 0 and not grid[x:x + l, y:y + w, z - 1].all():
                    return
            best = vol
            return
        go(i + 1, chosen, grid, vol)
        for (x, y, z, l, w, h) in options[i]:
            sl = (slice(x, x + l), slice(y, y + w), slice(z, z + h))
            if grid[sl].any():
                continue
            grid[sl] = True
            go(i + 1, chosen + [(x, y, z, l, w, h)], grid, vol + l * w * h)
            grid[sl] = False

    go(0, [], np.zeros(cdi, dtype=bool), 0)
    return best


def test_heuristics_never_exceed_brute_force_optimum():
    rng = random.Random(5)
    for _ in range(25):
        cd = rng.choice([(3.0, 3.0, 3.0), (4.0, 3.0, 3.0)])
        boxes = [tuple(float(rng.randint(1, 3)) for _ in range(3)) for _ in range(rng.randint(1, 4))]
        opt = _brute_opt(boxes, cd)
        for f in HEURISTICS:
            pl, _ = f(boxes, cd)
            assert sum(box_volume(p["dim"]) for p in pl) <= opt + 1e-9


def test_monobeam_width_1_equals_extreme_point_and_is_monotone():
    rng = random.Random(3)
    for _ in range(20):
        cd = (6.0, 5.0, 5.0)
        boxes = [tuple(round(rng.uniform(0.5, 3.0), 1) for _ in range(3)) for _ in range(rng.randint(3, 14))]
        ep, _ = extreme_point_packing(boxes, cd)
        m1, _ = monobeam_packing(boxes, cd, beam_width=1)
        assert [(p["pos"], p["dim"], p["box_idx"]) for p in ep] == [(p["pos"], p["dim"], p["box_idx"]) for p in m1]
        prev = -1.0
        for bw in (1, 2, 4, 8):
            pl, _ = monobeam_packing(boxes, cd, beam_width=bw)
            v = sum(box_volume(p["dim"]) for p in pl)
            assert v >= prev - 1e-12
            prev = v


def test_extra_containers_exact_multiple_not_rounded_up():
    """Regression (Orakel-Fund): gedreht multiplizierte Container-große Boxen
    ergaben 3,0000000000000004 und damit 4 statt 3 Zusatzcontainer."""
    container = (18.7, 28.8, 13.6)
    rotated = (13.6, 18.7, 28.8)
    unplaced = 3 * box_volume(rotated)
    assert estimate_extra_containers(unplaced, box_volume(container)) == 3
    assert estimate_extra_containers(box_volume(container) * 1.5, box_volume(container)) == 2
    assert estimate_extra_containers(0.0, box_volume(container)) == 0
