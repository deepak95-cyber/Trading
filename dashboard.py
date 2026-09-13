import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Stock Trading Journal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- DASHBOARD DARK THEME CSS ---
st.html("""
<style>
    .stApp {
        background-color: #0b0f17 !important;
        color: #94a3b8 !important;
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
    }
    .header-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background-color: #0f172a;
        padding: 12px 24px;
        border-radius: 12px;
        border: 1px solid #1e293b;
        margin-bottom: 20px;
    }
    .header-title {
        font-size: 20px;
        font-weight: 700;
        color: #f8fafc;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .header-subtitle { font-size: 13px; color: #64748b; }
    .header-stats { display: flex; align-items: center; gap: 20px; font-size: 14px; }
    .market-badge {
        background-color: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.3);
        color: #10b981;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 1px solid #1e293b;
        padding-bottom: 8px;
        margin-bottom: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #0f172a !important;
        border: 1px solid #1e293b !important;
        border-radius: 8px !important;
        color: #94a3b8 !important;
        padding: 8px 16px !important;
        font-weight: 500 !important;
        font-size: 14px !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: #064e3b !important;
        border: 1px solid #10b981 !important;
        color: #34d399 !important;
    }
    .kpi-card {
        background-color: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 16px 20px;
        height: 100%;
    }
    .kpi-title { font-size: 11px; font-weight: 700; color: #64748b; letter-spacing: 0.05em; margin-bottom: 8px; }
    .kpi-value { font-size: 28px; font-weight: 800; color: #f8fafc; margin-bottom: 4px; line-height: 1.1; }
    .kpi-sub { font-size: 12px; color: #64748b; }
    .section-card {
        background-color: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
    }
    .section-title { font-size: 16px; font-weight: 700; color: #f8fafc; margin-bottom: 2px; }
    .section-desc { font-size: 12px; color: #64748b; margin-bottom: 16px; }
    .callout-box { border-radius: 8px; padding: 14px; margin-bottom: 12px; font-size: 13px; line-height: 1.5; }
    .callout-green { background-color: rgba(6, 78, 59, 0.2); border: 1px solid rgba(16, 185, 129, 0.3); color: #34d399; }
    .callout-red { background-color: rgba(127, 29, 29, 0.2); border: 1px solid rgba(239, 68, 68, 0.3); color: #f87171; }
    .callout-blue { background-color: rgba(30, 58, 138, 0.2); border: 1px solid rgba(59, 130, 246, 0.3); color: #60a5fa; }
    .calc-display-green { background-color: rgba(6, 78, 59, 0.2); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; padding: 16px; margin-bottom: 12px; }
    .calc-display-blue { background-color: rgba(30, 58, 138, 0.2); border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 8px; padding: 16px; }
    .stTextInput input, .stNumberInput input, .stSelectbox > div > div { background-color: #0b0f17 !important; border: 1px solid #334155 !important; color: #f8fafc !important; border-radius: 6px !important; }
    label { color: #94a3b8 !important; font-size: 12px !important; font-weight: 600 !important; }
    .streamlit-expanderHeader { background-color: #0b0f17 !important; color: #34d399 !important; border-radius: 8px; border: 1px solid #1e293b; }
    div[data-testid="stForm"] { border: 1px solid #1e293b !important; background-color: #0f172a !important; border-radius: 12px !important; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""")

# --- INITIALIZE SESSION STATE FOR PLANNER & TABLE SCREENSHOTS ---
if 'selected_symbol' not in st.session_state:
    st.session_state['selected_symbol'] = "CUPID"
if 'entry_input' not in st.session_state:
    st.session_state['entry_input'] = 132.20
if 'sl_input' not in st.session_state:
    st.session_state['sl_input'] = 126.00
if 'table_screenshots' not in st.session_state:
    st.session_state['table_screenshots'] = {}

def select_trade(sym, entry, sl):
    st.session_state['selected_symbol'] = sym
    st.session_state['entry_input'] = float(entry)
    st.session_state['sl_input'] = float(sl)

# --- GOOGLE SHEETS CONNECTION ---
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def get_gspread_client():
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPE)
    return gspread.authorize(creds)

SPREADSHEET_ID = "1wptuCk60b7_mfD4jwGEuKs2NhubbhGjjxOzidGPpb2M"

def load_data():
    try:
        gc = get_gspread_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.worksheet("DTrades")
        rows = worksheet.get_all_values()
        if not rows:
            return pd.DataFrame()
        
        headers = rows[0]
        data = rows[1:]
        
        unique_headers = []
        counts = {}
        for h in headers:
            clean = h.strip().replace('\n', ' ') if h else "Unnamed"
            counts[clean] = counts.get(clean, 0) + 1
            unique_headers.append(f"{clean}_{counts[clean]}" if counts[clean] > 1 else clean)
            
        df = pd.DataFrame(data, columns=unique_headers)
        inst_col = next((c for c in df.columns if 'instrument' in c.lower() or 'ticker' in c.lower()), None)
        if inst_col:
            df = df[df[inst_col].astype(str).str.strip() != ''].copy()
        return df
    except Exception:
        return pd.DataFrame()

df = load_data()

def find_col(df, name):
    for c in df.columns:
        if name.lower() in c.lower():
            return c
    return None

# Capital Stats
initial_cap = 100000.0
pl_col = find_col(df, "p/l") or find_col(df, "realised") or find_col(df, "pl")

if not df.empty and pl_col:
    df['PL_Num'] = pd.to_numeric(
        df[pl_col].astype(str).str.replace(',', '').str.replace('₹', '').str.strip(), 
        errors='coerce'
    ).fillna(0.0)
    total_pl = float(df['PL_Num'].sum())
else:
    df['PL_Num'] = 0.0
    total_pl = 0.0

curr_cap = initial_cap + total_pl
ytd_pct = (total_pl / initial_cap) * 100

st.html(f"""
<div class="header-bar">
    <div>
        <div class="header-title">📈 Stock Trading Journal</div>
        <div class="header-subtitle">Deepak Mahesh • Performance Hub</div>
    </div>
    <div class="header-stats">
        <div>Capital: <b style="color:#f8fafc;">₹{curr_cap:,.0f}</b></div>
        <div>YTD P/L: <b style="color:#10b981;">+₹{total_pl:,.0f} (+{ytd_pct:.2f}%)</b></div>
        <div class="market-badge">🟢 Market Phase: GREEN</div>
    </div>
</div>
""")

# --- NAVIGATION TABS ---
tab_dash, tab_open, tab_rr, tab_log, tab_size, tab_rules = st.tabs([
    "📊 Dashboard", 
    "🔓 Open Positions",
    "🎯 Trade Planner (R:R)", 
    f"📋 Trade Log ({len(df)})", 
    "🧮 Position Sizer", 
    "📖 Rules & Playbook"
])

# ==========================================
# TAB 1: DASHBOARD
# ==========================================
with tab_dash:
    pct_col_name = None
    for col in df.columns:
        if '%' in col or 'gain' in col.lower() or 'pct' in col.lower() or 'return' in col.lower():
            pct_col_name = col
            break

    if pct_col_name:
        df['Pct_Num'] = pd.to_numeric(
            df[pct_col_name].astype(str).str.replace('%', '').str.replace(',', '').str.strip(), 
            errors='coerce'
        ).fillna(0.0)
    else:
        entry_col = find_col(df, "entry") or find_col(df, "buy")
        qty_col = find_col(df, "qty") or find_col(df, "quantity")
        if entry_col and qty_col:
            entry_val = pd.to_numeric(df[entry_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            qty_val = pd.to_numeric(df[qty_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            buy_val = entry_val * qty_val
            df['Pct_Num'] = (df['PL_Num'] / buy_val.replace(0, pd.NA)).fillna(0.0) * 100
        else:
            df['Pct_Num'] = 0.0

    wins = df[df['PL_Num'] > 0]
    losses = df[df['PL_Num'] < 0]
    total_trades = len(df)
    win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0.0

    avg_win_pct = float(wins['Pct_Num'].mean()) if not wins.empty else 0.0
    avg_loss_pct = float(losses['Pct_Num'].mean()) if not losses.empty else 0.0

    inst_col = find_col(df, "instrument") or find_col(df, "ticker") or (df.columns[2] if len(df.columns) > 2 else df.columns[0])
    best_trade = "N/A"
    worst_trade = "N/A"

    if not wins.empty and 'Pct_Num' in wins:
        best_idx = wins['Pct_Num'].idxmax()
        if pd.notnull(best_idx):
            best_trade = f"+{wins.loc[best_idx, 'Pct_Num']:.1f}% ({wins.loc[best_idx, inst_col]})"

    if not losses.empty and 'Pct_Num' in losses:
        worst_idx = losses['Pct_Num'].idxmin()
        if pd.notnull(worst_idx):
            worst_trade = f"{losses.loc[worst_idx, 'Pct_Num']:.1f}% ({losses.loc[worst_idx, inst_col]})"

    if not df.empty:
        df['Cumulative_PL'] = df['PL_Num'].cumsum()
        df['Cumulative_Pct'] = (df['Cumulative_PL'] / initial_cap) * 100
        df['Trade_Num'] = range(1, len(df) + 1)
        peak_pct = float(df['Cumulative_Pct'].max())
    else:
        df['Trade_Num'] = []
        df['Cumulative_Pct'] = []
        peak_pct = 0.0

    # Section 1: Top Metrics Bar
    k1, k2, k3, k4, k5, k6 = st.columns(6)

    k1.html(f"""
    <div class="kpi-card">
        <div class="kpi-title">TOTAL TRADES</div>
        <div class="kpi-value">{total_trades}</div>
        <div class="kpi-sub"><span style="color:#34d399;">{len(wins)} Wins</span> • <span style="color:#f87171;">{len(losses)} Losses</span></div>
    </div>
    """)

    k2.html(f"""
    <div class="kpi-card">
        <div class="kpi-title">WIN RATE</div>
        <div class="kpi-value" style="color:#34d399;">{win_rate:.2f}%</div>
        <div class="kpi-sub">Target: &gt; 40%</div>
    </div>
    """)

    k3.html(f"""
    <div class="kpi-card">
        <div class="kpi-title">AVG WIN (GAIN)</div>
        <div class="kpi-value" style="color:#34d399;">+{avg_win_pct:.2f}%</div>
        <div class="kpi-sub">Best: <span style="color:#34d399;">{best_trade}</span></div>
    </div>
    """)

    k4.html(f"""
    <div class="kpi-card">
        <div class="kpi-title">AVG LOSS</div>
        <div class="kpi-value" style="color:#f87171;">{avg_loss_pct:.2f}%</div>
        <div class="kpi-sub">Worst: <span style="color:#f87171;">{worst_trade}</span></div>
    </div>
    """)

    k5.html("""
    <div class="kpi-card">
        <div class="kpi-title">AVG R:R RATIO</div>
        <div class="kpi-value" style="color:#60a5fa;">2.80</div>
        <div class="kpi-sub">Reward to Risk</div>
    </div>
    """)

    k6.html("""
    <div class="kpi-card">
        <div class="kpi-title">PLAN FOLLOWED</div>
        <div class="kpi-value" style="color:#a855f7;">42.31%</div>
        <div class="kpi-sub" style="color:#f87171;">Needs Improvement</div>
    </div>
    """)

    st.html("<br>")

    # Section 2: Main Performance Charts & Setup Breakdown
    c_left, c_right = st.columns([1.7, 1])

    with c_left:
        st.html(f"""
        <div class="section-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <div class="section-title">Equity Curve (% Growth)</div>
                    <div class="section-desc">Trade-by-Trade Cumulative Return (Starting: ₹100,000)</div>
                </div>
                <div style="background-color:rgba(16, 185, 129, 0.1); border:1px solid rgba(16, 185, 129, 0.3); color:#34d399; padding:4px 10px; border-radius:12px; font-size:11px; font-weight:600;">
                    Peak: +{peak_pct:.2f}%
                </div>
            </div>
        """)
        
        fig = px.line(df, x='Trade_Num', y='Cumulative_Pct', markers=True)
        fig.update_traces(
            line_color="#10b981", 
            line_width=2.5, 
            fill='tozeroy',
            fillcolor='rgba(16, 185, 129, 0.08)',
            marker=dict(size=6, color="#10b981"),
            hovertemplate="Trade #%{x}<br>Return: %{y:.2f}%<extra></extra>"
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=10, b=20),
            height=280,
            xaxis=dict(showgrid=False, color="#64748b", title="Trade Number"),
            yaxis=dict(showgrid=True, gridcolor="#1e293b", color="#64748b", title=None, ticksuffix="%")
        )
        st.plotly_chart(fig, use_container_width=True)
        st.html("</div>")

    with c_right:
        st.html("""
        <div class="section-card">
            <div class="section-title">Trades by Setup</div>
            <div class="section-desc">Win rate distribution across entry setups</div>
        """)
        
        labels = ['20 UC', 'IPO Base', 'Flag Pattern']
        values = [12, 8, 6]
        colors = ['#10b981', '#3b82f6', '#8b5cf6']
        
        fig_pie = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.7, marker=dict(colors=colors))])
        fig_pie.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=0, b=0),
            height=180,
            showlegend=False
        )
        st.plotly_chart(fig_pie, use_container_width=True)
        
        st.html("""
        <div style="font-size:12px; color:#94a3b8; display:grid; grid-template-columns: 1fr 1fr; gap:8px; border-top:1px solid #1e293b; padding-top:12px;">
            <div><span style="color:#10b981;">■</span> 20 UC Setup: <b>12 trades</b></div>
            <div><span style="color:#3b82f6;">■</span> IPO Base: <b>8 trades</b></div>
            <div><span style="color:#8b5cf6;">■</span> Flag Pattern: <b>6 trades</b></div>
            <div>Best Setup: <b style="color:#f59e0b;">CUPID 20 UC</b></div>
        </div>
        </div>
        """)

    # Section 3: Monthly Ledger & Portfolio Observations
    m_left, m_right = st.columns([1.3, 1])

    with m_left:
        st.html("""
        <div class="section-card" style="height:100%;">
            <div class="section-title">Monthly Summary Ledger</div>
            <div class="section-desc" style="margin-bottom:12px;">Capital growth, charges, and monthly net gains breakdown</div>
            
            <div style="overflow-x:auto;">
                <table style="width:100%; font-size:12px; text-align:left; border-collapse:collapse; color:#94a3b8;">
                    <thead>
                        <tr style="border-bottom:1px solid #1e293b; color:#64748b; font-size:11px; text-transform:uppercase;">
                            <th style="padding:10px 6px;">MONTH</th>
                            <th style="padding:10px 6px;">START CAP</th>
                            <th style="padding:10px 6px;">REALISED P/L</th>
                            <th style="padding:10px 6px;">CHARGES</th>
                            <th style="padding:10px 6px;">NET %</th>
                            <th style="padding:10px 6px;">FINAL CAP</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr style="border-bottom:1px solid #1e293b; height:42px;">
                            <td style="padding:6px; font-weight:700; color:#f8fafc;">May 2026</td>
                            <td style="padding:6px; color:#cbd5e1;">₹100,000</td>
                            <td style="padding:6px; color:#34d399; font-weight:600;">+₹6,948</td>
                            <td style="padding:6px; color:#f87171;">₹0</td>
                            <td style="padding:6px; color:#34d399; font-weight:600;">+5.08%</td>
                            <td style="padding:6px; color:#f8fafc; font-weight:700;">₹100,000</td>
                        </tr>
                        <tr style="border-bottom:1px solid #1e293b; height:42px;">
                            <td style="padding:6px; font-weight:700; color:#f8fafc;">June 2026</td>
                            <td style="padding:6px; color:#cbd5e1;">₹100,000</td>
                            <td style="padding:6px; color:#34d399; font-weight:600;">+₹2,619</td>
                            <td style="padding:6px; color:#f87171;">₹327</td>
                            <td style="padding:6px; color:#34d399; font-weight:600;">+2.29%</td>
                            <td style="padding:6px; color:#f8fafc; font-weight:700;">₹102,292</td>
                        </tr>
                        <tr style="border-bottom:1px solid #1e293b; height:42px;">
                            <td style="padding:6px; font-weight:700; color:#f8fafc;">July 2026</td>
                            <td style="padding:6px; color:#cbd5e1;">₹102,292</td>
                            <td style="padding:6px; color:#34d399; font-weight:600;">+₹5,443</td>
                            <td style="padding:6px; color:#f87171;">₹445</td>
                            <td style="padding:6px; color:#34d399; font-weight:600;">+4.89%</td>
                            <td style="padding:6px; color:#f8fafc; font-weight:700;">₹107,290</td>
                        </tr>
                        <tr style="height:42px;">
                            <td style="padding:6px; font-weight:700; color:#f8fafc;">August 2026</td>
                            <td style="padding:6px; color:#cbd5e1;">₹107,290</td>
                            <td style="padding:6px; color:#f87171; font-weight:600;">-₹151</td>
                            <td style="padding:6px; color:#f87171;">₹362</td>
                            <td style="padding:6px; color:#f87171; font-weight:600;">-0.48%</td>
                            <td style="padding:6px; color:#f8fafc; font-weight:700;">₹106,777</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
        """)

    with m_right:
        st.html("""
        <div class="section-card" style="height:100%;">
            <div class="section-title">Key Portfolio Observations</div>
            <div class="section-desc" style="margin-bottom:12px;">Execution insights, winner analysis, and risk notes</div>
            
            <div class="callout-box callout-green" style="margin-bottom:10px;">
                <b style="font-size:13px;">🏆 Star Trade: CUPID (+52.60%)</b><br>
                Bought at ₹132.20 on 26-May with 20 UC setup. Held for 43 days and scaled out up to ₹224. Total Profit: ₹6,948 (+6.63% PF impact).
            </div>
            
            <div class="callout-box callout-red" style="margin-bottom:10px;">
                <b style="font-size:13px;">⚠️ Area for Improvement: FOMO & Stop Losses</b><br>
                Multiple tight stop-outs observed in illiquid and 5% circuit stocks (e.g. VEDPOWER). Need to keep SL &lt; 4% and avoid buying late into extended rallies.
            </div>
            
            <div class="callout-box callout-blue">
                <b style="font-size:13px;">💡 Pyramiding Execution</b><br>
                Successfully pyramided in HSCL and CUPID. Remember rule: Never merge 1st and 2nd position SLs unless 2nd position candle has high volume confirmation.
            </div>
        </div>
        """)

# ==========================================
# TAB 2: OPEN POSITIONS
# ==========================================
with tab_open:
    status_col = find_col(df, "status")
    inst_col_name = find_col(df, "instrument") or find_col(df, "ticker")
    entry_col_name = find_col(df, "entry")
    sl_col_name = find_col(df, "sl")
    qty_col_name = find_col(df, "qty") or find_col(df, "quantity")
    cmp_col_name = find_col(df, "cmp") or find_col(df, "current")

    # Helper function to extract numeric values safely from columns
    def get_num(row, col_name_str):
        if not col_name_str:
            return 0.0
        val = str(row.get(col_name_str, '')).replace(',', '').replace('₹', '').strip()
        num = pd.to_numeric(val, errors='coerce')
        return float(num) if pd.notnull(num) else 0.0

    # Locate Pyramid & Exit QTY Columns dynamically
    p1_qty_col = find_col(df, "p1 qty") or find_col(df, "pyramid 1 qty") or find_col(df, "p-1 qty") or find_col(df, "p1_qty")
    p2_qty_col = find_col(df, "p2 qty") or find_col(df, "pyramid 2 qty") or find_col(df, "p-2 qty") or find_col(df, "p2_qty")
    
    e1_qty_col = find_col(df, "exit 1 qty") or find_col(df, "exit-1 qty") or find_col(df, "ex1 qty") or find_col(df, "ex1_qty")
    e2_qty_col = find_col(df, "exit 2 qty") or find_col(df, "exit-2 qty") or find_col(df, "ex2 qty") or find_col(df, "ex2_qty")
    e3_qty_col = find_col(df, "exit 3 qty") or find_col(df, "exit-3 qty") or find_col(df, "ex3 qty") or find_col(df, "ex3_qty")

    open_positions_raw = []

    if not df.empty and inst_col_name:
        # Check for explicitly labeled open trades or positions missing exit status
        if status_col:
            open_df = df[df[status_col].astype(str).str.lower().str.contains("open", na=False)].copy()
        else:
            open_df = pd.DataFrame()

        # Fallback filter: rows with an entry price but no exit status marked closed
        if open_df.empty and entry_col_name:
            open_df = df[
                df[entry_col_name].astype(str).str.strip().ne('') & 
                ~df[status_col].astype(str).str.lower().str.contains("closed", na=False)
            ].copy()

        open_metadata = {
            "CUPID": {"earnings": date(2026, 9, 14)},
            "HSCL": {"earnings": date(2026, 9, 22)},
            "CMRGREEN": {"earnings": date(2026, 10, 8)}
        }

        for _, r in open_df.iterrows():
            ticker = str(r[inst_col_name]).strip().upper()
            entry_p = get_num(r, entry_col_name)
            sl_p = get_num(r, sl_col_name)
            cmp_p = get_num(r, cmp_col_name)
            if cmp_p <= 0:
                cmp_p = entry_p

            initial_qty = int(get_num(r, qty_col_name))
            p1_qty = int(get_num(r, p1_qty_col))
            p2_qty = int(get_num(r, p2_qty_col))
            
            ex1_qty = int(get_num(r, e1_qty_col))
            ex2_qty = int(get_num(r, e2_qty_col))
            ex3_qty = int(get_num(r, e3_qty_col))

            # Dynamic Quantity Calculations from Excel / Sheet inputs
            total_pos_qty = initial_qty + p1_qty + p2_qty
            total_exited_qty = ex1_qty + ex2_qty + ex3_qty
            open_pos_qty = max(0, total_pos_qty - total_exited_qty)

            # Use active open_pos_qty for valuation and risk calculations (fall back to total_pos_qty if open is 0)
            calc_qty = open_pos_qty if open_pos_qty > 0 else total_pos_qty

            risk_per_share = max(entry_p - sl_p, 0.0)
            total_risk = risk_per_share * calc_qty
            risk_pct_cap = (total_risk / curr_cap) * 100 if curr_cap > 0 else 0.0
            position_val = entry_p * calc_qty
            unrealised_pl = (cmp_p - entry_p) * calc_qty

            meta = open_metadata.get(ticker, {"earnings": None})

            open_positions_raw.append({
                "Ticker": ticker,
                "Total QTY": total_pos_qty,
                "Open QTY": open_pos_qty,
                "Entry Price": entry_p,
                "CMP": cmp_p,
                "Stop Loss": sl_p,
                "Position Value": position_val,
                "Open Risk (₹)": total_risk,
                "Risk % Capital": risk_pct_cap,
                "Unrealised P/L": unrealised_pl,
                "Earnings Date": meta["earnings"]
            })

    today_date = date.today()
    caution_threshold_days = 10

    total_invested_amt = sum(x["Position Value"] for x in open_positions_raw)
    total_invested_pct = (total_invested_amt / curr_cap) * 100 if curr_cap > 0 else 0.0
    total_open_risk_amt = sum(x["Open Risk (₹)"] for x in open_positions_raw)
    total_open_risk_pct = (total_open_risk_amt / curr_cap) * 100 if curr_cap > 0 else 0.0
    active_count = len(open_positions_raw)
    total_unrealised = sum(x["Unrealised P/L"] for x in open_positions_raw)

    o1, o2, o3, o4, o5 = st.columns(5)

    o1.html(f"""
    <div class="kpi-card">
        <div class="kpi-title">ACTIVE POSITIONS</div>
        <div class="kpi-value">{active_count}</div>
        <div class="kpi-sub">Open Positions</div>
    </div>
    """)

    o2.html(f"""
    <div class="kpi-card">
        <div class="kpi-title">CAPITAL INVESTED</div>
        <div class="kpi-value" style="color:#60a5fa;">₹{total_invested_amt:,.2f}</div>
        <div class="kpi-sub">{total_invested_pct:.1f}% Deployed</div>
    </div>
    """)

    o3.html(f"""
    <div class="kpi-card">
        <div class="kpi-title">TOTAL OPEN RISK</div>
        <div class="kpi-value" style="color:#f87171;">₹{total_open_risk_amt:,.2f}</div>
        <div class="kpi-sub">{total_open_risk_pct:.2f}% of Total Capital</div>
    </div>
    """)

    o4.html(f"""
    <div class="kpi-card">
        <div class="kpi-title">UNREALISED P/L</div>
        <div class="kpi-value" style="color:{'#34d399' if total_unrealised >= 0 else '#f87171'};">
            {'+' if total_unrealised >= 0 else ''}₹{total_unrealised:,.2f}
        </div>
        <div class="kpi-sub">Open Positions Gain/Loss</div>
    </div>
    """)

    o5.html("""
    <div class="kpi-card">
        <div class="kpi-title">RISK STATUS</div>
        <div class="kpi-value" style="color:#34d399;">SAFE</div>
        <div class="kpi-sub">Max Total Risk Cap: 3.0%</div>
    </div>
    """)

    st.html("<br>")

    st.html("""
    <div class="section-card">
        <div class="section-title">🔓 Active Holdings & Risk Matrix</div>
        <div class="section-desc">Live open risk calculations and days remaining to earnings</div>
    </div>
    """)

    table_rows_html = ""
    for pos in open_positions_raw:
        e_date = pos["Earnings Date"]
        if e_date:
            days_rem = (e_date - today_date).days
            date_str = e_date.strftime("%d-%b-%Y")
            
            if days_rem <= caution_threshold_days:
                earnings_badge = f'<div style="background-color:rgba(239, 68, 68, 0.2); border:1px solid rgba(239, 68, 68, 0.6); color:#f87171; padding:6px 10px; border-radius:6px; font-weight:700; text-align:center;">⚠️ {date_str}<br><span style="font-size:11px;">({days_rem} Days Left - CAUTION)</span></div>'
            else:
                earnings_badge = f'<div style="background-color:rgba(16, 185, 129, 0.1); border:1px solid rgba(16, 185, 129, 0.3); color:#34d399; padding:6px 10px; border-radius:6px; text-align:center;">📅 {date_str}<br><span style="font-size:11px;">({days_rem} Days Away)</span></div>'
        else:
            earnings_badge = '<span style="color:#64748b;">N/A</span>'

        p_pl = pos["Unrealised P/L"]
        pl_color = "#34d399" if p_pl >= 0 else "#f87171"
        pl_sign = "+" if p_pl >= 0 else ""

        table_rows_html += f"""
        <tr style="border-bottom:1px solid #1e293b; height:50px;">
            <td style="padding:10px; font-weight:700; color:#f8fafc;">{pos['Ticker']}</td>
            <td style="padding:10px; color:#cbd5e1; font-weight:600;">{pos['Total QTY']}</td>
            <td style="padding:10px; color:#34d399; font-weight:700;">{pos['Open QTY']}</td>
            <td style="padding:10px; color:#cbd5e1;">₹{pos['Entry Price']:,.2f}</td>
            <td style="padding:10px; color:#f8fafc; font-weight:600;">₹{pos['CMP']:,.2f}</td>
            <td style="padding:10px; color:#f87171;">₹{pos['Stop Loss']:,.2f}</td>
            <td style="padding:10px; color:#cbd5e1;">₹{pos['Position Value']:,.2f}</td>
            <td style="padding:10px; color:#f87171;">₹{pos['Open Risk (₹)']:,.2f}</td>
            <td style="padding:10px; color:#94a3b8;">{pos['Risk % Capital']:.2f}%</td>
            <td style="padding:10px; color:{pl_color}; font-weight:700;">{pl_sign}₹{p_pl:,.2f}</td>
            <td style="padding:6px;">{earnings_badge}</td>
        </tr>
        """

    st.html(f"""
    <div style="background-color:#0f172a; border:1px solid #1e293b; border-radius:10px; padding:12px; overflow-x:auto;">
        <table style="width:100%; font-size:12px; text-align:left; border-collapse:collapse; color:#94a3b8;">
            <thead>
                <tr style="border-bottom:1px solid #1e293b; color:#64748b; font-size:11px; text-transform:uppercase;">
                    <th style="padding:10px;">Ticker</th>
                    <th style="padding:10px;">Total QTY</th>
                    <th style="padding:10px;">Open QTY</th>
                    <th style="padding:10px;">Entry Price</th>
                    <th style="padding:10px;">CMP</th>
                    <th style="padding:10px;">Stop Loss</th>
                    <th style="padding:10px;">Pos Value</th>
                    <th style="padding:10px;">Open Risk (₹)</th>
                    <th style="padding:10px;">Risk % Cap</th>
                    <th style="padding:10px;">Unrealised P/L</th>
                    <th style="padding:10px; text-align:center;">Upcoming Earnings & Days Left</th>
                </tr>
            </thead>
            <tbody>
                {table_rows_html}
            </tbody>
        </table>
    </div>
    """)

# ==========================================
# TAB 3: TRADE PLANNER
# ==========================================
with tab_rr:
    col_open, col_calc = st.columns([1.25, 1])

    # Left Column: Open Trades Exit Signals Panel with Line Bar Visualizers
    with col_open:
        st.html("""
        <div class="section-card" style="padding:16px;">
            <div class="section-title">📂 Open Trades Exit Signals & R-Scale Visualizer</div>
            <div class="section-desc">Tracks current market price (LTP) against SL, Entry, 2R, and 4R milestone zones</div>
        </div>
        """)

        open_trades = []
        status_col = find_col(df, "status")
        inst_col_name = find_col(df, "instrument") or find_col(df, "ticker")
        entry_col_name = find_col(df, "entry")
        sl_col_name = find_col(df, "sl")
        cmp_col_name = find_col(df, "cmp") or find_col(df, "current")

        if not df.empty and inst_col_name:
            if status_col:
                open_df = df[df[status_col].astype(str).str.lower().str.contains("open", na=False)].copy()
            else:
                open_df = pd.DataFrame()

            if open_df.empty and entry_col_name:
                open_df = df[
                    df[entry_col_name].astype(str).str.strip().ne('') & 
                    ~df[status_col].astype(str).str.lower().str.contains("closed", na=False)
                ].copy()

            for _, row in open_df.iterrows():
                sym = str(row[inst_col_name]).strip().upper()
                e_val = pd.to_numeric(str(row[entry_col_name]).replace(',', '').replace('₹', ''), errors='coerce') if entry_col_name else 0.0
                s_val = pd.to_numeric(str(row[sl_col_name]).replace(',', '').replace('₹', ''), errors='coerce') if sl_col_name else 0.0
                c_val = pd.to_numeric(str(row[cmp_col_name]).replace(',', '').replace('₹', ''), errors='coerce') if cmp_col_name else e_val

                e_val = e_val if (pd.notnull(e_val) and e_val > 0) else 0.0
                s_val = s_val if (pd.notnull(s_val) and s_val > 0) else 0.0
                c_val = c_val if (pd.notnull(c_val) and c_val > 0) else e_val

                if e_val > s_val and e_val > 0:
                    r = e_val - s_val
                    open_trades.append({
                        'symbol': sym,
                        'entry': float(e_val),
                        'sl': float(s_val),
                        'cmp': float(c_val),
                        'risk': float(r),
                        '2r': float(e_val + 2 * r),
                        '4r': float(e_val + 4 * r)
                    })

        for ot in open_trades:
            e = ot['entry']
            sl = ot['sl']
            cmp = ot['cmp']
            r2 = ot['2r']
            r4 = ot['4r']
            risk = ot['risk']

            r_multiple = (cmp - e) / risk if risk > 0 else 0.0

            scale_min = sl
            scale_max = r4
            scale_range = scale_max - scale_min

            if scale_range > 0:
                pct_pos = max(0.0, min(100.0, ((cmp - scale_min) / scale_range) * 100.0))
            else:
                pct_pos = 0.0

            if r_multiple >= 4.0:
                status_label = "🔥 4R Hit! Book 1/3 or 1/2"
                status_color = "#a855f7"
            elif r_multiple >= 2.0:
                status_label = "🎯 2R Hit! SL to Breakeven"
                status_color = "#34d399"
            elif r_multiple >= 0:
                status_label = "🟢 In Profit (Building R)"
                status_color = "#60a5fa"
            else:
                status_label = "⚠️ Pullback / Near SL"
                status_color = "#f87171"

            card_col, btn_col = st.columns([3.7, 1.3])
            
            with card_col:
                st.html(f"""
                <div style="background-color:#0b0f17; border:1px solid #1e293b; border-radius:10px; padding:14px; margin-bottom:14px;">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
                        <div>
                            <b style="color:#f8fafc; font-size:17px;">{ot['symbol']}</b>
                            <span style="font-size:11px; background-color:rgba(255,255,255,0.05); color:{status_color}; padding:2px 8px; border-radius:10px; margin-left:6px; font-weight:600;">
                                {status_label}
                            </span>
                        </div>
                        <div style="text-align:right;">
                            <span style="font-size:11px; color:#64748b;">LTP:</span> 
                            <b style="font-size:15px; color:#f8fafc;">₹{cmp:,.2f}</b> 
                            <span style="font-size:12px; color:{status_color}; font-weight:700; margin-left:4px;">({r_multiple:+.2f}R)</span>
                        </div>
                    </div>
                    
                    <div style="display:flex; justify-content:space-between; font-size:11px; color:#64748b; margin-bottom:6px;">
                        <span>SL: <b style="color:#f87171;">₹{sl:.2f}</b></span>
                        <span>Entry: <b style="color:#f8fafc;">₹{e:.2f}</b></span>
                        <span>2R: <b style="color:#34d399;">₹{r2:.2f}</b></span>
                        <span>4R: <b style="color:#a855f7;">₹{r4:.2f}</b></span>
                    </div>

                    <div style="position:relative; width:100%; height:10px; background-color:#1e293b; border-radius:6px; margin:10px 0 6px 0;">
                        <div style="position:absolute; top:0; left:0; height:100%; width:{pct_pos:.1f}%; background:linear-gradient(90deg, #f87171 0%, #3b82f6 30%, #34d399 70%, #a855f7 100%); border-radius:6px;"></div>
                        <div style="position:absolute; top:-2px; left:{((e-sl)/scale_range)*100:.1f}%; width:2px; height:14px; background-color:#f8fafc;" title="Entry Price"></div>
                        <div style="position:absolute; top:-2px; left:{((r2-sl)/scale_range)*100:.1f}%; width:2px; height:14px; background-color:#34d399;" title="2R Target"></div>
                        <div style="position:absolute; top:-4px; left:calc({pct_pos:.1f}% - 5px); width:10px; height:18px; background-color:#ffffff; border:2px solid {status_color}; border-radius:3px; box-shadow: 0 0 6px {status_color};" title="Current Price: ₹{cmp:.2f}"></div>
                    </div>

                    <div style="display:flex; justify-content:space-between; font-size:10px; color:#475569; font-weight:600;">
                        <span>0R (SL)</span>
                        <span>1R (Entry)</span>
                        <span>3R</span>
                        <span>5R (4R Exit)</span>
                    </div>
                </div>
                """)

            with btn_col:
                st.button(
                    f"Load {ot['symbol']}", 
                    key=f"load_btn_{ot['symbol']}", 
                    on_click=select_trade, 
                    args=(ot['symbol'], ot['entry'], ot['sl'])
                )

    # Right Column: Target & R:R Calculator
    with col_calc:
        current_sym = st.session_state['selected_symbol']
        
        st.html(f"""
        <div class="section-card" style="padding:16px;">
            <div class="section-title">🎯 Target & R:R Matrix ({current_sym})</div>
            <div class="section-desc">Calculates target levels up to 50% consolidation zone</div>
        </div>
        """)

        r_in1, r_in2 = st.columns(2)
        
        p_entry_rr = r_in1.number_input("Entry Price (₹)", step=0.5, key="entry_input")
        p_sl_rr = r_in2.number_input("Stop Loss Price (₹)", step=0.5, key="sl_input")

        if p_entry_rr > p_sl_rr and p_entry_rr > 0:
            risk_sh = p_entry_rr - p_sl_rr
            risk_pct_rr = (risk_sh / p_entry_rr) * 100

            st.html(f"""
            <div style="background-color:rgba(239, 68, 68, 0.1); border:1px solid rgba(239, 68, 68, 0.3); padding:8px 12px; border-radius:8px; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:12px; color:#94a3b8;">Calculated 1R Risk:</span>
                <b style="font-size:14px; color:#f87171;">₹{risk_sh:.2f} ({risk_pct_rr:.2f}%)</b>
            </div>
            """)

            targets_ext = [5, 8, 10, 15, 20, 25, 30, 40, 50]
            rows_list = []
            for t in targets_ext:
                tgt_p = p_entry_rr * (1 + t / 100)
                rew = tgt_p - p_entry_rr
                rr = rew / risk_sh
                
                action = "-"
                if t == 10: action = "Monitor Momentum"
                elif t == 15: action = "Move SL to Breakeven (2R)"
                elif t == 20: action = "Sell 1/3 or 1/2 Position (4R)"
                elif t == 25: action = "Trail SL with 10 EMA"
                elif t == 30: action = "Book 75% Profits"
                elif t == 40: action = "Runner / Major Exit"
                elif t == 50: action = "⚡ Final Exit / Consolidation Zone"

                rows_list.append(
                    f'<tr style="border-bottom:1px solid #1e293b;">'
                    f'<td style="padding:8px 0; font-weight:600; color:#34d399;">{t}%</td>'
                    f'<td style="color:#f8fafc;">₹{tgt_p:.2f}</td>'
                    f'<td style="color:#f8fafc;">₹{rew:.2f}</td>'
                    f'<td style="color:#60a5fa; font-weight:700;">{rr:.1f} R</td>'
                    f'<td style="color:#94a3b8; font-size:11px;">{action}</td>'
                    f'</tr>'
                )

            table_body = "".join(rows_list)
            st.html(f"""
            <div style="background-color:#0f172a; border:1px solid #1e293b; border-radius:8px; padding:12px;">
                <table style="width:100%; font-size:11px; text-align:left; border-collapse:collapse; color:#94a3b8;">
                    <tr style="border-bottom:1px solid #1e293b; color:#64748b;">
                        <th style="padding:6px 0;">TARGET %</th>
                        <th>TARGET PRICE</th>
                        <th>REWARD</th>
                        <th>R:R RATIO</th>
                        <th>ACTION</th>
                    </tr>
                    {table_body}
                </table>
            </div>
            """)

# ==========================================
# TAB 4: TRADE LOG & FORM
# ==========================================
with tab_log:
    st.html("""
    <div class="section-card">
        <div class="section-title">Log New Position</div>
        <div class="section-desc">Appends all 35 columns into your Google Sheet journal</div>
    </div>
    """)
    
    with st.form("comprehensive_trade_form", clear_on_submit=True):
        st.markdown("<h4 style='color:#f8fafc; margin-bottom:10px;'>1. Primary Entry Details</h4>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        t_date = c1.date_input("Date", datetime.now())
        t_inst = c2.text_input("Instrument / Ticker", value="CUPID")
        t_strike = c3.text_input("Strike (Options / Equity EQ)", value="")
        t_type = c4.selectbox("Buy / Sell Type", ["B", "S"])
        
        c5, c6, c7, c8 = st.columns(4)
        t_entry = c5.number_input("Entry Price (₹)", min_value=0.0, value=132.20, step=0.1)
        t_sl = c6.number_input("Stop Loss Price (₹)", min_value=0.0, value=126.00, step=0.1)
        t_tsl = c7.number_input("Trailing Stop Loss (TSL ₹)", min_value=0.0, value=0.0, step=0.1)
        t_cmp = c8.number_input("Current Market Price (CMP ₹)", min_value=0.0, value=132.20, step=0.1)

        c9, c10, c11, c12 = st.columns(4)
        t_setup = c9.selectbox("Setup Pattern", ["20 UC", "IPO Base", "Flag Pattern", "VCP", "Cheat", "20 EMA Bounce", "High Tight Flag"])
        t_duration = c10.selectbox("Base Duration", ["<1 W", "1-2 W", "2 W", "1 M", "2 M", ">3 M"])
        t_qty = c11.number_input("Initial QTY", min_value=1, value=50, step=1)
        chart_image = c12.file_uploader("Upload Chart Screenshot", type=["png", "jpg", "jpeg"])

        with st.expander("🔽 Expand to add Pyramids (P-1, P-2) & Exits (Exit 1 to 4)"):
            st.markdown("<h5 style='color:#34d399;'>Pyramiding Additions</h5>", unsafe_allow_html=True)
            p1, p2, p3 = st.columns(3)
            t_p1_price = p1.number_input("Pyramid-1 Price (₹)", min_value=0.0, value=0.0, step=0.1)
            t_p1_qty = p2.number_input("Pyramid-1 QTY", min_value=0, value=0, step=1)
            t_p1_date = p3.date_input("Pyramid-1 Date", value=None)

            p4, p5, p6 = st.columns(3)
            t_p2_price = p4.number_input("Pyramid-2 Price (₹)", min_value=0.0, value=0.0, step=0.1)
            t_p2_qty = p5.number_input("Pyramid-2 QTY", min_value=0, value=0, step=1)
            t_p2_date = p6.date_input("Pyramid-2 Date", value=None)

            st.markdown("<h5 style='color:#60a5fa; margin-top:10px;'>Scale-Out Exits</h5>", unsafe_allow_html=True)
            e1, e2, e3 = st.columns(3)
            t_ex1_price = e1.number_input("Exit-1 Price (₹)", min_value=0.0, value=0.0, step=0.1)
            t_ex1_qty = e2.number_input("Exit-1 QTY", min_value=0, value=0, step=1)
            t_ex1_date = e3.date_input("Exit-1 Date", value=None)

            e4, e5, e6 = st.columns(3)
            t_ex2_price = e4.number_input("Exit-2 Price (₹)", min_value=0.0, value=0.0, step=0.1)
            t_ex2_qty = e5.number_input("Exit-2 QTY", min_value=0, value=0, step=1)
            t_ex2_date = e6.date_input("Exit-2 Date", value=None)

            e7, e8, e9 = st.columns(3)
            t_ex3_price = e7.number_input("Exit-3 Price (₹)", min_value=0.0, value=0.0, step=0.1)
            t_ex3_qty = e8.number_input("Exit-3 QTY", min_value=0, value=0, step=1)
            t_ex3_date = e9.date_input("Exit-3 Date", value=None)

            st.markdown("<h5 style='color:#a855f7; margin-top:10px;'>Trade Status & Analytics</h5>", unsafe_allow_html=True)
            a1, a2, a3 = st.columns(3)
            t_status = a1.selectbox("Position Status", ["Open", "Closed", "Partial Exit"])
            t_heat = a2.number_input("Open Heat %", min_value=0.0, value=0.0, step=0.1)
            t_notes = a3.text_input("Trade Notes / Learnings", value="")

        submit_btn = st.form_submit_button("Submit & Save Complete Trade to Sheet")

        if submit_btn:
            try:
                gc = get_gspread_client()
                sh = gc.open_by_key(SPREADSHEET_ID)
                ws = sh.worksheet("DTrades")

                chart_val = chart_image.name if chart_image is not None else ""

                new_row = [
                    "",
                    t_date.strftime("%d-%b-%y") if t_date else "",
                    t_inst.upper(),
                    t_strike,
                    t_type,
                    t_entry if t_entry > 0 else "",
                    t_entry if t_entry > 0 else "",
                    t_sl if t_sl > 0 else "",
                    t_tsl if t_tsl > 0 else "",
                    t_type,
                    t_cmp if t_cmp > 0 else "",
                    t_setup,
                    t_duration,
                    t_qty,
                    t_p1_price if t_p1_price > 0 else "",
                    t_p1_qty if t_p1_qty > 0 else "",
                    t_p1_date.strftime("%d-%b-%y") if t_p1_date else "",
                    t_p2_price if t_p2_price > 0 else "",
                    t_p2_qty if t_p2_qty > 0 else "",
                    t_p2_date.strftime("%d-%b-%y") if t_p2_date else "",
                    "", "", "",
                    t_ex1_price if t_ex1_price > 0 else "",
                    t_ex1_qty if t_ex1_qty > 0 else "",
                    t_ex1_date.strftime("%d-%b-%y") if t_ex1_date else "",
                    t_ex2_price if t_ex2_price > 0 else "",
                    t_ex2_qty if t_ex2_qty > 0 else "",
                    t_ex2_date.strftime("%d-%b-%y") if t_ex2_date else "",
                    t_ex3_price if t_ex3_price > 0 else "",
                    t_ex3_qty if t_ex3_qty > 0 else "",
                    "", "", "", "", "",
                    t_heat if t_heat > 0 else 0.0,
                    "", "",
                    t_status,
                    chart_val
                ]

                ws.append_row(new_row)
                st.success("Trade log successfully appended to Google Sheet!")
            except Exception as e:
                st.error(f"Error submitting to Google Sheet: {e}")

    st.html("""
    <div class="section-card" style="margin-top: 20px;">
        <div class="section-title">✏️ Live Interactive Trade Log Table</div>
        <div class="section-desc">Edit values directly in table cells below, manage chart screenshots per symbol, and click "Save Table Changes to Sheet"</div>
    </div>
    """)

    if not df.empty:
        display_cols = [c for c in df.columns if c not in ['PL_Num', 'Pct_Num', 'Cumulative_PL', 'Cumulative_Pct', 'Trade_Num']]
        
        table_df = df[display_cols].copy()
        if 'Chart Screenshot' not in table_df.columns:
            table_df['Chart Screenshot'] = ""

        cols_order = [c for c in table_df.columns if c != 'Chart Screenshot'] + ['Chart Screenshot']
        table_df = table_df[cols_order]

        inst_col_name = find_col(table_df, "instrument") or find_col(table_df, "ticker") or table_df.columns[1]

        for idx in table_df.index:
            if idx in st.session_state['table_screenshots']:
                table_df.at[idx, 'Chart Screenshot'] = st.session_state['table_screenshots'][idx]

        edited_df = st.data_editor(
            table_df,
            use_container_width=True,
            num_rows="dynamic",
            key="trade_log_editor",
            column_config={
                "Chart Screenshot": st.column_config.TextColumn(
                    "Chart Screenshot",
                    help="Filename of uploaded screenshot for this trade row",
                    disabled=False
                )
            }
        )

        with st.expander("📷 Upload & Manage Screenshots Per Symbol"):
            st.markdown("<p style='font-size:12px; color:#94a3b8;'>Select the specific row to attach or update its chart screenshot file:</p>", unsafe_allow_html=True)
            
            date_col_name = find_col(edited_df, "date") or edited_df.columns[0]
            entry_col_name = find_col(edited_df, "entry") or edited_df.columns[2]

            row_options = {}
            for idx, r in edited_df.iterrows():
                sym_val = str(r[inst_col_name]).strip().upper() if pd.notnull(r[inst_col_name]) else "N/A"
                dt_val = str(r[date_col_name]).strip() if pd.notnull(r[date_col_name]) else ""
                en_val = str(r[entry_col_name]).strip() if pd.notnull(r[entry_col_name]) else ""
                
                label = f"Row {idx + 1}: {sym_val}"
                if dt_val:
                    label += f" ({dt_val}"
                    if en_val:
                        label += f" @ ₹{en_val}"
                    label += ")"
                elif en_val:
                    label += f" (@ ₹{en_val})"
                    
                row_options[label] = idx

            if row_options:
                s_col1, s_col2 = st.columns([1.2, 1.8])
                with s_col1:
                    selected_label = st.selectbox(
                        "Select Specific Trade Row to Upload Screenshot", 
                        options=list(row_options.keys()), 
                        key="table_row_select"
                    )
                    selected_idx = row_options[selected_label]
                    selected_sym = str(edited_df.loc[selected_idx, inst_col_name]).strip().upper()

                    up_file = st.file_uploader(
                        f"Upload Chart Image for {selected_label}", 
                        type=["png", "jpg", "jpeg"], 
                        key=f"uploader_row_{selected_idx}"
                    )
                    
                    if up_file is not None:
                        st.session_state['table_screenshots'][selected_idx] = up_file.name
                        st.success(f"Attached screenshot '{up_file.name}' to {selected_label}")

                with s_col2:
                    current_attached = st.session_state['table_screenshots'].get(selected_idx, "None attached")
                    st.markdown(f"**Target Row:** `{selected_label}`")
                    st.markdown(f"**Current Attached File:** `{current_attached}`")
                    if up_file is not None:
                        st.image(up_file, caption=f"Chart Preview for {selected_label}", use_container_width=True)

        if st.button("💾 Save Table Changes to Sheet"):
            try:
                gc = get_gspread_client()
                sh = gc.open_by_key(SPREADSHEET_ID)
                ws = sh.worksheet("DTrades")

                updated_headers = edited_df.columns.tolist()
                updated_rows = [updated_headers] + edited_df.fillna("").values.tolist()

                ws.clear()
                ws.update(range_name="A1", values=updated_rows)

                st.success("Google Sheet updated successfully with live table edits and chart screenshot references!")
                st.cache_resource.clear()
            except Exception as e:
                st.error(f"Failed to update Google Sheet: {e}")
    else:
        st.info("No trade records loaded from Google Sheet yet.")

# ==========================================
# TAB 5: POSITION SIZER
# ==========================================
with tab_size:
    st.html("""
    <div class="section-card">
        <div class="section-title">🧮 Interactive Position Sizing Calculator</div>
        <div class="section-desc">Calculate exact quantity based on Risk % on Capital OR Fixed Portfolio Allocation.</div>
    </div>
    """)
    
    col_in, col_out = st.columns([1, 1.2])
    
    with col_in:
        p_cap = st.number_input("Total Account Capital (₹)", value=100000.0, step=1000.0)
        p_entry = st.number_input("Entry Price (₹)", value=419.0, step=1.0)
        p_sl = st.number_input("Stop Loss Price (₹)", value=411.0, step=1.0)
        
        r_col, a_col = st.columns(2)
        p_risk_pct = r_col.number_input("Risk on Capital %", value=0.40, step=0.05)
        p_alloc_pct = a_col.number_input("Target Allocation %", value=10.00, step=0.5)

    with col_out:
        if p_entry > p_sl and p_entry > 0:
            sl_dist_pct = ((p_entry - p_sl) / p_entry) * 100
            risk_per_sh = p_entry - p_sl
            
            max_risk_amt = p_cap * (p_risk_pct / 100)
            qty_m1 = int(max_risk_amt / risk_per_sh)
            alloc_m1 = qty_m1 * p_entry
            alloc_m1_pct = (alloc_m1 / p_cap) * 100
            
            st.html(f"""
            <div class="calc-display-green">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <div style="font-size:11px; font-weight:700; color:#34d399;">METHOD 1: RISK ON CAPITAL</div>
                    <div style="font-size:11px; color:#94a3b8;">Max Risk Amount: <b>₹{max_risk_amt:.2f}</b> | SL Distance: <b>{sl_dist_pct:.2f}%</b></div>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:baseline;">
                    <div style="font-size:14px; font-weight:700; color:#f8fafc;">BUY QTY:</div>
                    <div style="font-size:36px; font-weight:900; color:#34d399;">{qty_m1}</div>
                </div>
                <div style="font-size:12px; color:#64748b; margin-top:4px;">Capital Allocated: <b>₹{alloc_m1:,.0f} ({alloc_m1_pct:.2f}%)</b></div>
            </div>
            """)
            
            target_alloc_amt = p_cap * (p_alloc_pct / 100)
            qty_m2 = int(target_alloc_amt / p_entry)
            actual_risk_m2 = qty_m2 * risk_per_sh
            actual_risk_m2_pct = (actual_risk_m2 / p_cap) * 100
            
            st.html(f"""
            <div class="calc-display-blue">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <div style="font-size:11px; font-weight:700; color:#60a5fa;">METHOD 2: FIXED ALLOCATION</div>
                    <div style="font-size:11px; color:#94a3b8;">Allocated Capital: <b>₹{target_alloc_amt:,.0f}</b></div>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:baseline;">
                    <div style="font-size:14px; font-weight:700; color:#f8fafc;">BUY QTY:</div>
                    <div style="font-size:36px; font-weight:900; color:#60a5fa;">{qty_m2}</div>
                </div>
                <div style="font-size:12px; color:#64748b; margin-top:4px;">Actual Risk on Total Capital: <b>{actual_risk_m2_pct:.2f}% (₹{actual_risk_m2:.2f})</b></div>
            </div>
            """)

# ==========================================
# TAB 6: RULES & PLAYBOOK
# ==========================================
with tab_rules:
    st.html("""
    <div class="section-card">
        <div class="section-title">📖 Rules & Execution Playbook</div>
        <div class="section-desc">Core trading system rules and trade management principles</div>
        
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-top:16px;">
            <div class="callout-box callout-green">
                <b style="font-size:14px;">Entry & Risk Rules</b>
                <ul style="margin-top:8px; padding-left:16px;">
                    <li>Max Risk per trade: Never exceed 0.50% of total capital.</li>
                    <li>Always trade in alignment with Market Phase GREEN.</li>
                    <li>Only trade high volume breakout setups (20 UC, IPO Base, VCP).</li>
                </ul>
            </div>
            <div class="callout-box callout-blue">
                <b style="font-size:14px;">Exit & Pyramiding Rules</b>
                <ul style="margin-top:8px; padding-left:16px;">
                    <li>Move SL to breakeven at +2R gain.</li>
                    <li>Scale out 50% position at +4R gain.</li>
                    <li>Never merge 1st and 2nd position SLs without volume confirmation.</li>
                </ul>
            </div>
        </div>
    </div>
    """)