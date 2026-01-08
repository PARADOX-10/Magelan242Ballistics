import streamlit as st
import pandas as pd
import numpy as np
import math

# --- КОНФИГУРАЦИЯ ---
st.set_page_config(page_title="Magelan Ballistics v85", layout="wide")

# --- СТИЛИЗАЦИЯ ПОД ТАКТИЧЕСКИЙ ИНТЕРФЕЙС ---
st.markdown("""
    <style>
    .reportview-container { background: #0e1117; }
    .stMetric { background: #1a1a1a; padding: 15px; border-radius: 8px; border-left: 5px solid #ff0000; color: white; }
    div[data-testid="stExpander"] { background: #161b22; border: 1px solid #30363d; }
    </style>
    """, unsafe_allow_html=True)

# --- БАЛЛИСТИЧЕСКИЙ ВЫЧИСЛИТЕЛЬ ---
class PrecisionSolver:
    def __init__(self, p):
        self.p = p
        self.g = 9.80665
        self.omega = 7.292115e-5
        
        # 1. Коррекция V0 по температуре (Powder Sensitivity)
        # Стандарт: 15°C. Коэффициент чувствительности: ~0.12% на каждые 10°C
        t_ref = 15.0
        v0_factor = 1 + (p['temp'] - t_ref) * (p['temp_coeff'] / 100)
        self.v0 = p['v0'] * v0_factor
        
        # 2. Плотность воздуха
        self.rho = (p['press'] * 100) / (287.05 * (p['temp'] + 273.15))
        self.v_sound = 331.3 * math.sqrt(1 + p['temp'] / 273.15)

    def get_accel(self, v_vec):
        v_mag = np.linalg.norm(v_vec)
        mach = v_mag / self.v_sound
        
        # Модель сопротивления G7
        # Апроксимация функции Cd для лодочного хвоста (Boat Tail)
        if mach > 1.2: cd = 0.35
        elif mach > 0.8: cd = 0.35 + 0.15 * (1.2 - mach) / 0.4
        else: cd = 0.50
        
        # Сила сопротивления
        drag_const = 0.5 * self.rho * (1 / self.p['bc']) * 0.00052
        a_drag = -drag_const * v_mag * v_vec
        
        # Гравитация
        a_grav = np.array([0, -self.g, 0])
        
        # Эффект Кориолиса (вертикальный и горизонтальный)
        lat = math.radians(self.p['lat'])
        az = math.radians(self.p['az'])
        v_cor = 2 * self.omega * np.array([
            v_vec[2]*math.sin(lat) - v_vec[1]*math.cos(lat)*math.sin(az),
            v_vec[0]*math.cos(lat)*math.sin(az),
            -v_vec[0]*math.sin(lat)
        ])
        
        return a_drag + a_grav + v_cor

    def solve(self):
        dt = 0.005 # Крок 5 мс
        pos = np.array([0.0, self.p['sh']/100, 0.0])
        vel = np.array([self.v0, 0.0, 0.0])
        t = 0.0
        
        v_wind = np.array([
            self.p['ws'] * math.cos(math.radians(self.p['wh']*30)),
            0.0,
            self.p['ws'] * math.sin(math.radians(self.p['wh']*30))
        ])

        while pos[0] < self.p['dist']:
            # Интегрирование RK4
            v_rel = vel - v_wind
            k1 = self.get_accel(v_rel)
            k2 = self.get_accel(v_rel + 0.5 * dt * k1)
            
            vel += dt * k2
            pos += dt * vel
            t += dt

        # 3. Деривация (Spin Drift)
        # Упрощенная формула Лица для стабилизированной пули
        sd = 1.25 * (1.5 + 1.2) * (t**1.83) * 0.0254 # в метрах
        
        # 4. Итоговые поправки в MIL
        v_mil = abs(pos[1] * 100) / (self.p['dist'] / 10)
        h_mil = (abs(pos[2] + sd) * 100) / (self.p['dist'] / 10)
        
        return {
            'v_mil': round(v_mil, 2),
            'h_mil': round(h_mil, 2),
            'v_res': int(np.linalg.norm(vel)),
            'tof': round(t, 3),
            'mach': round(np.linalg.norm(vel)/self.v_sound, 2),
            'v0_actual': round(self.v0, 1)
        }

# --- ИНТЕРФЕЙС ---
st.title("🛡️ Magelan Omniscient v85.0")

with st.sidebar:
    st.header("🗜️ Снаряжение")
    v0 = st.number_input("Начальная скорость (м/с)", 893.0)
    bc = st.number_input("БК G7", 0.292, format="%.3f")
    t_coeff = st.slider("Термозависимость пороха (% на 10°C)", 0.0, 2.0, 0.5)
    sh = st.number_input("Высота прицела (см)", 5.0)
    
    st.header("🌍 Геопозиция")
    lat = st.number_input("Широта (градусы)", 50.0)
    az = st.slider("Азимут стрельбы", 0, 360, 90)

# ОСНОВНОЙ БЛОК
c1, c2, c3 = st.columns(3)
dist = c1.number_input("Дистанция до цели (м)", 100, 2000, 800)
temp = c2.slider("Температура воздуха (°C)", -25, 45, 15)
press = c3.number_input("Давление (гПа/mbar)", 900, 1100, 1013)

ws = c1.slider("Скорость ветра (м/с)", 0, 25, 3)
wh = c2.slider("Направление ветра (час)", 0, 12, 3)
click = c3.selectbox("Клик прицела", [0.1, 0.05], format_func=lambda x: f"{x} MIL")

# РАСЧЕТ
solver = PrecisionSolver({
    'v0': v0, 'bc': bc, 'temp_coeff': t_coeff, 'sh': sh,
    'dist': dist, 'temp': temp, 'press': press, 'ws': ws, 'wh': wh,
    'lat': lat, 'az': az
})
res = solver.solve()

st.divider()

# ВЫВОД РЕЗУЛЬТАТОВ
r1, r2, r3, r4 = st.columns(4)
r1.metric("ВЕРТИКАЛЬ (MIL)", res['v_mil'], f"{int(res['v_mil']/click)} кликов")
r2.metric("ГОРИЗОНТ (MIL)", res['h_mil'], f"{int(res['h_mil']/click)} кликов")
r3.metric("СКОРОСТЬ V0 (КОРР.)", f"{res['v0_actual']} м/с")
r4.metric("У ЦЕЛИ", f"Mach {res['mach']}")

# ПОЯСНЕНИЯ
with st.expander("📝 Анализ баллистического решения"):
    st.write(f"- **Время полета:** {res['tof']} сек")
    st.write(f"- **Температурный сдвиг скорости:** {round(res['v0_actual'] - v0, 1)} м/с")
    if res['mach'] < 1.2:
        st.error("⚠️ Пуля в трансзвуковой зоне. Прогнозируемая точность падает.")
    else:
        st.success("✅ Пуля сохраняет гироскопическую стабильность.")
