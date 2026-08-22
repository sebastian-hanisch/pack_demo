"""
Bewertung einer Packlösung: Raumnutzung, unplatzierte Boxen, sowie die
Umrechnung in eine geschäftliche Kennzahl (vermiedene Zusatzcontainer/-kosten)
- macht den Business-Case greifbar statt nur eine abstrakte Prozentzahl zu
zeigen (analog zur Fahrzeit/Kosten-Umrechnung in der Touren-Demo).
"""

from pack_constants import DEFAULT_COST_PER_CONTAINER


def box_volume(dim):
    return dim[0] * dim[1] * dim[2]


def evaluate_packing(placements, boxes, container_dim, unplaced):
    """Fasst eine Packlösung zusammen: genutztes/gesamtes Volumen, Nutzungsgrad
    in %, sowie Volumen und Anzahl der nicht untergebrachten Boxen."""
    container_volume = box_volume(container_dim)
    placed_volume = sum(box_volume(p["dim"]) for p in placements)
    unplaced_volume = sum(box_volume(boxes[i]) for i in unplaced)
    utilization_pct = (placed_volume / container_volume * 100) if container_volume > 0 else 0.0
    return {
        "container_volume": container_volume,
        "placed_volume": placed_volume,
        "unplaced_volume": unplaced_volume,
        "utilization_pct": utilization_pct,
        "n_placed": len(placements),
        "n_unplaced": len(unplaced),
    }


def estimate_extra_containers(unplaced_volume, container_volume):
    """Grobe Schätzung, wie viele zusätzliche Container/Paletten für das
    nicht untergebrachte Volumen nötig wären (rein volumenbasiert, ignoriert
    Formeffekte - für die Kostenabschätzung in der Demo ausreichend genau)."""
    if container_volume <= 0 or unplaced_volume <= 0:
        return 0
    import math
    return math.ceil(unplaced_volume / container_volume)


def volume_to_business(unplaced_volume, container_volume, cost_per_container=DEFAULT_COST_PER_CONTAINER):
    """Rechnet nicht untergebrachtes Volumen in eine geschätzte Anzahl
    zusätzlich benötigter Container und die damit verbundenen Zusatzkosten
    um."""
    extra_containers = estimate_extra_containers(unplaced_volume, container_volume)
    extra_cost = extra_containers * cost_per_container
    return extra_containers, extra_cost


def classify_comparison(candidates, tie_threshold_pct=0.05):
    """Bestimmt aus den Endergebnissen mehrerer Heuristiken (je ein Dict mit
    mindestens "label" und "final_utilization_pct"), ob es einen eindeutigen
    Sieger gibt oder ob (alle, oder nur die besten zwei) praktisch gleichauf
    liegen. Als eigene reine Funktion ausgelagert, damit sich diese Logik ohne
    die volle Streamlit-App testen lässt.

    Bug gefunden und behoben: eine erste Fassung prüfte nur, ob ALLE
    Kandidaten innerhalb der Toleranz liegen (all_tied) - max()/min() lieferten
    bei einem Gleichstand zwischen genau den besten ZWEI von drei Methoden
    weiterhin willkürlich den ERSTEN der beiden gleichauf liegenden Kandidaten
    als "Sieger", solange die dritte Methode klar genug abwich, um all_tied
    auf False zu halten. Jetzt wird zusätzlich der Abstand zwischen dem besten
    und dem zweitbesten Kandidaten unabhängig vom Rest geprüft."""
    ranked = sorted(candidates, key=lambda s: s["final_utilization_pct"], reverse=True)
    utilizations = [s["final_utilization_pct"] for s in candidates]
    all_tied = (max(utilizations) - min(utilizations)) < tie_threshold_pct
    top_two_tied = len(ranked) >= 2 and (ranked[0]["final_utilization_pct"] - ranked[1]["final_utilization_pct"]) < tie_threshold_pct
    return {
        "ranked": ranked,
        "best": ranked[0],
        "worst": ranked[-1],
        "all_tied": all_tied,
        "top_two_tied": top_two_tied,
        "is_tied": all_tied or top_two_tied,
    }
