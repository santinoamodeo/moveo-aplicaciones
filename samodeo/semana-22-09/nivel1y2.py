import cv2
import mediapipe as mp
import serial
import time

# -------------------------
# CONFIG SERIAL
# -------------------------
PORT = "/dev/ttyUSB0"  # Cambiar según tu puerto
BAUD = 115200
try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)  # Espera que se inicialice la conexión

    # Habilita todos los motores para que queden sostenidos
    ser.write(b"M17\n")
except:
    print("Error: No se pudo conectar al puerto serial")
    ser = None

# -------------------------
# CONFIGURACION MEDIAPIPE HANDS
# -------------------------
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=1,
                       min_detection_confidence=0.7,
                       min_tracking_confidence=0.7)

# -------------------------
# FUNCION PARA MANO ABIERTA
# -------------------------
def mano_abierta(landmarks):
    dedos = [8, 12, 16, 20]
    abiertos = 0
    for d in dedos:
        if landmarks[d].y < landmarks[d-2].y:
            abiertos += 1
    return abiertos >= 3

# -------------------------
# INICIO CAMARA
# -------------------------
cap = cv2.VideoCapture(0)
h, w = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)), int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
center_x = w // 2
center_y = h // 2

# -------------------------
# DELAYS
# -------------------------
delay_base_hombro = 1.5
delay_pinza = 0.5
last_base_time = 0
last_pinza_time = 0
estado_pinza = None

# -------------------------
# LOOP PRINCIPAL
# -------------------------
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    # Dibujos de referencia
    cv2.line(frame, (center_x, 0), (center_x, h), (0,255,0), 2)
    cv2.line(frame, (0, center_y), (w, center_y), (0,255,0), 2)

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            x = int(hand_landmarks.landmark[0].x * w)
            y = int(hand_landmarks.landmark[0].y * h)
            abierta = mano_abierta(hand_landmarks.landmark)
            current_time = time.time()

            # -------------------------
            # CONTROL PINZA ABIERTA/CERRADA
            # -------------------------
            if ser and current_time - last_pinza_time > delay_pinza:
                if abierta and estado_pinza != "abierta":
                    ser.write(b"M280 P2 S90\n")
                    estado_pinza = "abierta"
                    last_pinza_time = current_time
                    print("🖐 Pinza abierta")
                elif not abierta and estado_pinza != "cerrada":
                    ser.write(b"M280 P2 S180\n")
                    estado_pinza = "cerrada"
                    last_pinza_time = current_time
                    print("✊ Pinza cerrada")

            # -------------------------
            # CONTROL BASE Y HOMBRO
            # -------------------------
            if ser and current_time - last_base_time > delay_base_hombro:
                # Base
                if x < center_x - 50:
                    ser.write(b"G91\nG1 Y-5 F400\nG90\n")
                    last_base_time = current_time
                    print("⬅️ Base izquierda")
                elif x > center_x + 50:
                    ser.write(b"G91\nG1 Y5 F400\nG90\n")
                    last_base_time = current_time
                    print("➡️ Base derecha")

                # Hombro
                if y < center_y - 50:
                    ser.write(b"G91\nG1 Z5 F300\nG90\n")
                    last_base_time = current_time
                    print("⬆️ Hombro arriba")
                elif y > center_y + 50:
                    ser.write(b"G91\nG1 Z-5 F300\nG90\n")
                    last_base_time = current_time
                    print("⬇️ Hombro abajo")

    # Mostrar ventana
    cv2.imshow("Control Moveo - Nivel 1+2 Simplificado", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        break

# -------------------------
# CIERRE
# -------------------------
cap.release()
cv2.destroyAllWindows()
if ser:
    ser.close()

