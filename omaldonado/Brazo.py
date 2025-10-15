#Programa que dependiendo un mensaje realice una secuencia de movimientos

import time, threading, queue
import serial

#Defino valores de movimiento 
class Arm:
    def __init__(self, port: str, baud: int = 250000, name: str = "Brazo"):
        self.port = port
        self.baud = baud
        self.name = name
        self.ser = None
        self.q = queue.Queue()
        self._running = threading.Event()
        self._worker = None

        #Config general
        self.FEED_SLOW   = 600
        self.FEED_NORM   = 1200
        self.FEED_WRIST  = 300     # muñeca bien suave
        # Si Z+ SUBE en tu máquina, dejá -1 para "bajar". Si Z+ BAJA, poné +1.
        self.Z_DOWN_SIGN = -1

        #Servo pinza (M280)
        self.SERVO_INDEX    = 3
        self.SERVO_OPEN     = 40    # ángulo abrir  (0..180)
        self.SERVO_CLOSE    = 120   # ángulo cerrar (0..180)
        self.SERVO_DWELL_MS = 400

        #Amplitudes L1/L2 (ajustables) 
        self.AMP_BASE_L1   = 30
        self.AMP_Z_L1      = 18
        self.AMP_WRIST_L1  = 6

        self.AMP_BASE_L2   = 45
        self.AMP_Z_L2      = 22
        self.AMP_WRIST_L2  = 8

        # Roll (muñeca1) para dejar pinza vertical (usa T1+E)
        # AUMENTALO si no alcanza; cambiá el signo si queda inclinado al otro lado.
        self.WRIST_ROLL_TO_VERTICAL = +25

        # Pasos para muñeca X (más pasos = más suave)
        self.WRIST_STEPS = 12

    #Auxiliares del serial
    def _wait_ok(self, timeout=10.0):
        t0 = time.time(); buf = b""
        while True:
            if time.time() - t0 > timeout:
                raise TimeoutError(f"[{self.name}] Timeout esperando 'ok'")
            chunk = self.ser.read(256)
            if not chunk: 
                continue
            buf += chunk
            if b"\nok\n" in buf or buf.endswith(b"ok\n") or b"ok\r\n" in buf:
                return

    #Envia una linea de G-Code por serial y espera el OK
    def _send(self, line: str, ensure_ok=True):
        line = (line or "").split(";")[0].strip()
        if not line: return
        self.ser.write((line + "\n").encode("ascii"))
        if ensure_ok: self._wait_ok()
        # print(">>", line)

    #Mueve la pinza al angulo indicado
    def _servo(self, angle: int):
        self._send(f"M280 P{self.SERVO_INDEX} S{int(angle)}", True)
        self._send(f"G4 P{self.SERVO_DWELL_MS}", True)

    # Abre y sincroniza el Marlin, aplica el un set up seguro y abre el hilo del worker
    def open(self):
        self.ser = serial.Serial(self.port, baudrate=self.baud, timeout=0.25, write_timeout=1)
        time.sleep(0.2)
        # DTR reset (más tolerante tras cortes)
        try:
            self.ser.setDTR(False); time.sleep(0.2); self.ser.setDTR(True)
        except Exception: pass

        # Leer banner de arranque (si lo hay)
        t0 = time.time(); _ = b""
        while time.time() - t0 < 3.0:
            _ += self.ser.read(256)
            if b"start" in _ or b"Marlin" in _: break
        try:
            self.ser.reset_input_buffer(); self.ser.reset_output_buffer()
        except Exception: pass
        time.sleep(0.1)

        # Sincronizar numeración
        self.ser.write(b"\nM110 N0\n"); self._wait_ok(timeout=5.0)

        # Setup seguro
        for g in ("M17","M84 S0","M302 S0","M211 S0","M83","G91"):
            self._send(g, True)

        # Aceleraciones (Marlin ignora lo que no aplique)
        # Si tu Marlin usa Junction Deviation:
        self._send("M204 P200 T200 R100", True)   # aceleraciones
        self._send("M205 X2 Y2 Z2 E2", True)      # jerk clásico
        self._send("M205 J0.01", True)            # JD (si aplica)º

        self._running.set()
        self._worker = threading.Thread(target=self._loop, daemon=True)
        self._worker.start()
        print(f"[{self.name}] Serial listo en {self.port}@{self.baud}")

    #Funcion para cerrar el brazo de forma ordenada y detiene el worker y cierra el puerto serie
    def close(self, reenable_endstops=True, keep_on=True):
        self._running.clear()
        if self._worker:
            self.q.put(("__STOP__", {}))
            self._worker.join(timeout=2.0)
        if reenable_endstops:
            try: self._send("M211 S1", True)
            except Exception: pass
        if not keep_on:
            try: self._send("M18", True)
            except Exception: pass
        if self.ser and self.ser.is_open: self.ser.close()
        print(f"[{self.name}] Cerrado.")

    #Funcion que envia M410 sin esperar el "Ok", frena al instante manteniendo el torque e ignora errores
    def quickstop(self):
        try: self._send("M410", ensure_ok=False)
        except Exception: pass

    # Funcion que lee la cola de comandos y los despacha secuencialmente enviandolos al Marlin
    def _loop(self):
        while self._running.is_set():
            try:
                cmd, kwargs = self.q.get(timeout=0.1)
            except queue.Empty:
                continue
            if cmd == "__STOP__": break
            if cmd == "__ESTOP_SOFT__": self.quickstop(); continue
            if cmd == "__RAW__":        self._send(kwargs.get("line",""), kwargs.get("ok", True)); continue
            if cmd == "MOVE_DELTA":     self._do_move_delta(**kwargs); continue
            if cmd == "MACRO":          self._do_macro(kwargs.get("name","")); continue
            self._send(str(cmd), True)

    # API pública 
    #Envia G-Code tal cual
    def enqueue_raw(self, line: str, ensure_ok=True): self.q.put(("__RAW__", {"line": line, "ok": ensure_ok}))
    #Freno rapido M410
    def estop_soft(self):self.q.put(("__ESTOP_SOFT__", {}))
    #Mueve en relativo G1
    def move_delta(self, axes: dict, feed: int = 1200):  self.q.put(("MOVE_DELTA", {"axes": dict(axes or {}), "feed": int(feed)}))
    #Ejecuta la secuencia por nombre enviado del MQTT
    def run_macro(self, name: str):self.q.put(("MACRO", {"name": name}))

    # Implementacion
    #Funcion que limita cada eje a valores seguros, arma un G1 relativo con esos deltas, selecciona T0 si usas E, lo envia y espera a que termine (M400) 
    def _do_move_delta(self, axes: dict, feed: int):
        MAX = {"Y": 90, "Z": 60, "X": 30, "E": 45}
        def clamp(v, lo, hi): return max(lo, min(hi, v))
        safe = {}
        for k in ("Y","Z","X","E"):
            if k in axes: safe[k] = clamp(float(axes[k]), -MAX[k], +MAX[k])
        if "E" in safe: self._send("T0", True)  # codo2 en T0
        line = "G1" + "".join(f" {k}{safe[k]}" for k in safe) + f" F{int(feed)}"
        self._send(line, True); self._send("M400", True)

    #Orienta la pinza vertical usando la muñeca 1: selecciona T1 y mueve E una cantidad fija 
    def _wrist_roll_to_vertical(self):
        """Muñeca1 (roll) con T1+E para dejar pinza vertical."""
        self._send("T1", True)
        self._send(f"G1 E{self.WRIST_ROLL_TO_VERTICAL} F{self.FEED_WRIST}", True)
        self._send("M400", True)

    #Mueve la muñeca 2(X) en muchos pasos para que vaya mas suave( se puede modificar )
    def _wrist_pitch_smooth(self, amp: float, steps: int = None):
        """Muñeca2 (pitch, X) en pasos pequeños (suave)."""
        if steps is None: steps = self.WRIST_STEPS
        step = amp / steps
        for _ in range(steps):   self._send(f"G1 X{ step:.3f} F{self.FEED_WRIST}", True)
        self._send("M400", True)
        for _ in range(2*steps): self._send(f"G1 X{-step:.3f} F{self.FEED_WRIST}", True)
        self._send("M400", True)
        for _ in range(steps):   self._send(f"G1 X{ step:.3f} F{self.FEED_WRIST}", True)
        self._send("M400", True)

    #Ejecuta la secuencia dependiendo el comando enviado por MQTT
    def _do_macro(self, name: str):
        """
        L1/L2: base (barrido ±A) -> bajar -> roll a vertical -> abrir/cerrar -> subir -> muñeca suave.
        Extras de diagnóstico:
          - 'servo_test'     : mueve M280 en P{SERVO_INDEX} (40/120)
          - 'roll_test_pos'  : T1 E +10 (o el valor que configures)
          - 'roll_test_neg'  : T1 E -10
        """
        name = (name or "").strip().lower()
        #Distintos casos dependiendo el mensaje que enviemos del MQTT
        def g(axis, dist, feed):
            self._send(f"G1 {axis}{dist} F{feed}", True); self._send("M400", True)

        if name in ("l1", "presentar"):
            A = self.AMP_BASE_L1
            g("Y", +A, self.FEED_NORM); g("Y", -2*A, self.FEED_NORM); g("Y", +A, self.FEED_NORM)
            g("Z", self.Z_DOWN_SIGN * self.AMP_Z_L1, self.FEED_SLOW)
            self._wrist_roll_to_vertical()
            self._servo(self.SERVO_OPEN);  self._servo(self.SERVO_CLOSE)
            g("Z", -self.Z_DOWN_SIGN * self.AMP_Z_L1, self.FEED_SLOW)
            self._wrist_pitch_smooth(self.AMP_WRIST_L1)

        elif name in ("l2", "barrer"):
            A = self.AMP_BASE_L2
            g("Y", -A, self.FEED_NORM); g("Y", +2*A, self.FEED_NORM); g("Y", -A, self.FEED_NORM)
            g("Z", self.Z_DOWN_SIGN * self.AMP_Z_L2, self.FEED_SLOW)
            self._wrist_roll_to_vertical()
            self._servo(self.SERVO_OPEN);  self._servo(self.SERVO_CLOSE)
            g("Z", -self.Z_DOWN_SIGN * self.AMP_Z_L2, self.FEED_SLOW)
            self._wrist_pitch_smooth(self.AMP_WRIST_L2)

        elif name == "servo_test":
            # Test directo del servo en el canal configurado
            self._servo(self.SERVO_OPEN); self._servo(self.SERVO_CLOSE)

        elif name == "roll_test_pos":
            self._send("T1", True); self._send(f"G1 E{abs(self.WRIST_ROLL_TO_VERTICAL)} F{self.FEED_WRIST}", True); self._send("M400", True)

        elif name == "roll_test_neg":
            self._send("T1", True); self._send(f"G1 E{-abs(self.WRIST_ROLL_TO_VERTICAL)} F{self.FEED_WRIST}", True); self._send("M400", True)

        elif name == "parking":
            g("Z", -self.Z_DOWN_SIGN * 10, 500)

        else:
            raise ValueError(f"[{self.name}] Macro desconocida: {name}")