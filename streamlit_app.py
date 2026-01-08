import streamlit as st
import pandas as pd
import numpy as np
import math

st.set_page_config(page_title="Magelan Tactical", layout="centered")

# --- ЛОГІКА ТЕМИ ---
if 'night_mode' not in st.session_state:
    st.session_state.night_mode = False

def toggle_mode():
    st.session_state.night_mode = not st.session_state.night_mode

# --- АДАПТИВНА СТИЛІЗАЦІЯ ---
night = st.session_state.night_mode
bg_color = "#0A0000" if night else "#0E1117"
text_color = "#FF0000" if night else "#FFFFFF"
accent_color = "#CC0000" if night else "#C62828"
card_bg = "#1A0000" if night else "#1E1E1E"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg_color}; color: {text_color}; }}
    
    /* HUD */
    .mobile-hud {{
        position: sticky;
        top: 0;
        z-index: 100;
        background-color: {bg_color};
        padding: 10px 0;
        border-bottom: 2px solid {accent_color};
    }}
    
    .hud-card {{
        background-color: {card_bg};
        border-radius: 10px;
        padding: 12px;
        text-align: center;
        border-left: 4px solid {accent_color};
        margin-bottom: 5px;
    }}
    
    .hud-label {{ color: {"#660000" if night else "#888"}; font-size: 12px; font-weight: bold; }}
    .hud-value {{ color: {text_color}; font-size: 32px; font-weight: 900; }}
    
    /* Елементи керування */
    .stButton>button {{
        width: 100%;
        background-color: {card_bg};
        color: {text_color};
        border: 1px solid {accent_color};
    }}
    
    .section-head {{ 
        background: {card_bg}; 
        padding: 8px; 
        color: {accent_color}; 
        font-weight: bold; 
        margin: 15px 0 10px 0;
    }}
    
    /* Виправлення кольору тексту в інпутах для нічного режиму */
    input {{ color: {text_color} !important; background-color: {bg_color} !important; }}
    label {{ color: {text_color} !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- БАЛІСТИЧНЕ ЯДРО ---
def calc_mobile(p, dist, t_speed, t_angle):
    if dist <= 0: return {"v": 0, "h": 0, "tof": 0}
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    tof = (math.exp(k * dist) - 1) / (k * p['v0'])
    t_z = (math.exp(k * p['zero']) - 1) / (k * p['v0'])
    y_m = -((0.5 * 9.806 * tof**2) - (0.5 * 9.806 * t_z**2 + p['sh']/100) * (dist / p['zero']) + p['sh']/100)
    v_mil = abs((y_m * 100) / (dist / 10) / 0.1)
    w_rad = math.radians(p['w_hour'] * 30)
    wind_m = p['w_speed'] * math.sin(w_rad) * (tof - (dist/p['v0']))
    lead_m = (t_speed / 3.6) * math.sin(math.radians(t_angle)) * tof
    h_mil = abs(((wind_m + lead_m) * 100) / (dist / 10) / 0.1)
    return {"v": round(v_mil, 1), "h": round(h_mil, 1), "tof": round(tof, 3)}

# --- ІНТЕРФЕЙС ---

# Кнопка перемикання теми
st.button("🌙 ПЕРЕКЛЮЧИТИ РЕЖИМ (ДЕНЬ/НІЧ)", on_click=toggle_mode)

st.markdown('<div class="mobile-hud">', unsafe_allow_html=True)
m_dist = st.slider("🎯 ДИСТАНЦІЯ (м)", 0, 1500, 400, step=10)
res_col1, res_col2 = st.columns(2)
st.markdown('</div>', unsafe_allow_html=True)

with st.expander("🛠 ПАРАМЕТРИ", expanded=False):
    m_v0 = st.number_input("V0 (м/с)", value=830)
    m_bc = st.number_input("БК (G7)", value=0.243, format="%.3f")
    m_w_speed = st.slider("Вітер (м/с)", 0, 15, 3)
    m_w_hour = st.slider("Година", 1, 12, 3)
    m_t_speed = st.number_input("Ціль (км/год)", value=0.0)

# Розрахунок
params = {'v0': m_v0, 'bc': m_bc, 'temp': 15, 'press': 1013, 'sh': 5.0, 'zero': 100, 'w_speed': m_w_speed, 'w_hour': m_w_hour, 'model': 'G7'}
res = calc_mobile(params, m_dist, m_t_speed, 90)

# HUD
res_col1.markdown(f'<div class="hud-card"><div class="hud-label">ВЕРТИКАЛЬ</div><div class="hud-value">↑ {res["v"]}</div></div>', unsafe_allow_html=True)
res_col2.markdown(f'<div class="hud-card"><div class="hud-label">ГОРИЗОНТ</div><div class="hud-value">↔ {res["h"]}</div></div>', unsafe_allow_html=True)

st.markdown('<div class="section-head">📋 ТАБЛИЦЯ ПОПРАВОК</div>', unsafe_allow_html=True)
distances = [m_dist-100, m_dist, m_dist+100]
table_rows = [{"М": d, "↑ MIL": calc_mobile(params, d, m_t_speed, 90)['v'], "↔ MIL": calc_mobile(params, d, m_t_speed, 90)['h']} for d in distances if d >= 0]
st.table(pd.DataFrame(table_rows))
