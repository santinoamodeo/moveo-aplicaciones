import serial
import time

# ======================
# CONFIG SERIAL
# ======================
PORT = "COM8"      # ⚠️ Cambiá por el puerto correcto (ej. COM3, COM5...)
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
# SECUENCIA DE PRUEBA DE LA PINZA (servo M280)
# ======================
print("Iniciando prueba de pinza con servo...")

# Configuración básica
enviar("G21")   # milímetros
enviar("G90")   # posicionamiento absoluto

# Secuencia abrir / cerrar
for i in range(2):  # repetir dos veces
    enviar("M280 P0 S90")    # abre pinza
    enviar("G4 P1000")       # espera 1 s
    enviar("M280 P0 S180")   # cierra pinza
    enviar("G4 P1000")       # espera 1 s

print("✅ Prueba completada: la pinza debería haberse abierto y cerrado dos veces.")

# Desenergizar motores (opcional)
enviar("M18")
if ser:
    ser.close()
