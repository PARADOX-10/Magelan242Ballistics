import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math
import base64
import os

# --- 1. КОНФІГУРАЦІЯ СТОРІНКИ ---
st.set_page_config(page_title="Magelan242 ULTRA Ultimate", layout="wide", initial_sidebar_state="collapsed")

# --- 2. БАЗА ДАНИХ КУЛЬ ---
# Формат: "Назва": [Калібр (дюйм), Вага (гран), BC G7, Модель Drag]
BULLET_DB = {
    "Custom Bullet (Ручне налаштування)": None,
    ".223 Rem: Sierra TMK 77gr": [0.224, 77, 0.200, "G7"],
    ".223 Rem: Hornady BTHP 75gr": [0.224, 75, 0.183, "G7"],
    "6.5 CM: Hornady ELD-M 140gr": [0.264, 140, 0.326, "G7"],
    "6.5 CM: Lapua Scenar-L 136gr": [0.264, 136, 0.274, "G7"],
    "6.5 CM: Berger Hybrid 140gr": [0.264, 140, 0.311, "G7"],
    ".308 Win: Lapua Scenar 167gr": [0.308, 167, 0.216, "G7"],
    ".308 Win: Hornady ELD-M 178gr": [0.308, 178, 0.275, "G7"],
    ".308 Win: Sierra SMK 175gr": [0.308, 175, 0.243, "G7"],
    ".300 WM: Berger Hybrid 215gr": [0.308, 215, 0.354, "G7"],
    ".338 LM: Lapua Scenar 300gr": [0.338, 300, 0.368, "G7"],
    ".338 LM: Hornady ELD-M 285gr": [0.338, 285, 0.407, "G7"],
    ".50 BMG: Hornady A-MAX 750gr": [0.510, 750, 0.511, "G7"]
}

# --- 3. СТИЛІЗАЦІЯ (CSS) ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@300;500;700&display=swap');
        .stApp { background-color: #050505; font-family: 'Roboto Mono', monospace; color: #e0e0e0; }
        .header-container { border-bottom: 2px solid #00ff41; padding-bottom: 15px; margin-bottom: 25px; display: flex; align-items: center; gap: 20px;}
        .hud-card { background: rgba(15, 20, 25, 0.95); border-left: 5px solid #00ff41; border-radius: 10px; padding: 15px; text-align: center; margin-bottom: 10px;}
        .hud-label { color: #888; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px;}
        .hud-value { color: #fff; font-size: 1.8rem; font-weight: 700; }
        .hud-sub { color: #00ff41; font-size: 0.8rem; }
        /* Tabs styling */
        .stTabs [data-baseweb="tab-list"] { gap: 10px; }
        .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #111; border-radius: 5px; color: #fff; }
        .stTabs [aria-selected="true"] { background-color: #00ff41 !important; color: #000 !important; font-weight: bold;}
    </style>
""", unsafe_allow_html=True)

# --- 4. МАТЕМАТИЧНЕ ЯДРО (PHYSICS ENGINE: RK4) ---

def get_derivatives(state, p):
    """
    Обчислює похідні для методу Рунге-Кутти.
    state: [x, y, z, vx, vy, vz]
    """
    # Розпаковка вектора стану
    _, _, _, vx, vy, vz = state
    
    # Фізичні константи
    G = 9.80665
    OMEGA_E = 7.292115e-5 # Кутова швидкість Землі
    
    # 1. Вектор відносної швидкості (Швидкість кулі - Швидкість вітру)
    # Вітер вже переведений у компоненти w_long (зустрічний/попутний) та w_cross (боковий)
    v_rel_x = vx + p['w_long']
    v_rel_y = vy # Вертикального вітру зазвичай немає
    v_rel_z = vz + p['w_cross']
    
    # Повна швидкість відносно повітря
    v_total_rel = math.sqrt(v_rel_x**2 + v_rel_y**2 + v_rel_z**2)
    mach = v_total_rel / p['c_speed']
    
    # 2. Вибір моделі опору (G1 або G7)
    if p['model'] == "G7":
        # Апроксимація G7 для різних чисел Маха
        cd = 0.22 + 0.12 / (mach**1.5 + 0.1) if mach > 1 else 0.45 / (mach + 0.5)
    else:
        # Апроксимація G1
        cd = 0.42 + 0.1 / (mach**2 + 0.1) if mach > 1 else 0.55
        
    # Сила опору (Accelleration due to Drag)
    # Формула: -0.5 * rho * v^2 * S * Cd / m
    # bc_eff вже враховує масу та калібр
    accel_drag = (0.5 * p['rho_rel'] * v_total_rel**2 * cd * (1.0/p['bc_eff'])) * 0.00105
    
    # 3. Ефект Коріолiса та Етвеша (прискорення)
    cor_y = 2 * OMEGA_E * vx * math.cos(p['lat_rad']) * math.sin(p['az_rad']) # Вертикальний (Eötvös)
    cor_z = 2 * OMEGA_E * (vy * math.cos(p['lat_rad']) * math.cos(p['az_rad']) - vx * math.sin(p['lat_rad'])) # Горизонтальний

    # 4. Результуючі похідні (Швидкість -> Прискорення)
    dvx = -(accel_drag * (v_rel_x / v_total_rel))
    dvy = -(accel_drag * (v_rel_y / v_total_rel)) - G + cor_y
    dvz = -(accel_drag * (v_rel_z / v_total_rel)) + cor_z
    
    # Повертаємо [dx, dy, dz, dvx, dvy, dvz]
    return np.array([vx, vy, vz, dvx, dvy, dvz])

def run_simulation(p):
    """
    Основний цикл симуляції.
    p: словник з усіма параметрами пострілу
    """
    DT = 0.0015 # Крок часу (с) - High Precision
    
    # --- Підготовка параметрів ---
    ref_w = 175.0
    # Ізоенергетична корекція швидкості від ваги + Термокорекція
    v0_eff = p['v0'] * math.sqrt(ref_w / p['weight_gr']) + (p['temp'] - 15) * p['t_coeff']
    # Ефективний BC (масштабування)
    bc_eff = p['bc'] * (p['weight_gr'] / ref_w)
    
    # --- Атмосфера (ICAO Model + Humidity) ---
    tk = p['temp'] + 273.15
    # Тиск насиченої пари (Arden Buck equation)
    svp = 6.112 * math.exp((17.67 * p['temp']) / (p['temp'] + 243.5))
    pv = svp * (p['humid'] / 100.0) # Парціальний тиск пари
    # Густина вологого повітря
    rho = ((p['pressure'] - pv) * 100 / (287.05 * tk)) + (pv * 100 / (461.5 * tk))
    
    # Фізичний пакет для інтегратора
    p_phys = {
        'rho_rel': rho / 1.225, 
        'c_speed': 331.3 * math.sqrt(tk / 273.15),
        'bc_eff': bc_eff, 
        'model': p['model'], 
        'lat_rad': math.radians(p['latitude']), 
        'az_rad': math.radians(p['azimuth']),
        'w_long': p['w_speed'] * math.cos(math.radians(p['w_dir'] * 30)),
        'w_cross': p['w_speed'] * math.sin(math.radians(p['w_dir'] * 30))
    }
    
    # Фактор стабільності (Miller Twist Rule) для деривації
    s_g = (30 * p['weight_gr']) / ((p['twist']**2) * (p['caliber']**3) * (v0_eff/600))
    t_dir = 1 if p['twist_dir'] == "Right (Правий)" else -1
    
    # Обнулення (Zeroing Angle)
    angle_zero = math.atan((0.5 * 9.80665 * (p['zero_dist']/v0_eff)**2 + p['sh']/100) / p['zero_dist'])
    
    # Початковий стан: [x, y, z, vx, vy, vz]
    state = np.array([0.0, -p['sh']/100, 0.0, v0_eff * math.cos(angle_zero), v0_eff * math.sin(angle_zero), 0.0])
    
    t = 0.0
    dist = 0.0
    results = []
    step_check = 0

    # --- ЦИКЛ RK4 ---
    while dist <= p['max_dist'] + 5:
        k1 = get_derivatives(state, p_phys)
        k2 = get_derivatives(state + k1 * DT / 2, p_phys)
        k3 = get_derivatives(state + k2 * DT / 2, p_phys)
        k4 = get_derivatives(state + k3 * DT, p_phys)
        
        # Оновлення стану
        state += (k1 + 2*k2 + 2*k3 + k4) * DT / 6
        
        t += DT
        dist = state[0]
        
        # Запис результатів (кожні 10м або 50м для економії пам'яті, тут кожні ~крок)
        if dist >= step_check:
            vx, vy, vz = state[3], state[4], state[5]
            v_curr = math.sqrt(vx**2 + vy**2 + vz**2)
            
            # Spin Drift (Деривація) - емпірична формула на основі Sg
            s_drift = -1 * (0.06 * (dist/100)**2 * t_dir) / s_g
            
            # Aero Jump (Стрибок від бокового вітру)
            aero_jump = (p_phys['w_cross'] * 0.002 * t_dir * dist / 100)
            
            # Фінальні координати з урахуванням ефектів 2-го порядку
            y_f = state[1] + aero_jump
            z_f = state[2] + s_drift # Вітер вже врахований у векторі state[2] через get_derivatives, додаємо тільки деривацію
            
            # Розрахунок поправок (MRAD)
            mv = (y_f * 100) / (dist / 10) if dist > 0 else 0
            mh = (z_f * 100) / (dist / 10) if dist > 0 else 0
            
            results.append({
                "Дист.": int(dist), 
                "V": int(v_curr), 
                "Mach": round(v_curr/p_phys['c_speed'], 2), 
                "Падіння": y_f * 100, 
                "MRAD_V": mv, 
                "MRAD_H": mh, 
                "Sg": round(s_g, 2)
            })
            step_check += 10 # Крок запису в таблицю (метри)
            
    return pd.DataFrame(results)

# --- 5. ВІЗУАЛІЗАЦІЯ (PLOTLY) ---

def draw_reticle_analytics(mrad_v, mrad_h, unit, wez_data=None):
    """Малює прицільну сітку з точкою влучання та зоною WEZ"""
    limit = 12 if "MRAD" in unit else 40
    fig = go.Figure()
    
    # Зона ймовірних влучань (WEZ Cloud)
    if wez_data:
        fig.add_trace(go.Scatter(
            x=[-wez_data['h_min'], -wez_data['h_max'], -wez_data['h_max'], -wez_data['h_min']],
            y=[wez_data['v_min'], wez_data['v_min'], wez_data['v_max'], wez_data['v_max']],
            fill="toself", fillcolor="rgba(255, 50, 50, 0.25)", 
            line=dict(color="rgba(255, 50, 50, 0.5)", width=1),
            name="WEZ (Zone)"
        ))

    # Основні лінії сітки
    fig.add_shape(type="line", x0=-limit, y0=0, x1=limit, y1=0, line=dict(color="white", width=1))
    fig.add_shape(type="line", x0=0, y0=-limit, x1=0, y1=limit, line=dict(color="white", width=1))
    
    # Точка прицілювання (Hold)
    fig.add_trace(go.Scatter(
        x=[-mrad_h], y=[mrad_v], 
        mode='markers', 
        marker=dict(color='#00ff41', size=15, symbol='circle-open', line=dict(width=3)),
        name="POI"
    ))
    
    # Налаштування вигляду
    fig.update_layout(
        template="plotly_dark", 
        height=500, width=500, 
        showlegend=False, 
        xaxis=dict(range=[-limit, limit], title=unit, zeroline=False), 
        yaxis=dict(range=[-limit, limit], title=unit, zeroline=False),
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(20,20,20,0.8)',
        margin=dict(l=20, r=20, t=20, b=20)
    )
    return fig

# --- 6. ІНТЕРФЕЙС КОРИСТУВАЧА (UI) ---

st.markdown('<div class="header-container"><div style="font-size:2.5rem;">🎯</div><div><div class="header-title">Magelan242 ULTRA</div><div class="header-sub">V4.7 Ultimate | RK4 Vector Engine</div></div></div>', unsafe_allow_html=True)

# Вкладки
t_res, t_env, t_gun, t_wez = st.tabs(["🚀 ОБЧИСЛЕННЯ", "🌍 СЕРЕДОВИЩЕ", "🔫 ЗБРОЯ", "📊 АНАЛІТИКА (WEZ)"])

# --- Вкладка: СЕРЕДОВИЩЕ ---
with t_env:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 🌡️ Атмосфера")
        temp = st.slider("Температура (°C)", -30, 50, 15)
        hum = st.slider("Вологість (%)", 0, 100, 50, help="Впливає на густину повітря")
        press = st.number_input("Тиск (hPa)", 800, 1150, 1013)
    with col2:
        st.markdown("#### 💨 Вітер та Гео")
        lat = st.number_input("Широта (град)", 0, 90, 50, help="Для ефекту Коріоліса")
        az = st.slider("Азимут стрільби (°)", 0, 360, 90)
        w_s = st.number_input("Швидкість вітру (м/с)", 0.0, 20.0, 3.0)
        w_d = st.slider("Напрям вітру (год)", 1, 12, 3)

# --- Вкладка: ЗБРОЯ ---
with t_gun:
    st.markdown("#### 🛠️ Параметри комплексу")
    # Вибір кулі
    bullet_choice = st.selectbox("База даних куль:", list(BULLET_DB.keys()))
    db_data = BULLET_DB[bullet_choice]
    
    g1, g2 = st.columns(2)
    with g1:
        v0 = st.number_input("V0 Дульна швидкість (м/с)", 300, 1300, 820)
        # Якщо обрано кулю з бази, підставляємо значення, інакше дефолт
        weight = st.number_input("Вага кулі (гран)", 40, 750, db_data[1] if db_data else 175)
        bc = st.number_input("BC (Балістичний коефіцієнт)", 0.1, 1.5, db_data[2] if db_data else 0.505, format="%.3f")
        model = st.radio("Драг-модель", ["G1", "G7"], index=1 if (not db_data or db_data[3]=="G7") else 0, horizontal=True)
        
    with g2:
        cal = st.number_input("Калібр (дюйм)", 0.22, 0.51, db_data[0] if db_data else 0.308, step=0.001)
        twist = st.number_input("Твіст (дюйм)", 6.0, 16.0, 10.0)
        twist_dir = st.radio("Напрям нарізів", ["Right (Правий)", "Left (Лівий)"], horizontal=True)
        sh = st.number_input("Висота прицілу (см)", 3.0, 10.0, 5.0)
        zero = st.number_input("Дистанція нуль (м)", 50, 300, 100)

# --- Вкладка: АНАЛІТИКА (WEZ Setup) ---
with t_wez:
    st.markdown("#### 🎲 Зона ймовірних влучань (WEZ)")
    st.info("Цей інструмент розраховує, наскільки зміниться точка влучання, якщо ви допустили помилку у вимірі вітру або якщо швидкість кулі нестабільна.")
    wez_c1, wez_c2 = st.columns(2)
    err_w = wez_c1.slider("Похибка читання вітру (+/- м/с)", 0.0, 5.0, 1.0)
    err_v = wez_c2.slider("Стабільність V0 (SD м/с)", 0.0, 10.0, 2.0)

# --- ОСНОВНИЙ РОЗРАХУНОК (Main Thread) ---
with t_res:
    # Вхідні дані для розрахунку (target setup)
    res_c1, res_c2 = st.columns([1, 2])
    with res_c1:
        dist_target = st.number_input("ДИСТАНЦІЯ ДО ЦІЛІ (м)", 100, 3000, 1000, step=50)
        unit = st.selectbox("Одиниці поправок", ["MRAD", "MOA"])
    
    # Збірка параметрів у словник
    params = {
        'v0': v0, 'bc': bc, 'model': model, 'weight_gr': weight, 
        'temp': temp, 'pressure': press, 'humid': hum, 
        'latitude': lat, 'azimuth': az, 
        'w_speed': w_s, 'w_dir': w_d, 
        'angle': 0, 'twist': twist, 'twist_dir': twist_dir,
        'caliber': cal, 'zero_dist': zero, 'max_dist': dist_target, 'sh': sh, 
        't_coeff': 0.1, 'turret_unit': unit
    }

    try:
        # 1. Головна симуляція
        df = run_simulation(params)
        res = df.iloc[-1]
        
        # 2. WEZ Симуляція (Min/Max scenarios)
        # Сценарій "Мінімум": Вітер слабший, V0 нижча
        p_min = params.copy()
        p_min.update({'w_speed': max(0, w_s - err_w), 'v0': v0 - err_v})
        
        # Сценарій "Максимум": Вітер сильніший, V0 вища
        p_max = params.copy()
        p_max.update({'w_speed': w_s + err_w, 'v0': v0 + err_v})
        
        res_min = run_simulation(p_min).iloc[-1]
        res_max = run_simulation(p_max).iloc[-1]
        
        # Формування даних для WEZ-прямокутника
        wez_zone = {
            'v_min': min(res_min['MRAD_V'], res_max['MRAD_V']),
            'v_max': max(res_min['MRAD_V'], res_max['MRAD_V']),
            'h_min': min(res_min['MRAD_H'], res_max['MRAD_H']),
            'h_max': max(res_min['MRAD_
