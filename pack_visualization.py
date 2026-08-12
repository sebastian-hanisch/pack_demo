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
# und ohne Überlappung abgedeckt.
_BOX_TRIANGLES_I = [0, 0, 4, 4, 0, 0, 3, 3, 0, 0, 1, 1]
_BOX_TRIANGLES_J = [1, 2, 5, 6, 1, 5, 2, 6, 3, 7, 2, 6]
_BOX_TRIANGLES_K = [2, 3, 6, 7, 5, 4, 6, 7, 7, 4, 6, 5]


def _box_mesh_trace(pos, dim, color, name, opacity=0.85):
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
    max_dim = max(CL, CW, CH)
    fig.update_layout(
        scene=dict(
            xaxis=dict(title="Länge (cm)", range=[0, max_dim]),
            yaxis=dict(title="Breite (cm)", range=[0, max_dim]),
            zaxis=dict(title="Höhe (cm)", range=[0, max_dim]),
            aspectmode="data",
            camera=dict(eye=dict(x=1.5, y=-1.5, z=1.0)),
        ),
        height=560, margin=dict(l=0, r=0, t=20, b=0),
    )
    return fig
