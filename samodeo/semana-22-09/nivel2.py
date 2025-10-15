import cv2
import mediapipe as mp
import serial
import time

# ---- CONFIGURACIÓN SERIAL ----
PORT = "/dev/ttyUSB0"   # Cambia si tu Arduino está en otro puerto
BAUD = 115200
ser = serial.Serial(PORT, BAUD, timeout=1)
time.sleep(2)

# ---- MEDIAPIPE ----
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

# Función: detectar si mano abierta o cerrada
def mano_abierta(landmarks):
    dedos = [8, 12, 16, 20]  # puntas (excepto pulgar)
    abiertos = 0
    for d in dedos:
        if landmarks[d].y < landmarks[d - 2].y:  # punta arriba de nudillo
            abiertos += 1
    return abiertos >= 3

# ---- LOOP PRINCIPAL ----
with mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7) as hands:

    estado_pinza = None
    ultimo_envio = 0
    delay = 0.3  # segundos entre comandos

    cap = cv2.VideoCapture(0)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)  # espejo
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(
                    frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

                abierta = mano_abierta(hand_landmarks.landmark)
                x = hand_landmarks.landmark[9].x  # centro de la palma

                # --- PINZA ---
                if abierta and estado_pinza != "abierta":
                    if time.time() - ultimo_envio > delay:
                        print("🖐 Mano abierta → abrir pinza")
                        ser.write(b"M280 P2 S90\n")
                        estado_pinza = "abierta"
                        ultimo_envio = time.time()

                elif not abierta and estado_pinza != "cerrada":
                    if time.time() - ultimo_envio > delay:
                        print("✊ Mano cerrada → cerrar pinza")
                        ser.write(b"M280 P2 S180\n")
                        estado_pinza = "cerrada"
                        ultimo_envio = time.time()

                # --- MOVIMIENTO BASE ---
                if time.time() - ultimo_envio > delay:
                    if x < 0.4:  # izquierda
                        print("⬅️ Mano a la izquierda → base izquierda")
                        ser.write(b"G1 Y-10 F2000\n")  # mover base izquierda
                        ultimo_envio = time.time()
                    elif x > 0.6:  # derecha
                        print("➡️ Mano a la derecha → base derecha")
                        ser.write(b"G1 Y10 F2000\n")   # mover base derecha
                        ultimo_envio = time.time()

        cv2.imshow("Nivel 1+2 - Pinza + Base", frame)
        if cv2.waitKey(5) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()
    ser.close()

