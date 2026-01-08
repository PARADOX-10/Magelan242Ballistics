import streamlit as st
import pandas as pd
import numpy as np
import math

st.set_page_config(page_title="Magelan Ballistics UA", layout="centered")

# --- ПРЕСЕТИ ---
PRESETS = {
    "Мій .300 Win Mag (195gr)": {
        "cal": 0.308, "weight": 195.0, "len": 1.450, 
        "bc_g7": 0.292, "bc_g1": 0.584, "v0": 893.0, "twist": 11.0
    },
    ".308 Win (175gr)": {"cal": 0.308, "weight": 175.0, "len": 1.24, "bc_g7": 0.243, "bc_g1": 0.495, "v0": 790, "twist": 11.0}
}

# --- ТЕМА ---
if 'night' not in st.session_state: st.session_state.night = False
night = st.session_state.night
bg, txt, acc, card = ("#0A0000", "#FF0000", "#CC0000", "#1A0000") if night else ("#0E1117", "#FFFFFF", "#C62828", "#1E1E1E")

st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg}; color: {txt}; }}
    .hud-card {{ background-color: {card}; border-radius: 10px; padding: 12px; text-align: center; border-left: 4px solid {acc}; margin-bottom: 5px; }}
    .hud-label {{ color: {'#660000' if night else '#888'}; font-size: 11px; font-weight: bold; text-transform: uppercase; }}
    .hud-value {{ color: {txt}; font-size: 32px; font-weight: 900; }}
    .stButton>button {{ width: 100%; background-color: {card}; color: {txt}; border: 1px solid {acc}; }}
    </style>
    """, unsafe_allow_html=True)

# --- БАЛІСТИЧНЕ ЯДРО ---
def get_ballistics(p, d):
    if d <= 0: return {"v_mil": 0, "h_mil": 0, "h_side": "R", "v_at": p['v0'], "mach": 0, "sg": 0, "tof": 0, "cor_h_cm": 0}
    
    # 1. Щільність повітря
    e_sat = 6.112 * math.exp((17.67 * p['temp']) / (p['temp'] + 243.5))
    rho = ((p['press'] - (p['hum']/100)*e_sat) * 100 / (287.05 * (p['temp'] + 273.15)))
    
    # 2. Опір
    bc_adj = p['bc'] * (1.225 / rho)
    k = 0.5 * rho * (1/bc_adj) * 0.00052 * (0.91 if p['model'] == "G7" else 1.0)
    
    tof = (math.exp(k * d) - 1) / (k * p['v0'])
    v_at = p['v0'] * math.exp(-k * d)
    mach = v_at / (331.3 * math.sqrt(1 + p['temp'] / 273.15))

    # 3. Коріоліс та Етвеш
    omega = 7.2921e-5
    cor_h_cm = abs(2 * omega * d * p['v0'] * math.sin(math.radians(p['lat'])) * tof / d) * 100
    cor_v = 2 * omega * d * p['v0'] * math.cos(math.radians(p['lat'])) * math.sin(math.radians(p['az'])) * tof / d

    # 4. Поправки
    w_rad = math.radians(p['w_hour'] * 30)
    wind_x = p['w_speed'] * math.sin(w_rad)
    aj = 0.012 * wind_x * (d / 100) / 10 * (1 if p['tw_d'] == "R" else -1)
    
    t_z = (math.exp(k * p['zero']) - 1) / (k * p['v0'])
    drop = -((0.5 * 9.806 * tof**2) - (0.5 * 9.806 * t_z**2 + p['sh']/100) * (d / p['zero']) + p['sh']/100)
    
    v_mil = abs((drop + cor_v) * 100 / (d/10) / 0.1) + aj
    
    sd = 1.25 * (p['tw_v'] / 10 + 1.2) * (tof**1.83) * (1 if p['tw_d'] == "R" else -1)
    cor_h = 2 * omega * d * p['v0'] * math.sin(math.radians(p['lat'])) * tof / d
    h_mil = (wind_x * (tof - d/p['v0']) + sd + cor_h) * 100 / (d/10) / 0.1

    # 5. Стабільність
    m_lb, m_cal = p['weight'] / 7000, p['cal']
    sg = (30 * m_lb) / ( (p['tw_v']/m_cal)**2 * m_cal**3 * (p['len']/m_cal) * (1 + (p['len']/m_cal)**2) ) * (p['v0']/2800)**(1/3)

    return {"v": round(v_mil, 2), "h": round(abs(h_mil), 2), "side": "Л" if h_mil < 0 else "П", "v_at": int(v_at), "mach": round(mach, 2), "sg": round(sg, 2), "cor_cm": cor_h_cm}

# --- ІНТЕРФЕЙС ---
st.button("🌙 НІЧНИЙ РЕЖИМ", on_click=lambda: st.session_state.update({'night': not st.session_state.night}))

preset_name = st.selectbox("ОБЕРІТЬ НАБІЙ:", list(PRESETS.keys()))
defaults = PRESETS[preset_name]

st.markdown('<div style="position: sticky; top: 0; background: #0E1117; z-index: 100; padding: 10px 0; border-bottom: 2px solid red;">', unsafe_allow_html=True)
dist = st.slider("🎯 ДИСТАНЦІЯ ДО ЦІЛІ (м)", 0, 1800, 800, step=5)
h_c1, h_c2 = st.columns(2)
st.markdown('</div>', unsafe_allow_html=True)

with st.expander("🔫 ЗБРОЯ ТА ПАТРОН", expanded=True):
    m_mod = st.radio("Драг-модель", ["G7", "G1"], horizontal=True, help="G7 — для далекобійних куль (Boat Tail), G1 — для плоских куль.")
    c1, c2 = st.columns(2)
    v0 = c1.number_input("Швидкість V0 (м/с)", value=float(defaults['v0']), help="Початкова швидкість кулі на зрізі ствола.")
    bc = c2.number_input(f"Коефіцієнт БК ({m_mod})", value=float(defaults['bc_g7'] if m_mod=="G7" else defaults['bc_g1']), format="%.3f", help="Здатність кулі долати опір повітря.")
    tw = c1.number_input("Твіст ствола 1:", value=float(defaults['twist']), help="Крок нарізів у дюймах. Впливає на стабільність та деривацію.")
    tw_d = c2.radio("Напрямок нарізів", ["R", "L"], horizontal=True, help="R - правобічні нарізи (стандарт).")
    
    sh = st.number_input("Висота прицілу (см)", value=5.0, help="Відстань від центру ствола до центру оптичного прицілу.")
    zero = st.number_input("Дистанція пристрілки (м)", value=100, help="Дистанція, на якій приціл виставлено в 'нуль'.")

with st.expander("🌍 МЕТЕО ТА ГЕОПОЗИЦІЯ"):
    t = st.slider("Температура (°C)", -30, 50, 15, help="Впливає на швидкість звуку та щільність повітря.")
    p_at = st.number_input("Тиск (гПа)", value=1013, help="Атмосферний тиск. Нижчий тиск = менший опір повітря.")
    h = st.slider("Вологість (%)", 0, 100, 50, help="Впливає на щільність повітря (вологе повітря менш щільне).")
    st.divider()
    ws = st.slider("Швидкість вітру (м/с)", 0, 20, 3, help="Швидкість вітру на дистанції.")
    wh = st.slider("Напрямок вітру (год)", 1, 12, 3, help="12 - зустрічний, 6 - попутний, 3 - справа.")
    
    # Адаптивна геопозиція (Коріоліс)
    check_p = {**defaults, 'temp':t,'press':p_at,'hum':h,'v0':v0,'bc':bc,'model':m_mod,'lat':50,'az':90,'tw_v':tw,'tw_d':tw_d,'sh':sh,'zero':zero,'w_speed':ws,'w_hour':wh}
    impact = get_ballistics(check_p, dist)
    
    if impact['cor_cm'] > 3.0:
        st.warning(f"⚠️ Ефект Коріолліса: відхилення {round(impact['cor_cm'],1)} см.")
        lat = st.number_input("Широта місця", value=50, help="Географічна широта. Необхідна для розрахунку сили Коріолліса.")
        az = st.slider("Азимут стрільби", 0, 360, 90, help="Напрямок стрільби відносно сторін світу (0-Пн, 90-Сх).")
    else:
        lat, az = 50, 90
        st.caption("ℹ️ Коріолліс ігнорується (вплив < 3 см на цій відстані)")

# ПОВНИЙ РОЗРАХУНОК
final_p = {**defaults, 'temp':t,'press':p_at,'hum':h,'v0':v0,'bc':bc,'model':m_mod,'lat':lat,'az':az,'tw_v':tw,'tw_d':tw_d,'sh':sh,'zero':zero,'w_speed':ws,'w_hour':wh}
res = get_ballistics(final_p, dist)

# HUD
h_c1.markdown(f'<div class="hud-card"><div class="hud-label">Вертикаль MIL</div><div class="hud-value">↑ {res["v"]}</div></div>', unsafe_allow_html=True)
h_c2.markdown(f'<div class="hud-card"><div class="hud-label">Горизонт {res["side"]} MIL</div><div class="hud-value">↔ {res["h"]}</div></div>', unsafe_allow_html=True)

# СТАТУС
if res['mach'] < 1.2:
    st.error(f"⚠️ ТРАНСЗВУК (Число Маха {res['mach']}): Куля втрачає швидкість. Стабільність Sg: {res['sg']}")
else:
    st.success(f"🚀 Швидкість: {res['mach']} Mach | Стабільність Sg: {res['sg']}")

st.write(f"**Інфо:** Час польоту: {res['tof']} с | Швидкість у цілі: {res['v_at']} м/с")
