import streamlit as st
import pd as pd
import numpy as np
import plotly.graph_objects as go
import math

# --- КОНФИГУРАЦИЯ ---
st.set_page_config(page_title="Magelan242 Ballistics Pro", layout="wide")

# Стиль кнопок и индикаторов
st.markdown("""
    <style>
    .stButton>button { width: 100%; font-size: 24px; font-weight: bold; height: 3.5rem; border-radius: 10px; background-color: #262730; color: white; }
    .stButton>button:hover { border-color: #00FF00; color: #00FF00; }
    .metric-box { background-color: #1a1c24; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #333; }
    .status-safe { color: #00FF00; font-weight: bold; }
    .status-warn { color: #FFA500; font-weight: bold; }
    .status-danger { color: #FF4B4B; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# Инициализация состояния
if 'dist_val' not in st.session_state: st.session_state.dist_val = 500
if 'wind_val' not in st.session_state: st.session_state.wind_val = 0.0

def get_drag_g7(mach):
    if mach >= 1.2: return 0.202
    if mach >= 0.95: return 0.202 + (1.2 - mach) * 0.45
    return 0.35

def run_pro_simulation(p):
    v0_corr = p['v0'] + (p['temp'] - 15) * p['t_coeff']
    tk = p['temp'] + 273.15
    rho = (p['pressure'] * 100) / (287.05 * tk)
    vsound = 331.3 * math.sqrt(tk / 273.15)
    weight_kg = p['weight_gr'] * 0.0000647989
    g = 9.80665
    dt = 0.001 
    
    results = []
    curr_v = v0_corr
    curr_x, curr_y, curr_t = 0.0, -p['sh'] / 100, 0.0
    vx, vy = v0_corr, 0.0 # Упрощенный вектор для вычисления падения

    while curr_x <= 1500: # Считаем до 1.5км для анализа зон
        v_mag = math.sqrt(vx**2 + vy**2)
        mach = v_mag / vsound
        cd = get_drag_g7(mach)
        
        drag_accel = (0.5 * rho * v_mag * cd * 0.00051) / (p['bc'] * weight_kg)
        
        ax = -drag_accel * vx
        ay = -drag_accel * vy - g
        
        vx += ax * dt
        vy += ay * dt
        curr_x += vx * dt
        curr_y += vy * dt
        curr_t += dt
        
        if round(curr_x) % 10 == 0:
            wind_drift = (p['w_speed'] * math.sin(math.radians(p['w_dir']*30))) * (curr_t - curr_x/v0_corr)
            results.append({
                "Distance": round(curr_x),
                "Drop_m": curr_y,
                "Windage_m": wind_drift,
                "Velocity": v_mag,
                "Energy": 0.5 * weight_kg * (v_mag**2),
                "Mach": mach
            })
            
    df = pd.DataFrame(results).drop_duplicates('Distance')
    
    # Расчет Zero
    try:
        zero_drop = df.iloc[(df['Distance']-p['zero_dist']).abs().argsort()[:1]]['Drop_m'].values[0]
        df['Drop_cm'] = (df['Drop_m'] - (zero_drop * df['Distance'] / p['zero_dist'])) * 100
        df['Clicks_V'] = abs(df['Drop_cm'] / (df['Distance'] * 0.1 + 1e-9))
        df['Clicks_H'] = abs(df['Windage_m'] * 100 / (df['Distance'] * 0.1 + 1e-9))
    except: pass
    
    return df, vsound

# --- ИНТЕРФЕЙС ---
with st.sidebar:
    st.title("🛡️ Magelan G7 Core")
    v0 = st.number_input("Начальная скорость (м/с)", value=830.0)
    bc = st.number_input("БК G7", value=0.310, format="%.3f")
    weight = st.number_input("Вес кули (гран)", value=175.0)
    zero_dist = st.number_input("Дистанция пристрелки (м)", value=100)
    sh = st.number_input("Высота прицела (см)", value=4.5)

st.title("🏹 Magelan242 Ballistics Pro")

# Кнопки управления
c_dist, c_wind = st.columns(2)
with c_dist:
    st.subheader("🎯 Дистанция")
    b1, b2, b3 = st.columns([1,2,1])
    if b1.button("−50"): st.session_state.dist_val -= 50
    b2.markdown(f"<div class='metric-box'><span style='font-size:24px;'>{st.session_state.dist_val} м</span></div>", unsafe_allow_html=True)
    if b3.button("+50"): st.session_state.dist_val += 50

with c_wind:
    st.subheader("💨 Ветер")
    w1, w2, w3 = st.columns([1,2,1])
    if w1.button("−1"): st.session_state.wind_val -= 1
    w2.markdown(f"<div class='metric-box'><span style='font-size:24px;'>{st.session_state.wind_val} м/с</span></div>", unsafe_allow_html=True)
    if w3.button("+1"): st.session_state.wind_val += 1

# Расчет
df_res, vsound = run_pro_simulation({
    'v0': v0, 'bc': bc, 'weight_gr': weight, 'temp': 15, 'pressure': 1013,
    'w_speed': st.session_state.wind_val, 'w_dir': 3, 'zero_dist': zero_dist, 
    'max_dist': 1500, 'sh': sh, 't_coeff': 0.1, 'angle': 0
})

# Данные для текущей дистанции
row = df_res.iloc[(df_res['Distance'] - st.session_state.dist_val).abs().argsort()[:1]].iloc[0]

# Определение Зоны Поражения
status_class = "status-safe"
status_text = "СВЕРХЗВУК (Уверенная зона)"
if row['Mach'] < 1.2:
    status_class = "status-warn"
    status_text = "ТРАНСЗВУК (Низкая стабильность)"
if row['Mach'] < 1.0:
    status_class = "status-danger"
    status_text = "ДОЗВУК (Критическая зона)"

# Вывод метрик
st.markdown("---")
m1, m2, m3, m4 = st.columns(4)
m1.metric("ВЕРТИКАЛЬ (Клик 0.1)", f"{row['Clicks_V']:.1f}")
m2.metric("ГОРИЗОНТАЛЬ (Клик 0.1)", f"{row['Clicks_H']:.1f}")
m3.metric("ЭНЕРГИЯ (Дж)", f"{int(row['Energy'])}")
m4.markdown(f"<div style='text-align:center'><small>Статус пули</small><br><span class='{status_class}'>{status_text}</span></div>", unsafe_allow_html=True)

# График с зонами
fig = go.Figure()
fig.add_trace(go.Scatter(x=df_res['Distance'], y=df_res['Velocity'], name="Скорость", line=dict(color='lime')))
# Линия скорости звука
fig.add_hline(y=vsound * 1.2, line_dash="dash", line_color="orange", annotation_text="Груница трансзвука (1.2M)")
fig.add_vline(x=st.session_state.dist_val, line_color="white")

fig.update_layout(template="plotly_dark", height=400, title="График скорости и стабильности", xaxis_title="Дистанция (м)", yaxis_title="Скорость (м/с)")
st.plotly_chart(fig, use_container_width=True)

# Таблица прострела
with st.expander("📊 Таблица поправок (Data Card)"):
    st.dataframe(df_res[df_res['Distance'] % 100 == 0][['Distance', 'Clicks_V', 'Clicks_H', 'Velocity', 'Mach']].style.format(precision=2))
