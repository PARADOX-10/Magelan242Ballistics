import streamlit as st
import pandas as pd
import numpy as np
import math
import plotly.graph_objects as go

st.set_page_config(page_title="Magelan Ballistics Pro", layout="centered")

# --- ПРЕСЕТИ ---
PRESETS = {
    "Мій .300 Win Mag (195gr)": {
        "cal": 0.308, "weight": 195.0, "len": 1.450, 
        "bc_g7": 0.292, "bc_g1": 0.584, "v0": 893.0, "twist": 11.0
    }
}

# --- ТЕМА ---
if 'night' not in st.session_state: st.session_state.night = False
night = st.session_state.night
bg, txt, acc, card = ("#0A0000", "#FF0000", "#CC0000", "#1A0000") if night else ("#0E1117", "#FFFFFF", "#C62828", "#1E1E1E")

st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg}; color: {txt}; }}
    .hud-card {{ background-color: {card}; border-radius: 10px; padding: 12px; text-align: center; border-left: 4px solid {acc}; margin-bottom: 5px; }}
    .hud-label {{ color: {'#660000' if night else '#888'}; font-size: 11px; font-weight: bold; text-transform: uppercase; }}
    .hud-value {{ color: {txt}; font-size: 32px; font-weight: 900; }}
    .stButton>button {{ width: 100%; background-color: {card}; color: {txt}; border: 1px solid {acc}; }}
    </style>
    """, unsafe_allow_html=True)

# --- БАЛІСТИЧНЕ ЯДРО ---
def get_ballistics(p, d):
    if d <= 0: return {"v": 0, "h": 0, "side": "П", "v_at": p['v0'], "mach": 0, "sg": 0, "tof": 0, "cor_cm": 0}
    
    # Повітря
    e_sat = 6.112 * math.exp((17.67 * p['temp']) / (p['temp'] + 243.5))
    rho = ((p['press'] - (p['hum']/100)*e_sat) * 100 / (287.05 * (p['temp'] + 273.15)))
    
    # Опір
    bc_adj = p['bc'] * (1.225 / rho)
    k = 0.5 * rho * (1/bc_adj) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    
    tof = (math.exp(k * d) - 1) / (k * p['v0'])
    v_at = p['v0'] * math.exp(-k * d)
    mach = v_at / (331.3 * math.sqrt(1 + p['temp'] / 273.15))

    # Коріоліс
    omega = 7.2921e-5
    lat_r = math.radians(p['lat'])
    az_r = math.radians(p['az'])
    cor_h_cm = abs(2 * omega * d * p['v0'] * math.sin(lat_r) * tof / d) * 100
    cor_v = 2 * omega * d * p['v0'] * math.cos(lat_r) * math.sin(az_r) * tof / d

    # Поправки
    wind_x = p['w_speed'] * math.sin(math.radians(p['w_hour'] * 30))
    aj = 0.012 * wind_x * (d / 100) / 10 * (1 if p['tw_d'] == "R" else -1)
    
    t_z = (math.exp(k * p['zero']) - 1) / (k * p['v0'])
    drop = -((0.5 * 9.806 * tof**2) - (0.5 * 9.806 * t_z**2 + p['sh']/100) * (d / p['zero']) + p['sh']/100)
    
    v_mil = abs((drop + cor_v) * 100 / (d/10) / 0.1) + aj
    sd = 1.25 * (p['tw_v'] / 10 + 1.2) * (tof**1.83) * (1 if p['tw_d'] == "R" else -1)
    cor_h = 2 * omega * d * p['v0'] * math.sin(lat_r) * tof / d
    h_mil = (wind_x * (tof - d/p['v0']) + sd + cor_h) * 100 / (d/10) / 0.1

    m_lb, m_cal = p['weight'] / 7000, p['cal']
    sg = (30 * m_lb) / ( (p['tw_v']/m_cal)**2 * m_cal**3 * (p['len']/m_cal) * (1 + (p['len']/m_cal)**2) ) * (p['v0']/2800)**(1/3)

    return {"v": round(v_mil, 2), "h": round(abs(h_mil), 2), "side": "Л" if h_mil < 0 else "П", "v_at": int(v_at), "mach": round(mach, 2), "sg": round(sg, 2), "tof": round(tof, 3), "cor_cm": cor_h_cm}

# --- ІНТЕРФЕЙС ---
st.button("🌙 НІЧНИЙ РЕЖИМ", on_click=lambda: st.session_state.update({'night': not st.session_state.night}))

preset_name = st.selectbox("ОБЕРІТЬ НАБІЙ:", list(PRESETS.keys()))
defaults = PRESETS[preset_name]

st.markdown('<div style="position: sticky; top: 0; background: #0E1117; z-index: 100; padding: 10px 0; border-bottom: 2px solid red;">', unsafe_allow_html=True)
dist = st.slider("🎯 ДИСТАНЦІЯ ДО ЦІЛІ (м)", 0, 1800, 800, step=5)
h_c1, h_c2 = st.columns(2)
st.markdown('</div>', unsafe_allow_html=True)

# Секції параметрів (з поясненнями)
with st.expander("🔫 1. ПАРАМЕТРИ ЗБРОЇ", expanded=True):
    st.caption("Базові характеристики вашого стрілецького комплексу.")
    m_mod = st.radio("Драг-модель", ["G7", "G1"], horizontal=True, help="Для .300 WM 195gr обирайте G7.")
    c1, c2 = st.columns(2)
    v0 = c1.number_input("V0 (м/с)", value=float(defaults['v0']), help="Швидкість кулі.")
    bc = c2.number_input("БК", value=float(defaults['bc_g7'] if m_mod=="G7" else defaults['bc_g1']), format="%.3f")
    tw = c1.number_input("Твіст 1:", value=float(defaults['twist']))
    sh = c2.number_input("Висота оптики (см)", value=5.0)

with st.expander("🌍 2. ПРИРОДНІ ФАКТОРИ"):
    st.caption("Зовнішні умови, що змінюють щільність повітря та зносять кулю.")
    t = st.slider("Температура (°C)", -30, 50, 15)
    p_at = st.number_input("Тиск (гПа)", value=1013)
    ws = st.slider("Вітер (м/с)", 0, 20, 3)
    wh = st.slider("Напрямок (год)", 1, 12, 3)

with st.expander("🛰️ 3. ГЕОПОЗИЦІЯ"):
    st.caption("Корекція на обертання планети (Коріоліс та Етвеш).")
    lat = st.number_input("Широта", value=50)
    az = st.slider("Азимут", 0, 360, 90)

# РОЗРАХУНОК
final_p = {**defaults, 'temp':t,'press':p_at,'hum':50,'v0':v0,'bc':bc,'model':m_mod,'lat':lat,'az':az,'tw_v':tw,'tw_d':"R",'sh':sh,'zero':100,'w_speed':ws,'w_hour':wh}
res = get_ballistics(final_p, dist)

# HUD
h_c1.markdown(f'<div class="hud-card"><div class="hud-label">Вгору (MIL)</div><div class="hud-value">↑ {res["v"]}</div></div>', unsafe_allow_html=True)
h_c2.markdown(f'<div class="hud-card"><div class="hud-label">Бік ({res["side"]}) MIL</div><div class="hud-value">↔ {res["h"]}</div></div>', unsafe_allow_html=True)

# ГРАФІК ШВИДКОСТІ (MACH)
st.divider()
st.subheader("📊 Графік енергії та стабільності")


distances = np.arange(0, 1600, 20)
mach_values = [get_ballistics(final_p, d)['mach'] for d in distances]

fig = go.Figure()
fig.add_trace(go.Scatter(x=distances, y=mach_values, name="Швидкість (Mach)", line=dict(color='red', width=3)))
fig.add_hline(y=1.2, line_dash="dash", line_color="orange", annotation_text="Межа трансзвуку (Mach 1.2)")
fig.add_hline(y=1.0, line_dash="dot", line_color="white", annotation_text="Швидкість звуку")

fig.update_layout(
    title="Падіння швидкості відносно дистанції",
    xaxis_title="Відстань (м)",
    yaxis_title="Число Маха",
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(color="white")
)
st.plotly_chart(fig)

if res['mach'] < 1.2:
    st.error(f"⚠️ ПОПЕРЕДЖЕННЯ: Куля в трансзвуковій зоні (Mach {res['mach']}). Точність не гарантована.")
    
else:
    st.success(f"✅ Куля стабільна (Mach {res['mach']})")
