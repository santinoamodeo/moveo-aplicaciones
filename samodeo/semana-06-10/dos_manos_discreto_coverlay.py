import cv2
import mediapipe as mp
import serial
import time
import math

# =========================
# CONFIG SERIAL
# =========================
PORT = "/dev/ttyUSB0"   # tu puerto
BAUD = 115200
ser = None
try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)
    ser.write(b"M17\n")  # energizar motores
    print("[OK] Serial abierto y motores energizados (M17).")
except Exception as e:
    print(f"[WARN] No se pudo abrir el serial: {e}. Se ejecuta en modo simulación.")

# =========================
# MEDIAPIPE HANDS
# =========================
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    max_num_hands=2,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

# =========================
# CAMARA
# =========================
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("No se pudo abrir la cámara.")

W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
CX = W // 2
CY = H // 2

# =========================
# PARAMETROS DE LOS EJES
# =========================
LIMITS = {
    "Y": (-90, 90),
    "X": (-15, 15),
    "Z": (0, 40),
    "E": (-40, 40)
}
FEEDS = {"Y": 1000, "X": 600, "Z": 200, "E": 500}
STEP = {"Y": 1, "X": 1, "Z": 1, "E": 1}
DELAY_AXIS = {"Y": 0.10, "X": 0.12, "Z": 0.20, "E": 0.12}

PINZA_THRESH_OPEN  = 0.10
PINZA_THRESH_CLOSE = 0.05
PINZA_DELAY = 0.6
pinza_estado = None
last_pinza_time = 0.0

DEAD_PX = 50
ALPHA = 0.3
smooth_pos = {"Left": None, "Right": None}
soft_pose = {"Y": 0.0, "X": 0.0, "Z": 20.0, "E": 0.0}
last_axis_time = {k: 0.0 for k in ["Y", "X", "Z", "E"]}

# =========================
# MODO CONTROL
# =========================
modo_continuo = False  # comienza en discreto

# =========================
# UTILS
# =========================
def clamp(v, vmin, vmax): return max(vmin, min(vmax, v))

def ema(prev, new):
    if prev is None: return new
    return (1 - ALPHA) * prev + ALPHA * new

def pinch_distance_norm(lm):
    x1, y1 = lm[4].x, lm[4].y
    x2, y2 = lm[8].x, lm[8].y
    return math.hypot(x2 - x1, y2 - y1)

def dir_from_offset(offset_px, dead_px):
    if offset_px > dead_px: return +1
    elif offset_px < -dead_px: return -1
    return 0

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
    send_gcode(f"G91\nG1 {axis}{STEP[axis]*direction} F{FEEDS[axis]}\nG90")
    soft_pose[axis] = new_soft
    last_axis_time[axis] = now
    return True

def draw_text(img, text, org, color=(0,255,0)):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)

# =========================
# LOOP PRINCIPAL
# =========================
print("[INFO] Controles:")
print(" - Mano DERECHA (mitad derecha): Base (Y), Hombro (Z), Pinza (P2)")
print(" - Mano IZQUIERDA (mitad izquierda): Codo (X), Muñeca (E)")
print(" - C: alterna entre modo discreto y continuo")
print(" - SPACE: M18 (liberar motores)")
print(" - ESC: salir\n")

while True:
    ok, frame = cap.read()
    if not ok: break

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)
    now = time.time()

    cv2.line(frame, (CX, 0), (CX, H), (0, 255, 0), 2)
    cv2.line(frame, (0, CY), (W, CY), (0, 255, 0), 2)
    draw_text(frame, "Codo (X) / Muneca (E)", (20, 30), (255, 200, 0))
    draw_text(frame, "Base (Y) / Hombro (Z) / Pinza", (CX + 20, 30), (255, 200, 0))

    status_L, status_R = [], []

    if results.multi_hand_landmarks:
        for idx, lmset in enumerate(results.multi_hand_landmarks):
            label = results.multi_handedness[idx].classification[0].label  # "Left"/"Right"
            mp_draw.draw_landmarks(frame, lmset, mp_hands.HAND_CONNECTIONS)
            x, y = int(lmset.landmark[0].x * W), int(lmset.landmark[0].y * H)
            prev = smooth_pos[label]
            smooth_pos[label] = (ema(prev[0] if prev else None, x),
                                 ema(prev[1] if prev else None, y)) if prev else (x, y)
            sx, sy = smooth_pos[label]
            cv2.circle(frame, (int(sx), int(sy)), 8, (0, 255, 255), -1)

            if label == "Right":
                offset_x = sx - (CX + W//4)
                offset_y = CY - sy
                dirY, dirZ = dir_from_offset(offset_x, DEAD_PX), dir_from_offset(offset_y, DEAD_PX)
                if modo_continuo:
                    send_gcode(f"G91\nG1 Y{dirY} Z{dirZ} F{FEEDS['Y']}\nG90")
                    status_R.append("Modo CONTINUO")
                else:
                    if maybe_step("Y", dirY, now):
                        status_R.append("➡️ Base der" if dirY > 0 else "⬅️ Base izq")
                    if maybe_step("Z", dirZ, now):
                        status_R.append("⬆️ Hombro arriba" if dirZ > 0 else "⬇️ Hombro abajo")
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

            elif label == "Left":
                offset_x = sx - (W//4)
                offset_y = CY - sy
                dirX, dirE = dir_from_offset(offset_x, DEAD_PX), dir_from_offset(offset_y, DEAD_PX)
                if modo_continuo:
                    send_gcode(f"G91\nG1 X{dirX} E{dirE} F{FEEDS['X']}\nG90")
                    status_L.append("Modo CONTINUO")
                else:
                    if maybe_step("X", dirX, now):
                        status_L.append("➡️ Codo +X" if dirX > 0 else "⬅️ Codo -X")
                    if maybe_step("E", dirE, now):
                        status_L.append("⬆️ Muneca +E" if dirE > 0 else "⬇️ Muneca -E")

    # Mostrar estado
    for i, t in enumerate(status_L[:4]): draw_text(frame, t, (20, 60 + 24 * i), (0, 255, 255))
    for i, t in enumerate(status_R[:6]): draw_text(frame, t, (CX + 20, 60 + 24 * i), (0, 255, 255))
    draw_text(frame,
              f"Modo: {'CONTINUO' if modo_continuo else 'DISCRETO'} | "
              f"Y:{int(soft_pose['Y'])} X:{int(soft_pose['X'])} Z:{int(soft_pose['Z'])} "
              f"E:{int(soft_pose['E'])} | Pinza:{pinza_estado or '-'}",
              (20, H - 20), (200, 255, 200))

    cv2.imshow("Moveo - Control manos", frame)
    key = cv2.waitKey(1) & 0xFF
    if key == 27:
        break
    elif key == ord(' '):
        send_gcode("M18")
        print("[PANICO] M18: motores liberados.")
    elif key == ord('c'):
        modo_continuo = not modo_continuo
        print(f"[MODO] Cambiado a {'CONTINUO' if modo_continuo else 'DISCRETO'}.")

# =========================
# CIERRE
# =========================
cap.release()
cv2.destroyAllWindows()
if ser:
    try:
        ser.close()
    except:
        pass

