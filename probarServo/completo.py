import serial
import time

# ======================
# CONFIG SERIAL
# ======================
PORT = "COM8"      # ⚠️ Cambiá por el puerto correcto
BAUD = 115200

try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)
    ser.write(b"M17\n")  # Energiza motores
    print("[OK] Serial abierto y motores energizados.")
except Exception as e:
    print(f"[ERROR] No se pudo abrir el puerto serial: {e}")
    ser = None

# ======================
# FUNCIÓN PARA ENVIAR COMANDOS
# ======================
def enviar(cmd, espera=1):
    if ser:
        ser.write((cmd + "\n").encode())
        print(f">> {cmd}")
        time.sleep(espera)

# ======================
# SECUENCIA DE PRUEBA COMPLETA
# ======================
print("Iniciando secuencia de prueba del brazo...")

# Configuración inicial
enviar("G21")   # milímetros
enviar("G90")   # posicionamiento absoluto

# ----------------------
# BASE (EJE Y)
# ----------------------
enviar("G1 Y25 F600")    # pequeño giro derecha
enviar("G1 Y-25 F600")   # pequeño giro izquierda
enviar("G1 Y0 F600")     # vuelve al centro

# ----------------------
# HOMBRO (EJE Z)
# ----------------------
enviar("G1 Z20 F500")    # sube hombro
enviar("G1 Z0 F500")     # baja hombro

# ----------------------
# CODO (EJE X)
# ----------------------
enviar("G1 X15 F400")    # adelanta
enviar("G1 X0 F400")     # vuelve

# ----------------------
# MUÑECA (EJE E o A, según firmware)
# ----------------------
# Reducido para que gire menos
enviar("T1")
enviar("G1 E5 F250")     # gira poco la muñeca
enviar("G1 E0 F250")     # vuelve
time.sleep(1)

# ----------------------
# PINZA (SERVO M280) — probado y funcional
# ----------------------
print("Probando pinza...")
enviar("G21")
enviar("G90")

for i in range(2):
    enviar("M280 P0 S90")    # abre pinza
    enviar("G4 P1000")       # espera 1 s
    enviar("M280 P0 S180")   # cierra pinza
    enviar("G4 P1000")       # espera 1 s

# ----------------------
# FINAL
# ----------------------
print("✅ Prueba completa: base, hombro, codo, muñeca (poco giro) y pinza (servo confirmado).")
enviar("M18")  # Desenergiza motores

if ser:
    ser.close()
