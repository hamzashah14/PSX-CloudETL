import dash
from dash import dcc, html, Input, Output, callback, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
from functools import lru_cache
import json
import os

# Initialize Dash app with premium styling
app = dash.Dash(__name__, external_stylesheets=[
    dbc.themes.CYBORG,
    "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap",
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"
])
app.title = "CloudETL Quantum Analytics"

# --- Premium Design System ---
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            @keyframes gradient-shift {
                0% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
                100% { background-position: 0% 50%; }
            }
            
            @keyframes float {
                0%, 100% { transform: translateY(0px); }
                50% { transform: translateY(-10px); }
            }
            
            @keyframes pulse-glow {
                0%, 100% { box-shadow: 0 0 20px rgba(0, 242, 255, 0.2); }
                50% { box-shadow: 0 0 40px rgba(0, 242, 255, 0.4); }
            }
            
            @keyframes spinner {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            
            :root {
                --bg-primary: #0A0E1A;
                --bg-secondary: #121829;
                --bg-card: rgba(18, 24, 41, 0.7);
                --bg-card-hover: rgba(25, 33, 54, 0.85);
                --sidebar-bg: linear-gradient(180deg, #0F1424 0%, #1A1F35 100%);
                --accent-cyan: #00F2FF;
                --accent-purple: #A78BFA;
                --accent-pink: #F472B6;
                --accent-orange: #FB923C;
                --gradient-primary: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                --gradient-success: linear-gradient(135deg, #10B981 0%, #059669 100%);
                --gradient-danger: linear-gradient(135deg, #EF4444 0%, #DC2626 100%);
                --gradient-cyber: linear-gradient(135deg, #00F2FF 0%, #8B5CF6 50%, #EC4899 100%);
                --text-primary: #F1F5F9;
                --text-secondary: #94A3B8;
                --text-muted: #64748B;
                --border-glass: rgba(255, 255, 255, 0.1);
                --shadow-premium: 0 20px 60px rgba(0, 0, 0, 0.5);
                --shadow-card: 0 8px 32px rgba(0, 0, 0, 0.3);
            }
            
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body { 
                background: var(--bg-primary);
                background-image: 
                    radial-gradient(circle at 20% 30%, rgba(102, 126, 234, 0.1) 0%, transparent 50%),
                    radial-gradient(circle at 80% 70%, rgba(139, 92, 246, 0.1) 0%, transparent 50%);
                font-family: 'Inter', sans-serif;
                color: var(--text-primary);
                overflow-x: hidden;
                line-height: 1.6;
            }
            
            /* Sidebar Styling */
            .sidebar {
                background: var(--sidebar-bg);
                backdrop-filter: blur(40px);
                -webkit-backdrop-filter: blur(40px);
                border-right: 1px solid var(--border-glass);
                height: 100vh;
                position: fixed;
                width: 300px;
                z-index: 1000;
                padding: 40px 24px;
                box-shadow: 4px 0 30px rgba(0, 0, 0, 0.3);
                overflow-y: auto;
            }
            
            .sidebar::-webkit-scrollbar {
                width: 6px;
            }
            
            .sidebar::-webkit-scrollbar-track {
                background: rgba(255, 255, 255, 0.05);
                border-radius: 10px;
            }
            
            .sidebar::-webkit-scrollbar-thumb {
                background: var(--accent-cyan);
                border-radius: 10px;
            }
            
            .logo-section {
                margin-bottom: 50px;
                padding-bottom: 30px;
                border-bottom: 1px solid var(--border-glass);
            }
            
            .logo-title {
                font-size: 2rem;
                font-weight: 900;
                background: var(--gradient-cyber);
                background-size: 200% 200%;
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                animation: gradient-shift 4s ease infinite;
                letter-spacing: -1px;
                margin-bottom: 8px;
            }
            
            .logo-subtitle {
                font-size: 0.7rem;
                font-weight: 700;
                color: var(--text-secondary);
                letter-spacing: 3px;
                text-transform: uppercase;
            }
            
            /* Navigation Pills */
            .nav-section {
                margin-bottom: 40px;
            }
            
            .nav-section-title {
                font-size: 0.65rem;
                font-weight: 700;
                color: var(--text-muted);
                letter-spacing: 2px;
                text-transform: uppercase;
                margin-bottom: 15px;
                padding-left: 16px;
            }
            
            .nav-pill {
                display: flex;
                align-items: center;
                padding: 14px 20px;
                border-radius: 14px;
                color: var(--text-secondary);
                cursor: pointer;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                margin-bottom: 8px;
                font-weight: 500;
                font-size: 0.95rem;
                border: 1px solid transparent;
                position: relative;
                overflow: hidden;
            }
            
            .nav-pill::before {
                content: '';
                position: absolute;
                left: 0;
                top: 0;
                height: 100%;
                width: 3px;
                background: var(--gradient-cyber);
                transform: scaleY(0);
                transition: transform 0.3s ease;
            }
            
            .nav-pill:hover {
                background: rgba(0, 242, 255, 0.08);
                border-color: rgba(0, 242, 255, 0.2);
                transform: translateX(4px);
            }
            
            .nav-pill.active {
                background: rgba(0, 242, 255, 0.12);
                color: var(--accent-cyan);
                border-color: rgba(0, 242, 255, 0.3);
                font-weight: 600;
            }
            
            .nav-pill.active::before {
                transform: scaleY(1);
            }
            
            .nav-icon {
                margin-right: 14px;
                font-size: 1.1rem;
                width: 24px;
                text-align: center;
            }
            
            /* Content Area */
            .content-area {
                margin-left: 300px;
                padding: 40px 50px;
                min-height: 100vh;
            }
            
            /* Header Section */
            .header-section {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 40px;
                padding-bottom: 30px;
                border-bottom: 1px solid var(--border-glass);
            }
            
            .header-controls {
                display: flex;
                align-items: center;
                gap: 20px;
            }
            
            /* Glass Panel */
            .glass-panel {
                background: var(--bg-card) !important;
                backdrop-filter: blur(30px);
                -webkit-backdrop-filter: blur(30px);
                border: 1px solid var(--border-glass) !important;
                border-radius: 24px !important;
                box-shadow: var(--shadow-card);
                transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
                overflow: hidden;
            }
            
            .glass-panel:hover {
                border-color: rgba(0, 242, 255, 0.25) !important;
                transform: translateY(-2px);
                box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
            }
            
            /* Stat Cards */
            .stat-card {
                background: var(--bg-card);
                backdrop-filter: blur(30px);
                border: 1px solid var(--border-glass);
                border-radius: 20px;
                padding: 32px 28px;
                transition: all 0.3s ease;
                position: relative;
                overflow: hidden;
            }
            
            .stat-card::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 3px;
                background: var(--gradient-cyber);
                transform: scaleX(0);
                transition: transform 0.3s ease;
            }
            
            .stat-card:hover::before {
                transform: scaleX(1);
            }
            
            .stat-card:hover {
                transform: translateY(-4px);
                border-color: rgba(0, 242, 255, 0.3);
                box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
            }
            
            .stat-label {
                font-size: 0.7rem;
                font-weight: 700;
                color: var(--text-muted);
                letter-spacing: 2px;
                text-transform: uppercase;
                margin-bottom: 12px;
            }
            
            .stat-value {
                font-size: 2.8rem;
                font-weight: 800;
                color: var(--text-primary);
                margin-bottom: 8px;
                line-height: 1;
                font-family: 'JetBrains Mono', monospace;
            }
            
            .stat-change {
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 1rem;
                font-weight: 600;
            }
            
            .stat-change.positive {
                color: #10B981;
            }
            
            .stat-change.negative {
                color: #EF4444;
            }
            
            /* Buttons */
            .btn-primary {
                background: var(--gradient-cyber);
                background-size: 200% 200%;
                color: white;
                border: none;
                padding: 12px 28px;
                border-radius: 12px;
                font-weight: 700;
                font-size: 0.9rem;
                cursor: pointer;
                transition: all 0.3s ease;
                text-transform: uppercase;
                letter-spacing: 1px;
                box-shadow: 0 4px 20px rgba(0, 242, 255, 0.3);
            }
            
            .btn-primary:hover {
                animation: gradient-shift 2s ease infinite;
                transform: translateY(-2px);
                box-shadow: 0 6px 30px rgba(0, 242, 255, 0.5);
            }
            
            .btn-primary:active {
                transform: translateY(0);
            }
            
            .btn-ghost {
                background: transparent;
                border: 1px solid var(--border-glass);
                color: var(--text-secondary);
                padding: 10px 22px;
                border-radius: 10px;
                font-weight: 600;
                font-size: 0.85rem;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            
            .btn-ghost:hover {
                background: rgba(255, 255, 255, 0.05);
                border-color: var(--accent-cyan);
                color: var(--accent-cyan);
            }
            
            .btn-ghost.active {
                background: rgba(0, 242, 255, 0.12);
                border-color: var(--accent-cyan);
                color: var(--accent-cyan);
            }
            
            /* Dropdown Styling - Updated for Dash Components */
            div[class*="dropdown"] div[class*="control"] {
                background-color: rgba(255, 255, 255, 0.05) !important;
                border: 1px solid var(--border-glass) !important;
                border-radius: 12px !important;
                min-height: 42px !important;
                transition: all 0.3s ease !important;
            }
            
            div[class*="dropdown"] div[class*="control"]:hover {
                border-color: var(--accent-cyan) !important;
                background-color: rgba(255, 255, 255, 0.08) !important;
            }
            
            div[class*="dropdown"] div[class*="placeholder"],
            div[class*="dropdown"] div[class*="singleValue"] {
                color: white !important;
                font-weight: 600 !important;
            }
            
            div[class*="dropdown"] div[class*="menu"] {
                background-color: rgba(18, 24, 41, 0.98) !important;
                border: 1px solid var(--border-glass) !important;
                border-radius: 12px !important;
                backdrop-filter: blur(20px);
                margin-top: 4px !important;
                box-shadow: var(--shadow-premium) !important;
            }
            
            div[class*="dropdown"] div[class*="option"] {
                background-color: transparent !important;
                color: var(--text-secondary) !important;
                padding: 12px 16px !important;
                font-weight: 500 !important;
                transition: all 0.2s ease !important;
                cursor: pointer !important;
            }
            
            div[class*="dropdown"] div[class*="option"]:hover {
                background-color: rgba(0, 242, 255, 0.1) !important;
                color: var(--accent-cyan) !important;
            }
            
            div[class*="dropdown"] div[class*="option--is-selected"] {
                background-color: rgba(0, 242, 255, 0.15) !important;
                color: var(--accent-cyan) !important;
                font-weight: 600 !important;
            }
            
            div[class*="dropdown"] svg {
                fill: var(--accent-cyan) !important;
            }
            
            /* Dash Loading Spinner Customization */
            .dash-spinner.dash-default-spinner {
                width: 60px !important;
                height: 60px !important;
            }
            
            .dash-spinner.dash-default-spinner svg circle {
                stroke: var(--accent-cyan) !important;
            }
            
            ._dash-loading-callback {
                background: rgba(10, 14, 26, 0.6) !important;
                backdrop-filter: blur(4px) !important;
            }
            
            /* Footer Badge */
            .version-badge {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                background: rgba(16, 185, 129, 0.1);
                border: 1px solid rgba(16, 185, 129, 0.3);
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 0.7rem;
                font-weight: 700;
                color: #10B981;
                letter-spacing: 1px;
            }
            
            .status-dot {
                width: 6px;
                height: 6px;
                background: #10B981;
                border-radius: 50%;
                animation: pulse-glow 2s ease-in-out infinite;
            }
            
            /* Chart Container Enhancements */
            .chart-container {
                padding: 24px;
            }
            
            .chart-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
                padding-bottom: 16px;
                border-bottom: 1px solid var(--border-glass);
            }
            
            .chart-title {
                font-size: 1.2rem;
                font-weight: 700;
                color: var(--text-primary);
            }
            
            /* Responsive Design */
            @media (max-width: 1200px) {
                .sidebar {
                    width: 260px;
                }
                .content-area {
                    margin-left: 260px;
                    padding: 30px 35px;
                }
            }
            
            @media (max-width: 768px) {
                .sidebar {
                    transform: translateX(-100%);
                }
                .content-area {
                    margin-left: 0;
                    padding: 20px;
                }
            }
            
            /* Custom Scrollbar */
            ::-webkit-scrollbar {
                width: 10px;
                height: 10px;
            }
            
            ::-webkit-scrollbar-track {
                background: var(--bg-secondary);
            }
            
            ::-webkit-scrollbar-thumb {
                background: linear-gradient(180deg, var(--accent-cyan), var(--accent-purple));
                border-radius: 10px;
            }
            
            ::-webkit-scrollbar-thumb:hover {
                background: linear-gradient(180deg, var(--accent-purple), var(--accent-pink));
            }
        </style>
    </head>
    <body class="quantum-ui">
        {%app_entry%}
        <footer>{%config%}{%scripts%}{%renderer%}</footer>
    </body>
</html>
'''

# Enhanced Color Palette
colors = {
    'background': '#0A0E1A',
    'card': 'rgba(18, 24, 41, 0.7)',
    'text': '#F1F5F9',
    'text_secondary': '#94A3B8',
    'text_muted': '#64748B',
    'accent_cyan': '#00F2FF',
    'accent_purple': '#A78BFA',
    'accent_pink': '#F472B6',
    'positive': '#10B981',
    'negative': '#EF4444',
    'grid': 'rgba(255, 255, 255, 0.08)',
    'warning': '#FB923C'
}

@lru_cache(maxsize=128)
def get_cached_data(ticker, period, timestamp):
    """Fetch from transform API with caching.

    Raises on any failure: lru_cache never stores an exception, so a failed fetch is retried on the next
    call instead of being remembered as "no data" for the rest of the five-minute window.
    """
    transform_url = os.getenv('TRANSFORM_SERVICE_URL', 'http://transform-service:8001')
    response = requests.post(
        f'{transform_url}/transform_batch',
        json={'tickers': ticker, 'period': period},
        timeout=30
    )
    if response.status_code != 200:
        raise RuntimeError(f"transform service answered {response.status_code}")
    return response.json()['data']

def get_data_with_cache(ticker, period):
    """Get historical data with 5-minute caching"""
    cache_key = int(time.time() / 300)
    try:
        return get_cached_data(ticker, period, cache_key)
    except Exception as e:
        print(f"API Error: {e}")
        return []

# --- Enhanced Chart Components ---

def apply_premium_layout(fig, height=400, title=None, show_legend=True):
    """Apply consistent premium styling to all charts"""
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(family="Inter", size=18, color=colors['text']),
            x=0.02,
            xanchor='left'
        ) if title else None,
        template="plotly_dark",
        height=height,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Inter", color=colors['text'], size=12),
        margin=dict(l=60, r=40, t=60, b=50),
        xaxis=dict(
            showgrid=True,
            gridcolor=colors['grid'],
            linecolor=colors['grid'],
            zeroline=False,
            tickfont=dict(size=11, color=colors['text_secondary'])
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=colors['grid'],
            zeroline=False,
            tickfont=dict(size=11, color=colors['text_secondary'])
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="rgba(18, 24, 41, 0.95)",
            font_size=13,
            font_family="Inter",
            bordercolor=colors['accent_cyan']
        ),
        showlegend=show_legend,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11)
        )
    )
    return fig

def create_candlestick_chart(df, ticker):
    """Enhanced candlestick chart with gradient styling"""
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No Data Available",
            showarrow=False,
            font=dict(size=16, color=colors['text_secondary']),
            xref="paper", yref="paper",
            x=0.5, y=0.5
        )
        return apply_premium_layout(fig, height=550, title=f"{ticker} Price Action", show_legend=False)
    
    fig = go.Figure(data=[go.Candlestick(
        x=df['Date'],
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        increasing_line_color=colors['positive'],
        increasing_fillcolor=colors['positive'],
        decreasing_line_color=colors['negative'],
        decreasing_fillcolor=colors['negative'],
        name=ticker
    )])
    
    fig.update_layout(xaxis_rangeslider_visible=False)
    
    return apply_premium_layout(fig, height=550, title=f"{ticker} Price Action", show_legend=False)

def create_volume_chart(df):
    """Enhanced volume chart with color coding"""
    if df.empty:
        return go.Figure()
    
    colors_volume = [colors['positive'] if row['Close'] >= row['Open'] else colors['negative'] 
                     for _, row in df.iterrows()]
    
    fig = go.Figure(data=go.Bar(
        x=df['Date'],
        y=df['Volume'],
        marker_color=colors_volume,
        opacity=0.7,
        hovertemplate='<b>%{x}</b><br>Volume: %{y:,.0f}<extra></extra>'
    ))
    
    return apply_premium_layout(fig, height=280, title="Trading Volume", show_legend=False)

def create_intel_suite(df):
    """Enhanced intelligence suite with improved indicators"""
    if df.empty:
        return go.Figure()
    
    fig = make_subplots(
        rows=3, cols=1,
        vertical_spacing=0.08,
        row_heights=[0.2, 0.5, 0.3],
        subplot_titles=("RSI Indicator", "Price & Moving Averages", "Volume Profile")
    )
    
    # RSI with colored zones
    fig.add_trace(go.Scatter(
        x=df['Date'],
        y=df['RSI_14'],
        name='RSI',
        line=dict(color=colors['accent_cyan'], width=2.5),
        hovertemplate='RSI: %{y:.2f}<extra></extra>'
    ), row=1, col=1)
    
    # RSI zones
    fig.add_hrect(y0=70, y1=100, fillcolor=colors['negative'], opacity=0.1, row=1, col=1)
    fig.add_hrect(y0=0, y1=30, fillcolor=colors['positive'], opacity=0.1, row=1, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color=colors['negative'], line_width=1, row=1, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color=colors['positive'], line_width=1, row=1, col=1)
    fig.add_hline(y=50, line_dash="dot", line_color=colors['text_muted'], line_width=1, row=1, col=1)
    
    # Price
    fig.add_trace(go.Scatter(
        x=df['Date'],
        y=df['Close'],
        name='Price',
        line=dict(color='white', width=3),
        hovertemplate='Price: $%{y:.2f}<extra></extra>'
    ), row=2, col=1)
    
    # Moving Averages
    if 'MA_30' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['Date'],
            y=df['MA_30'],
            name='MA 30',
            line=dict(color=colors['accent_purple'], width=2, dash='dot'),
            hovertemplate='MA30: $%{y:.2f}<extra></extra>'
        ), row=2, col=1)
    
    if 'MA_7' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['Date'],
            y=df['MA_7'],
            name='MA 7',
            line=dict(color=colors['accent_pink'], width=2, dash='dash'),
            hovertemplate='MA7: $%{y:.2f}<extra></extra>'
        ), row=2, col=1)
    
    # Volume
    colors_volume = [colors['positive'] if row['Close'] >= row['Open'] else colors['negative'] 
                     for _, row in df.iterrows()]
    fig.add_trace(go.Bar(
        x=df['Date'],
        y=df['Volume'],
        name='Volume',
        marker_color=colors_volume,
        opacity=0.6
    ), row=3, col=1)
    
    apply_premium_layout(fig, height=750, show_legend=True)
    
    fig.update_yaxes(title_text="RSI", row=1, col=1, range=[0, 100])
    fig.update_yaxes(title_text="Price ($)", row=2, col=1)
    fig.update_yaxes(title_text="Volume", row=3, col=1)
    
    return fig

def create_risk_suite(df):
    """Enhanced risk analysis suite"""
    if df.empty:
        return go.Figure()
    
    fig = make_subplots(
        rows=1, cols=2,
        horizontal_spacing=0.12,
        subplot_titles=("Return Distribution", "Volatility Analysis")
    )
    
    # Return Distribution Histogram
    fig.add_trace(go.Histogram(
        x=df['Daily_Return'],
        name='Returns',
        marker_color=colors['accent_cyan'],
        opacity=0.75,
        nbinsx=30,
        hovertemplate='Return: %{x:.2%}<br>Count: %{y}<extra></extra>'
    ), row=1, col=1)
    
    # Add mean line
    mean_return = df['Daily_Return'].mean()
    fig.add_vline(
        x=mean_return,
        line_dash="dash",
        line_color=colors['warning'],
        line_width=2,
        row=1, col=1
    )
    
    # Volatility over time
    if 'Volatility_7' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['Date'],
            y=df['Volatility_7'],
            name='7-Day Volatility',
            line=dict(color=colors['accent_purple'], width=2.5),
            fill='tozeroy',
            fillcolor='rgba(167, 139, 250, 0.2)',
            hovertemplate='Volatility: %{y:.4f}<extra></extra>'
        ), row=1, col=2)
    
    apply_premium_layout(fig, height=450)
    
    fig.update_xaxes(title_text="Daily Return", row=1, col=1)
    fig.update_xaxes(title_text="Date", row=1, col=2)
    fig.update_yaxes(title_text="Frequency", row=1, col=1)
    fig.update_yaxes(title_text="Volatility", row=1, col=2)
    
    return fig

def create_correlation_matrix(df):
    """Create correlation heatmap for technical indicators"""
    if df.empty:
        return go.Figure()
    
    # Select numerical columns for correlation
    corr_cols = ['Close', 'Volume', 'RSI_14', 'Daily_Return']
    available_cols = [col for col in corr_cols if col in df.columns]
    
    if len(available_cols) < 2:
        return go.Figure()
    
    corr_matrix = df[available_cols].corr()
    
    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix.values,
        x=available_cols,
        y=available_cols,
        colorscale=[
            [0, colors['negative']],
            [0.5, '#1E293B'],
            [1, colors['positive']]
        ],
        zmid=0,
        text=corr_matrix.values,
        texttemplate='%{text:.2f}',
        textfont={"size": 12},
        hovertemplate='%{x} vs %{y}<br>Correlation: %{z:.3f}<extra></extra>'
    ))
    
    return apply_premium_layout(fig, height=400, title="Correlation Matrix")

def create_stats_panel(df):
    """Enhanced statistics panel with premium styling"""
    if df.empty:
        return html.Div("No Data Available", className='stat-card')
    
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    change = latest['Close'] - prev['Close']
    pct = (change / prev['Close']) * 100
    is_positive = change >= 0
    
    return html.Div([
        # Main Price Card
        html.Div([
            html.Div("CURRENT PRICE", className='stat-label'),
            html.Div(f"${latest['Close']:,.2f}", className='stat-value'),
            html.Div([
                html.I(className=f"fas fa-arrow-{'up' if is_positive else 'down'}"),
                html.Span(f"${abs(change):.2f} ({abs(pct):.2f}%)"),
            ], className=f"stat-change {'positive' if is_positive else 'negative'}")
        ], className='stat-card', style={'flex': '2', 'minWidth': '280px'}),
        
        # Period High
        html.Div([
            html.Div("PERIOD HIGH", className='stat-label'),
            html.Div(f"${df['High'].max():,.2f}", className='stat-value', 
                    style={'fontSize': '2rem'}),
            html.Div([
                html.I(className="fas fa-chart-line", 
                      style={'color': colors['positive'], 'fontSize': '0.9rem'})
            ], style={'marginTop': '8px'})
        ], className='stat-card', style={'flex': '1', 'minWidth': '200px'}),
        
        # Period Low
        html.Div([
            html.Div("PERIOD LOW", className='stat-label'),
            html.Div(f"${df['Low'].min():,.2f}", className='stat-value',
                    style={'fontSize': '2rem'}),
            html.Div([
                html.I(className="fas fa-chart-line", 
                      style={'color': colors['negative'], 'fontSize': '0.9rem'})
            ], style={'marginTop': '8px'})
        ], className='stat-card', style={'flex': '1', 'minWidth': '200px'}),
        
        # Average Volume
        html.Div([
            html.Div("AVG VOLUME", className='stat-label'),
            html.Div(f"{df['Volume'].mean()/1e6:.1f}M", className='stat-value',
                    style={'fontSize': '2rem'}),
            html.Div([
                html.I(className="fas fa-signal", 
                      style={'color': colors['accent_purple'], 'fontSize': '0.9rem'})
            ], style={'marginTop': '8px'})
        ], className='stat-card', style={'flex': '1', 'minWidth': '200px'}),
        
    ], style={
        'display': 'flex',
        'gap': '24px',
        'marginBottom': '40px',
        'flexWrap': 'wrap'
    })

# --- View Generators ---

def create_markets_view(df, ticker):
    """Enhanced markets view"""
    return html.Div([
        dbc.Row([
            dbc.Col(
                html.Div([
                    dcc.Graph(
                        figure=create_candlestick_chart(df, ticker),
                        config={'displayModeBar': True, 'displaylogo': False}
                    )
                ], className='glass-panel chart-container'),
                width=12
            )
        ], style={'marginBottom': '30px'}),
        
        dbc.Row([
            dbc.Col(
                html.Div([
                    dcc.Graph(
                        figure=create_volume_chart(df),
                        config={'displayModeBar': True, 'displaylogo': False}
                    )
                ], className='glass-panel chart-container'),
                width=12
            )
        ])
    ])

def create_intel_view(df):
    """Enhanced intelligence view"""
    return html.Div([
        dbc.Row([
            dbc.Col(
                html.Div([
                    dcc.Graph(
                        figure=create_intel_suite(df),
                        config={'displayModeBar': True, 'displaylogo': False}
                    )
                ], className='glass-panel chart-container'),
                width=12
            )
        ])
    ])

def create_risk_view(df):
    """Enhanced risk view"""
    return html.Div([
        dbc.Row([
            dbc.Col(
                html.Div([
                    dcc.Graph(
                        figure=create_risk_suite(df),
                        config={'displayModeBar': True, 'displaylogo': False}
                    )
                ], className='glass-panel chart-container'),
                width=12
            )
        ], style={'marginBottom': '30px'}),
        
        dbc.Row([
            dbc.Col(
                html.Div([
                    dcc.Graph(
                        figure=create_correlation_matrix(df),
                        config={'displayModeBar': True, 'displaylogo': False}
                    )
                ], className='glass-panel chart-container'),
                width=12
            )
        ])
    ])

# --- Main Layout ---

app.layout = html.Div([
    dcc.Store(id='active-view', data='markets'),
    
    # Sidebar
    html.Div([
        # Logo Section
        html.Div([
            html.Div("QUANTUM", className='logo-title'),
            html.Div("ETL ANALYTICS", className='logo-subtitle')
        ], className='logo-section'),
        
        # Navigation
        html.Div([
            html.Div("MAIN VIEWS", className='nav-section-title'),
            html.Div([
                html.I(className="fas fa-chart-candlestick nav-icon"),
                "Markets"
            ], id='view-markets', className='nav-pill active'),
            
            html.Div([
                html.I(className="fas fa-brain nav-icon"),
                "Intelligence"
            ], id='view-intel', className='nav-pill'),
            
            html.Div([
                html.I(className="fas fa-shield-halved nav-icon"),
                "Risk Analysis"
            ], id='view-risk', className='nav-pill'),
        ], className='nav-section'),
        
        # Footer
        html.Div([
            html.Div([
                html.Div(className='status-dot'),
                html.Span("STABLE v2.0")
            ], className='version-badge')
        ], style={'marginTop': 'auto', 'paddingTop': '40px'})
    ], className='sidebar'),
    
    # Main Content Area
    html.Div([
        # Header Section
        html.Div([
            html.Div([
                dcc.Dropdown(
                    id='ticker-dropdown',
                    options=[
                        {'label': f'{t}', 'value': t}
                        for t in ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA', 'AMD', 'META', 'AMZN', 'NFLX', 'GOOG']
                    ],
                    value='AAPL',
                    clearable=False,
                    style={
                        'width': '200px',
                        'marginRight': '20px',
                        'fontWeight': '600',
                        'fontSize': '14px'
                    }
                ),
                
                html.Button(
                    [html.I(className="fas fa-calendar-day", style={'marginRight': '8px'}), '1M'],
                    id='btn-1m',
                    className='btn-ghost active'
                ),
                html.Button(
                    [html.I(className="fas fa-calendar-alt", style={'marginRight': '8px'}), '1Y'],
                    id='btn-1y',
                    className='btn-ghost',
                    style={'marginLeft': '12px'}
                ),
            ], className='header-controls'),
            
            html.Button(
                [html.I(className="fas fa-sync-alt", style={'marginRight': '10px'}), 'REFRESH'],
                id='refresh-btn',
                className='btn-primary'
            )
        ], className='header-section'),
        
        # Statistics Panel
        html.Div(id='stats'),
        
        # Dynamic Content with Loading
        dcc.Loading(
            id='main-loading',
            children=[html.Div(id='view-content')],
            type='circle',
            color=colors['accent_cyan']
        )
    ], className='content-area')
])


@app.callback(
    [Output('active-view', 'data'),
     Output('view-markets', 'className'),
     Output('view-intel', 'className'),
     Output('view-risk', 'className')],
    [Input('view-markets', 'n_clicks'),
     Input('view-intel', 'n_clicks'),
     Input('view-risk', 'n_clicks')],
    [State('active-view', 'data')]
)
def switch_dashboard_view(n1, n2, n3, current):
    """Handle view switching"""
    ctx = dash.callback_context
    if not ctx.triggered:
        return current, 'nav-pill active', 'nav-pill', 'nav-pill'
    
    btn_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    views = {
        'view-markets': ('markets', 'nav-pill active', 'nav-pill', 'nav-pill'),
        'view-intel': ('intel', 'nav-pill', 'nav-pill active', 'nav-pill'),
        'view-risk': ('risk', 'nav-pill', 'nav-pill', 'nav-pill active')
    }
    
    return views.get(btn_id, views['view-markets'])

@app.callback(
    [Output('view-content', 'children'),
     Output('stats', 'children'),
     Output('btn-1m', 'className'),
     Output('btn-1y', 'className')],
    [Input('active-view', 'data'),
     Input('ticker-dropdown', 'value'),
     Input('btn-1m', 'n_clicks'),
     Input('btn-1y', 'n_clicks'),
     Input('refresh-btn', 'n_clicks')]
)
def refresh_engine(view, ticker, n_m, n_y, n_r):
    """Main data refresh and view rendering"""
    ctx = dash.callback_context
    period = '1mo'
    m_class, y_class = 'btn-ghost active', 'btn-ghost'
    
    if ctx.triggered:
        btn_id = ctx.triggered[0]['prop_id'].split('.')[0]
        if btn_id == 'btn-1y':
            period = '1y'
            m_class, y_class = 'btn-ghost', 'btn-ghost active'
        if btn_id == 'refresh-btn':
            get_cached_data.cache_clear()
    
    data = get_data_with_cache(ticker, period)
    
    if not data:
        err_msg = html.Div([
            html.I(className="fas fa-exclamation-triangle", 
                  style={'fontSize': '3rem', 'color': colors['negative'], 'marginBottom': '20px'}),
            html.H3("DATA FEED UNAVAILABLE", 
                   style={'color': colors['text'], 'fontWeight': '700'}),
            html.P("Unable to connect to transform service", 
                  style={'color': colors['text_secondary']})
        ], style={
            'textAlign': 'center',
            'padding': '100px',
            'color': colors['text']
        })
        return err_msg, None, m_class, y_class
    
    df = pd.DataFrame(data)
    stats = create_stats_panel(df)
    
    # Route to appropriate view
    view_map = {
        'markets': create_markets_view(df, ticker),
        'intel': create_intel_view(df),
        'risk': create_risk_view(df)
    }
    
    content = view_map.get(view, create_markets_view(df, ticker))
    
    return content, stats, m_class, y_class

# Flask routes for health checks
from flask import Flask, jsonify
import psutil

server = app.server

@server.route('/health')
def health_check():
    """Comprehensive health check"""
    start_time = time.time()
    
    checks = {
        "service": "visualization-service",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }
    
    try:
        memory_percent = psutil.virtual_memory().percent
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        checks["checks"]["memory"] = "healthy" if memory_percent < 80 else "degraded"
        checks["memory_usage_percent"] = round(memory_percent, 1)
        
        checks["checks"]["cpu"] = "healthy" if cpu_percent < 80 else "degraded"
        checks["cpu_usage_percent"] = round(cpu_percent, 1)
        
    except Exception as e:
        checks["checks"]["system"] = f"degraded - {str(e)[:50]}"
    
    try:
        transform_url = os.getenv('TRANSFORM_SERVICE_URL', 'http://localhost:8001')
        response = requests.get(f'{transform_url}/health', timeout=3)
        checks["checks"]["transform_service"] = "healthy" if response.status_code == 200 else "degraded"
    except Exception as e:
        checks["checks"]["transform_service"] = f"unhealthy - {str(e)[:50]}"
    
    response_time = (time.time() - start_time) * 1000
    checks["response_time_ms"] = round(response_time, 2)
    checks["checks"]["response_time"] = "healthy" if response_time < 2000 else "degraded"
    
    unhealthy = sum(1 for c in checks["checks"].values() if "unhealthy" in str(c))
    degraded = sum(1 for c in checks["checks"].values() if "degraded" in str(c))
    
    checks["status"] = "unhealthy" if unhealthy > 0 else ("degraded" if degraded > 0 else "healthy")
    
    return jsonify(checks)

@server.route('/refresh')
def refresh_dashboard():
    """Trigger dashboard refresh"""
    try:
        get_cached_data.cache_clear()
        return jsonify({
            "message": "Dashboard cache cleared successfully",
            "timestamp": datetime.now().isoformat(),
            "status": "success"
        })
    except Exception as e:
        return jsonify({
            "error": f"Failed to refresh: {str(e)}",
            "timestamp": datetime.now().isoformat(),
            "status": "error"
        }), 500

if __name__ == '__main__':
    app.run_server(debug=False, host='0.0.0.0', port=8002)
