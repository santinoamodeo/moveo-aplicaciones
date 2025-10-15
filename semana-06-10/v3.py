import cv2
import mediapipe as mp
import serial
import time
import math

# =========================
# CONFIG SERIAL
# =========================
PORT = "/dev/ttyUSB0"
BAUD = 115200
ser = None
try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)
    ser.write(b"M17\n")
    print("[OK] Serial abierto y motores energizados (M17).")
except Exception as e:
    print(f"[WARN] No se pudo abrir el serial: {e}. Se ejecuta en modo simulación.")

# =========================
# MEDIAPIPE
# =========================
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=2,
                       min_detection_confidence=0.7,
                       min_tracking_confidence=0.7)

# =========================
# CAMARA
# =========================
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("No se pudo abrir la cámara.")
W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
CX, CY = W // 2, H // 2

# =========================
# PARAMETROS
# =========================
LIMITS = {"Y": (-90, 90), "X": (-15, 15), "Z": (0, 40), "E": (-40, 40)}
FEEDS = {"Y": 1000, "X": 600, "Z": 200, "E": 500}
STEP = {"Y": 1, "X": 1, "Z": 1, "E": 1}
DELAY_AXIS = {"Y": 0.10, "X": 0.12, "Z": 0.20, "E": 0.12}
DEAD_PX = 50
ALPHA = 0.3

PINZA_THRESH_OPEN, PINZA_THRESH_CLOSE = 0.10, 0.05
PINZA_DELAY = 0.6
pinza_estado, last_pinza_time = None, 0.0

# TOOL
active_tool = 0
tool_hold_start = None
tool_change_msg = ""
tool_msg_timer = 0.0
TOOL_HOLD_TIME = 1.0
TOOL_MSG_DURATION = 2.0

# MANOS ESTABLES
hand_data = {"Left": None, "Right": None}
hand_stable_count = {"Left": 0, "Right": 0}
STABILITY_FRAMES = 2

smooth_pos = {"Left": None, "Right": None}
soft_pose = {"Y": 0.0, "X": 0.0, "Z": 20.0, "E": 0.0}
last_axis_time = {k: 0.0 for k in ["Y", "X", "Z", "E"]}

# =========================
# FUNCIONES
# =========================
def ema(prev, new):
    if prev is None: return new
    return (1 - ALPHA) * prev + ALPHA * new

def dir_from_offset(offset_px, dead_px):
    if offset_px > dead_px: return +1
    elif offset_px < -dead_px: return -1
    return 0

def pinch_distance_norm(lm):
    x1, y1 = lm[4].x, lm[4].y
    x2, y2 = lm[8].x, lm[8].y
    return math.hypot(x2 - x1, y2 - y1)

def mano_abierta(landmarks):
    dedos = [8, 12, 16, 20]
    abiertos = 0
    for d in dedos:
        if landmarks[d].y < landmarks[d-2].y:
            abiertos += 1
    return abiertos >= 3

def mano_cerrada(landmarks):
    dedos = [8, 12, 16, 20]
    for d in dedos:
        if landmarks[d].y < landmarks[d-2].y:
            return False
    return True

def send_gcode(cmd: str):
    if ser:
        try: ser.write((cmd + "\n").encode())
        except: pass
    else:
        print("[SIM]", cmd)

def maybe_step(axis, direction, now):
    if direction == 0: return False
    if (now - last_axis_time[axis]) < DELAY_AXIS[axis]: return False
    new_soft = soft_pose[axis] + (STEP[axis] * direction)
    lo, hi = LIMITS[axis]
    if not (lo <= new_soft <= hi): return False
    send_gcode(f"T{active_tool}")
    send_gcode(f"G91\nG1 {axis}{STEP[axis]*direction} F{FEEDS[axis]}\nG90")
    soft_pose[axis] = new_soft
    last_axis_time[axis] = now
    return True

def draw_text(img, text, org, color=(0,255,0), scale=0.6):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2, cv2.LINE_AA)

# =========================
# LOOP PRINCIPAL
# =========================
print("[INFO] Control discreto + Tool gesture + Extrusor T1 activo")
print(" - Mano DERECHA → Base (Y), Hombro (Z), Pinza")
print(" - Mano IZQUIERDA → Codo/Muñeca (T0) o Extrusor (T1)")
print(" - ESC → salir\n")

while True:
    ok, frame = cap.read()
    if not ok: break
    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)
    now = time.time()

    # Color segun Tool
    overlay_color = (0, 255, 0) if active_tool == 0 else (255, 200, 0)

    # Líneas y etiquetas
    cv2.line(frame, (CX, 0), (CX, H), overlay_color, 2)
    cv2.line(frame, (0, CY), (W, CY), overlay_color, 2)
    draw_text(frame, f"Modo: DISCRETO | Tool activo: T{active_tool}", (20, 30), overlay_color, 0.7)
    draw_text(frame, "Codo (X) / Muneca (E) o Extrusor", (20, 55), (255, 200, 0))
    draw_text(frame, "Base (Y) / Hombro (Z) / Pinza", (CX + 20, 55), (255, 200, 0))

    if tool_change_msg and (now - tool_msg_timer < TOOL_MSG_DURATION):
        draw_text(frame, tool_change_msg, (W - 280, 30), overlay_color, 0.6)
    elif tool_change_msg:
        tool_change_msg = ""

    # Reiniciar detección estable
    for h in ["Left", "Right"]:
        hand_data[h] = None

    if results.multi_hand_landmarks:
        for i, lmset in enumerate(results.multi_hand_landmarks):
            label = results.multi_handedness[i].classification[0].label
            hand_data[label] = lmset

    status_L, status_R = [], []

    # Confirmar estabilidad
    for h in ["Left", "Right"]:
        if hand_data[h] is not None:
            hand_stable_count[h] += 1
        else:
            hand_stable_count[h] = 0

    # Procesar manos
    for h in ["Left", "Right"]:
        if hand_stable_count[h] < 2: 
            continue

        lmset = hand_data[h]
        mp_draw.draw_landmarks(frame, lmset, mp_hands.HAND_CONNECTIONS)
        x, y = int(lmset.landmark[0].x * W), int(lmset.landmark[0].y * H)
        prev = smooth_pos[h]
        smooth_pos[h] = (ema(prev[0] if prev else None, x),
                         ema(prev[1] if prev else None, y)) if prev else (x, y)
        sx, sy = smooth_pos[h]
        cv2.circle(frame, (int(sx), int(sy)), 8, (0, 255, 255), -1)

        # ---------- MANO DERECHA ----------
        if h == "Right":
            offset_x, offset_y = sx - (CX + W//4), CY - sy
            dirY, dirZ = dir_from_offset(offset_x, DEAD_PX), dir_from_offset(offset_y, DEAD_PX)
            if maybe_step("Y", dirY, now):
                status_R.append("➡️ Base der" if dirY > 0 else "⬅️ Base izq")
            if maybe_step("Z", dirZ, now):
                status_R.append("⬆️ Hombro arriba" if dirZ > 0 else "⬇️ Hombro abajo")

            # Pinza
            dist = pinch_distance_norm(lmset.landmark)
            if (now - last_pinza_time) > PINZA_DELAY:
                if pinza_estado != "cerrada" and dist < PINZA_THRESH_CLOSE:
                    send_gcode("M280 P2 S180")
                    pinza_estado, last_pinza_time = "cerrada", now
                    status_R.append("✊ Pinza CERRADA")
                elif pinza_estado != "abierta" and dist > PINZA_THRESH_OPEN:
                    send_gcode("M280 P2 S90")
                    pinza_estado, last_pinza_time = "abierta", now
                    status_R.append("🖐 Pinza ABIERTA")

        # ---------- MANO IZQUIERDA ----------
        elif h == "Left":
            offset_x, offset_y = sx - (W//4), CY - sy
            dirX, dirE = dir_from_offset(offset_x, DEAD_PX), dir_from_offset(offset_y, DEAD_PX)

            if active_tool == 0:
                # Control normal del brazo
                if maybe_step("X", dirX, now):
                    status_L.append("➡️ Codo +X" if dirX > 0 else "⬅️ Codo -X")
                if maybe_step("E", dirE, now):
                    status_L.append("⬆️ Muñeca +E" if dirE > 0 else "⬇️ Muñeca -E")

            elif active_tool == 1:
                # Control del extrusor T1
                if dirE != 0 and (now - last_axis_time["E"]) > 0.2:
                    send_gcode("T1")
                    send_gcode(f"G91\nG1 E{dirE*2} F200\nG90")
                    last_axis_time["E"] = now
                    status_L.append("🌀 Extrusor +E" if dirE > 0 else "🌀 Extrusor -E")

            # Gesto cambio Tool
            if mano_cerrada(lmset.landmark):
                if tool_hold_start is None:
                    tool_hold_start = now
                elif now - tool_hold_start > TOOL_HOLD_TIME and active_tool == 0:
                    active_tool = 1
                    send_gcode("T1")
                    tool_change_msg = "Cambio realizado: Tool T1"
                    tool_msg_timer = now
                    tool_hold_start = None
            elif mano_abierta(lmset.landmark):
                if tool_hold_start is None:
                    tool_hold_start = now
                elif now - tool_hold_start > TOOL_HOLD_TIME and active_tool == 1:
                    active_tool = 0
                    send_gcode("T0")
                    tool_change_msg = "Cambio realizado: Tool T0"
                    tool_msg_timer = now
                    tool_hold_start = None
            else:
                tool_hold_start = None

    # Mostrar overlay dinámico
    for i, t in enumerate(status_L[:4]):
        draw_text(frame, t, (20, 80 + 24 * i), (0, 255, 255))
    for i, t in enumerate(status_R[:6]):
        draw_text(frame, t, (CX + 20, 80 + 24 * i), (0, 255, 255))
    draw_text(frame, f"Pinza: {pinza_estado or '-'}", (20, H - 20), (200, 255, 200))

    cv2.imshow("Moveo - Control manos (Discreto + Extrusor T1)", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        break

# =========================
# CIERRE
# =========================
cap.release()
cv2.destroyAllWindows()
if ser:
    try: ser.close()
    except: pass

