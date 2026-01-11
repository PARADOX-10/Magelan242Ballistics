import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math

# --- КОНФІГУРАЦІЯ ---
st.set_page_config(page_title="Magelan242 Ballistics Pro", layout="wide")

# Стилізація інтерфейсу
st.markdown("""
    <style>
    .stButton>button { width: 100%; font-size: 24px; font-weight: bold; height: 3.5rem; border-radius: 10px; background-color: #262730; color: white; border: 2px solid #444; }
    .stButton>button:hover { border-color: #00FF00; color: #00FF00; }
    .metric-box { background-color: #1a1c24; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #333; }
    .status-safe { color: #00FF00; font-weight: bold; font-size: 18px; }
    .status-warn { color: #FFA500; font-weight: bold; font-size: 18px; }
    .status-danger { color: #FF4B4B; font-weight: bold; font-size: 18px; }
    </style>
    """, unsafe_allow_html=True)

# Ініціалізація стану сесії для кнопок
if 'dist_val' not in st.session_state: st.session_state.dist_val = 500
if 'wind_val' not in st.session_state: st.session_state.wind_val = 0.0

def get_drag_g7(mach):
    """Модель опору G7 залежно від швидкості звуку"""
    if mach >= 1.2: return 0.202
    if mach >= 0.95: return 0.202 + (1.2 - mach) * 0.45
    return 0.35

def run_pro_simulation(p):
    # Корекція швидкості від температури
    v0_corr = p['v0'] + (p['temp'] - 15) * p['t_coeff']
    tk = p['temp'] + 273.15
    rho = (p['pressure'] * 100) / (287.05 * tk)
    vsound = 331.3 * math.sqrt(tk / 273.15)
    weight_kg = p['weight_gr'] * 0.0000647989
    g = 9.80665
    dt = 0.001 
    
    results = []
    curr_x, curr_y, curr_t = 0.0, -p['sh'] / 100, 0.0
    vx, vy = v0_corr, 0.0 

    # Розрахунок до 1500 метрів
    while curr_x <= 1500:
        v_mag = math.sqrt(vx**2 + vy**2)
        mach = v_mag / vsound
        cd = get_drag_g7(mach)
        
        # Сила опору (Спрощена модель G7)
        drag_accel = (0.5 * rho * v_mag * cd * 0.00051) / (p['bc'] * weight_kg)
        
        ax = -drag_accel * vx
        ay = -drag_accel * vy - g
        
        vx += ax * dt
        vy += ay * dt
        curr_x += vx * dt
        curr_y += vy * dt
        curr_t += dt
        
        if round(curr_x) % 10 == 0:
            # Боковий знос вітром
            wind_drift = (p['w_speed'] * math.sin(math.radians(p['w_dir']*30))) * (curr_t - curr_x/v0_corr)
            results.append({
                "Дистанція": round(curr_x),
                "Drop_m": curr_y,
                "Windage_m": wind_drift,
                "Швидкість": v_mag,
                "Енергія": 0.5 * weight_kg * (v_mag**2),
                "Мах": mach
            })
            
    df = pd.DataFrame(results).drop_duplicates('Дистанція')
    
    # Розрахунок кута пристрілки (Zeroing)
    try:
        zero_drop = df.iloc[(df['Дистанція']-p['zero_dist']).abs().argsort()[:1]]['Drop_m'].values[0]
        df['Drop_cm'] = (df['Drop_m'] - (zero_drop * df['Дистанція'] / p['zero_dist'])) * 100
        # 1 MIL = 10 см на 100 м
        df['Кліки_V'] = abs(df['Drop_cm'] / (df['Дистанція'] * 0.1 + 1e-9)) / 0.1
        df['Кліки_H'] = abs(df['Windage_m'] * 100 / (df['Дистанція'] * 0.1 + 1e-9)) / 0.1
    except: pass
    
    return df, vsound

# --- БОКОВЕ МЕНЮ ---
with st.sidebar:
    st.title("🛡️ Magelan Налаштування")
    v0 = st.number_input("Початкова швидкість (м/с)", value=830.0, step=1.0)
    bc = st.number_input("БК G7", value=0.310, format="%.3f")
    weight = st.number_input("Вага кулі (гран)", value=175.0)
    zero_dist = st.number_input("Дистанція пристрілки (м)", value=100)
    sh = st.number_input("Висота прицілу (см)", value=4.5)
    temp = st.slider("Температура (°C)", -30, 50, 15)
    press = st.number_input("Тиск (hPa)", value=1013)

st.title("🏹 Magelan242 Ballistics Pro")

# --- КНОПКИ КЕРУВАННЯ ---
c_dist, c_wind = st.columns(2)

with c_dist:
    st.subheader("🎯 Дистанція цілі")
    b1, b2, b3 = st.columns([1,2,1])
    if b1.button("− 50"): st.session_state.dist_val -= 50
    b2.markdown(f"<div class='metric-box'><span style='font-size:26px; color:#00FF00;'>{st.session_state.dist_val} м</span></div>", unsafe_allow_html=True)
    if b3.button("+ 50"): st.session_state.dist_val += 50

with c_wind:
    st.subheader("💨 Боковий вітер")
    w1, w2, w3 = st.columns([1,2,1])
    if w1.button("− 1"): st.session_state.wind_val -= 1
    w2.markdown(f"<div class='metric-box'><span style='font-size:26px; color:#00FFFF;'>{st.session_state.wind_val} м/с</span></div>", unsafe_allow_html=True)
    if w3.button("+ 1"): st.session_state.wind_val += 1

# Виконання симуляції
df_res, vsound = run_pro_simulation({
    'v0': v0, 'bc': bc, 'weight_gr': weight, 'temp': temp, 'pressure': press,
    'w_speed': st.session_state.wind_val, 'w_dir': 3, 'zero_dist': zero_dist, 
    'sh': sh, 't_coeff': 0.1, 'angle': 0
})

# Отримання даних для обраної дистанції
current_dist = max(10, st.session_state.dist_val)
row = df_res.iloc[(df_res['Дистанція'] - current_dist).abs().argsort()[:1]].iloc[0]

# Визначення зони стабільності
if row['Мах'] >= 1.2:
    status_class, status_text = "status-safe", "СВЕРХЗВУК (Стабільно)"
elif row['Мах'] >= 1.0:
    status_class, status_text = "status-warn", "ТРАНСЗВУК (Нестабільно)"
else:
    status_class, status_text = "status-danger", "ДОЗВУК (Критично)"

# --- ВИВІД РЕЗУЛЬТАТІВ ---
st.markdown("---")
m1, m2, m3, m4 = st.columns(4)
m1.metric("ВЕРТИКАЛЬ (Кліки)", f"{row['Кліки_V']:.1f}")
m2.metric("ГОРИЗОНТАЛЬ (Кліки)", f"{row['Кліки_H']:.1f}")
m3.metric("Енергія (Дж)", f"{int(row['Енергія'])}")
m4.markdown(f"<div style='text-align:center'><small>Статус кулі</small><br><span class='{status_class}'>{status_text}</span></div>", unsafe_allow_html=True)

# Графік зони ураження

fig = go.Figure()
fig.add_trace(go.Scatter(x=df_res['Дистанція'], y=df_res['Швидкість'], name="Швидкість кулі", line=dict(color='lime', width=3)))
fig.add_hline(y=vsound * 1.2, line_dash="dash", line_color="orange", annotation_text="Межа трансзвуку (1.2M)")
fig.add_vline(x=current_dist, line_color="white", line_dash="dot")

fig.update_layout(
    template="plotly_dark", 
    height=400, 
    title="Аналіз швидкості та стабільності польоту",
    xaxis_title="Дистанція (м)", 
    yaxis_title="Швидкість (м/с)",
    margin=dict(l=20, r=20, t=40, b=20)
)
st.plotly_chart(fig, use_container_width=True)

# Картка вогню
with st.expander("📋 Таблиця поправок (Data Card)"):
    st.write("Крок: 100 метрів (1 клік = 0.1 MIL / 1 см на 100 м)")
    data_card = df_res[df_res['Дистанція'] % 100 == 0][['Дистанція', 'Кліки_V', 'Кліки_H', 'Швидкість', 'Мах']]
    st.dataframe(data_card.style.format(precision=2), use_container_width=True)
