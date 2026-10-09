"""Scenario map as a Plotly figure dict. Pure Python."""
from __future__ import annotations

from .records import TestRecord


def scenario_map(rec: TestRecord) -> dict:
    r = rec.planner_result
    goal_x = r["goal_x"] if r else 8.0
    data = [
        {"type": "scatter", "mode": "lines", "name": "Straight line", "x": [0, goal_x], "y": [0, 0],
         "line": {"dash": "dash", "color": "#888"}},
        {"type": "scatter", "mode": "markers+text", "name": "Start / goal", "x": [0, goal_x], "y": [0, 0],
         "text": ["start", "goal"], "textposition": "bottom center", "marker": {"size": 12, "color": "#2a6fdb"}},
    ]
    annotations = []
    if rec.obstacles:
        xs, ys = zip(*rec.obstacles)
        data.append({"type": "scatter", "mode": "markers", "name": "Obstacles", "x": list(xs), "y": list(ys),
                     "marker": {"size": 14, "symbol": "square", "color": "#d62728"}})
        cx, cy = min(rec.obstacles, key=lambda o: abs(o[1]))
        clr = r["min_clearance_m"] if r else abs(cy)
        data.append({"type": "scatter", "mode": "lines", "name": "Closest approach", "x": [cx, cx], "y": [0, cy],
                     "line": {"color": "#ff7f0e", "width": 3}})
        annotations.append({"x": cx, "y": cy, "text": f"clearance {clr:.2f} m", "showarrow": True, "ay": -30})
    else:
        annotations.append({"x": goal_x / 2, "y": 0.5, "text": "no obstacles", "showarrow": False})
    return {"data": data, "layout": {
        "title": {"text": rec.name}, "annotations": annotations,
        "xaxis": {"title": {"text": "x (m)"}}, "yaxis": {"title": {"text": "y (m)"}, "scaleanchor": "x"},
        "legend": {"orientation": "h"}}}
