import cv2
import mediapipe as mp
import serial
import time

# -------------------------
# CONFIGURACIÓN SERIAL
# -------------------------
PORT = "/dev/ttyUSB0"  # Cambiar según tu puerto
BAUD = 115200
try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)  # Espera a inicializar conexión

    # Habilita todos los motores para que queden sostenidos
    ser.write(b"M17\n")
except:
    print("Error: No se pudo conectar al puerto serial")
    ser = None

# -------------------------
# CONFIGURACIÓN MEDIAPIPE HANDS
# -------------------------
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.7)

# -------------------------
# INICIO CÁMARA
# -------------------------
cap = cv2.VideoCapture(0)

# -------------------------
# DELAYS
# -------------------------
delay_mov = 1.5    # segundos entre movimientos base/hombro
delay_pinza = 0.5  # segundos entre abrir/cerrar pinza
last_mov_time = 0
last_pinza_time = 0

# -------------------------
# LOOP PRINCIPAL
# -------------------------
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)  # espejo
    h, w, c = frame.shape
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    center_x = w // 2
    center_y = h // 2
    cv2.line(frame, (center_x, 0), (center_x, h), (0,255,0), 2)
    cv2.line(frame, (0, center_y), (w, center_y), (0,255,0), 2)

    current_time = time.time()

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            # --- Base y Hombro ---
            x = int(hand_landmarks.landmark[0].x * w)
            y = int(hand_landmarks.landmark[0].y * h)

            if current_time - last_mov_time > delay_mov:
                # Base
                if x < center_x - 50:
                    cv2.putText(frame, "BASE IZQUIERDA", (50,50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
                    if ser:
                        ser.write(b"G91\nG1 Y-5 F400\nG90\n")
                elif x > center_x + 50:
                    cv2.putText(frame, "BASE DERECHA", (50,50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
                    if ser:
                        ser.write(b"G91\nG1 Y5 F400\nG90\n")

                # Hombro
                if y < center_y - 50:
                    cv2.putText(frame, "HOMBRO ARRIBA", (50,100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,0,0), 2)
                    if ser:
                        ser.write(b"G91\nG1 Z5 F300\nG90\n")
                elif y > center_y + 50:
                    cv2.putText(frame, "HOMBRO ABAJO", (50,100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,0), 2)
                    if ser:
                        ser.write(b"G91\nG1 Z-5 F300\nG90\n")

                last_mov_time = current_time

            # --- Pinza ---
            dedos = [8, 12, 16, 20]  # puntas de dedos
            abiertos = 0
            for d in dedos:
                if hand_landmarks.landmark[d].y < hand_landmarks.landmark[d-2].y:
                    abiertos += 1
            pinza_abierta = abiertos >= 3

            if pinza_abierta and current_time - last_pinza_time > delay_pinza:
                cv2.putText(frame, "PINZA ABIERTA", (50,150), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,255), 2)
                if ser:
                    ser.write(b"M280 P2 S90\n")  # abrir
                last_pinza_time = current_time
            elif not pinza_abierta and current_time - last_pinza_time > delay_pinza:
                cv2.putText(frame, "PINZA CERRADA", (50,150), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
                if ser:
                    ser.write(b"M280 P2 S180\n")  # cerrar
                last_pinza_time = current_time

    # Mostrar ventana
    cv2.imshow("Control Moveo - Gestos Nivel 1+2", frame)

    if cv2.waitKey(1) & 0xFF == 27:  # ESC para salir
        break

# -------------------------
# CIERRE
# -------------------------
cap.release()
cv2.destroyAllWindows()

# Todos los motores permanecen habilitados y energizados
if ser:
    ser.close()

