import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math

# --- КОНФІГУРАЦІЯ ---
st.set_page_config(page_title="Magelan242 Pro Mobile", layout="wide", initial_sidebar_state="collapsed")

# --- CSS: ТАКТИЧНИЙ СТИЛЬ + ЗАХИСТ ВІД МІСКЛІКІВ ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@300;500;700&display=swap');

        .stApp {
            background-color: #050505;
            background-image: radial-gradient(circle at 50% 50%, #111418 0%, #050505 100%);
            font-family: 'Roboto Mono', monospace;
            color: #e0e0e0;
        }

        /* --- ЗАХИСТ ВІД МІСКЛІКІВ (МОБІЛЬНИЙ) --- */
        /* Високі поля вводу */
        input[type="number"] {
            min-height: 50px !important; 
            font-size: 18px !important;
            padding-left: 15px !important;
            background-color: #0e1117 !important;
            color: white !important;
            border: 1px solid #333 !important;
        }
        /* Великі кнопки +/- */
        button[kind="secondary"] {
            min-height: 50px !important;
            min-width: 50px !important;
        }
        /* Великі вкладки */
        button[data-baseweb="tab"] {
            font-size: 16px !important;
            padding: 15px !important;
            flex-grow: 1;
        }
        
        /* --- HUD КАРТКИ --- */
        .hud-card {
            background: rgba(20, 25, 30, 0.8);
            border: 1px solid #333;
            border-left: 4px solid #00ff41;
            border-radius: 12px;
            padding: 15px;
            text-align: center;
            margin-bottom: 10px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.5);
        }
        .hud-label { color: #888; font-size: 0.8rem; text-transform: uppercase; margin-bottom: 5px; letter-spacing: 1px;}
        .hud-value { color: #fff; font-size: 2.2rem; font-weight: 700; text-shadow: 0 0 10px rgba(0,255,65,0.3); }
        .hud-sub { color: #00ff41; font-size: 0.8rem; }

        /* Заголовок */
        h1 { border-bottom: 2px solid #00ff41; padding-bottom: 15px; margin-bottom: 20px; text-transform: uppercase; }
        
        /* Прибираємо відступи */
        .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    </style>
""", unsafe_allow_html=True)

# --- ФІЗИЧНЕ ЯДРО (ПОВНЕ) ---
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
        # 1. Час польоту (з урахуванням зустрічного вітру)
        v0_eff = v0_corr - w_long 
        t = d / (v0_eff * math.exp(-k_drag * d / 2)) if d > 0 else 0
        
        # 2. Гравітація (з урахуванням кута місця)
        drop = 0.5 * g * (t**2) * math.cos(angle_rad)
        
        # 3. Пристрілка
        t_zero = p['zero_dist'] / (v0_corr * math.exp(-k_drag * p['zero_dist'] / 2))
        drop_zero = 0.5 * g * (t_zero**2)
        y_m = -(drop - (drop_zero + p['sh']/100) * (d / p['zero_dist']) + p['sh']/100)
        
        # 4. Аеродинамічний стрибок
        aero_jump_mrad = 0.025 * w_cross * t_dir
        aero_jump_cm = aero_jump_mrad * (d / 10) 
        y_m += (aero_jump_cm / 100)
        
        # 5. Вітер (Lag)
        wind_drift = w_cross * (t - (d/v0_corr)) if d > 0 else 0
        
        # 6. Деривація
        derivation = -1 * 0.05 * (10 / p['twist']) * (d / 100)**2 * t_dir if d > 0 else 0
        
        # Енергетика
        v_curr = v0_corr * math.exp(-k_drag * d)
        energy = (weight_kg * v_curr**2) / 2
        
        # Кліки
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
            "Падіння": y_m * 100 # Зберігаємо для графіка
        })
    return pd.DataFrame(results), v0_corr

# --- ІНТЕРФЕЙС ---

st.markdown("<h1>🎯 MAGELAN-242 <span style='font-size:0.5em; color:#00ff41'>PRO</span></h1>", unsafe_allow_html=True)

# Головний контейнер вводу
with st.container():
    c1, c2 = st.columns([2, 1])
    with c1:
        dist_input = st.number_input("ДИСТАНЦІЯ (м)", 100, 3000, 1200, step=10, help="Цільова дистанція")
    with c2:
        turret_unit = st.selectbox("КЛІКИ", ["MRAD", "MOA"])

st.markdown("---")

# Вкладки налаштувань (Безпечні для мобільного)
tab_env, tab_gun, tab_vis = st.tabs(["🌪️ УМОВИ", "🔫 ЗБРОЯ", "📈 АНАЛІЗ"])

with tab_env:
    ec1, ec2 = st.columns(2)
    with ec1:
        w_speed = st.number_input("Вітер (м/с)", 0.0, 30.0, 4.0, step=0.5)
        w_dir = st.number_input("Напрям (год)", 1, 12, 3, step=1)
    with ec2:
        temp = st.number_input("Темп. (°C)", -50, 60, 15, step=1)
        press = st.number_input("Тиск (hPa)", 800, 1200, 1013, step=5)
        angle = st.number_input("Кут місця (°)", -60, 60, 0, step=5)

with tab_gun:
    gc1, gc2 = st.columns(2)
    with gc1:
        v0 = st.number_input("V0 (м/с)", 500, 1500, 961, step=5)
        bc = st.number_input("BC", 0.1, 1.0, 0.395, format="%.3f", step=0.005)
        model = st.radio("Модель", ["G7", "G1"], horizontal=True)
    with gc2:
        zero_dist = st.number_input("Нуль (м)", 50, 1000, 300, step=50)
        sh = st.number_input("Вис. прицілу (см)", 0.0, 15.0, 5.0, step=0.1)
        twist = st.number_input("Твіст (дюйм)", 5.0, 20.0, 11.0, step=0.1)
        twist_dir = st.radio("Нарізи", ["Right (Правий)", "Left (Лівий)"], horizontal=True)
        with st.expander("Додатково"):
            weight = st.number_input("Вага (гран)", 50, 1000, 200, step=1)
            t_coeff = st.number_input("Термо %", 0.0, 2.0, 0.1, step=0.1)

# --- РОЗРАХУНОК ---
params = {'v0': v0, 'bc': bc, 'model': model, 'weight_gr': weight, 'temp': temp,
          'pressure': press, 'w_speed': w_speed, 'w_dir': w_dir, 'angle': angle,
          'twist': twist, 'zero_dist': zero_dist, 'max_dist': dist_input, 'sh': sh, 
          't_coeff': t_coeff, 'turret_unit': turret_unit, 'twist_dir': twist_dir}

df, v0_final = run_simulation(params)
res = df.iloc[-1]

# --- РЕЗУЛЬТАТИ (HUD) ---
st.markdown("<br>", unsafe_allow_html=True)
def create_hud_card(label, value, sub, color="#00ff41"):
    return f"""
    <div class="hud-card">
        <div class="hud-label">{label}</div>
        <div class="hud-value" style="color:{color}">{value}</div>
        <div class="hud-sub">{sub}</div>
    </div>
    """

r1, r2 = st.columns(2)
with r1:
    st.markdown(create_hud_card("ВЕРТИКАЛЬ", res['UP/DN'], f"Drop: {int(res['Падіння'])} cm", "#ffcc00"), unsafe_allow_html=True)
with r2:
    st.markdown(create_hud_card("ГОРИЗОНТАЛЬ", res['L/R'], "Wind + Spin", "#ffcc00"), unsafe_allow_html=True)

r3, r4 = st.columns(2)
with r3:
    st.markdown(create_hud_card("ШВИДКІСТЬ", int(res['V, м/с']), "м/с", "#00f3ff"), unsafe_allow_html=True)
with r4:
    st.markdown(create_hud_card("ЕНЕРГІЯ", int(res['E, Дж']), "Дж", "#ff3333"), unsafe_allow_html=True)

# --- ВІЗУАЛІЗАЦІЯ І ТАБЛИЦЯ ---
with tab_vis:
    st.markdown("### 📉 Траєкторія польоту")
    
    # Підготовка даних для графіка
    y_data = df['Падіння'].values
    x_data = df['Дист.'].values
    
    # 1. Трансформація дуги (0-to-0)
    y_shifted = y_data - y_data[0]
    slope = -y_shifted[-1] / x_data[-1] if x_data[-1] > 0 else 0
    y_arc = y_shifted + slope * x_data
    
    # 2. Пошук максимумів
    max_h_val = np.max(y_arc)
    max_h_idx = np.argmax(y_arc)
    dist_at_max = x_data[max_h_idx]
    
    # 3. Абсолютне падіння на фінальній точці
    drop_at_target = y_data[-1]

    # Plotly
    fig = go.Figure()

    # Зелена дуга (Політ з поправкою)
    fig.add_trace(go.Scatter(
        x=x_data, y=y_arc,
        mode='lines',
        name='Траєкторія',
        line=dict(color='#00ff41', width=3),
        fill='tozeroy', fillcolor='rgba(0, 255, 65, 0.1)'
    ))

    # Жовта точка (Макс. висота)
    fig.add_trace(go.Scatter(
        x=[dist_at_max], y=[max_h_val],
        mode='markers+text',
        text=[f"MAX: {max_h_val:.0f}"],
        textposition="top center",
        textfont=dict(color="#ffcc00"),
        marker=dict(color='#ffcc00', size=10, symbol='diamond')
    ))

    # Червоний хрест (Абсолютне падіння)
    fig.add_trace(go.Scatter(
        x=[x_data[-1]], y=[drop_at_target],
        mode='markers+text',
        text=[f"Без попр: {drop_at_target:.0f}"],
        textposition="bottom center",
        textfont=dict(color="#ff3333"),
        marker=dict(color='#ff3333', size=12, symbol='x')
    ))

    # Червона пунктирна лінія
    fig.add_trace(go.Scatter(
        x=[x_data[-1], x_data[-1]],
        y=[0, drop_at_target],
        mode='lines',
        line=dict(color='#ff3333', width=1, dash='dash'),
        hoverinfo='skip'
    ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(10,15,20,0.5)',
        height=350,
        margin=dict(l=10, r=10, t=20, b=10),
        showlegend=False,
        xaxis=dict(title="Метри", gridcolor='#333'),
        yaxis=dict(title="См", gridcolor='#333')
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"ℹ️ Жовте: Максимальний підйом. Червоне: Куди впаде куля, якщо не крутити барабан.")

    st.markdown("---")
    st.markdown("### 📋 Таблиця поправок")
    
    p_step = st.select_slider("Крок таблиці", [25, 50, 100], value=50)
    df_show = df[df['Дист.'] % p_step == 0].copy()
    
    st.dataframe(
        df_show, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Дист.": st.column_config.NumberColumn("М", format="%d"),
            "UP/DN": st.column_config.TextColumn("ВЕРТ"),
            "L/R": st.column_config.TextColumn("ГОР"),
            "V, м/с": st.column_config.NumberColumn("V", format="%d"),
            "E, Дж": st.column_config.NumberColumn("E", format="%d"),
            "Падіння": st.column_config.NumberColumn("ПАД", format="%d"),
        }
    )
    
    st.markdown("#### 📚 Враховані фактори:")
    st.markdown("""
    <div style="font-size: 14px; color: #888;">
    • <b>Атмосфера:</b> Щільність повітря, темп. пороху.<br>
    • <b>Вітер:</b> Зустрічний (на час), Боковий (Lag Method).<br>
    • <b>Спін:</b> Деривація (Spin Drift) та Аеродинамічний стрибок.<br>
    • <b>Геометрія:</b> Кут місця цілі, висота прицілу.
    </div>
    """, unsafe_allow_html=True)
