# 📦 3D-Packungsoptimierung (Container-/Palettenstauung)

Interaktive Demo zur dreidimensionalen Beladung eines Containers oder einer Palette.

**[→ Demo live ausprobieren](https://sebastianhanisch-pack-demo.streamlit.app/)**

## Worum geht's?

Welche Boxen passen wie in einen Container, um möglichst wenig Leerraum zu verschwenden — und wie viele zusätzliche Container oder Paletten spart eine bessere Packung? Ein 3D-Bin-Packing-Problem, hier interaktiv mit eigenen Kistengrößen und Container-/Palettenmaßen.

## Methodik

- Drei selbst implementierte Heuristiken im Vergleich: eine **schichtenweise** Vorgehensweise (wie man intuitiv von Hand packen würde, ohne Rotation), eine fortgeschrittene **Extreme-Point**-Konstruktion und eine **Beam-Search**-Variante
- 3D-Visualisierung der resultierenden Packung, Vergleichstabelle der drei Verfahren
- Button-gesteuerte Verbesserungssuche (`rescue_unplaced_via_swap`) für nicht platzierte Boxen
- Animation, PDF-Export, Permalink für eigene Beispielszenarien

Bewusst schlanker gehalten als die Tourenplanung-Demo (drei Heuristiken statt fünf, kein externer Solver), aber mit denselben Komfortfunktionen für gutes Verständnis.

## Lokal ausführen

```bash
pip install -r requirements-dev.txt
streamlit run app.py
```

Tests: `pytest tests/ -v`

---

Teil des [Operations-Research-Demo-Portfolios](https://sebastianhanisch.net/demos.html) von [Sebastian Hanisch](https://sebastianhanisch.net) — Operations Research und Machine Learning. Interesse an einer maßgeschneiderten Lösung? [Kontakt aufnehmen](https://sebastianhanisch.net/kontakt.html).
