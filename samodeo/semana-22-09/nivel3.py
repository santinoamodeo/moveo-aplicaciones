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
    time.sleep(2)
    ser.write(b"M17\n")  # Energizar motores
except:
    print("Error: No se pudo conectar al puerto serial")
    ser = None

# -------------------------
# CONFIG MEDIAPIPE
# -------------------------
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

# -------------------------
# CAMARA
# -------------------------
cap = cv2.VideoCapture(0)

# -------------------------
# RETARDOS
# -------------------------
delay = 1.0  # segundos entre comandos
last_command_time = 0

# -------------------------
# LOOP PRINCIPAL
# -------------------------
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    # Dibujo de referencias
    center_x = w // 2
    center_y = h // 2
    cv2.line(frame, (center_x, 0), (center_x, h), (0,255,0), 2)
    cv2.line(frame, (0, center_y), (w, center_y), (0,255,0), 2)

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            # Coordenadas palma
            x = int(hand_landmarks.landmark[9].x * w)
            y = int(hand_landmarks.landmark[9].y * h)

            current_time = time.time()
            if current_time - last_command_time > delay:

                # -------------------------
                # CONTROL MUÑECA (X)
                # -------------------------
                if x < center_x - 50:
                    cv2.putText(frame, "MUÑECA IZQ", (50,50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
                    print("MUÑECA IZQ")
                    if ser:
                        ser.write(b"G91\nG1 X-5 F400\nG90\n")
                    last_command_time = current_time

                elif x > center_x + 50:
                    cv2.putText(frame, "MUÑECA DER", (50,50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
                    print("MUÑECA DER")
                    if ser:
                        ser.write(b"G91\nG1 X5 F400\nG90\n")
                    last_command_time = current_time

                # -------------------------
                # CONTROL CODO (Y)
                # -------------------------
                if y < center_y - 50:
                    cv2.putText(frame, "CODO EXTENDER", (50,100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,0,0), 2)
                    print("CODO EXTENDER")
                    if ser:
                        ser.write(b"G91\nG1 E5 F300\nG90\n")
                    last_command_time = current_time

                elif y > center_y + 50:
                    cv2.putText(frame, "CODO RETRAER", (50,100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,0), 2)
                    print("CODO RETRAER")
                    if ser:
                        ser.write(b"G91\nG1 E-5 F300\nG90\n")
                    last_command_time = current_time

    # -------------------------
    # MOSTRAR VENTANA ÚNICA
    # -------------------------
    cv2.imshow("Control Moveo - Nivel 3", frame)

    # Salida con ESC
    if cv2.waitKey(1) & 0xFF == 27:
        break

# -------------------------
# CIERRE
# -------------------------
cap.release()
cv2.destroyAllWindows()
if ser:
    ser.close()
