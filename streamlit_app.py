import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import math
import time

# --- КОНФІГУРАЦІЯ СТОРІНКИ ---
st.set_page_config(page_title="Magelan242 HUD UA", layout="wide", initial_sidebar_state="collapsed")

# --- СУЧАСНИЙ UI / CSS МАГІЯ (Стилі ті самі, адаптовані під кирилицю) ---
st.markdown("""
    <style>
        /* ІМПОРТ ШРИФТУ ROBOTO MONO (Підтримує кирилицю) */
        @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@300;500;700&display=swap');

        /* ЗАГАЛЬНИЙ ФОН */
        .stApp {
            background-color: #050505;
            background-image: radial-gradient(circle at 50% 50%, #111418 0%, #050505 100%);
            font-family: 'Roboto Mono', monospace;
            color: #e0e0e0;
        }

        /* АНІМАЦІЯ ПОЯВИ */
        @keyframes fadeInUp {
            from { opacity: 0; transform: translate3d(0, 20px, 0); }
            to { opacity: 1; transform: translate3d(0, 0, 0); }
        }

        /* КАСТОМНІ КАРТКИ (HUD CARDS) */
        .hud-card {
            background: rgba(20, 25, 30, 0.7);
            border: 1px solid #333;
            border-left: 3px solid #00ff41; /* Tactical Green */
            border-radius: 8px;
            padding: 15px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0, 255, 65, 0.1);
            backdrop-filter: blur(5px);
            animation: fadeInUp 0.6s ease-out;
            transition: all 0.3s ease;
        }
        .hud-card:hover {
            border-left: 3px solid #ffcc00; /* Amber on hover */
            box-shadow: 0 6px 20px rgba(255, 204, 0, 0.2);
            transform: translateY(-2px);
        }
        .hud-label {
            font-size: 0.8rem;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 5px;
        }
        .hud-value {
            font-size: 2.2rem;
            font-weight: 700;
            color: #fff;
            text-shadow: 0 0 10px rgba(255, 255, 255, 0.3);
        }
        .hud-sub {
            font-size: 0.8rem;
            color: #00ff41; /* Green Accent */
            margin-top: 5px;
        }
        
        /* СТИЛІЗАЦІЯ ВВОДУ */
        div[data-baseweb="input"] {
            background-color: #0e1117 !important;
            border: 1px solid #30363d !important;
            color: white !important;
            border-radius: 4px !important;
        }
        
        /* СТИЛІЗАЦІЯ ТАБЛИЦІ */
        [data-testid="stDataFrame"] {
            border: 1px solid #333;
            border-radius: 5px;
            overflow: hidden;
            animation: fadeInUp 0.8s ease-out;
        }

        /* ЗАГОЛОВОК */
        h1 {
            color: #fff;
            text-transform: uppercase;
            letter-spacing: 3px;
            text-shadow: 0 0 15px rgba(0, 255, 65, 0.5);
            border-bottom: 2px solid #00ff41;
            display: inline-block;
            padding-bottom: 10px;
        }

        /* СКРИТИ ЗАЙВЕ ПРИ ДРУКУ */
        @media print {
            .stApp { background: white; color: black; }
            .hud-card { border: 1px solid black; box-shadow: none; color: black; }
            .hud-value, .hud-sub { color: black !important; text-shadow: none; }
            .stSidebar, header, footer { display: none; }
        }
    </style>
""", unsafe_allow_html=True)

# --- ФІЗИЧНЕ ЯДРО (БЕЗ ЗМІН) ---
def run_simulation(p):
    v0_corr = p['v0'] + (p['temp'] - 15) * p['t_coeff']
    tk = p['temp'] + 273.15
    rho = (p['pressure'] * 100) / (287.05 * tk)
    k_drag = 0.5 * rho * (1/p['bc']) * 0.00052
    if p['model'] == "G7": k_drag *= 0.91

    results = []
    g = 9.80665
    weight_kg = p['weight_gr'] * 0.0000647989
    angle_rad = math.radians(p['angle'])
    
    wind_rad = math.radians(p['w_dir'] * 30)
    w_long = p['w_speed'] * math.cos(wind_rad)
    w_cross = p['w_speed'] * math.sin(wind_rad)

    MOA_PER_MRAD = 3.4377
    is_moa = "MOA" in p['turret_unit']
    click_val = 0.25 if is_moa else 0.1
    t_dir = 1 if p['twist_dir'] == "Right (Правий)" else -1

    for d in range(0, p['max_dist'] + 1, 5):
        v0_eff = v0_corr - w_long 
        t = d / (v0_eff * math.exp(-k_drag * d / 2)) if d > 0 else 0
        drop = 0.5 * g * (t**2) * math.cos(angle_rad)
        t_zero = p['zero_dist'] / (v0_corr * math.exp(-k_drag * p['zero_dist'] / 2))
        drop_zero = 0.5 * g * (t_zero**2)
        y_m = -(drop - (drop_zero + p['sh']/100) * (d / p['zero_dist']) + p['sh']/100)
        
        aero_jump_mrad = 0.025 * w_cross * t_dir
        aero_jump_cm = aero_jump_mrad * (d / 10) 
        y_m += (aero_jump_cm / 100)
        
        wind_drift = w_cross * (t - (d/v0_corr)) if d > 0 else 0
        derivation = -1 * 0.05 * (10 / p['twist']) * (d / 100)**2 * t_dir if d > 0 else 0
        
        v_curr = v0_corr * math.exp(-k_drag * d)
        energy = (weight_kg * v_curr**2) / 2
        
        mrad_v_raw = (y_m * 100) / (d / 10) if d > 0 else 0
        mrad_h_raw = ((wind_drift + derivation) * 100) / (d / 10) if d > 0 else 0

        val_v = mrad_v_raw * (MOA_PER_MRAD if is_moa else 1)
        val_h = mrad_h_raw * (MOA_PER_MRAD if is_moa else 1)
        
        c_v = abs(val_v / click_val)
        c_h = abs(val_h / click_val)

        dir_v = "⬆️" if y_m < 0 else "⬇️"
        dir_h = "➡️" if mrad_h_raw > 0 else "⬅️"

        results.append({
            "Дист.": d,
            "UP/DN": f"{dir_v} {c_v:.1f}",
            "L/R": f"{dir_h} {c_h:.1f}",
            "V, м/с": int(v_curr),
            "E, Дж": int(energy),
            "Падіння": y_m * 100
        })
    return pd.DataFrame(results), v0_corr

# --- UI ЛОГІКА (УКРАЇНСЬКА МОВА) ---

# Заголовок з іконкою
st.markdown("<h1>🎯 MAGELAN-242 <span style='font-size:0.5em; color:#666'>ТАКТИЧНИЙ ІНТЕРФЕЙС</span></h1>", unsafe_allow_html=True)

# Верхня панель (Швидкий доступ)
col_dist, col_unit = st.columns([2, 1])
with col_dist:
    dist_input = st.number_input("ДИСТАНЦІЯ ДО ЦІЛІ (Метри)", 10, 3000, 1200, step=10)
with col_unit:
    turret_unit = st.selectbox("СИСТЕМА (КЛІКИ)", ["MRAD (0.1)", "MOA (1/4)"])

# Налаштування (Collapsible)
with st.expander("🛠️ НАЛАШТУВАННЯ ЗБРОЇ"):
    c1, c2, c3 = st.columns(3)
    v0 = c1.number_input("V0 (м/с)", 200, 1500, 961)
    bc = c2.number_input("Балістичний Коеф. (BC)", 0.01, 2.0, 0.395, format="%.3f")
    model = c3.selectbox("Драг-модель", ["G1", "G7"], index=1)
    weight = c1.number_input("Вага кулі (гран)", 10, 1000, 200)
    zero_dist = c2.number_input("Дист. пристрілки (м)", 50, 1000, 300)
    twist = c3.number_input("Твіст (дюйм)", 5.0, 20.0, 11.0)
    sh = c1.number_input("Висота прицілу (см)", 0.0, 15.0, 5.0)
    t_coeff = c2.number_input("Термозалежність %", 0.0, 5.0, 0.1)
    twist_dir = c3.selectbox("Напрямок нарізів", ["Right (Правий)", "Left (Лівий)"])

with st.expander("🌪️ АТМОСФЕРА ТА УМОВИ"):
    c1, c2, c3 = st.columns(3)
    temp = c1.slider("Температура (°C)", -40, 60, 15)
    press = c2.number_input("Тиск (hPa)", 800, 1200, 1013)
    angle = c3.slider("Кут місця цілі (°)", -60, 60, 0)
    w_speed = c1.slider("Швидкість вітру (м/с)", 0.0, 30.0, 4.0)
    w_dir = c2.slider("Напрям вітру (год)", 1, 12, 3)

# Розрахунок
params = {'v0': v0, 'bc': bc, 'model': model, 'weight_gr': weight, 'temp': temp,
          'pressure': press, 'w_speed': w_speed, 'w_dir': w_dir, 'angle': angle,
          'twist': twist, 'zero_dist': zero_dist, 'max_dist': dist_input, 'sh': sh, 
          't_coeff': t_coeff, 'turret_unit': turret_unit, 'twist_dir': twist_dir}

# Імітація обробки даних
with st.spinner('РОЗРАХУНОК БАЛІСТИКИ...'):
    df, v0_final = run_simulation(params)
    res = df.iloc[-1]

# --- ВІДОБРАЖЕННЯ РЕЗУЛЬТАТІВ (HUD CARDS) ---
st.markdown("<br>", unsafe_allow_html=True)
hud1, hud2, hud3, hud4 = st.columns(4)

# Функція для генерації HTML картки
def create_card(label, value, sub, color="#00ff41"):
    return f"""
    <div class="hud-card">
        <div class="hud-label">{label}</div>
        <div class="hud-value" style="color:{color}">{value}</div>
        <div class="hud-sub">{sub}</div>
    </div>
    """

with hud1:
    st.markdown(create_card("ВЕРТИКАЛЬ", res['UP/DN'], f"Падіння: {int(res['Падіння'])} см", "#ffcc00"), unsafe_allow_html=True)
with hud2:
    st.markdown(create_card("ГОРИЗОНТАЛЬ", res['L/R'], "Врах. вітер та деривацію", "#ffcc00"), unsafe_allow_html=True)
with hud3:
    st.markdown(create_card("ШВИДКІСТЬ", int(res['V, м/с']), "м/с", "#00f3ff"), unsafe_allow_html=True)
with hud4:
    st.markdown(create_card("ЕНЕРГІЯ", int(res['E, Дж']), "Джоулі", "#ff3333"), unsafe_allow_html=True)

# --- ГРАФІК ТА ТАБЛИЦЯ ---
st.markdown("<br>", unsafe_allow_html=True)
tab_graph, tab_data = st.tabs(["📉 ВІЗУАЛІЗАЦІЯ", "📋 ДЕТАЛЬНА ТАБЛИЦЯ"])

with tab_graph:
    # Розрахунок дуги
    y_data = df['Падіння'].values
    x_data = df['Дист.'].values
    y_shifted = y_data - y_data[0]
    slope = -y_shifted[-1] / x_data[-1] if x_data[-1] > 0 else 0
    y_arc = y_shifted + slope * x_data
    
    # Макс. висота
    max_h_val = np.max(y_arc)
    max_h_idx = np.argmax(y_arc)
    dist_at_max = x_data[max_h_idx]

    # Plotly з неоновим стилем
    fig = go.Figure()

    # Заливка під графіком
    fig.add_trace(go.Scatter(
        x=x_data, y=y_arc,
        mode='lines',
        name='Траєкторія',
        line=dict(color='#00ff41', width=4, shape='spline'),
        fill='tozeroy',
        fillcolor='rgba(0, 255, 65, 0.1)'
    ))

    # Точка максимуму
    fig.add_trace(go.Scatter(
        x=[dist_at_max], y=[max_h_val],
        mode='markers+text',
        text=[f"МАКС: {max_h_val:.0f}см"],
        textposition="top center",
        textfont=dict(family="Roboto Mono", size=12, color="#ffcc00"),
        marker=dict(color='#ffcc00', size=12, symbol='cross')
    ))

    # Стилізація Plotly
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor='rgba(0,0,0,0)', # Прозорий фон
        plot_bgcolor='rgba(10,15,20,0.5)',
        height=400,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(
            title="ДИСТАНЦІЯ (м)", 
            gridcolor='#333', 
            zerolinecolor='#555'
        ),
        yaxis=dict(
            title="ВИСОТА (см)", 
            gridcolor='#333', 
            zerolinecolor='#555'
        ),
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"ℹ️ Максимальний підйом траєкторії: {max_h_val:.1f} см на дистанції {dist_at_max} м")

with tab_data:
    p_step = st.select_slider("КРОК ТАБЛИЦІ (м)", [10, 25, 50, 100], value=50)
    df_show = df[df['Дист.'] % p_step == 0].copy()
    st.dataframe(
        df_show, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Дист.": st.column_config.NumberColumn("ДИСТ", format="%d м"),
            "UP/DN": st.column_config.TextColumn("ВЕРТ", help="Поправка по вертикалі"),
            "L/R": st.column_config.TextColumn("ГОР", help="Поправка по горизонталі"),
            "V, м/с": st.column_config.NumberColumn("ШВ", format="%d", help="Швидкість (м/с)"),
            "E, Дж": st.column_config.NumberColumn("ЕН", format="%d", help="Енергія (Дж)"),
            "Падіння": st.column_config.NumberColumn("ПАД", format="%d см", help="Абсолютне падіння"),
        }
    )
