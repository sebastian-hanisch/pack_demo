"""
3D-Visualisierung der Packlösung mit Plotly: Container als Drahtgitter,
platzierte Boxen als massive Quader (go.Mesh3d). Die "Animation" (Boxen
erscheinen nacheinander) folgt demselben Schritt-Slider + Auto-Play-Muster
wie die LKW-Tourenplanung-Demo, statt einer nativen Plotly-Play/Pause-
Animation - das Platzieren ist ohnehin ein diskreter Vorgang (eine Box nach
der anderen), keine Bewegungs-Interpolation nötig.
"""

import plotly.graph_objects as go

from pack_constants import BOX_COLORS

# Standard-Eckpunkt-Reihenfolge eines Quaders und seine 12 Dreiecke
# (2 pro Seitenfläche × 6 Flächen) für go.Mesh3d. Geometrisch verifiziert
# (siehe Testsuite): jede der 6 Flächen wird von genau 2 Dreiecken lückenlos
# und ohne Überlappung abgedeckt, UND alle 12 Dreiecke haben konsistent
# nach AUSSEN zeigende Normalen (rechte-Hand-Regel bei der gewählten
# Eckpunkt-Reihenfolge) - auf Nutzerhinweis ("Sichtbarkeit aus
# verschiedenen Perspektiven") gefunden: die ursprüngliche Reihenfolge
# hatte bei 4 von 6 Flächen (unten, hinten, links) nach INNEN zeigende
# Normalen, nur 2 von 6 (oben, vorne, rechts eigentlich 3 von 6) waren
# korrekt - je nach Blickwinkel und Beleuchtung/Rendering-Verhalten von
# Plotly konnte das zu unsichtbaren oder falsch schattierten Flächen
# führen. Siehe README für die Herleitung.
_BOX_TRIANGLES_I = [0, 0, 4, 4, 0, 0, 3, 3, 0, 0, 1, 1]
_BOX_TRIANGLES_J = [2, 3, 5, 6, 1, 5, 6, 7, 7, 4, 2, 6]
_BOX_TRIANGLES_K = [1, 2, 6, 7, 5, 4, 2, 6, 3, 7, 6, 5]


def _box_mesh_trace(pos, dim, color, name, opacity=1.0):
    x0, y0, z0 = pos
    dx, dy, dz = dim
    x1, y1, z1 = x0 + dx, y0 + dy, z0 + dz
    xs = [x0, x1, x1, x0, x0, x1, x1, x0]
    ys = [y0, y0, y1, y1, y0, y0, y1, y1]
    zs = [z0, z0, z0, z0, z1, z1, z1, z1]
    return go.Mesh3d(
        x=xs, y=ys, z=zs,
        i=_BOX_TRIANGLES_I, j=_BOX_TRIANGLES_J, k=_BOX_TRIANGLES_K,
        color=color, opacity=opacity, flatshading=True,
        # Auf Nutzerhinweis ergänzt ("manche Packstücke wirken durchsichtig,
        # andere nicht, alle wirken irgendwie 'fest' unterrepräsentiert"):
        # bei halbtransparenten (opacity<1) Boxen muss WebGL mehrere
        # UNABHÄNGIGE Mesh3d-Traces (eine pro Box) nach Tiefe sortiert
        # überblenden - das gelingt zwischen getrennten Traces nicht
        # zuverlässig, wodurch je nach Zeichenreihenfolge und Kamerawinkel
        # manche Boxen die Überblendung "gewinnen" (wirken solide) und
        # andere "verlieren" (wirken durchsichtig). Volle Deckkraft
        # (opacity=1.0) umgeht das komplett - dann reicht einfacher
        # Tiefenvergleich (Z-Buffer) statt Alpha-Blending, das ist
        # zwischen unabhängigen Traces immer korrekt. Zusätzlich explizite
        # Beleuchtung statt Plotlys Standardwerten - gibt den Flächen mehr
        # Kontrast zwischen Licht und Schatten (wirkt "fester", nicht flach
        # papierartig), abhängig von den jetzt korrekt nach außen
        # zeigenden Flächennormalen (siehe vorherige Korrektur).
        lighting=dict(ambient=0.55, diffuse=0.7, specular=0.35, roughness=0.6, fresnel=0.1),
        lightposition=dict(x=100, y=-100, z=200),
        name=name, hovertext=name, hoverinfo="text", showlegend=False,
    )


def _container_wireframe_trace(container_dim):
    CL, CW, CH = container_dim
    corners = [
        (0, 0, 0), (CL, 0, 0), (CL, CW, 0), (0, CW, 0),
        (0, 0, CH), (CL, 0, CH), (CL, CW, CH), (0, CW, CH),
    ]
    edges = [
        (0, 1), (1, 2), (2, 3), (3, 0),  # unten
        (4, 5), (5, 6), (6, 7), (7, 4),  # oben
        (0, 4), (1, 5), (2, 6), (3, 7),  # senkrecht
    ]
    xs, ys, zs = [], [], []
    for a, b in edges:
        xs += [corners[a][0], corners[b][0], None]
        ys += [corners[a][1], corners[b][1], None]
        zs += [corners[a][2], corners[b][2], None]
    return go.Scatter3d(
        x=xs, y=ys, z=zs, mode="lines",
        line=dict(color="rgba(60,60,60,0.6)", width=3),
        name="Container", hoverinfo="skip", showlegend=False,
    )


def build_3d_figure(placements_subset, boxes, ids, container_dim):
    """Baut die 3D-Ansicht für einen gegebenen Stand (Teilmenge platzierter
    Boxen) - wird sowohl für die statische Endansicht als auch für jeden
    Schritt der Platzierungs-Animation verwendet."""
    fig = go.Figure()
    fig.add_trace(_container_wireframe_trace(container_dim))

    for entry in placements_subset:
        idx = entry["box_idx"]
        color = BOX_COLORS[idx % len(BOX_COLORS)]
        label = f"Box {ids[idx]} ({entry['dim'][0]:.0f}×{entry['dim'][1]:.0f}×{entry['dim'][2]:.0f} cm)"
        fig.add_trace(_box_mesh_trace(entry["pos"], entry["dim"], color, label))

    CL, CW, CH = container_dim
    fig.update_layout(
        scene=dict(
            xaxis=dict(title="Länge (cm)", range=[0, CL]),
            yaxis=dict(title="Breite (cm)", range=[0, CW]),
            zaxis=dict(title="Höhe (cm)", range=[0, CH]),
            aspectmode="data",
            camera=dict(eye=dict(x=1.5, y=-1.5, z=1.0)),
        ),
        height=560, margin=dict(l=0, r=0, t=20, b=0),
    )
    return fig
