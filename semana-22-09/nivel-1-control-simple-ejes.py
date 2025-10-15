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
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.7)

# -------------------------
# INICIO CAMARA
# -------------------------
cap = cv2.VideoCapture(0)

# -------------------------
# RETARDO ENTRE COMANDOS
# -------------------------
delay = 1.5  # segundos entre comandos
last_command_time = 0

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

    # Dibujo de líneas de referencia
    center_x = w // 2
    center_y = h // 2
    cv2.line(frame, (center_x, 0), (center_x, h), (0,255,0), 2)
    cv2.line(frame, (0, center_y), (w, center_y), (0,255,0), 2)

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            x = int(hand_landmarks.landmark[0].x * w)
            y = int(hand_landmarks.landmark[0].y * h)

            current_time = time.time()
            if current_time - last_command_time > delay:
                # -------------------------
                # CONTROL BASE
                # -------------------------
                if x < center_x - 50:
                    cv2.putText(frame, "BASE IZQUIERDA", (50,50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
                    print("BASE IZQUIERDA")
                    if ser:
                        ser.write(b"G91\nG1 Y-5 F400\nG90\n")
                    last_command_time = current_time
                elif x > center_x + 50:
                    cv2.putText(frame, "BASE DERECHA", (50,50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
                    print("BASE DERECHA")
                    if ser:
                        ser.write(b"G91\nG1 Y5 F400\nG90\n")
                    last_command_time = current_time

                # -------------------------
                # CONTROL HOMBRO
                # -------------------------
                if y < center_y - 50:
                    cv2.putText(frame, "HOMBRO ARRIBA", (50,100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,0,0), 2)
                    print("HOMBRO ARRIBA")
                    if ser:
                        ser.write(b"G91\nG1 Z5 F300\nG90\n")
                    last_command_time = current_time
                elif y > center_y + 50:
                    cv2.putText(frame, "HOMBRO ABAJO", (50,100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,0), 2)
                    print("HOMBRO ABAJO")
                    if ser:
                        ser.write(b"G91\nG1 Z-5 F300\nG90\n")
                    last_command_time = current_time

    # Mostrar ventana
    cv2.imshow("Control Moveo - Nivel 1", frame)

    # ESC para salir
    if cv2.waitKey(1) & 0xFF == 27:
        break

# -------------------------
# CIERRE
# -------------------------
cap.release()
cv2.destroyAllWindows()

# Todos los motores permanecen habilitados y energizados
if ser:
    ser.close()

