#Programa donde defino funciones de movimiento, dependiendo el comando que lee va a ser la secuencia que va a ejecutar el brazo

import time
import serial

class Arm:
    def __init__(self, port: str, baud: int = 115200, name: str = "Brazo"):
        self.port = port
        self.baud = baud
        self.name = name
        self.ser = None

        # --- Servo ---
        self.SERVO_INDEX    = 0
        self.SERVO_OPEN     = 90
        self.SERVO_CLOSE    = 180
        self.SERVO_DWELL_MS = 350

        #Feeds
        self.FEED_SLOW   = 600
        self.FEED_NORM   = 1200
        self.FEED_WRIST  = 1000 

        #Amplitudes 
        self.AMP_BASE_L1   = 30
        self.AMP_Z_L1      = 18
        self.AMP_WRIST_L1  = 6

        self.AMP_BASE_L2   = 45
        self.AMP_Z_L2      = 22
        self.AMP_WRIST_L2  = 8 

        self.WRIST_ROLL_TO_VERTICAL = +25

    #---Funciones auxiliares del Serial---

    #Envia un mensaje con confirmacion del "Ok"
    def _send(self, cmd, espera=0.02): 
        """Envía G-code y espera 'ok' de forma simple."""
        self.ser.write((cmd + "\n").encode("ascii"))
        print(f">> {cmd}")
        t0 = time.time(); buf = b""
        while True:
            if time.time() - t0 > 2:
                break
            chunk = self.ser.read(256)
            if chunk:
                buf += chunk
                if b"ok" in buf or b"OK" in buf:
                    break
        time.sleep(espera)

    #Envia un mensaje por serial sin necesidad de esperar el "Ok"
    def _raw(self, cmd, pausa_s=0.0):
        """Escritura 'cruda' (para M280/G4 del servo)."""
        self.ser.write((cmd + "\n").encode("ascii"))
        print(f">> (raw) {cmd}")
        if pausa_s > 0:
            time.sleep(pausa_s)

    #Funcion que mueve la pinza al angulo solicitado
    def servo(self, angle):
        self._raw(f"M280 P{self.SERVO_INDEX} S{int(angle)}")
        self._raw(f"G4 P{self.SERVO_DWELL_MS}", pausa_s=self.SERVO_DWELL_MS/1000)

    #Funcion que cierra, abre y vuelve a cerrar el servomotor
    def servo_close_open_close(self):
        self.servo(self.SERVO_CLOSE)
        self.servo(self.SERVO_OPEN)
        self.servo(self.SERVO_CLOSE)

    #Funcion que activa y prepara el brazo para operar
    def open(self):
        self.ser = serial.Serial(self.port, baudrate=self.baud, timeout=1, write_timeout=1)
        time.sleep(1.2)
        self._send("M17")
        self._send("G21")
        self._send("G90")  # arrancamos en absoluto
        self._send("M204 P200 T200 R100")
        self._send("M205 X2 Y2 Z2 E2")
        self._send("M205 J0.01")
        print(f"[{self.name}] Serial listo en {self.port}@{self.baud}")

    #Funcion que apaga y cierra todo correctamente en el serial
    def close(self):
        self._send("M18")
        if self.ser and self.ser.is_open:
            self.ser.close()
        print(f"[{self.name}] Cerrado.")

    #Funcion que lleva el brazo a posicion vertical(90 grados)
    def vertical(self):
        """Llevar (absoluto) a Z0/E0/X0 y sincronizar."""
        self._send("G90")
        self._send("G1 Z0 F600")
        self._send("G1 E0 F600")
        self._send("G1 X0 F600")
        self._send("M400")

    # Funcion de movimiento relativo en el eje "E"
    def _g1_rel(self, axes: dict, feed: int, pausa=0.0):
        """Mover en relativo (G91) ejes indicados en un solo G1."""
        self._send("G91")  # relativo
        parts = [f"{k}{v}" for k, v in axes.items()]
        self._send(f"G1 {' '.join(parts)} F{int(feed)}")
        self._send("M400")
        if pausa > 0:
            time.sleep(pausa)
        self._send("G90")  # vuelvo a absoluto
    
    #Genera movimiento en la muñeca 2 (motor paso a paso)
    def _wrist2_suave(self, amp: float, steps: int = 3, feed: int = None):
        """
        Muñeca2 (X) suave pero más rápida:
        - menos pasos (6) y feed más alto (por defecto FEED_WRIST).
        Ejecutar con el brazo en vertical.
        """
        if feed is None:
            feed = self.FEED_NORM

        self._send("G91")  # relativo
        step = float(amp) / steps

        # ir adelante
        for _ in range(steps):
            self._send(f"G1 X{ step:.3f} F{feed}")
        self._send("M400")

        # volver pasado el centro y regresar
        for _ in range(2*steps):
            self._send(f"G1 X{-step:.3f} F{feed}")
        self._send("M400")

        for _ in range(steps):
            self._send(f"G1 X{ step:.3f} F{feed}")
        self._send("M400")

        self._send("G90")

    # Ejecuta los macros de movimiento
    def run_macro(self, name):
        name = (name or "").strip().lower()
        print(f"[MACRO] Ejecutando: {name}")

        #Secuencia "servo_test"
        if name == "servo_test":
            self.servo_close_open_close()
            self.vertical()

        #Secuencia "L2"
        elif name == "l2":
            # 1) BASE: barrido RELATIVO rápido y simétrico (sin pausas intermedias)
            A = self.AMP_BASE_L2
            self._g1_rel({'Y': -A},   self.FEED_NORM, pausa=0.0)
            self._g1_rel({'Y': +2*A}, self.FEED_NORM, pausa=0.0)
            self._g1_rel({'Y': -A},   self.FEED_NORM, pausa=0.0)

            # 2) CODO2 (E): bajar y subir inmediatamente 
            self._send("T0")
            self._g1_rel({'E': +38}, self.FEED_SLOW, pausa=0.0)
            self._g1_rel({'E': -38}, self.FEED_SLOW, pausa=0.0)

            # 3) A vertical antes de muñeca2
            self.vertical()

            # 4) MUÑECA2 suave pero más rápida
            self._wrist2_suave(self.AMP_WRIST_L2, steps=7, feed=1200) 

            # 5) SERVO al final
            self.servo_close_open_close()

            # 6) Opcional: dejar vertical
            self.vertical()

        #Secuencia "invert"
        elif name == "invert":
            self._g1_rel({'Z': -15}, 500, pausa=0.0)
            self.servo_close_open_close()
            self.vertical()
            self._g1_rel({'Z': +15}, 500, pausa=0.0)
            self.servo_close_open_close()
            self.vertical()
        
        elif name == "topa":
            self._g1_rel({'Z': -15}, 500, pausa=0.0)
            self.servo_close_open_close()
            self._send("M83")
            self._send("T1")
            self._send("G1 E1 F100")
        
        elif name == "apu":
            self._send("M17")
            self._send("M83")
            self._send("M84 S0")
            self._send("G90")
            self._send("M302 S")
            self._send("M400")
            self._send("M280 PO S90")
            self._send("T1")
            self._send("G1 E4 F100")
            self._send("G1 Y-170 F1300")
            self._send("T0")
            self._send("G1 E-30 F500")
            self._send("G1 E-10 Z35 F500")
            self._send("M400")
            self._send("M280 P0 S150")
            self._send("G1 Z30 F500")
            self._send("G1 Y170 F1300")
            self._send("G1 Z38 F500")
            self._send("M400")
            self._send("M280 P0 S90")
            self._send("G1 E-3 Z30 F500")
            self._send("G1 Z28 F600")
            self._send("G1 E43 Z0 F500")
            self._send("G1 Y0 F1300")
            self._send("T1")
            self._send("G1 E-4 F100")
            
        #Secuencia "parking"
        elif name == "parking":
            self._g1_rel({'Z': -15}, 500, pausa=0.0)
            self.vertical()
            
        else:
            print((f"[ERROR] Macro desconocida: {name}"))





