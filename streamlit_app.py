import streamlit as st
import pandas as pd
import numpy as np
import math
import plotly.graph_objects as go

# --- КОНФІГУРАЦІЯ СТОРІНКИ ---
st.set_page_config(page_title="Magelan Ballistics Pro UA", layout="centered")

# --- ПРЕСЕТИ ---
PRESETS = {
    "Мій .300 Win Mag (195gr)": {
        "cal": 0.308, "weight": 195.0, "len": 1.450, 
        "bc_g7": 0.292, "bc_g1": 0.584, "v0": 893.0, "twist": 11.0
    },
    ".308 Win (175gr)": {
        "cal": 0.308, "weight": 175.0, "len": 1.24, 
        "bc_g7": 0.243, "bc_g1": 0.495, "v0": 790, "twist": 11.0
    }
}

# --- ТЕМА (НІЧНИЙ РЕЖИМ) ---
if 'night' not in st.session_state: st.session_state.night = False
night = st.session_state.night
bg, txt, acc, card = ("#0A0000", "#FF0000", "#CC0000", "#1A0000") if night else ("#0E1117", "#FFFFFF", "#C62828", "#1E1E1E")

st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg}; color: {txt}; }}
    .hud-card {{ background-color: {card}; border-radius: 10px; padding: 15px; text-align: center; border-left: 5px solid {acc}; margin-bottom: 10px; }}
    .hud-label {{ color: {'#880000' if night else '#888'}; font-size: 12px; font-weight: bold; text-transform: uppercase; }}
    .hud-value {{ color: {txt}; font-size: 36px; font-weight: 900; }}
    .stButton>button {{ width: 100%; background-color: {card}; color: {txt}; border: 1px solid {acc}; }}
    </style>
    """, unsafe_allow_html=True)

# --- БАЛІСТИЧНЕ ЯДРО ---
def get_ballistics(p, d):
    if d <= 0: return {"v": 0, "h": 0, "side": "П", "v_at": p['v0'], "mach": 0, "sg": 0, "tof": 0, "cor_cm": 0}
    
    # 1. Атмосфера та щільність
    e_sat = 6.112 * math.exp((17.67 * p['temp']) / (p['temp'] + 243.5))
    rho = ((p['press'] - (p['hum']/100)*e_sat) * 100 / (287.05 * (p['temp'] + 273.15)))
    
    # 2. Опір повітря (Drag)
    bc_adj = p['bc'] * (1.225 / rho)
    k = 0.5 * rho * (1/bc_adj) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    
    tof = (math.exp(k * d) - 1) / (k * p['v0'])
    v_at = p['v0'] * math.exp(-k * d)
    mach = v_at / (331.3 * math.sqrt(1 + p['temp'] / 273.15))

    # 3. Геофізичні ефекти (Коріоліс)
    omega = 7.2921e-5
    lat_r = math.radians(p['lat'])
    az_r = math.radians(p['az'])
    cor_h_cm = abs(2 * omega * d * p['v0'] * math.sin(lat_r) * tof / d) * 100
    cor_v = 2 * omega * d * p['v0'] * math.cos(lat_r) * math.sin(az_r) * tof / d

    # 4. Вітер та деривація
    wind_x = p['w_speed'] * math.sin(math.radians(p['w_hour'] * 30))
    aj = 0.012 * wind_x * (d / 100) / 10 * (1 if p['tw_d'] == "R" else -1)
    
    # Траєкторія
    t_z = (math.exp(k * p['zero']) - 1) / (k * p['v0'])
    drop = -((0.5 * 9.806 * tof**2) - (0.5 * 9.806 * t_z**2 + p['sh']/100) * (d / p['zero']) + p['sh']/100)
    
    v_mil = abs((drop + cor_v) * 100 / (d/10) / 0.1) + aj
    sd = 1.25 * (p['tw_v'] / 10 + 1.2) * (tof**1.83) * (1 if p['tw_d'] == "R" else -1)
    cor_h = 2 * omega * d * p['v0'] * math.sin(lat_r) * tof / d
    h_mil = (wind_x * (tof - d/p['v0']) + sd + cor_h) * 100 / (d/10) / 0.1

    return {
        "v": round(v_mil, 2), "h": round(abs(h_mil), 2), 
        "side": "Л" if h_mil < 0 else "П", "v_at": int(v_at), 
        "mach": round(mach, 2), "tof": round(tof, 3), "cor_cm": cor_h_cm
    }

# --- ІНТЕРФЕЙС ---
st.button("🌙 НІЧНИЙ РЕЖИМ", on_click=lambda: st.session_state.update({'night': not st.session_state.night}))

preset_name = st.selectbox("ОБЕРІТЬ НАБІЙ:", list(PRESETS.keys()))
defaults = PRESETS[preset_name]

st.markdown('<div style="position: sticky; top: 0; background: #0E1117; z-index: 100; padding: 10px 0; border-bottom: 2px solid red;">', unsafe_allow_html=True)
dist = st.slider("🎯 ДИСТАНЦІЯ ДО ЦІЛІ (м)", 0, 1800, 800, step=5)
h_c1, h_c2 = st.columns(2)
st.markdown('</div>', unsafe_allow_html=True)

with st.expander("⚙️ 1. ОПТИКА ТА ЦІНА КЛІКА", expanded=True):
    click_val = st.number_input("Ціна кліка (MIL)", value=0.1, step=0.01, help="Пояснення: Скільки MIL в одному кліку барабана.")
    sh = st.number_input("Висота осі прицілу (см)", value=5.0, help="Відстань від центру ствола до центру лінзи.")
    zero = st.number_input("Дистанція пристрілки (м)", value=100)

with st.expander("🔫 2. ЗБРОЯ ТА ПАТРОН"):
    m_mod = st.radio("Драг-модель", ["G7", "G1"], horizontal=True, help="G7 - для BT куль, G1 - для плоских.")
    c1, c2 = st.columns(2)
    v0 = c1.number_input("Швидкість V0 (м/с)", value=float(defaults['v0']))
    bc = c2.number_input(f"Коефіцієнт БК", value=float(defaults['bc_g7'] if m_mod=="G7" else defaults['bc_g1']), format="%.3f")
    tw = c1.number_input("Твіст ствола 1:", value=float(defaults['twist']))
    tw_d = c2.radio("Напрямок нарізів", ["R", "L"], horizontal=True)

with st.expander("🌍 3. СЕРЕДОВИЩЕ ТА ГЕОПОЗИЦІЯ"):
    t = st.slider("Температура (°C)", -30, 50, 15)
    p_at = st.number_input("Тиск (гПа)", value=1013)
    ws = st.slider("Швидкість вітру (м/с)", 0, 20, 3)
    wh = st.slider("Напрямок вітру (год)", 1, 12, 3)
    lat = st.number_input("Широта (гео)", value=50)
    az = st.slider("Азимут стрільби", 0, 360, 90)

# РОЗРАХУНОК
final_p = {**defaults, 'temp':t,'press':p_at,'hum':50,'v0':v0,'bc':bc,'model':m_mod,'lat':lat,'az':az,'tw_v':tw,'tw_d':tw_d,'sh':sh,'zero':zero,'w_speed':ws,'w_hour':wh}
res = get_ballistics(final_p, dist)

# ОКРУГЛЕННЯ КЛІКІВ
v_cl = int(round(res['v'] / click_val))
h_cl = int(round(res['h'] / click_val))

# HUD ВИВІД
h_c1.markdown(f'<div class="hud-card"><div class="hud-label">↑ ВГОРУ (MIL)</div><div class="hud-value">{res["v"]}</div><div class="hud-label" style="color:red">{v_cl} КЛІКІВ</div></div>', unsafe_allow_html=True)
h_c2.markdown(f'<div class="hud-card"><div class="hud-label">↔ {res["side"]} (MIL)</div><div class="hud-value">{res["h"]}</div><div class="hud-label" style="color:red">{h_cl} КЛІКІВ</div></div>', unsafe_allow_html=True)

# --- ВІЗУАЛІЗАЦІЯ СІТКИ MILDOT ---
st.subheader("🔭 Візуалізація сітки (Holdover)")


fig_ret = go.Figure()
# Хрест
fig_ret.add_shape(type="line", x0=-10, y0=0, x1=10, y1=0, line=dict(color="gray", width=1))
fig_ret.add_shape(type="line", x0=0, y0=-15, x1=0, y1=5, line=dict(color="gray", width=1))
# Точки (dots)
for i in range(-10, 11):
    if i != 0: fig_ret.add_trace(go.Scatter(x=[i], y=[0], mode='markers', marker=dict(color='gray', size=5), showlegend=False))
for i in range(-15, 6):
    if i != 0: fig_ret.add_trace(go.Scatter(x=[0], y=[i], mode='markers', marker=dict(color='gray', size=5), showlegend=False))

# Точка влучання
ix = -res['h'] if res['side'] == "П" else res['h']
iy = -res['v']
fig_ret.add_trace(go.Scatter(x=[ix], y=[iy], mode='markers', marker=dict(color='red', size=15, symbol='cross'), name="Точка влучання"))

fig_ret.update_layout(xaxis=dict(range=[-10, 10], showgrid=False), yaxis=dict(range=[-15, 5], showgrid=False), 
                      width=500, height=500, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white"))
st.plotly_chart(fig_ret)

# --- ГРАФІК ШВИДКОСТІ ---
st.subheader("📊 Аналіз енергії (Mach)")


dists = np.arange(0, 1600, 20)
machs = [get_ballistics(final_p, d)['mach'] for d in dists]
fig_v = go.Figure()
fig_v.add_trace(go.Scatter(x=dists, y=machs, name="Mach", line=dict(color='red', width=3)))
fig_v.add_hline(y=1.2, line_dash="dash", line_color="orange", annotation_text="Межа стабільності")
fig_v.update_layout(xaxis_title="Дистанція (м)", yaxis_title="Число Маха", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white"))
st.plotly_chart(fig_v)

# --- ТАБЛИЦЯ ПОПРАВОК ---
if st.checkbox("Показати таблицю поправок (Drop Chart)"):
    chart = []
    for d in range(100, 1250, 50):
        r = get_ballistics(final_p, d)
        chart.append({
            "Дистанція (м)": d, "MIL ↑": r['v'], "Кліки ↑": int(round(r['v'] / click_val)),
            "MIL ↔": r['h'], "Кліки ↔": int(round(r['h'] / click_val)), "Статус": "🟢" if r['mach'] > 1.2 else "🟡"
        })
    st.table(pd.DataFrame(chart))
