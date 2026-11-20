import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def create_sweet_spot_matrix(df: pd.DataFrame):
    plot_df = df.dropna(subset=["PER (배)", "PEG (배)"]).copy()
    if plot_df.empty:
        return None

    plot_df["PER_plot"] = plot_df["PER (배)"].clip(lower=0, upper=80)
    plot_df["PEG_plot"] = plot_df["PEG (배)"].clip(lower=0, upper=3.5)
    plot_df["ROE_size"] = plot_df["ROE (%)"].fillna(12).clip(lower=12, upper=45)
    med_per = float(plot_df["PER_plot"].median())

    fig = go.Figure()
    fig.add_shape(
        type="rect", x0=0, y0=0, x1=med_per, y1=1.0,
        fillcolor="rgba(16, 185, 129, 0.18)",
        line=dict(color="rgba(16, 185, 129, 0.6)", width=1.5, dash="dot"),
        layer="below"
    )
    fig.add_annotation(
        x=med_per / 2, y=0.15,
        text="💎 SWEET SPOT (저PER + PEG<1.0)",
        showarrow=False,
        font=dict(color="#34d399", size=12, weight="bold")
    )

    fig.add_trace(go.Scatter(
        x=plot_df["PER_plot"],
        y=plot_df["PEG_plot"],
        mode="markers+text",
        text=plot_df["종목명"],
        textposition="top center",
        textfont=dict(size=11, color="#f1f5f9"),
        marker=dict(
            size=plot_df["ROE_size"],
            color=plot_df["종합 스코어"],
            colorscale="Viridis",
            showscale=True,
            colorbar=dict(title="종합 스코어"),
            line=dict(width=1.5, color="#ffffff")
        ),
        hovertemplate="<b>%{text}</b><br>PER: %{x:.1f}배<br>PEG: %{y:.2f}<extra></extra>"
    ))

    fig.add_hline(y=1.0, line_dash="dash", line_color="#10b981", annotation_text="PEG 1.0 저평가 기준선")
    fig.add_vline(x=med_per, line_dash="dash", line_color="#6366f1", annotation_text=f"업종 중위 PER ({med_per:.1f}배)")

    fig.update_layout(
        template="plotly_dark",
        height=540,
        xaxis=dict(title="PER (배) → 낮을수록 가격 저평가", range=[0, max(plot_df["PER_plot"].max() * 1.15, 35)]),
        yaxis=dict(title="PEG (배) → 낮을수록 성장 가성비 우수", range=[0, max(plot_df["PEG_plot"].max() * 1.15, 2.5)]),
        paper_bgcolor="#0c1220",
        plot_bgcolor="#0c1220",
        margin=dict(l=30, r=30, t=35, b=35)
    )
    return fig

def create_pro_candlestick_chart(hist_df: pd.DataFrame, chart_style: str, show_bb: bool, show_mas: list, fair_p: float, curr_mark: str, is_intraday: bool):
    df = hist_df.sort_index().copy()
    df["EMA5"] = df["Close"].ewm(span=5, adjust=False).mean()
    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["EMA60"] = df["Close"].ewm(span=60, adjust=False).mean()

    r_mean = df["Close"].rolling(window=20).mean()
    r_std = df["Close"].rolling(window=20).std()
    df["BB_Upper"] = r_mean + (r_std * 2)
    df["BB_Lower"] = r_mean - (r_std * 2)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])

    if show_bb:
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_Upper"], mode="lines", line=dict(color="rgba(99, 102, 241, 0.3)", width=1), name="BB 상한", hoverinfo="skip"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_Lower"], mode="lines", line=dict(color="rgba(99, 102, 241, 0.3)", width=1), fill="tonexty", fillcolor="rgba(99, 102, 241, 0.05)", name="BB 밴드", hoverinfo="skip"), row=1, col=1)

    if "캔들스틱" in chart_style:
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
            name="주가(캔들)",
            increasing=dict(line=dict(color="#f43f5e", width=1.2), fillcolor="#f43f5e"),
            decreasing=dict(line=dict(color="#3b82f6", width=1.2), fillcolor="#3b82f6"),
        ), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["Close"], mode="lines", name="종가 추세",
            line=dict(color="#38bdf8", width=2.5), fill="tozeroy", fillcolor="rgba(56, 189, 248, 0.08)"
        ), row=1, col=1)

    if "5선 (단기)" in show_mas:
        fig.add_trace(go.Scatter(x=df.index, y=df["EMA5"], mode="lines", name="5선", line=dict(color="#f59e0b", width=1.5)), row=1, col=1)
    if "20선 (생명선)" in show_mas:
        fig.add_trace(go.Scatter(x=df.index, y=df["EMA20"], mode="lines", name="20선", line=dict(color="#10b981", width=2)), row=1, col=1)
    if "60선 (추세선)" in show_mas:
        fig.add_trace(go.Scatter(x=df.index, y=df["EMA60"], mode="lines", name="60선", line=dict(color="#8b5cf6", width=1.5, dash="dot")), row=1, col=1)

    if fair_p and fair_p > 0 and not is_intraday:
        fig.add_hline(
            y=fair_p, line_dash="dash", line_color="#38bdf8",
            annotation_text=f"자체 퀀트 적정가 ({curr_mark}{fair_p:,.0f})",
            annotation_position="top left",
            annotation_font=dict(color="#38bdf8", size=11, family="Pretendard"),
            row=1, col=1
        )

    if "Volume" in df.columns:
        vol_colors = ["#f43f5e" if c >= o else "#3b82f6" for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="거래량", marker_color=vol_colors, opacity=0.75), row=2, col=1)

    fig.update_layout(
        template="plotly_dark", height=560, xaxis_rangeslider_visible=False,
        paper_bgcolor="#090d16", plot_bgcolor="#090d16",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11)),
        margin=dict(l=30, r=30, t=25, b=25), hovermode="x unified"
    )
    fig.update_xaxes(gridcolor="rgba(148, 163, 184, 0.08)", showspikes=True, spikecolor="#6366f1", spikethickness=1, fixedrange=False)
    fig.update_yaxes(gridcolor="rgba(148, 163, 184, 0.08)", row=1, col=1, title="주가", fixedrange=False)
    fig.update_yaxes(gridcolor="rgba(148, 163, 184, 0.05)", row=2, col=1, title="거래량", fixedrange=False)
    return fig