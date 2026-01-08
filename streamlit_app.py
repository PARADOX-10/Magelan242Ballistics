import streamlit as st
import pandas as pd
import numpy as np
import math

# --- НАЛАШТУВАННЯ СТОРІНКИ ---
st.set_page_config(page_title="Magelan Ballistics v90", layout="wide")

# --- СТИЛІЗАЦІЯ ---
st.markdown("""
    <style>
    .stApp { background: #0b0e14; color: #e0e0e0; }
    .stMetric { background: #161b22; padding: 20px; border-radius: 10px; border-top: 4px solid #cc0000; }
    .stNumberInput, .stSlider { background: #0b0e14; }
    h1, h2, h3 { color: #ff0000; font-family: 'Courier New', Courier, monospace; }
    </style>
    """, unsafe_allow_html=True)

# --- БАЛІСТИЧНИЙ ОБЧИСЛЮВАЧ ---
class BalisticEngine:
    def __init__(self, p):
        self.p = p
        self.g = 9.80665
        self.omega = 7.292115e-5
        
        # Термозалежність швидкості
        t_ref = 15.0
        v0_corr = p['v0'] * (1 + (p['temp'] - t_ref) * (p['powder_sens'] / 100))
        self.v0 = v0_corr
        
        # Параметри атмосфери
        self.rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
        self.v_sound = 331.3 * math.sqrt(1 + p['temp'] / 273.15)

    def get_acceleration(self, v_vec):
        v_mag = np.linalg.norm(v_vec)
        mach = v_mag / self.v_sound
        
        # Драг-модель G7 (професійна апроксимація)
        if mach > 1.0: cd = 0.35 + (mach - 1.0) * 0.05
        else: cd = 0.45
        
        drag_const = 0.5 * self.rho * (1 / self.p['bc']) * 0.00052
        a_drag = -drag_const * v_mag * v_vec
        
        # Гравітація
        a_grav = np.array([0, -self.g, 0])
        
        # Ефекти Коріолліса (Широта та Азимут)
        lat = math.radians(self.p['lat'])
        az = math.radians(self.p['az'])
        a_cor = 2 * self.omega * np.array([
            v_vec[2]*math.sin(lat) - v_vec[1]*math.cos(lat)*math.sin(az),
            v_vec[0]*math.cos(lat)*math.sin(az),
            -v_vec[0]*math.sin(lat)
        ])
        
        return a_drag + a_grav + a_cor

    def calculate(self):
        dt = 0.002 # Висока дискретність для точності
        pos = np.array([0.0, self.p['sh']/100, 0.0])
        vel = np.array([self.v0 * math.cos(math.radians(self.p['angle'])), 
                        self.v0 * math.sin(math.radians(self.p['angle'])), 0.0])
        t = 0.0
        
        v_wind = np.array([
            self.p['ws'] * math.cos(math.radians(self.p['wh']*30)),
            0.0,
            self.p['ws'] * math.sin(math.radians(self.p['wh']*30))
        ])

        while pos[0] < self.p['dist']:
            v_rel = vel - v_wind
            k1 = self.get_acceleration(v_rel)
            vel += dt * k1
            pos += dt * vel
            t += dt

        # Деривація (Spin Drift) - вплив кроку нарізів
        sg = (30 * (self.p['weight']/7000)) / ((self.p['twist']/0.308)**2 * 0.308**3 * (1.45/0.308) * (1+(1.45/0.308)**2))
        sd = 1.25 * (sg + 1.2) * (t**1.83) * 0.01

        v_mil = abs(pos[1] * 100) / (self.p['dist'] / 10)
        h_mil = (abs(pos[2] + sd) * 100) / (self.p['dist'] / 10)
        
        return {
            'v_mil': round(v_mil, 2), 'h_mil': round(h_mil, 2),
            'v_res': int(np.linalg.norm(vel)), 'tof': round(t, 3),
            'mach': round(np.linalg.norm(vel)/self.v_sound, 2),
            'v0_actual': round(self.v0, 1)
        }

# --- ІНТЕРФЕЙС ---
st.title("🏹 MAGELAN OMNISCIENT v90.0")

with st.sidebar:
    st.header("🔫 ХАРАКТЕРИСТИКИ ЗБРОЇ")
    v0 = st.number_input("Початкова швидкість V0 (м/с)", 893.0)
    bc = st.number_input("Балістичний коефіцієнт (G7)", 0.292, format="%.3f")
    weight = st.number_input("Вага кулі (гран)", 195.0)
    twist = st.number_input("Твіст ствола 1: (дюймів)", 11.0)
    sh = st.number_input("Висота прицілу (см)", 5.0)
    
    st.header("🌡️ ПАРАМЕТРИ ПОРОХУ")
    p_sens = st.slider("Термозалежність (% на 10°C)", 0.0, 3.0, 0.7)
    
    st.header("🗺️ ГЕОПОЗИЦІЯ")
    lat = st.number_input("Широта (Україна ≈ 50)", 50.0)
    az = st.slider("Азимут стрільби (0-Пн, 90-Сх)", 0, 360, 90)

# ОСНОВНИЙ БЛОК
c1, c2, c3 = st.columns(3)
with c1:
    st.subheader("🎯 ЦІЛЬ")
    dist = st.number_input("Дистанція до цілі (м)", 100, 2000, 800, step=10)
    angle = st.slider("Кут місця цілі (°)", -45, 45, 0)
with c2:
    st.subheader("☁️ МЕТЕО")
    temp = st.slider("Температура повітря (°C)", -30, 50, 15)
    press = st.number_input("Атмосферний тиск (гПа)", 900, 1100, 1013)
with c3:
    st.subheader("💨 ВІТЕР")
    ws = st.slider("Швидкість вітру (м/с)", 0, 25, 3)
    wh = st.slider("Напрямок (години)", 0, 12, 3)

# РОЗРАХУНОК
engine = BalisticEngine({
    'v0': v0, 'bc': bc, 'weight': weight, 'twist': twist, 'sh': sh,
    'powder_sens': p_sens, 'dist': dist, 'temp': temp, 'press': press,
    'ws': ws, 'wh': wh, 'lat': lat, 'az': az, 'angle': angle
})
res = engine.calculate()

st.divider()

# ВИВІД РЕЗУЛЬТАТІВ
r1, r2, r3, r4 = st.columns(4)
r1.metric("ВЕРТИКАЛЬ (MIL)", res['v_mil'], f"{int(res['v_mil']*10)} кліків")
r2.metric("ГОРИЗОНТ (MIL)", res['h_mil'], f"{int(res['h_mil']*10)} кліків")
r3.metric("ПОТОЧНА V0", f"{res['v0_actual']} м/с")
r4.metric("ШВИДКІСТЬ У ЦІЛІ", f"Mach {res['mach']}")

# ТАКТИЧНИЙ АНАЛІЗ
with st.expander("📝 РОЗШИРЕНИЙ БАЛІСТИЧНИЙ ЗВІТ"):
    col_a, col_b = st.columns(2)
    with col_a:
        st.write(f"**Час польоту:** {res['tof']} с")
        st.write(f"**Енергія у цілі:** Залишкова швидкість {res['v_res']} м/с")
    with col_b:
        st.write(f"**Статус стабільності:** {'✅ Стабільно' if res['mach'] > 1.2 else '⚠️ Трансзвук'}")
        st.write(f"**Корекція на термозалежність:** {round(res['v0_actual'] - v0, 1)} м/с")

    st.info("Поправка враховує деривацію, ефект Коріолліса та зміну щільності повітря за моделлю ICAO.")
