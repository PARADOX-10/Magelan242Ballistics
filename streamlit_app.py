import streamlit as st
import numpy as np
import math
import plotly.graph_objects as go

# --- КОНФІГУРАЦІЯ СТОРІНКИ ---
st.set_page_config(page_title="Magelan Apex Pro v135", layout="wide")

class AdvancedBallistics:
    def __init__(self, p):
        self.p = p
        self.g = 9.80665
        self.m_kg = p['weight'] * 0.0000647989 
        self.v0 = p['v0'] * (1 + (p['temp'] - 15) * (p['p_sens'] / 100))
        self.rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
        self.omega_earth = 7.292115e-5 

    def get_drag_g7(self, velocity):
        """Модель опору G7 залежно від швидкості звуку"""
        mach = velocity / (331.3 + 0.606 * self.p['temp'])
        if mach > 1.0: return 0.22 + (0.05 * (mach - 1))
        return 0.22 + (0.15 * (1 - mach))

    def solve(self, target_dist, extra_angle_moa=0):
        dt = 0.001
        # Початкова позиція: ствол на -sh см від лінії прицілювання
        pos = np.array([0.0, -self.p['sh']/100, 0.0])
        
        # Кут вильоту = кут цілі + кут пристрілки
        total_angle = math.radians(self.p['angle'] + (extra_angle_moa / 60))
        vel = np.array([
            self.v0 * math.cos(total_angle),
            self.v0 * math.sin(total_angle),
            0.0
        ])
        
        wind_rad = math.radians(self.p['wh'] * 30)
        v_wind = np.array([0.0, 0.0, self.p['ws'] * math.sin(wind_rad)])
        
        t = 0.0
        while pos[0] < target_dist and t < 4.0:
            v_rel = vel - v_wind
            v_mag = np.linalg.norm(v_rel)
            
            # Опір
            cd = self.get_drag_g7(v_mag)
            accel_drag = -(0.5 * self.rho * v_mag * cd * 0.00052 / (self.p['bc'] * self.m_kg)) * v_rel
            
            # Коріоліс (спрощено для середніх широт)
            lat_rad = math.radians(self.p['lat'])
            coriolis_z = 2 * vel[0] * self.omega_earth * math.sin(lat_rad)
            
            accel_total = accel_drag + np.array([0, -self.g, coriolis_z])
            
            vel += accel_total * dt
            pos += vel * dt
            t += dt
            
        return pos, t, vel

    def get_corrections(self):
        # 1. Знаходимо кут пристрілки для 100м (Zeroing)
        zero_angle = 0
        for _ in range(3):
            pos, _, _ = self.solve(100, zero_angle)
            zero_angle -= (pos[1] / 100) * (180/math.pi) * 60

        # 2. Основний розрахунок на дистанцію
        final_pos, tof, final_vel = self.solve(self.p['dist'], zero_angle)
        
        # 3. Деривація (Spin Drift)
        sd_m = (1.25 * (1.5 + 1.2) * (tof**1.83)) * 0.0254
        
        # Перерахунок у MIL
        v_mil = -(final_pos[1] * 100) / (self.p['dist'] / 10)
        h_mil = ((final_pos[2] + sd_m) * 100) / (self.p['dist'] / 10)
        
        return {
            "v_mil": round(v_mil, 2),
            "h_mil": round(h_mil, 2),
            "v_at": int(np.linalg.norm(final_vel)),
            "tof": round(tof, 3)
        }

# --- ВІЗУАЛІЗАЦІЯ СІТКИ ---
def draw_reticle(v_mil, h_mil):
    fig = go.Figure()
    # Основні лінії
    fig.add_shape(type="line", x0=-10, y0=0, x1=10, y1=0, line=dict(color="rgba(255,255,255,0.5)", width=1))
    fig.add_shape(type="line", x0=0, y0=-15, x1=0, y1=5, line=dict(color="rgba(255,255,255,0.5)", width=1))
    
    # Спрощена "ялинка" (MIL dots)
    for i in range(1, 13):
        fig.add_shape(type="line", x0=-0.2, y0=-i, x1=0.2, y1=-i, line=dict(color="white", width=1))
        if i % 2 == 0: # Додаткові лінії для вітру
            fig.add_shape(type="line", x0=-i/4, y0=-i, x1=i/4, y1=-i, line=dict(color="rgba(255,255,255,0.2)", width=1))

    # Точка влучання
    fig.add_trace(go.Scatter(
        x=[h_mil], y=[-v_mil],
        mode="markers",
        marker=dict(color="red", size=15, symbol="cross"),
        name="Impact"
    ))

    fig.update_layout(
        template="plotly_dark",
        xaxis=dict(range=[-5, 5], showgrid=False, zeroline=False),
        yaxis=dict(range=[-13, 2], showgrid=False, zeroline=False),
        margin=dict(l=0, r=0, t=0, b=0),
        height=600, width=500
    )
    return fig

# --- STREAMLIT UI ---
st.title("🏹 Magelan Apex Pro v135")

col_side, col_main = st.columns([1, 2])

with col_side:
    st.header("⚙️ ТТХ")
    v0 = st.number_input("V0 (м/с)", value=820)
    bc = st.number_input("BC G7", value=0.305, format="%.3f")
    weight = st.number_input("Вага (гран)", value=175)
    sh = st.number_input("Висота прицілу (см)", value=4.5)
    
    st.header("🌍 Середовище")
    dist = st.slider("Дистанція (м)", 100, 1500, 800)
    ws = st.slider("Вітер (м/с)", 0.0, 15.0, 4.0)
    wh = st.slider("Вітер (год)", 0, 12, 3)
    temp = st.slider("Температура (°C)", -20, 40, 15)
    lat = st.slider("Широта (Коріоліс)", 0, 90, 48)

# Розрахунок
engine = AdvancedBallistics({
    'v0': v0, 'bc': bc, 'weight': weight, 'sh': sh, 'dist': dist,
    'ws': ws, 'wh': wh, 'temp': temp, 'press': 1013, 'p_sens': 1.0, 
    'angle': 0, 'lat': lat
})
res = engine.get_corrections()

with col_main:
    # HUD
    c1, c2, c3 = st.columns(3)
    c1.metric("Вертикаль (MIL)", res['v_mil'])
    c2.metric("Горизонталь (MIL)", res['h_mil'])
    c3.metric("Швидкість (м/с)", res['v_at'])
    
    # Відображення сітки
    st.plotly_chart(draw_reticle(res['v_mil'], res['h_mil']), use_container_width=True)
    st.info(f"Час польоту: {res['tof']} сек")
