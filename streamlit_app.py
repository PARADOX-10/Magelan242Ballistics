import streamlit as st
import pandas as pd
import numpy as np
import math
import plotly.graph_objects as go

st.set_page_config(page_title="Magelan Tactical Pro", layout="centered")

# --- ЛОГІКА ТЕМИ (v53.0) ---
if 'night_mode' not in st.session_state:
    st.session_state.night_mode = False

def toggle_mode():
    st.session_state.night_mode = not st.session_state.night_mode

night = st.session_state.night_mode
bg_color = "#0A0000" if night else "#0E1117"
text_color = "#FF0000" if night else "#FFFFFF"
accent_color = "#CC0000" if night else "#C62828"
card_bg = "#1A0000" if night else "#1E1E1E"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg_color}; color: {text_color}; }}
    .mobile-hud {{
        position: sticky; top: 0; z-index: 100;
        background-color: {bg_color}; padding: 10px 0;
        border-bottom: 2px solid {accent_color};
    }}
    .hud-card {{
        background-color: {card_bg}; border-radius: 10px;
        padding: 12px; text-align: center;
        border-left: 4px solid {accent_color}; margin-bottom: 5px;
    }}
    .hud-label {{ color: {"#660000" if night else "#888"}; font-size: 12px; font-weight: bold; text-transform: uppercase; }}
    .hud-value {{ color: {text_color}; font-size: 32px; font-weight: 900; }}
    .stButton>button {{ width: 100%; background-color: {card_bg}; color: {text_color}; border: 1px solid {accent_color}; }}
    .section-head {{ background: {card_bg}; padding: 8px; color: {accent_color}; font-weight: bold; margin: 15px 0 10px 0; border-radius: 4px; }}
    input, label, .stSlider {{ color: {text_color} !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- РОЗШИРЕНА МАТЕМАТИКА (G1/G7) ---
def calculate_ballistics(p, target_d):
    rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
    # Коефіцієнт форми: G7 зазвичай потребує корекції відносно G1
    k = 0.5 * rho * (1/p['bc']) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    
    def get_stats(d):
        if d <= 0: return {"v": p['v0'], "drop_cm": 0, "tof": 0}
        tof = (math.exp(k * d) - 1) / (k * p['v0'])
        v_dist = p['v0'] * math.exp(-k * d)
        t_z = (math.exp(k * p['zero']) - 1) / (k * p['v0'])
        y_m = -((0.5 * 9.806 * tof**2) - (0.5 * 9.806 * t_z**2 + p['sh']/100) * (d / p['zero']) + p['sh']/100)
        return {"v": v_dist, "drop_cm": y_m * 100, "tof": tof}

    current = get_stats(target_d)
    v_mil = abs(current['drop_cm'] / (target_d / 10)) if target_d > 0 else 0
    
    # Вітер
    w_rad = math.radians(p['w_hour'] * 30)
    wind_m = p['w_speed'] * math.sin(w_rad) * (current['tof'] - (target_d/p['v0']))
    w_mil = abs((wind_m * 100) / (target_d / 10)) if target_d > 0 else 0
    
    energy = (p['weight'] * 0.0000648 * current['v']**2) / 2
    return {"v_mil": round(v_mil, 1), "w_mil": round(w_mil, 1), "v": int(current['v']), "e": int(energy), "tof": round(current['tof'], 3), "drop_cm": current['drop_cm']}

# --- ІНТЕРФЕЙС ---
st.button("🌙 ТАКТИЧНИЙ РЕЖИМ (ДЕНЬ/НІЧ)", on_click=toggle_mode)

# Фіксований HUD
st.markdown('<div class="mobile-hud">', unsafe_allow_html=True)
m_dist = st.slider("🎯 ДИСТАНЦІЯ (м)", 0, 1500, 500, step=10)
res_col1, res_col2 = st.columns(2)
st.markdown('</div>', unsafe_allow_html=True)

# Блоки налаштувань
with st.expander("🧪 НАБІЙ ТА ДРАГ-МОДЕЛЬ", expanded=True):
    m_model = st.radio("Оберіть модель (G1/G7)", ["G1", "G7"], index=1, horizontal=True)
    m_v0 = st.number_input("V0 швидкість (м/с)", value=830)
    m_bc = st.number_input(f"Коефіцієнт {m_model}", value=0.243 if m_model=="G7" else 0.480, format="%.3f")
    m_weight = st.number_input("Вага кулі (гран)", value=175.0)

with st.expander("🌍 СЕРЕДОВИЩЕ ТА ВІТЕР"):
    m_w_speed = st.slider("Вітер (м/с)", 0, 20, 3)
    m_w_hour = st.slider("Напрямок (год)", 1, 12, 3)
    m_temp = st.slider("Температура (°C)", -30, 50, 15)
    m_press = st.number_input("Тиск (гПа)", value=1013)
    m_sh = st.number_input("Висота оптики (см)", value=5.0)
    m_zero = st.number_input("Пристрілка (м)", value=100)

# Розрахунок
params = {'v0': m_v0, 'bc': m_bc, 'weight': m_weight, 'model': m_model, 'temp': m_temp, 'press': m_press, 'sh': m_sh, 'zero': m_zero, 'w_speed': m_w_speed, 'w_hour': m_w_hour}
res = calculate_ballistics(params, m_dist)

# Вивід у HUD
res_col1.markdown(f'<div class="hud-card"><div class="hud-label">Вертикаль MIL</div><div class="hud-value">↑ {res["v_mil"]}</div></div>', unsafe_allow_html=True)
res_col2.markdown(f'<div class="hud-card"><div class="hud-label">Горизонт MIL</div><div class="hud-value">↔ {res["w_mil"]}</div></div>', unsafe_allow_html=True)

# Аналітичний блок (Графіки та Таблиці)
with st.expander("📊 ГЛИБОКА АНАЛІТИКА ТА ГРАФІКИ"):
    st.markdown('<div class="section-head">📈 ТРАЄКТОРІЯ ТА ШВИДКІСТЬ</div>', unsafe_allow_html=True)
    
    # Генеруємо дані для графіків
    d_range = np.arange(0, 1501, 20)
    plot_data = [calculate_ballistics(params, d) for d in d_range]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d_range, y=[r['drop_cm'] for r in plot_data], name="Падіння (см)", line=dict(color=accent_color)))
    fig.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=300, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown('<div class="section-head">📋 ТАБЛИЦЯ ПОПРАВОК</div>', unsafe_allow_html=True)
    table_d = np.arange(0, 1001, 100)
    df_rows = []
    for d in table_d:
        r = calculate_ballistics(params, d)
        df_rows.append({"М": d, "↑ MIL": r['v_mil'], "↔ MIL": r['w_mil'], "м/с": r['v'], "Дж": r['e']})
    st.dataframe(pd.DataFrame(df_rows), use_container_width=True)

st.caption(f"ToF: {res['tof']} с | V цілі: {res['v']} м/с | Енергія: {res['e']} Дж")
