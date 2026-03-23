"""Plotly chart helpers for Lyrio Dashboard."""
from __future__ import annotations
import plotly.graph_objects as go
import pandas as pd


def style_chart(fig: go.Figure) -> go.Figure:
    """Apply Lyrio theme to any Plotly figure."""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#8B949E"),
        margin=dict(l=0, r=0, t=20, b=0),
        xaxis=dict(
            gridcolor="rgba(255,255,255,0.05)",
            tickcolor="#8B949E",
            linecolor="rgba(255,255,255,0.06)",
        ),
        yaxis=dict(
            gridcolor="rgba(255,255,255,0.05)",
            tickcolor="#8B949E",
            linecolor="rgba(255,255,255,0.06)",
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(color="#8B949E", size=12),
        ),
    )
    return fig


def sparkline(data: list[float], color: str = "#6366F1", height: int = 50) -> go.Figure:
    """Minimal sparkline — no axes, transparent bg."""
    fig = go.Figure()
    # Convert hex to rgba fill
    if color.startswith("#") and len(color) == 7:
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        fill = f"rgba({r},{g},{b},0.1)"
    else:
        fill = color.replace(")", ", 0.1)").replace("rgb", "rgba") if "rgb" in color else color
    fig.add_trace(go.Scatter(
        y=data,
        mode="lines",
        line=dict(color=color, width=2),
        fill="tozeroy",
        fillcolor=fill,
        showlegend=False,
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0),
        height=height,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


def area_chart(df: pd.DataFrame, bot_colors: dict | None = None) -> go.Figure:
    """14-day conversations by bot — 3 stacked area traces."""
    if bot_colors is None:
        bot_colors = {"seller": "#6366F1", "buyer": "#10B981", "lead": "#F59E0B"}

    fig = go.Figure()
    for bot_id, color in bot_colors.items():
        col = bot_id  # df columns should be named "seller", "buyer", "lead"
        if col not in df.columns:
            continue
        # hex to rgba fill
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        fig.add_trace(go.Scatter(
            x=df["date"],
            y=df[col],
            name=f"{col.title()} Bot",
            mode="lines",
            line=dict(color=color, width=2),
            fill="tozeroy",
            fillcolor=f"rgba({r},{g},{b},0.15)",
        ))
    return style_chart(fig)


def bar_chart(df: pd.DataFrame, color: str = "#6366F1") -> go.Figure:
    """Daily cost bar chart."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["date"],
        y=df["cost_usd"],
        marker_color=color,
        name="Daily spend",
        hovertemplate="$%{y:.4f}<extra></extra>",
    ))
    return style_chart(fig)
