# 3D-Packungsoptimierung (Container-/Palettenstauung) – Streamlit-Demo

Interaktive Demo zur dreidimensionalen Beladung eines Containers oder einer Palette.
Drei selbst implementierte Heuristiken werden direkt verglichen. Bewusst schlanker
gehalten als die Tourenplanung-Demo (drei Heuristiken statt fünf, kein externer Solver),
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
- **Vier Ein-Klick-Beispielszenarien:** Gleichmäßige Kartons, Gemischte Ladung, Viele
  kleine Pakete, sowie "Enges Puzzle" - systematisch gesucht, um zu zeigen, wo Beam
  Search deutlich (nicht nur knapp) vor beiden anderen Heuristiken liegt (siehe
  eigener Abschnitt unten).
- **Verbesserungssuche für unplatzierte Boxen** (Button-gesteuert, je Heuristik-Tab):
  sucht gezielt nach Umplatzierungen, die zusätzliche Boxen unterbringen - eigener
  Abschnitt unten, auf Wunsch ergänzt.
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

*(Hinweis: Dieser Abschnitt beschreibt die ursprüngliche `beam_search_packing`-
Implementierung. Sie wurde später durch `monobeam_packing` ersetzt - siehe den Abschnitt
"Monobeam" weiter unten für den Grund und den vollständigen Verlauf. Als historische
Dokumentation belassen, die Zahlen hier gelten für die alte Implementierung.)*

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
Breite = minimal besser, aber im Worst Case langsamer).

### Ein Szenario, in dem die alte Beam Search deutlich vorne lag

Auf Wunsch systematisch gesucht: über 4 Boxanzahlen (25/35/45), 4 Größenbereiche
(8-70 cm) und je bis zu 15 Seeds (~180 Konfigurationen), gefiltert auf "eng, aber nicht
hoffnungslos" (Gesamtvolumen der Boxen 90-250% des Containervolumens). Bestes Ergebnis
mit der alten Implementierung: 25 Boxen, 15-55 cm Kantenlänge, Seed 3 - Schichten-
basiert 42,0 %, Extreme-Point 68,8 %, Beam Search 82,7 % (+13,9 Prozentpunkte). Dieser
konkrete Seed ist mit `monobeam_packing` **nicht reproduzierbar** (siehe unten) - der
Preset wurde entsprechend auf ein neues, für monobeam repräsentatives Szenario
umgestellt.

## Monobeam: von "nicht durchgehend besser" zu nachweislich monoton

Eine gezielte Nachfrage deckte auf: `beam_search_packing` hatte - genau wie die zuerst
verworfene Beam-Search-Variante der Seefracht-Demo - **keine Monotonie-Garantie**. Eine
größere Beam-Breite konnte die Raumnutzung tatsächlich verschlechtern, nicht nur in
Ausnahmefällen: systematisch über 14 Testinstanzen (Breiten 1, 2, 4, 6, 8, 12, 16)
geprüft, zeigten **11 von 14** eine sinkende statt steigende Raumnutzung bei
zunehmender Breite.

### Die Lösung: dieselbe monobeam-Adaption wie in der Seefracht-Demo

`monobeam_packing` überträgt den sequenziellen Slot-Mechanismus aus
`monobeam_construction` (Seefracht-Demo, nach Lemons, Linares López, Holte & Ruml,
"Beam Search: Faster and Monotonic", ICAPS 2022) auf die 3D-Packungskonstruktion: der
Beam wird als geordnete Folge nummerierter Slots behandelt, jeder Slot expandiert und
beansprucht **sofort** das beste verbliebene Element aus einem gemeinsamen
Kandidatenpool, bevor der nächste Slot überhaupt angefasst wird.

**Zwei eigene Implementierungsfehler unterwegs gefunden - keine Kleinigkeiten:**

1. **Getrennte statt verschachtelte Erzeugung/Zuweisung.** Die erste Fassung erzeugte
   die Kandidaten aller Slots in einer Schleife und verteilte sie erst danach in einer
   zweiten - das verletzt die Kernvoraussetzung des Verfahrens (Slot c darf nur von
   Slots 1..c des VORHERIGEN Beams abhängen). Ergebnis: **12 von 14 Verletzungen -
   sogar mehr als das Original!** Behoben durch Verschmelzen zu einer einzigen
   Schleife (Erzeugung und sofortige Beanspruchung pro Slot), exakt wie im
   funktionierenden `monobeam_construction` der Seefracht-Demo. Danach: 2 von 14.
2. **Bewertung nach Boxenzahl statt Volumen.** Die verbliebenen 2 Verletzungen waren
   winzig (~0,1 Prozentpunkt) - nachgeprüft: die Boxen-*Anzahl* war in beiden Fällen
   bereits perfekt monoton, nur die *Raumnutzung* (die tatsächlich angezeigte Kennzahl)
   zeigte die Abweichung, weil "mehr Boxen" nicht dasselbe ist wie "mehr Volumen"
   (viele kleine vs. wenige große Boxen). Auf direkte Volumen-Bewertung umgestellt -
   seitdem exakt **0 von 30 Verletzungen** über eine breite Stichprobe (variable
   Boxenzahl 15-40, Größenbereiche 8-70 cm).

### Ein ehrlicher Kompromiss: monoton heißt nicht automatisch besser

Über 30 Testinstanzen ist monobeam im Schnitt **+0,25 Prozentpunkte besser** als die
alte, nicht-monotone Implementierung und gewinnt häufiger, als es verliert (15 von 30
vs. 9 von 30, 6 Gleichstände) - aber im **Einzelfall bis zu 9,1 Prozentpunkte
schlechter**. Die Garantie "breiter wird nie schlechter" erkauft sich eine stärker
eingeschränkte Suche (Slot 1 ist bei jeder Breite identisch zur Breite-1-Lösung) - die
alte, unprinzipielle Version konnte gelegentlich bessere, aber unvorhersehbare Zufalls-
funde machen, die monobeam durch seine Disziplin nicht macht. Konkret beim alten "Enges
Puzzle"-Szenario (Seed 3): monobeam erreicht dort selbst bei Breite 50 nur ~77 % statt
der mit der alten Implementierung erzielten 82,7 %.

**Trotzdem als neuer Standard übernommen** (auf ausdrücklichen Wunsch: im Schnitt
besser und vorhersagbar gut wiegt schwerer als ein gelegentlich höherer, aber
unvorhersehbarer Einzelwert) - `app.py` nutzt jetzt durchgehend `monobeam_packing`
statt `beam_search_packing`. Die alte Funktion wurde zunächst absichtlich als
vollständig getestete Vergleichs-Baseline im Code belassen, ist inzwischen aber - nach
einer Konsistenzprüfung, die auffiel, dass die Testabdeckung dafür nicht mehr aktuell
war - ganz entfernt worden. Ihr Verhalten bleibt hier und in den Abschnitten oben
vollständig dokumentiert; die Implementierung selbst ist über die Git-Historie
abrufbar.

**Neues "Enges Puzzle"-Szenario, für monobeam gefunden:** dieselbe systematische Suche
wie zuvor (jetzt gegen monobeam statt die alte Implementierung), zusätzlich gefiltert
auf Fälle, in denen die Breite selbst sichtbar etwas bewirkt (nicht nur bei Breite 1
bereits ausgereizt). Bestes Ergebnis: 25 Boxen, 8-70 cm, Seed 11 -

| Breite | Raumnutzung |
|---|---|
| 1 | 71,2 % |
| 2 | 79,0 % |
| 3-5 | 80,1 % |
| 6-10 | 80,7 % |

Gegenüber Extreme-Point (71,8 %) ein Vorsprung von +8,9 Prozentpunkten bei
Standardbreite 6 - und durchgehend nachweislich monoton, keine einzige Verletzung über
die getesteten Breiten. *(Werte nach Einbau der Stützungsprüfung - siehe eigener
Abschnitt weiter unten - erneut aktualisiert: vorher konnten Boxen unphysikalisch
"schweben", was sowohl Extreme-Point als auch monobeam künstlich höhere Werte zeigen
ließ. Der Vorsprung von Beam Search gegenüber Extreme-Point ist bei korrekter
Stützungsprüfung sogar noch etwas größer als vorher gemessen.)*

**Performance:** Worst Case (60 Boxen, 300×300×300-cm-Container) jetzt ~1,45s statt der
alten ~1,0s - noch etwas langsamer (ca. 11x statt 6-7x gegenüber Extreme-Point), da
monobeam pro Slot eine echte Prioritätswarteschlange über *alle* Kandidaten pflegt statt
nur die besten pro Zustand vorab zu begrenzen. Bleibt mit <2s im für automatische
Neuberechnung vertretbaren Rahmen (`test_monobeam_worst_case_completes_within_budget`).

**Zwei weitere Funde beim Nachbessern der Testsuite:**
1. Zwei Testfunktionen hatten durch einen früheren Edit ihre `def`-Signatur verloren
   und liefen unbemerkt als angehängter Code innerhalb der vorherigen Funktion weiter
   (dieselbe Fehlerklasse wie bereits einmal in der Seefracht-Demo gefunden) - per
   `pytest --collect-only` und AST-Funktionszählung aufgefallen, behoben.
2. Ein Qualitäts-Sanity-Check summierte rohe (nicht prozentual normierte) Volumina über
   nur 5 Seeds mit unterschiedlicher Boxenzahl - dadurch weder aussagekräftig
   vergleichbar noch groß genug, um die bekannte Varianz robust abzubilden; schlug bei
   einer unglücklichen Stichprobe fehl, obwohl kein Bug vorlag. Auf 20 Seeds und
   prozentuale (containernormierte) Differenzen umgestellt.

## Presets nachträglich überprüft: zwei weitere Funde

Auf Nachfrage wurden auch die übrigen drei Presets systematisch nachgeprüft (nicht nur
auf Absturzfreiheit, sondern darauf, ob sie tatsächlich zeigen, was ihr Name
verspricht) - zwei zeigten echte Probleme.

### "Gleichmäßige Kartons": Beam Search war in 13 von 14 Seeds tatsächlich schlechter

Der ursprüngliche Seed (10) zeigte Beam Search bei 54,1% Raumnutzung - schlechter als
sowohl Schichten-basiert (56,2%) als auch Extreme-Point (56,2%), ein Widerspruch zum
eigenen Hilfetext ("alle drei sollten hier gut abschneiden"). Nachgeprüft über 14
weitere Seeds bei denselben Parametern: **13 von 14 zeigten dasselbe Muster.** Kein
Zufall, sondern ein echter, verstehbarer algorithmischer Effekt - ein Kontrolltest mit
denselben Seeds, aber breiterem Größenbereich (10-60cm statt 25-35cm) zeigte Beam
Search in 7 von 10 Fällen mindestens gleichauf statt nur 1 von 10. Die Erklärung: Beam
Search probiert mehrere leicht unterschiedliche Sortierreihenfolgen der Boxen durch
(siehe Beam-Search-Abschnitt oben) - bei uniformen Boxgrößen unterscheiden sich diese
Reihenfolgen kaum, das Durchprobieren bringt kaum Nutzen, kann aber durch die
zufällige Störung sogar leicht schaden. Auf Seed 8 korrigiert - dort liegen alle drei
Methoden exakt gleichauf (53,3%), keine schneidet schlechter ab.
Regressionstest: `test_gleichmaessige_kartons_preset_shows_no_beam_regression`.

**Ein drittes Kapitel dieser Geschichte:** nach Einbau der Stützungsprüfung
(`is_supported`, siehe eigener Abschnitt weiter unten) verschob sich das Bild erneut -
Seed 8 zeigte Beam Search jetzt WIEDER schlechter als Extreme-Point (51,1% vs. 53,3%).
Grund: die vorherigen frei "schwebenden" Platzierungen hatten den tatsächlichen
Qualitätsunterschied zwischen den Methoden verzerrt. Mit korrekter Stützungsprüfung neu
gesucht: Beam Search ist bei uniformen Boxgrößen jetzt überwiegend BESSER oder
gleichauf mit Extreme-Point (23 von 32 getesteten Seeds "besser", 9 "gleichauf",
keiner mehr "schlechter") - fast das Gegenteil des ursprünglichen Befunds. Auf Seed 3
aktualisiert (sauberer Gleichstand zwischen Extreme-Point und Beam Search, 51,2%
beide - Schichten-basiert liegt hier deutlich darunter bei 29,7%, aber das war nie der
Vergleich, um den es in diesem Preset ging).

### "Viele kleine Pakete": kein Stresstest, sondern das Gegenteil

Der ursprüngliche Preset (45 Boxen, 8-25cm, Standardcontainer 120×80×100cm) hatte ein
Gesamtboxvolumen von nur 20,9% des Containervolumens. Dadurch passten **alle** 45
Boxen bei **allen drei** Methoden vollständig hinein (0 unplatzierte Boxen je Methode)
- und die Raumnutzung war bei allen drei Methoden identisch (20,9%), weil sie nur noch
"Gesamtvolumen der Boxen ÷ Containervolumen" maß, nicht mehr Packqualität. Ein
"Stresstest" ohne jeden Stress. Sogar bei der maximal einstellbaren Boxenzahl (60)
reicht das Volumen kleiner Boxen (8-25cm) bei diesem Container nie an 100% heran - das
Problem lag also nicht am gewählten Seed, sondern strukturell an der Container-Box-
Kombination. Korrigiert durch einen kleineren Container (70×60×50cm statt
120×80×100cm) - bei maximaler Boxenzahl (60) beträgt das Gesamtvolumen jetzt ~131% des
Containers, echte Konkurrenz um den Platz, robust über mehrere Seeds (123-146% je nach
Seed, durchgehend deutliche Differenzierung zwischen den Methoden).
Regressionstest: `test_viele_kleine_pakete_preset_is_genuinely_capacity_constrained`.

## Verbesserungssuche für unplatzierte Boxen (auf Wunsch ergänzt)

Nach den Beam-Search-Verbesserungen der Seefracht-Demo lag die Frage nahe: überträgt
sich dieselbe Idee hierher? Die Extreme-Point-Heuristik trifft für jede Box eine
einmalige, gierige Platzierungsentscheidung ("tiefste, unterste, am weitesten links
liegende" zulässige Position) - genau wie die starre Hafen-Zuordnung der Fracht-Demo
könnte das Wert liegen lassen: eine leicht andere (nicht die für die aktuelle Box
"beste") Platzierung könnte für eine SPÄTERE Box viel mehr Raum freihalten.

**Bestätigt - mit echtem Nutzen:** Ein Prototyp (`rescue_unplaced_via_swap` in
`pack_heuristics.py`) sucht gezielt nach Umplatzierungen: für jede unplatzierte Box wird
probeweise eine bereits platzierte Box entfernt, geprüft ob die unplatzierte Box dann
passt, und ob die entfernte Box selbst anderswo wieder untergebracht werden kann.
Gelingt beides, werden beide Boxen übernommen - netto eine Box mehr platziert, garantiert
nie schlechter als der Ausgangszustand.

**Beim Szenario "Viele kleine Pakete":** 1 zusätzliche Box gerettet, Raumnutzung von
70,9 % auf 72,7 % gestiegen. **Beim (aktuellen) Szenario "Enges Puzzle":** ebenfalls 1
zusätzliche Box gerettet, 71,8 % auf 73,0 % gestiegen. *(Werte nach Einbau der
Stützungsprüfung - siehe eigener Abschnitt weiter unten - deutlich kleiner als zuvor
gemessen: vorher konnte Extreme-Point unphysikalisch "schwebende" Platzierungen
mitzählen, was die Startwerte künstlich höher und dadurch mehr scheinbares
Rettungspotential zeigen ließ. Systematisch nachgesucht, ob ein anderer Seed mit dem
korrigierten Algorithmus eine stärkere Demonstration zeigt - Seed 1 blieb bei "Viele
kleine Pakete" die beste verfügbare, auch wenn kleiner als zuvor.)*
(Hinweis: dieser Wert bezieht sich auf die Rettungssuche angewandt auf Extreme-Point's
eigenes Ergebnis, unabhängig davon, welche Methode im Beam-Search-Tab verwendet wird.)

**Anders als bei der Fracht-Demo: keine wirksame Kandidaten-Vorauswahl gefunden.** Bei
der Fracht-Demo half eine inkrementelle Kostenberechnung enorm. Hier wurde versucht, die
Suche auf die größten platzierten Boxen zu beschränken (in der Annahme, dass große Boxen
am ehesten genug Platz freigeben) - das hat die tatsächlich hilfreichen Kandidaten
(nicht notwendig die größten, sondern die an der richtigen Position) verpasst und die
gefundene Verbesserung komplett zunichtegemacht. Bei einem echten 3D-Geometrieproblem
zählt die Position, nicht nur die Größe - eine einfache Vorsortierung reicht hier nicht.

**Deshalb Button-gesteuert statt automatisch** (`🔧 Unplatzierte Boxen nachträglich
retten` je Heuristik-Tab, nur sichtbar wenn tatsächlich Boxen unplatziert sind) - Worst
Case bei maximaler Boxenzahl (60): ~3,6s reine Rechenzeit, für eine bewusst ausgelöste
Aktion vertretbar (ähnliche Größenordnung wie die OR-Tools-Zeitbegrenzung der
Tourenplanung-Demo). Mit demselben Stale-Result-Schutz wie dort abgesichert - ändert
sich die Konfiguration nach einem Klick, wird das alte Ergebnis verworfen statt
fälschlich weiter angezeigt (`test_rescue_result_becomes_stale_after_config_change`).

### Ein Namensfehler: keine echte Beam Search, trotz des Namens

Die Funktion und der Button hießen zunächst "Beam-Search-Verbesserungssuche" - ein
Fehler, der bei einer Nachfrage auffiel. `rescue_unplaced_via_swap` hat **keinen**
`beam_width`-Parameter, keine parallel verfolgten Kandidatenzustände - ein einziger
deterministischer Durchlauf, der bei der ersten erfolgreichen Verschiebung sofort
übernimmt (first-improvement). Die Monotonie-Frage ("wird eine größere Breite nie
schlechter") stellt sich damit gar nicht - die Dimension, auf die sie sich bezieht,
existiert hier nicht.

**Nachgeprüft, ob eine echte Breite etwas bringen würde:** mehrere Durchläufe mit
zufällig unterschiedlicher Reihenfolge der (unplatziert, platziert)-Paare, jeweils
bestes Ergebnis behalten. Ergebnis über mehrere Testinstanzen: vereinzelt deutlich mehr
Rettungen (z. B. 2 statt 1, oder 4 statt 2 - teils Verdopplung), aber **inkonsistent**
(bei manchen Instanzen keinerlei Unterschied) und bei **linear mit der Breite
wachsender Rechenzeit** (3 Durchläufe kosten bereits das 3-fache der Zeit eines
einzelnen). Da ein einzelner Durchlauf im Worst Case schon ~3,6s braucht, würde selbst
eine bescheidene Breite von 3-5 den Worst Case auf 10-18s treiben - für einen
unsicheren, teils ausbleibenden Zusatznutzen zu teuer für eine Button-Aktion. Bewusst
nicht eingebaut; Button und Docstring korrekt auf "Greedy-Verbesserungssuche"
umbenannt, mit Regressionstest (`test_rescue_button_not_mislabeled_as_beam_search`),
der sicherstellt, dass "Beam" nicht wieder fälschlich im Button-Text auftaucht.

## Drei gemeldete Darstellungsfehler in der 3D-Ansicht

### 1. Verzerrte Achsen bei nicht-würfelförmigen Containern

Auf den Hinweis "sehr merkwürdige 3D-Darstellung des Containers" gefunden: alle drei
Achsen (Länge, Breite, Höhe) bekamen denselben Wertebereich `[0, max(L,B,H)]` statt
jeweils ihre eigene tatsächliche Ausdehnung - beim Standard-Container 120×80×100cm
bekamen also Breite und Höhe beide den Bereich 0-120, obwohl sie nur 80 bzw. 100cm
messen.

**Warum das die Darstellung verzerrte:** Mit `aspectmode="data"` (bewusst gewählt,
damit Boxen nicht optisch gestreckt wirken) leitet Plotly das Seitenverhältnis der
3D-Szene direkt aus den angegebenen Achsenbereichen ab - bei drei identischen Bereichen
erzwingt das einen würfelförmigen Anzeigerahmen. Der tatsächliche (nicht-würfelförmige)
Container füllte darin nur einen Teil aus, mit auffälligem leerem Rand auf zwei Seiten
statt eines vollständig ausgefüllten Quaders - bei stark länglichen Containern (z. B.
70×60×50cm bei "Viele kleine Pakete") besonders deutlich sichtbar.

**Fix:** jede Achse bekommt jetzt ihren eigenen Bereich (`xaxis: [0, Länge]`, `yaxis:
[0, Breite]`, `zaxis: [0, Höhe]`) statt eines gemeinsamen, am größten Maß orientierten
Bereichs. Verifiziert: das Container-Drahtgitter füllt jetzt exakt seinen eigenen
Achsenbereich in allen drei Dimensionen, keine Verzerrung mehr.

### 2. Nach innen zeigende Flächennormalen bei den Box-Meshes

Auf Nachfrage präzisiert: eigentlich ging es um die Sichtbarkeit der Packstücke selbst
aus verschiedenen Blickwinkeln, nicht die Container-Skalierung. Systematisch per
Kreuzprodukt geprüft: **4 von 6 Seitenflächen** jedes Box-Meshs (unten, hinten, links)
hatten eine nach INNEN statt nach AUSSEN zeigende Normale - nur 2 von 6 (oben, vorne)
plus rechts (3 von 6 insgesamt) waren korrekt orientiert. Ursache: die
Dreiecks-Eckpunktreihenfolge (`_BOX_TRIANGLES_I/J/K`) folgte für diese vier Flächen
nicht der rechte-Hand-Regel für nach außen zeigende Normalen.

**Warum das die Sichtbarkeit beeinträchtigte:** Mit `flatshading=True` hängt Plotlys
Beleuchtungsberechnung direkt von der Normalenrichtung jeder Fläche ab - bei
uneinheitlich orientierten Normalen können Flächen je nach Blickwinkel und
Lichteinfall unsichtbar wirken oder falsch (zu dunkel/zu hell) schattiert erscheinen.
Da 4 von 6 Flächen betroffen waren, hätte praktisch jede Kamera-Perspektive
mindestens eine falsch wirkende Fläche gezeigt - passend zum gemeldeten Eindruck einer
"merkwürdigen" Darstellung, die sich beim Rotieren der Ansicht nicht auflöste.

**Wichtig - ein bereits bestehender Test (`test_box_mesh_triangles_cover_all_six_faces_exactly`)
hatte das nicht erkannt:** er prüft nur, ob jede Fläche flächenmäßig korrekt (kein
Loch, keine Überlappung) von 2 Dreiecken abgedeckt wird - das gilt unabhängig von der
Wicklungsrichtung, da die Flächenberechnung den Betrag nimmt. Die Normalenrichtung
selbst wurde nirgends geprüft. Ergänzt: `test_box_mesh_triangles_have_consistent_outward_normals`,
das explizit das Kreuzprodukt jedes Dreiecks gegen die erwartete Flächen-Außennormale
prüft - ein Beispiel dafür, dass geometrische Korrektheit mehrere unabhängige
Eigenschaften hat (hier: Flächendeckung UND Orientierung), die jeweils eigene Tests
brauchen.

**Fix:** die Eckpunktreihenfolge der 4 betroffenen Flächen (8 der 12 Dreiecke) so
vertauscht, dass alle 12 Dreiecke jetzt konsistent nach außen zeigen. Die abgedeckte
Fläche je Seite bleibt dabei unverändert (nur die Wicklungsrichtung ändert sich, nicht
die Position der Dreiecke) - verifiziert durch Neuberechnung der Flächensumme je Seite
nach der Korrektur.

### 3. Uneinheitliche Transparenz zwischen den Box-Meshes

Weiter präzisiert: "manche Packstücke scheinen durchsichtig zu sein, andere nicht, und
allen fehlt irgendwie die feste Substanz". Ursache: jede Box ist ein eigener,
unabhängiger `go.Mesh3d`-Trace, gerendert mit `opacity=0.85` (Halbtransparenz).

**Warum das zu inkonsistenter Durchsichtigkeit führte:** bei Halbtransparenz muss der
Renderer mehrere überlappende bzw. nahe beieinanderliegende Objekte nach Tiefe
sortiert überblenden (Alpha-Blending), damit die Sichtbarkeit stimmt. Das funktioniert
zuverlässig INNERHALB eines einzelnen Meshs, aber nicht zwangsläufig ZWISCHEN mehreren
UNABHÄNGIGEN Traces - Plotlys WebGL-Backend sortiert primär die Dreiecke innerhalb
eines Traces, nicht notwendigerweise alle Traces einer Szene gegeneinander. Je nach
Zeichenreihenfolge (welche Box zuerst zur Figur hinzugefügt wurde) und Kamerawinkel
konnte eine Box die Überblendung "gewinnen" (wirkt solide) oder "verlieren" (wirkt
durchsichtig) - unabhängig von ihrer tatsächlichen 3D-Position. Die pauschale
Halbtransparenz selbst erklärt zusätzlich das "fehlt die feste Substanz".

**Fix:** volle Deckkraft (`opacity=1.0` statt `0.85`) - damit reicht ein einfacher
Tiefenvergleich (Z-Buffer) statt Alpha-Blending, der zwischen unabhängigen Traces immer
korrekt funktioniert, keine Sortierungsmehrdeutigkeit mehr möglich. Zusätzlich
explizite Beleuchtungsparameter (`lighting`, `lightposition`) statt Plotlys
Standardwerten ergänzt - mehr Kontrast zwischen Licht und Schatten je Fläche, wirkt
plastischer/fester statt flach - profitiert von den jetzt korrekt nach außen zeigenden
Flächennormalen aus Fund 2, da Beleuchtungsberechnung direkt von der Normalenrichtung
abhängt.
`test_box_meshes_render_fully_opaque_with_explicit_lighting`.

Alle drei Funde mit Regressionstests abgesichert:
`test_container_wireframe_matches_actual_dimensions_not_cube`,
`test_container_wireframe_matches_dimensions_for_all_presets`,
`test_box_mesh_triangles_have_consistent_outward_normals`,
`test_box_meshes_render_fully_opaque_with_explicit_lighting`.

## Kein Darstellungsfehler, sondern ein echter Algorithmus-Bug: schwebende Packstücke

Weiter präzisiert: "manche Packstücke scheinen selbst bei den fortgeschritteneren
Methoden teilweise in der Luft zu schweben, obwohl sie bei Kippung in den Zwischenraum
darunter passen würden". Anders als die drei Darstellungsfehler oben war das kein
Rendering-Problem - die Packheuristiken selbst platzierten Boxen an physikalisch
unmöglichen Positionen.

### Das Ausmaß, systematisch geprüft

Eine eigens geschriebene Stützungsprüfung (Grundfläche einer Box gegen ein Raster
abgetastet: liegt an jedem Punkt darunter tatsächlich etwas Festes?) auf ein reales
Szenario (25 Boxen, Standardcontainer) angewendet: **6 von 15 platzierten Boxen (40%)**
bei Extreme-Point waren nicht vollständig gestützt, eine davon **komplett frei
schwebend (0% Stützung)**. Bei "Schichten-basiert" und der (damaligen) Beam-Search-
Implementierung dasselbe Bild - alle drei Heuristiken betroffen, inklusive
komplett schwebender Boxen.

**Ursache:** keine der vier Konstruktionsfunktionen (`layer_based_packing`,
`extreme_point_packing`, `beam_search_packing`, `monobeam_packing`) noch die
Rettungssuche (`rescue_unplaced_via_swap`) prüfte jemals, ob eine Position tatsächlich
gestützt ist - nur Überlappung (`any_overlap`) und Containergrenzen
(`fits_in_container`). Ein Extrempunkt entsteht als "ferne Ecke" einer bereits
platzierten Box; wird dort eine GRÖSSERE Box platziert, überragt sie die stützende Box
- der überstehende Teil hängt buchstäblich in der Luft, ohne dass das irgendwo geprüft
wurde.

### Die Lösung: exakte Flächenabdeckungsprüfung statt Stichproben-Raster

`is_supported()` in `pack_geometry.py` - keine Stichprobe, sondern eine exakte
Prüfung per Koordinatenkompression: jede bereits platzierte Box, deren Oberseite exakt
auf Höhe der Unterseite der neuen Box liegt, trägt ihre Grundfläche als
"Stützrechteck" bei; die Vereinigung dieser Stützrechtecke muss die gesamte
Grundfläche der neuen Box lückenlos abdecken (auch wenn mehrere kleinere Boxen
GEMEINSAM die volle Fläche stützen - das zählt als vollständig gestützt). Gegen sechs
handgerechnete Fälle verifiziert (Boden, exakt passend, überstehend, gemeinsame
Stützung mehrerer Boxen, komplett schwebend, Lücke zwischen zwei Stützen).

Als zusätzliche Nebenbedingung (wie `any_overlap`, `fits_in_container`) in alle vier
Konstruktionsfunktionen sowie `_try_place_one` (von der Rettungssuche genutzt)
integriert. Ergebnis: **0 schwebende Boxen** über alle vier Heuristiken und die
Rettungssuche, in allen vier Presets verifiziert.

### "Schichten-basiert" brauchte einen tieferen Umbau, nicht nur einen Filter

Bei den drei punktbasierten Heuristiken (Extreme-Point, Beam-Varianten, Rettungssuche)
reichte es, `is_supported()` als zusätzlichen Ablehnungsfilter in die bestehende
Kandidatensuche einzubauen. Bei "Schichten-basiert" nicht - zwei Zwischenversuche,
bevor die richtige Lösung stand:

1. **Reines Ablehnen unpassender Positionen** (gleiches Muster wie bei den anderen
   drei) behob das Schweben vollständig, ließ aber die Raumnutzung einbrechen (Seed 1:
   von 25 auf 5 platzierte Boxen). Grund: der ursprüngliche Algorithmus nutzte einen
   einzelnen globalen Höhen-Cursor (`z += layer_height`, Höhe der GRÖSSTEN Box einer
   Reihe für ALLE Boxen dieser Reihe) - bei unterschiedlich hohen Boxen in derselben
   Reihe (durchaus möglich, da nur nach Höhe absteigend sortiert, nicht nach Reihen
   gruppiert wird) reichten kleinere Boxen nicht bis zu dieser Höhe. Das war exakt der
   gemeldete Fehler - aber pures Ablehnen ohne Alternative half dem simplen
   3-Versuche-Cursor nicht, eine bessere Position zu finden.
2. **Live berechnete Stützhöhe statt Cursor** (`_support_height_for_footprint` - die
   tatsächlich nötige Höhe für einen Fußabdruck direkt aus den bereits platzierten
   Boxen ableiten, statt einem separaten Höhen-Cursor zu vertrauen) behob das
   Schweben ebenfalls, aber die Raumnutzung brach WEITERHIN ein (Seed 1: 25 auf 5
   Boxen) - ein anderer, subtilerer Grund: scheiterte eine Box an einer bestimmten
   (x,y)-Position (z. B. weil die berechnete Höhe den Container überstieg), blieb der
   (x,y)-Cursor dort "stecken", da er nur 3 begrenzte Versuche hatte und beim
   Fehlschlagen einfach zur nächsten Box weiterging - JEDE nachfolgende Box startete
   dann an derselben, bereits als schlecht bekannten Position und scheiterte
   ebenfalls. Ein Nachverfolgen des konkreten Ablaufs (Box für Box, mit
   Zwischenausgaben) deckte das auf.

**Die funktionierende Lösung:** ein robustes, wachsendes 2D-Raster aus (x,y)-Kandidaten
(Ecken bereits platzierter Boxen in der Grundfläche, ähnlich wie Extreme-Points
Kandidatenpunkte, aber auf die x,y-Ebene beschränkt - keine Rotation, kein
3D-Extrempunkt-Verfahren, bewusst einfacher). Für jede Box wird die "tiefste,
hinterste, am weitesten links liegende" Position über dieses Raster gesucht, mit der
tatsächlichen Stützhöhe für die Z-Koordinate. Scheitert eine Box, bleibt der
Rasterzustand für die nächste Box unverändert - kein Steckenbleiben mehr möglich, da
es keinen einzelnen "Cursor" mehr gibt, der vergiftet werden könnte. Ergebnis:
Raumnutzung zurück auf 44-62% (Seed 1: 48,8%, sogar über den ursprünglichen ~40% vor
jedem Fix), 0 schwebende Boxen, und der pädagogische Abstand zu Extreme-Point/Beam
Search (10-27 Prozentpunkte über 7 getestete Seeds) bleibt deutlich erhalten.

### Nebenwirkung: mehrere Preset-Werte mussten neu verifiziert werden

Da sich die zugrundeliegenden Packergebnisse legitim geändert haben (vorher teils
unphysikalisch überhöhte Werte durch schwebende Platzierungen), waren mehrere zuvor
sorgfältig verifizierte Zahlen betroffen:

- **"Gleichmäßige Kartons":** drittes Kapitel einer bereits zweimal korrigierten
  Geschichte (siehe eigener Abschnitt oben) - Seed 8 zeigte plötzlich wieder Beam
  Search schlechter, neu auf Seed 3 korrigiert.
- **"Enges Puzzle":** Werte durchgehend niedriger (Extreme-Point 80,1%→71,8%,
  Beam bei Standardbreite 85,4%→80,7%), aber die Kernaussage (deutlicher Vorsprung
  von Beam Search) blieb erhalten - der Abstand ist mit korrekter Stützungsprüfung
  sogar etwas GRÖSSER als vorher gemessen (8,9 statt 5,3 Prozentpunkte).
- **Rettungssuche bei "Viele kleine Pakete" und "Enges Puzzle":** deutlich weniger
  Rettungspotential übrig (3 gerettete Boxen wurden 1, bzw. 1 blieb 1) - Extreme-Point
  selbst liefert jetzt von Anfang an eine konservativere, aber korrekte Konstruktion,
  die vorher fälschlich als besser galt, weil sie teils auf schwebenden Platzierungen
  beruhte.

Alle betroffenen Tests mit den neu verifizierten Werten aktualisiert, nicht einfach
gelockert - jede neue Zahl wurde einzeln nachgerechnet.
`test_gleichmaessige_kartons_preset_shows_no_beam_regression`,
`test_rescue_finds_known_improvement_on_viele_kleine_pakete`.

## "Sollte Extreme-Point nicht in Beam Search enthalten sein?" - eine berechtigte Frage

Scharfe Nachfrage: Beam Search bei Breite 1 sollte doch praktisch Extreme-Point sein,
und dank der Monotonie-Garantie sollte eine größere Breite nie schlechter werden - wie
kann Extreme-Point dann in Presets wie "Gemischte Ladung" (81,4 % vs. 78,8 %) besser
abschneiden als Beam Search?

### Zwei unabhängige Ursachen, nicht nur eine

Direkt geprüft: Breite 1 war tatsächlich NICHT identisch mit Extreme-Point.

1. **Falsche Bewertungsgröße.** Monobeam bewertete Kandidaten pro Schritt nach
   `(-Volumen, resultierende Maximalhöhe)`, Extreme-Point nach DBL (`z, y, x` der
   Position - "tiefste, hinterste, am weitesten linke"). Da das Volumen für EIN
   bestimmtes Packstück bei JEDER gültigen Position identisch ist, reduzierte sich
   Monobeams Kriterium faktisch auf "minimiere die resultierende Maximalhöhe" - ein
   anderes Kriterium als DBL, nicht nur eine andere Formulierung desselben.
2. **Unterschiedliche Gleichstand-Auflösung.** Selbst nach Angleichen der
   Bewertungsgröße blieben die Ergebnisse verschieden. Grund: mehrere gültige
   Rotationen an derselben Position ergeben denselben DBL-Wert (der nur von der
   Position abhängt, nicht der Rotation) - ein ECHTER Gleichstand. Extreme-Point löst
   das über die Erzeugungsreihenfolge auf (`points` außen, Rotationen innen
   durchlaufen, striktes `<` behält den ZUERST gefundenen bei Gleichstand). Monobeams
   Heap löste stattdessen über den State-Fingerprint auf - eine andere, unabhängige
   Regel. Empirisch häufig: bei einer 25-Boxen-Instanz traten 24 solcher echten
   Gleichstände auf.

### Der Fix, und ein Kombinationsversuch, der nicht funktionierte

Beide Punkte korrigiert (DBL als Bewertungsgröße, ein expliziter
Erzeugungsreihenfolge-Zähler als Tie-Break, in derselben Reihenfolge wie
Extreme-Point) - danach war Breite 1 **byte-identisch** mit `extreme_point_packing`,
über mehrere Instanzen verifiziert.

Naheliegender nächster Gedanke: könnte man die Vorteile beider Bewertungsgrößen
kombinieren, indem die resultierende Maximalhöhe als ZUSÄTZLICHER Tie-Break nach DBL
dient (statt der reinen Erzeugungsreihenfolge)? Getestet - Ergebnis negativ: Breite 1
wich dadurch wieder in 12 von 14 Fällen von Extreme-Point ab, in 6 davon sogar
SCHLECHTER. Auch als Test, ob eine höhenbasierte Tie-Break-Regel Extreme-Point SELBST
verbessern würde (dann könnten beide synchron umgestellt werden): über 20 Instanzen
fast ausgeglichen (9 besser, 8 schlechter) - keine der beiden Regeln ist objektiv
überlegen, nur unterschiedlich.

**Die Kombination, die tatsächlich funktioniert, ist keine cleverere Formel pro
Schritt, sondern eine saubere Aufgabentrennung:** DBL lenkt die Suche (bewährt, exakt
wie Extreme-Point), eine deterministische Reihenfolge löst echte Gleichstände auf
(ebenfalls wie Extreme-Point), und erst die Auswahl zwischen den am Ende verbliebenen
Beam-Zuständen nutzt das tatsächlich interessierende Volumen. Der eigentliche Nutzen
einer größeren Breite kommt daher, mehrere unterschiedlich aufgelöste
Gleichstands-Pfade parallel zu verfolgen und danach den besten zu übernehmen - nicht
aus einer schlaueren Einzelentscheidung an jedem Schritt.

### Ergebnis: die vom Nutzer erwartete Eigenschaft gilt jetzt tatsächlich

Da Breite 1 exakt Extreme-Point entspricht UND die Monotonie-Garantie gilt, folgt
zwingend: Beam Search kann bei KEINER Breite mehr schlechter als Extreme-Point sein.
Über 30 Testinstanzen verifiziert (5 besser, 0 schlechter, 25 gleich) - vorher war das
nicht garantiert. Alle vier Presets zeigen das jetzt korrekt:

| Preset | Extreme-Point | Beam Search |
|---|---|---|
| Gleichmäßige Kartons | 50,3 % | 50,3 % |
| Gemischte Ladung | 81,4 % | 81,6 % |
| Viele kleine Pakete | 70,9 % | 71,1 % |
| Enges Puzzle | 71,6 % | 76,2 % |

`test_beam_search_beam_width_1_exactly_equals_extreme_point`,
`test_beam_search_never_worse_than_extreme_point`.

### Gibt es eine schlauere Bewertungsgröße als DBL? Nachgefragt und getestet

DBL ist bewährt, aber nicht zwangsläufig optimal - naheliegende Nachfrage: gibt es aus
der Container-Loading-Literatur etwas Besseres? Ein bekannter Ansatz (u. a. bei
Crainic/Perboli/Tadei selbst diskutiert): **Kontaktfläche maximieren** - eine Box, die
an mehreren Seiten (Boden, Rückwand, linke Wand oder andere Boxen) satt anliegt, sitzt
kompakter als eine, die nur zufällig eine tiefe Koordinate hat.

Implementiert (`contact_area()` in `pack_geometry.py`, exakte Flächenüberlappung, kein
Stichproben-Raster) und in vier Varianten gegen DBL getestet:

| Variante | Ergebnis (28-135 Instanzen) |
|---|---|
| Reine Kontaktfläche | DBL besser (15 vs. 11 Siege) |
| DBL zuerst, Kontaktfläche als Gleichstand-Kriterium | fast ausgeglichen, Ø −0,36pp |
| Kontaktfläche zuerst, DBL als Gleichstand-Kriterium | DBL besser (15 vs. 11), Ø −0,51pp |
| Gewichtete Kombination (normierte Höhe − Gewicht × normierte Kontaktfläche) | auf 56 Instanzen scheinbar +0,51pp, auf 135 Instanzen **verschwand der Vorteil wieder** (Ø −0,2 bis −0,3pp) - ein Stichproben-Zufallseffekt, kein robuster Befund |

**Keine der vier Varianten schlägt DBL robust.** Das ist selbst ein ehrliches Ergebnis,
kein Fehlschlag der Suche - DBL ist in der Literatur nicht nur aus Bequemlichkeit
etabliert, sondern weil es für dieses Setting bereits schwer zu schlagen ist. Bei DBL
belassen, statt eine unbewiesene Alternative einzubauen.



Bei dem zuvor verwendeten Seed (n=25, Seed 11) blieb Beam Search nach der Korrektur
exakt bei Extreme-Points Wert (71,8 %) - selbst bei Breite 32. Der vorher gezeigte
Vorsprung (71,8 %→80,7 %) war teilweise ein Artefakt der falschen Bewertungsgröße,
keine echte Exploration mehrerer Gleichstands-Pfade. Systematisch neu gesucht (~300
Konfigurationen): echte, wenn auch seltenere Vorteile bleiben nachweisbar (41
Konfigurationen mit >1 Prozentpunkt Vorsprung gefunden). Auf n=30, Größe 8-70cm, Seed
10 aktualisiert - zeigt bei Standardbreite 6 einen Vorsprung von 4,6 Prozentpunkten
(71,6 %→76,2 %), der mit wachsender Breite weiter zunimmt (Breite 16: 81,7 %). Auch
"Gleichmäßige Kartons" wurde erneut geprüft: mit der DBL-Korrektur zeigt praktisch
jeder Seed einen sauberen Gleichstand (44 von 49 getesteten) statt nur einem einzelnen
sorgfältig gesuchten - auf den einfachsten verfügbaren Seed (1) vereinfacht.

## Auf Nutzerwunsch ergänzt: finale Packungen nebeneinander im Vergleichs-Tab

Die VRP-Demo zeigt im Vergleichs-Tab bereits die finalen Touren aller Methoden
nebeneinander (eigene kleine Karte je Methode) - dieselbe Idee auf Pack übertragen.
Jede der drei Heuristiken bekommt jetzt eine eigene 3D-Ansicht ihrer finalen Packung
(inklusive einer eventuellen Rettungssuche, falls durchgeführt) direkt nebeneinander,
mit Raumnutzung in der Beschriftung - zusätzlich zur bereits vorhandenen numerischen
Tabelle.

Technisch unkompliziert: `render_packing_panel` gab die finalen `placements` bereits im
zurückgegebenen Summary-Dict zurück (inklusive einer eventuellen Rettungssuche, da die
lokale `placements`-Variable innerhalb der Funktion bei erfolgreicher Rettung
überschrieben wird, bevor sie zurückgegeben wird) - nur `build_3d_figure` musste in
`app.py` importiert und mit `st.columns()` aufgerufen werden, exakt nach demselben
Muster wie in der VRP-Demo.
`test_comparison_tab_shows_final_packings_side_by_side`.

## Vom Nutzer gemeldet: "Neue Boxen generieren" tat bei unverändertem Seed nichts

Im Zuge einer Konsistenzprüfung über alle vier Demos gefunden (identischer Fehler auch
in der Tourenplanung-Demo, dort zuerst gefunden und behoben - siehe dortiges README für
die volle Herleitung): der Button rief nur ein normales `st.button()` auf. Sein Wert
floss zwar in die Neuberechnungs-Bedingung ein (`regenerate or force_regen`), aber die
automatische Neugenerierung reagiert bereits auf jede Änderung von Parametern oder Seed
- blieb der Seed unverändert, lieferte die deterministische Zufallserzeugung dieselben
Werte erneut. Ein Klick löste zwar technisch eine Neuberechnung aus, das Ergebnis war
aber identisch - für den Nutzer sichtbar ein reiner Leerlauf-Klick.

**Der bestehende Test hatte diese Lücke nicht erkannt:** `test_regenerate_button` prüfte
nur "kein Absturz", nie die tatsächliche Wirkung. Auf echte Wirkungsprüfung umgestellt
(Seed muss sich nach dem Klick unterscheiden).

**Fix, kein ersatzloses Entfernen:** statt den wirkungslosen Button zu streichen, bekam
er eine echte Funktion - er würfelt jetzt einen neuen Zufalls-Seed (`randomize_seed()`
in `pack_presets.py`, nach demselben `on_click`-Callback-Muster wie `apply_preset`). Ein
Klick liefert garantiert neue Boxen, ohne selbst eine neue Seed-Zahl eintippen zu
müssen.

**Bei der Verifikation ein Fehlalarm im eigenen Testskript, kein App-Fehler:** ein
Skript, das denselben (veralteten) Python-Objektverweis auf den Button zweimal in Folge
anklickte, ohne ihn zwischen den Klicks über `at.button` neu zu holen, löste einen
`KeyError` in Streamlits Test-Framework aus (`layer_step` nicht initialisiert). Mit
korrekt bei jedem Klick neu geholter Button-Referenz (wie ein echter Nutzer das erlebt,
der immer ein frisch gerendertes Element anklickt) traten über 15 aufeinanderfolgende
Klicks keinerlei Probleme auf - ein Artefakt der Testmethodik, keine echte
Anwendungsschwäche.
`test_regenerate_button` (verstärkt).

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

95 Tests, laufen automatisch bei jedem Push/PR über GitHub Actions
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
