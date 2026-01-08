import streamlit as st
import pandas as pd
import numpy as np
import math
import plotly.graph_objects as go

# --- КОНФІГУРАЦІЯ ---
st.set_page_config(page_title="Magelan Apex v135 Pro", layout="wide")

class BallisticCore:
    def __init__(self, p):
        self.p = p
        self.g = 9.80665
        # Переведення одиниць
        self.m_kg = p['weight'] * 0.0000647989 
        self.v0 = p['v0'] * (1 + (p['temp'] - 15) * (p['p_sens'] / 100))
        
    def get_drag_coeff(self, velocity):
        """Апроксимація коефіцієнта опору G7 залежно від числа Маха"""
        mach = velocity / (331.3 + 0.606 * self.p['temp'])
        # Спрощена крива G7
        if mach > 1.2: return 0.25
        if mach > 0.8: return 0.25 + (1.2 - mach) * 0.2
        return 0.40

    def solve_trajectory(self, target_dist, launch_angle_moa=0):
        dt = 0.001 # Точніший крок
        pos = np.array([0.0, -self.p['sh']/100, 0.0]) # Ствол нижче прицілу
        
        # Початковий вектор швидкості з урахуванням кута пристрілки + кута цілі
        total_angle = math.radians(self.p['angle'] + (launch_angle_moa / 60))
        vel = np.array([
            self.v0 * math.cos(total_angle),
            self.v0 * math.sin(total_angle),
            0.0
        ])
        
        # Вітер
        wind_rad = math.radians(self.p['wh'] * 30)
        v_wind = np.array([
            self.p['ws'] * math.cos(wind_rad) * -1, # Спрощено: вітер в обличчя/спину
            0.0,
            self.p['ws'] * math.sin(wind_rad)
        ])
        
        rho = (self.p['press'] * 100) / (287.05 * (self.p['temp'] + 273.15))
        path = []
        t = 0.0
        
        while pos[0] < target_dist and t < 5.0:
            v_rel = vel - v_wind
            v_mag = np.linalg.norm(v_rel)
            
            # Динамічний опір
            drag_c = self.get_drag_coeff(v_mag)
            # Корекція БК (спрощено: BC G7 базується на стандартній кулі)
            accel_drag = -(0.5 * rho * v_mag * drag_c * (0.0005) / (self.p['bc'] * self.m_kg)) * v_rel
            
            accel_total = accel_drag + np.array([0, -self.g, 0])
            
            vel += accel_total * dt
            pos += vel * dt
            t += dt
            path.append(pos.copy())
            
        return np.array(path), t, vel

    def calculate(self):
        # 1. Знаходимо кут пристрілки (Zero Angle) для 100м
        # Робимо ітерацію, щоб знайти під яким кутом куля влучає в 0 на 100м
        zero_angle = 0
        for _ in range(3):
            path, _, _ = self.solve_trajectory(100, zero_angle)
            drop_at_zero = path[-1][1]
            zero_angle -= (drop_at_zero / 100) * 3438 # корекція в MOA

        # 2. Рахуємо реальну траєкторію
        full_path, tof, final_vel = self.solve_trajectory(self.p['dist'], zero_angle)
        
        # 3. Деривація (Spin Drift)
        # Спрощена формула: Dr = 1.25 * (Sg + 1.2) * TOF^1.83 (в дюймах, переводимо в метри)
        sd_m = (1.25 * (1.5 + 1.2) * (tof**1.83)) * 0.0254
        
        # Поправки в MIL
        drop_m = full_path[-1][1]
        v_mil = -(drop_m * 10) / (self.p['dist'] / 100)
        h_mil = (sd_m * 10) / (self.p['dist'] / 100)
        
        return {
            'v_mil': round(max(0, v_mil), 2),
            'h_mil': round(h_mil, 2),
            'v_at': int(np.linalg.norm(final_vel)),
            'e_final': int(0.5 * self.m_kg * np.linalg.norm(final_vel)**2),
            'path': full_path,
            'tof': round(tof, 3)
        }

# --- INTERFACE (Streamlit) ---
st.title("🏹 Magelan Apex v135 Pro")

col_main, col_side = st.columns([3, 1])

with col_side:
    st.subheader("⚙️ Параметри")
    v0 = st.number_input("V0 м/с", value=830)
    bc = st.number_input("BC G7", value=0.310, format="%.3f")
    tw = st.number_input("Твіст 1:10", value=10)
    weight = st.number_input("Вага (гран)", value=175)
    sh = st.number_input("Висота прицілу (см)", value=4.5)

with col_main:
    d = st.slider("Відстань (м)", 100, 1200, 500)
    ws = st.slider("Вітер (м/с)", 0, 15, 4)
    wh = st.slider("Напрямок вітру (год)", 0, 12, 3)
    
    engine = BallisticCore({
        'v0': v0, 'bc': bc, 'weight': weight, 'sh': sh, 'dist': d,
        'ws': ws, 'wh': wh, 'temp': 15, 'press': 1013, 'p_sens': 1.0, 'angle': 0
    })
    res = engine.calculate()

    # HUD
    c1, c2, c3 = st.columns(3)
    c1.metric("Вертикаль (MIL)", res['v_mil'])
    c2.metric("Горизонталь (SD/Wind)", res['h_mil'])
    c3.metric("Енергія (Дж)", res['e_final'])

    # Графік
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=res['path'][:,0], y=res['path'][:,1] * 100, name="Траєкторія (см)"))
    fig.update_layout(title="Падіння кулі (см)", template="plotly_dark", height=400)
    st.plotly_chart(fig, use_container_width=True)

st.info(f"Час польоту: {res['tof']} с | Швидкість у цілі: {res['v_at']} м/с")
