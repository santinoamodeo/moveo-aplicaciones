import serial
import time

PORT = "COM4"
BAUDRATE = 115200

gcode_commands = [
    "M17",          # Encender motores
    "M83",          # Estrusion relativa
    "M84 S0",       # Nunca apagar motores automáticamente
    "G90",          # Coordenadas ABSOLUTOS
    "M302 S",       # activa extrusores en frio
    "M400", #HACE QUE LOS MOVIMIENTOS SEAN SINCRONIZADOS, LOS PONE EN LA COLA A TODOS
    "M280 P2 S90",
    "T1",
    "G1 E1 F100",
    "G1 Y127 F1200", #no tocar
    "T0",      
    "G1 E-45 F500",
    "G1 Z-15 F500",
    #DEBE DE RETRAERSE 
    "T0",
    "G1 Z-40 F500 E40",
    "M400", #HACE QUE LOS MOVIMIENTOS SEAN SINCRONIZADOS, LOS PONE EN LA COLA A TODOS
    "M280 P2 S177",#OBJETO AGARRAD0
    "M400",
    "T0",
    #SE VUELVE
    "G1 Z-24 F500 E-27",  
    "G1 Z-21 F500",
    "G1 Y-85 F800",
    "M400",
    "M280 P2 S90",
    #SE RETRAE YA SOLTADO
    "G1 Z-24 F500",
    "T0",
    "G1 Z-15 F500 E-10",
    "G1 Z0 F500",
    "G1 Y0 F800 E42",
    "T1",
    "G1 E-1 F100",
    "M84"  
]

def send_gcode():
    try:
        ser = serial.Serial(PORT, BAUDRATE, timeout=2)
        time.sleep(2)  # Esperar a que Marlin inicie
        print("Conectado a", PORT)

        # Vaciar el buffer
        ser.reset_input_buffer()

        for cmd in gcode_commands:
            ser.write((cmd + "\n").encode())
            print(">>", cmd)

            # Esperar confirmación "ok"
            response = ""
            start = time.time()
            while True:
                if ser.in_waiting > 0:
                    line = ser.readline().decode(errors='ignore').strip()
                    if line:
                        print("<<", line)
                        if line.lower().startswith("ok"):
                            break
                # Evita bloqueo eterno
                if time.time() - start > 5:
                    print("⚠️ Timeout esperando 'ok' de Marlin")
                    break

        # Esperar a que se vacíe el buffer y que termine el último movimiento
        ser.write(b"M400\n")
        ser.flush()
        time.sleep(3)

        print("✅ Programa terminado correctamente.")
        ser.close()

    except Exception as e:
        print("❌ Error:", e)

if __name__ == "__main__":
    send_gcode()
