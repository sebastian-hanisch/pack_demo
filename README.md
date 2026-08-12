# 3D-Packungsoptimierung (Container-/Palettenstauung) – Streamlit-Demo

Interaktive Demo zur dreidimensionalen Beladung eines Containers oder einer Palette.
Zwei selbst implementierte Heuristiken werden direkt verglichen. Bewusst schlanker
gehalten als die Tourenplanung-Demo (zwei Heuristiken statt fünf, kein externer Solver),
aber mit denselben Komfortfunktionen für gutes Verständnis. Teil des Demo-Portfolios für
die Website "Sebastian Hanisch – Operations Research und Machine Learning".

## Dateistruktur

Von Anfang an modular gebaut (Lehre aus der Tourenplanung-Demo, die erst nachträglich
aufgeteilt wurde):

| Datei | Inhalt |
|---|---|
| `app.py` | Streamlit-Hauptablauf (Sidebar, Tabs, Vergleichstab) |
| `pack_constants.py` | Konstanten (Standardwerte, Farben) |
| `pack_geometry.py` | Rotationen, Überlappungs-/Bounds-Prüfung (AABB) |
| `pack_heuristics.py` | Schichten-basierte und Extreme-Point-Heuristik |
| `pack_evaluation.py` | Raumnutzung, geschäftliche Kennzahl (Zusatzcontainer-Kosten) |
| `pack_visualization.py` | 3D-Darstellung (Plotly Mesh3d) |
| `pack_pdf_export.py` | PDF-Packplan-Erzeugung |
| `pack_feedback.py` | Feedback-Logging |
| `pack_ui_panel.py` | Wiederverwendbares UI-Panel je Heuristik |
| `pack_presets.py` | Beispielszenarien, Permalink-Logik (`SETTING_SPECS`) |

## Funktionsumfang

- **Drei eigene Packheuristiken:**
  - *Schichten-basiert:* Boxen werden nach Höhe sortiert und in Reihen/Schichten
    angeordnet - wie man intuitiv von Hand packen würde. Einfach und schnell,
    verschwendet aber Raum bei unterschiedlich hohen Boxen innerhalb einer Schicht.
    Dient als feste Baseline für den Vergleich.
  - *Extreme-Point* (Crainic, Perboli, Tadei 2008): verfolgt eine Liste konkurrierender
    Eckpunkte, probiert dort alle 6 Rotationen jeder Box durch und bevorzugt die
    unterste/hinterste/linkeste zulässige Position. Füllt Lücken zwischen
    unterschiedlich großen Boxen gezielter als die Baseline.
  - *Beam Search:* verfolgt mehrere Teil-Packungen parallel statt nur einer - pro Box
    werden mehrere Kandidatenpositionen erzeugt, die insgesamt besten Teilzustände
    bleiben im Rennen. Im Schnitt etwas besser als Extreme-Point (siehe Benchmark
    unten), aber nicht durchgehend und mit spürbar höherer Rechenzeit.
- **3D-Visualisierung:** Container als Drahtgitter, platzierte Boxen als massive Quader
  (Plotly `Mesh3d`), pro Box eigenfarbig mit Hover-Info.
- **Animation:** Schritt-Regler + Auto-Play zeigt, wie die Heuristik den Container Box
  für Box befüllt - dasselbe bewährte Muster wie die LKW-Animation in der
  Tourenplanung-Demo (kein natives Plotly-Play/Pause, da das Platzieren ohnehin ein
  diskreter Vorgang ist, keine Bewegungs-Interpolation nötig).
- **Geschäftliche Kennzahl:** Passen nicht alle Boxen in einen Container, wird geschätzt,
  wie viele zusätzliche Container (volumenbasiert) nötig wären und was das kostet
  (einstellbarer €/Container-Regler) - macht den Heuristik-Unterschied konkret.
- **PDF-Packplan:** Download-Button pro Tab, Zusammenfassung + Positionsliste je Box.
- **Drei Ein-Klick-Beispielszenarien:** Gleichmäßige Kartons, Gemischte Ladung, Viele
  kleine Pakete.
- **Permalink:** Adresszeile spiegelt die aktuelle Konfiguration; robust gegen Werte
  außerhalb der Slider-Grenzen (`SETTING_SPECS`-Muster von Anfang an übernommen, siehe
  unten).
- **Feedback-Mechanismus:** 👍/👎 am Seitenende, loggt in `feedback_log.csv`. Gleiche
  Einschränkung wie in der Tourenplanung-Demo: Streamlit Community Cloud hat kein
  dauerhaft persistentes Dateisystem.

## Aus der Tourenplanung-Demo übernommene Lehren

Diese Demo wurde bewusst so gebaut, dass mehrere dort erst nachträglich gefundene
Probleme von Anfang an vermieden werden:

- **Modulare Struktur von Beginn an** statt einer wachsenden Einzeldatei.
- **`SETTING_SPECS`-Muster für Permalink-Wertebereiche** von Anfang an: Slider-Grenzen
  stehen an einer einzigen Stelle (`pack_presets.py`), aus der sowohl die Slider selbst
  als auch die Permalink-Begrenzung lesen. Verifiziert: Permalinks mit Werten weit
  außerhalb des Bereichs (`?n_boxes=9999`, `?cost=nan`, `?seed=-42`, ungültiger Text)
  stürzen die App nicht ab (`test_permalink_handles_bad_values_without_crash`).
- **Tests von Anfang an**, nicht nachgerüstet.

## Ein Bug beim Bauen gefunden und behoben

Die Dreiecksliste für die 3D-Box-Darstellung (`go.Mesh3d`, 12 Dreiecke für die 6
Seitenflächen eines Quaders) wurde beim ersten Schreiben falsch zusammengestellt: eine
Fläche blieb unbedeckt (sichtbares Loch im gerenderten Quader), eine andere hatte ein
überzähliges/falsches Dreieck. Kein Rendering-Tool mit Bildschirmausgabe verfügbar
(Chrome/Kaleido fehlt in dieser Umgebung) - stattdessen geometrisch verifiziert: für
jede der 6 Flächen eines Einheitswürfels wurde geprüft, dass genau 2 Dreiecke sie
lückenlos und ohne Überlappung abdecken (Flächeninhalt exakt 1.0). Der Fehler wurde so
gefunden, korrigiert und erneut verifiziert, bevor die App das erste Mal lief. Dauerhaft
abgesichert durch `test_box_mesh_triangles_cover_all_six_faces_exactly`.

## Benchmark: alle drei Heuristiken im Vergleich

25 zufällige Boxen (10-50 cm Kantenlänge) in einem 120×80×100-cm-Container, über 5
Testinstanzen, ohne Nachbearbeitung (reine Konstruktionsqualität):

| Instanz | Schichten-basiert | Extreme-Point | Beam Search |
|---|---|---|---|
| seed=1 | 35,2 % | 59,3 % | 71,0 % |
| seed=2 | 45,4 % | 78,0 % | 79,3 % |
| seed=3 | 46,1 % | 77,5 % | 78,1 % |
| seed=4 | 56,8 % | 77,2 % | 77,3 % |
| seed=5 | 24,6 % | 75,9 % | 79,6 % |

Der Unterschied Schichten-basiert vs. Extreme-Point ist deutlicher als bei den
Heuristiken der Tourenplanung-Demo, weil dort im Anschluss noch eine lokale Suche
(2-opt + Or-opt) läuft, die Konstruktionsschwächen teilweise ausgleicht - hier gibt es
keine Nachbearbeitung. Das macht den Rohunterschied zwischen einer naiven und einer
durchdachten Heuristik besonders anschaulich.

## Beam Search: eine ehrliche Abwägung, kein Selbstläufer

Anders als bei der ersten Version dieser Demo (nur Schichten-basiert + Extreme-Point)
wurde Beam Search nachträglich ergänzt, auf ausdrücklichen Wunsch - und wie bei der
Tourenplanung-Demo (dort wurde eine Beam-Search-Variante nach Benchmark wieder
verworfen) erst nach Korrektheits-, Qualitäts- und Performance-Prüfung übernommen,
nicht blind hinzugefügt.

**Ergebnis über 10 Testinstanzen (15-35 Boxen):** Beam Search gewinnt in 6 Fällen,
verliert in 2 (um jeweils <1 Prozentpunkt), 2 Gleichstände. Im Schnitt **+0,9
Prozentpunkte** Raumnutzung gegenüber Extreme-Point, bei praktisch identischer
Rechenzeit (<0,15s) für diese Instanzgrößen.

**Aber:** Im Worst-Case-Test (60 Boxen, großer 300×300×300-cm-Container, viele Boxen
passen leicht hinein) liefert Beam Search dreimal **exakt dieselbe** Raumnutzung wie
Extreme-Point - keine Verbesserung -, braucht dafür aber 6-7x länger (0,98-1,01s
gegenüber 0,15s bei Extreme-Point). Plausible Erklärung: Bei einem großen, dünn
besiedelten Container gibt es an jedem Schritt eine eindeutig beste Position, die beide
Verfahren gleichermaßen finden - die zusätzlichen Kandidaten von Beam Search bringen
dann keinen Mehrwert, kosten aber trotzdem Rechenzeit.

Verwendete Parameter (`pack_constants.py`): `BEAM_WIDTH=6`,
`BEAM_CANDIDATES_PER_STATE=4` - ein bewusster Kompromiss (getestet auch mit
Breite 4 und 8: weniger Breite = schneller, aber auch weniger Qualitätsgewinn; mehr
Breite = minimal besser, aber im Worst Case langsamer). Wird automatisch bei jeder
UI-Interaktion neu berechnet (nicht Button-gesteuert wie OR-Tools in der
Tourenplanung-Demo), Worst-Case-Zeit bleibt mit ~1s im vertretbaren Rahmen - abgesichert
durch `test_beam_search_worst_case_completes_within_budget`.

## 1. Lokal ausführen

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

## 2. Tests ausführen

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

50 Tests, laufen automatisch bei jedem Push/PR über GitHub Actions
(`.github/workflows/tests.yml`).

## 3. Kostenlos online stellen (Streamlit Community Cloud)

1. Diesen Ordner in ein GitHub-Repository hochladen.
2. Auf [share.streamlit.io](https://share.streamlit.io) anmelden.
3. "New app" → Repository und `app.py` als Hauptdatei → Deploy.

## 4. Einbindung auf der Ionos-Website

Wie bei der Tourenplanung-Demo: Button/Link auf der Demo-Unterseite, der die
Streamlit-App-URL in einem neuen Tab öffnet.

```html
<a href="https://<deine-app>.streamlit.app" target="_blank" rel="noopener">
  Demo starten →
</a>
```

## 5. Bewusst nicht enthalten (Scope-Entscheidung)

- Kein OR-Tools-/Solver-Vergleich (OR-Tools hat zwar CP-SAT-basierte Packing-Recipes,
  aber das wäre nochmal ein eigenes Stück Arbeit für eine bewusst schlank gehaltene Demo)
- Keine Gewichtsverteilung, Stapelbarkeit oder "diese Seite oben"-Kennzeichnung
- Kein Packen über mehrere Container gleichzeitig (nur ein Container, mit Hinweis auf
  fehlenden Restplatz)
- Keine CO₂-Kennzahl (anders als die Tourenplanung-Demo) - hätte hier keine
  offensichtliche, nicht-künstliche Entsprechung

## 6. Anpassungsideen für später

- Gewichtsbasierte Nebenbedingung (schwere Boxen unten, Tragfähigkeitsgrenzen)
- "Diese Seite oben"-Kennzeichnung (Rotation einschränken)
- Mehrere Container/Paletten gleichzeitig optimieren
- Test an einem echten Mobilgerät (3D-Ansicht per Touch drehen - noch nicht geprüft)
