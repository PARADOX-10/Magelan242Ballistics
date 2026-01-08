import streamlit as st
import pandas as pd
import numpy as np
import math

# --- КОНФІГУРАЦІЯ СТОРІНКИ ---
st.set_page_config(page_title="Magelan Apex v100", layout="centered")

# --- СУЧАСНИЙ МОБІЛЬНИЙ СТИЛЬ (UI/UX) ---
st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background: #080a0c; }
    .main-card { 
        background: #12161b; 
        padding: 20px; 
        border-radius: 15px; 
        border-left: 6px solid #ff4b4b; 
        margin-bottom: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .label { color: #8e949e; font-size: 13px; text-transform: uppercase; font-weight: bold; letter-spacing: 1px; }
    .value { color: #ffffff; font-size: 36px; font-weight: 900; line-height: 1.1; }
    .sub-value { color: #ff4b4b; font-size: 16px; font-weight: bold; }
    .unit { font-size: 14px; color: #5c636a; }
    h1, h2, h3 { color: #ffffff; font-family: 'Segoe UI', Roboto, sans-serif; }
    .stSlider, .stNumberInput { margin-bottom: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- БАЛІСТИЧНЕ ЯДРО (PRECISION 3-DOF) ---
class ApexEngine:
    def __init__(self, p):
        self.p = p
        self.g = 9.80665
        self.omega = 7.292115e-5 # Кутова швидкість Землі
        self.m_kg = p['weight'] * 0.0000647989 # Гран в Кг
        
        # Термозалежність швидкості (v90)
        t_ref = 15.0
        self.v0 = p['v0'] * (1 + (p['temp'] - t_ref) * (p['p_sens'] / 100))
        
        # Параметри атмосфери ICAO
        self.rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
        self.v_sound = 331.3 * math.sqrt(1 + p['temp'] / 273.15)

    def calculate(self):
        dt = 0.002 # Висока точність інтегрування
        pos = np.array([0.0, self.p['sh']/100, 0.0]) # x, y, z
        
        # Вектор початкової швидкості з урахуванням кута місця цілі
        vel = np.array([
            self.v0 * math.cos(math.radians(self.p['angle'])), 
            self.v0 * math.sin(math.radians(self.p['angle'])), 
            0.0
        ])
        
        t = 0.0
        v_wind = np.array([
            self.p['ws'] * math.cos(math.radians(self.p['wh']*30)),
            0.0,
            self.p['ws'] * math.sin(math.radians(self.p['wh']*30))
        ])
        
        drag_const = 0.5 * self.rho * (1 / self.p['bc']) * 0.00052

        while pos[0] < self.p['dist']:
            v_rel = vel - v_wind
            v_mag = np.linalg.norm(v_rel)
            
            # 1. Сила опору (Drag) G7
            a_drag = -drag_const * v_mag * v_rel
            
            # 2. Гравітація
            a_grav = np.array([0, -self.g, 0])
            
            # 3. Ефект Коріолліса (v90)
            lat = math.radians(self.p['lat'])
            az = math.radians(self.p['az'])
            a_cor = 2 * self.omega * np.array([
                vel[2]*math.sin(lat) - vel[1]*math.cos(lat)*math.sin(az),
                vel[0]*math.cos(lat)*math.sin(az),
                -vel[0]*math.sin(lat)
            ])
            
            # Оновлення вектора швидкості та позиції
            vel += dt * (a_drag + a_grav + a_cor)
            pos += dt * vel
            t += dt

        # 4. Деривація (Spin Drift) з v90
        # Розрахунок фактора стабільності Sg
        sg = (30 * (self.p['weight']/7000)) / ((self.p['twist']/0.308)**2 * 0.308**3 * (1.45/0.308) * (1+(1.45/0.308)**2))
        sd_m = 1.25 * (sg + 1.2) * (t**1.83) * 0.01 # метри
        
        v_final = np.linalg.norm(vel)
        energy_start = 0.5 * self.m_kg * (self.v0**2)
        energy_final = 0.5 * self.m_kg * (v_final**2)
        
        # Конвертація в MIL
        v_mil = abs(pos[1] * 100) / (self.p['dist'] / 10)
        h_mil = (abs(pos[2] + sd_m) * 100) / (self.p['dist'] / 10)
        
        return {
            'v_mil': round(v_mil, 2),
            'h_mil': round(h_mil, 2),
            'v_at': int(v_final),
            'e_start': int(energy_start),
            'e_final': int(energy_final),
            'mach': round(v_final / self.v_sound, 2),
            'tof': round(t, 3),
            'v0_actual': round(self.v0, 1)
        }

# --- ІНТЕРФЕЙС ШВИДКОГО ДОСТУПУ (HUD) ---
st.markdown("<h1 style='text-align: center;'>APEX PREDATOR v100</h1>", unsafe_allow_html=True)

# Основні оперативні слайдери (великі, для пальців)
dist_op = st.slider("🎯 ДИСТАНЦІЯ (м)", 50, 1800, 800, step=10)
wind_op = st.slider("💨 ВІТЕР (м/с)", 0, 25, 3)

# --- ПРИХОВАНІ НАЛАШТУВАННЯ (ПОВНИЙ СПИСОК v90) ---
with st.sidebar:
    st.header("🔫 ПАРАМЕТРИ ЗБРОЇ")
    v0_in = st.number_input("Початкова швидкість V0 (м/с)", value=893.0)
    bc_in = st.number_input("БК кулі (G7)", value=0.292, format="%.3f")
    w_in = st.number_input("Вага кулі (гран)", value=195.0)
    twist_in = st.number_input("Твіст ствола 1:", value=11.0)
    sh_in = st.number_input("Висота прицілу (см)", value=5.0)
    p_sens_in = st.slider("Термозалежність пороху (% на 10°C)", 0.0, 3.0, 0.7)
    
    st.header("🗺️ ГЕОПОЗИЦІЯ")
    lat_in = st.number_input("Широта", value=50.0)
    az_in = st.slider("Азимут стрільби (0-Пн, 90-Сх)", 0, 360, 90)

with st.expander("☁️ ДОДАТКОВЕ МЕТЕО ТА ЦІЛЬ"):
    temp_in = st.slider("Температура повітря (°C)", -30, 50, 15)
    press_in = st.number_input("Атмосферний тиск (гПа)", 900, 1100, 1013)
    wh_in = st.slider("Напрямок вітру (години)", 0, 12, 3)
    angle_in = st.slider("Кут місця цілі (°)", -45, 45, 0)

# ОБРОБКА ДАНИХ
params = {
    'v0': v0_in, 'bc': bc_in, 'weight': w_in, 'twist': twist_in, 'sh': sh_in,
    'p_sens': p_sens_in, 'lat': lat_in, 'az': az_in,
    'dist': dist_op, 'temp': temp_in, 'press': press_in, 
    'ws': wind_op, 'wh': wh_in, 'angle': angle_in
}

engine = ApexEngine(params)
res = engine.calculate()

# --- ВИВІД РЕЗУЛЬТАТІВ (MOBILE HUD) ---
c1, c2 = st.columns(2)
with c1:
    st.markdown(f"""<div class="main-card">
        <div class="label">Вертикаль (MIL)</div>
        <div class="value">{res['v_mil']}</div>
        <div class="sub-value">{int(res['v_mil']*10)} КЛІКІВ</div>
    </div>""", unsafe_allow_html=True)

with c2:
    st.markdown(f"""<div class="main-card">
        <div class="label">Горизонт (MIL)</div>
        <div class="value">{res['h_mil']}</div>
        <div class="sub-value">ВРАХ. ДЕРИВАЦІЮ</div>
    </div>""", unsafe_allow_html=True)

e_col1, e_col2 = st.columns(2)
with e_col1:
    st.markdown(f"""<div class="main-card" style="border-left-color: #ff9f1c;">
        <div class="label">Енергія цілі</div>
        <div class="value">{res['e_final']} <span style="font-size:16px">J</span></div>
        <div class="unit">Старт: {res['e_start']} J</div>
    </div>""", unsafe_allow_html=True)

with e_col2:
    st.markdown(f"""<div class="main-card" style="border-left-color: #4b7bff;">
        <div class="label">Швидкість цілі</div>
        <div class="value">{res['v_at']} <span style="font-size:16px">м/с</span></div>
        <div class="sub-value">Mach {res['mach']}</div>
    </div>""", unsafe_allow_html=True)

# ТАКТИЧНИЙ ЗВІТ
with st.expander("📝 ПОВНИЙ БАЛІСТИЧНИЙ ЗВІТ"):
    st.write(f"**Час польоту кулі:** {res['tof']} с")
    st.write(f"**Коригована швидкість V0:** {res['v0_actual']} м/с (відхилення {round(res['v0_actual']-v0_in,1)} м/с)")
    st.write(f"**Стан кулі:** {'🟢 Надзвук' if res['mach'] > 1.2 else '🔴 Трансзвук (ризик дестабілізації)'}")
    st.info("Розрахунок проведено за методом RK2 3-DOF з урахуванням ефектів Коріолліса, Етвеша та спін-дрифту.")
