import cv2
import mediapipe as mp

# Inicializamos mediapipe
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

# Captura de la cámara (0 = cámara por defecto)
cap = cv2.VideoCapture(0)

with mp_hands.Hands(
    max_num_hands=1,  # solo 1 mano
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7) as hands:

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Convertir a RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Procesar con mediapipe
        results = hands.process(rgb_frame)

        # Dibujar eje central
        height, width, _ = frame.shape
        center_x = width // 2
        cv2.line(frame, (center_x, 0), (center_x, height), (0, 255, 0), 2)

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # Dibujar la mano
                mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

                # Coordenada X de la palma (landmark 0 = wrist/muñeca)
                x = int(hand_landmarks.landmark[0].x * width)

                if x < center_x - 50:
                    cv2.putText(frame, "IZQUIERDA", (50, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    print("IZQUIERDA")
                elif x > center_x + 50:
                    cv2.putText(frame, "DERECHA", (50, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
                    print("DERECHA")

        # Mostrar la ventana (SOLO UNA)
        cv2.imshow("Deteccion Mano Izq-Der", frame)

        # Salir con "q"
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()

