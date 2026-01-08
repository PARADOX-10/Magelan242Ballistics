import streamlit as st
import pandas as pd
import math
import plotly.graph_objects as go

# 1. Базові налаштування (мають бути першим рядком)
st.set_page_config(page_title="Magelan242 PRO", layout="centered")

# 2. CSS для відтворення дизайну 4DOF
st.markdown("""
    <style>
    /* Темна тема та шрифти */
    .stApp { background-color: #121212; color: #FFFFFF; }
    
    /* Верхня червона панель */
    .header-pro {
        background-color: #C62828;
        padding: 10px;
        text-align: center;
        font-weight: bold;
        font-size: 20px;
        border-radius: 0 0 10px 10px;
        margin-bottom: 20px;
    }

    /* Картки результатів як на скриншоті */
    .hud-card {
        background-color: #FFFFFF;
        border-top: 5px solid #C62828;
        padding: 15px;
        text-align: center;
        border-radius: 4px;
        margin: 5px;
    }
    .hud-label { color: #C62828; font-size: 12px; font-weight: bold; margin-bottom: 5px; text-transform: uppercase; }
    .hud-value { color: #000000 !important; font-size: 32px !important; font-weight: 900 !important; }

    /* Кнопки режимів */
    .stButton>button {
        background-color: #C62828; color: white; border: none; padding: 10px; font-weight: bold; width: 100%;
    }
    .secondary-btn>div>button {
        background-color: #424242 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- МАТЕМАТИЧНА МОДЕЛЬ ---
def calculate(dist, v0, bc, zero, sh, w_speed, w_dir):
    # Спрощена, але точна G7 модель
    k = 0.5 * 1.225 * (1/bc) * 0.00052 * 0.91
    t = (math.exp(k * dist) - 1) / (k * v0) if dist > 0 else 0
    # Падіння
    t_z = (math.exp(k * zero) - 1) / (k * v0)
    drop = 0.5 * 9.806 * (t**2)
    drop_z = 0.5 * 9.806 * (t_z**2)
    y_m = -(drop - (drop_z + sh/100) * (dist / zero) + sh/100)
    # Вітер
    w_rad = math.radians(w_dir)
    drift = (w_speed * math.sin(w_rad)) * (t - (dist/v0))
    
    # Кліки (0.1 MRAD)
    v_clicks = round(abs(((y_m * 100) / (dist / 10)) / 0.1), 1) if dist > 0 else 0.0
    h_clicks = round(abs(((drift * 100) / (dist / 10)) / 0.1), 1) if dist > 0 else 0.0
    return v_clicks, h_clicks, round(t, 3)

# --- ІНТЕРФЕЙС ---
st.markdown('<div class="header-pro">4DOF® HUD PRO : MAGELAN</div>', unsafe_allow_html=True)

# Кнопка редагування (вгорі як на скрині)
col_top1, col_top2 = st.columns([2,1])
col_top1.write("Новий Профіль")
if col_top2.button("РЕДАГУВАТИ ЗБРОЮ"):
    st.info("Налаштування в бічній панелі 👈")

# Статус-панель
st.markdown("""
<div style="display: flex; justify-content: space-between; background: #1A1C24; padding: 10px; border-radius: 5px; margin-bottom: 20px; border: 1px solid #333;">
    <div style="text-align: center;"><small style="color: #888;">ВИСОТА</small><br><b>0 м</b></div>
    <div style="text-align: center;"><small style="color: #888;">ТЕМП</small><br><b>15°C</b></div>
    <div style="text-align: center;"><small style="color: #888;">ТИСК</small><br><b>1013 гПа</b></div>
    <div style="text-align: center;"><small style="color: #888;">ВІТЕР</small><br><b>5 м/с</b></div>
</div>
""", unsafe_allow_html=True)

# Вибір режиму
c_b1, c_b2, c_b3 = st.columns(3)
with c_b1: st.button("КУТ (0)")
with c_b2: st.markdown('<div class="secondary-btn">', unsafe_allow_html=True); st.button("ЗЕМЛЯ"); st.markdown('</div>', unsafe_allow_html=True)
with c_b3: st.markdown('<div class="secondary-btn">', unsafe_allow_html=True); st.button("ЦІЛЬ"); st.markdown('</div>', unsafe_allow_html=True)

# Основний блок (Дистанція та Компас)
st.divider()
col_main1, col_main2 = st.columns([1, 1.2])

with col_main1:
    st.markdown("<p style='text-align:center; color:#C62828;'>Distance<br>Meters</p>", unsafe_allow_html=True)
    dist = st.number_input("", 0, 2000, 486, label_visibility="collapsed")
    st.markdown(f"<h1 style='text-align:center; font-size:60px; color:white; margin:0;'>{dist}</h1>", unsafe_allow_html=True)

with col_main2:
    w_dir = st.slider("ВІТЕР", 0, 360, 326, label_visibility="hidden")
    fig = go.Figure(go.Scatterpolar(r=[0, 1], theta=[w_dir, w_dir], mode='lines+markers', marker=dict(symbol='arrow', size=15, color='#C62828'), line=dict(color='#C62828', width=5)))
    fig.update_layout(polar=dict(bgcolor='#1A1C24', angularaxis=dict(direction='clockwise', rotation=90, gridcolor="#444")), showlegend=False, height=220, margin=dict(l=20, r=20, t=20, b=20), paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)

# Розрахунок
v_c, h_c, flight_time = calculate(dist, 825, 0.450, 100, 5, 5, w_dir)

# Нижні результати
st.markdown("<br>", unsafe_allow_html=True)
res_c1, res_c2, res_c3 = st.columns(3)

with res_c1:
    st.markdown(f'<div class="hud-card"><div class="hud-label">ВЕРТИКАЛЬ</div><div class="hud-value">↑ {v_c}</div></div>', unsafe_allow_html=True)
with res_c2:
    st.markdown(f'<div class="hud-card"><div class="hud-label">ГОР-ТАЛЬ</div><div class="hud-value">→ {h_c}</div></div>', unsafe_allow_html=True)
with res_c3:
    st.markdown(f'<div class="hud-card"><div class="hud-label">ЧАС (С)</div><div class="hud-value">{flight_time}</div></div>', unsafe_allow_html=True)

# Налаштування в сайдбарі для стабільності
with st.sidebar:
    st.header("Налаштування профілю")
    v0 = st.number_input("V0", 100, 1200, 825)
    bc_in = st.number_input("BC G7", 0.1, 1.0, 0.450)
    st.divider()
    if st.button("Генерувати Таблицю"):
        data = []
        for d in range(0, 1001, 100):
            v, h, _ = calculate(d, v0, bc_in, 100, 5, 5, 326)
            data.append({"М": d, "V": v, "H": h})
        st.table(pd.DataFrame(data))
