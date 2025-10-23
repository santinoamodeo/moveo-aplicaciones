import serial
import time

##ESTA SECUENCIA MUEVE DE UN EXTREMO DE LA MESA HACIA OTRO.

# Configura el puerto serie donde está conectado tu Arduino
# En Windows suele ser COM3, COM4, etc. En Linux: /dev/ttyUSB0
PORT = "COM4"    
BAUDRATE = 115200  

# G-code program
gcode_commands = [
    "M17",          # Encender motores
    "M83",          # Estrusion relativa
    "M84 S0",       # Nunca apagar motores automáticamente
    "G90",          # Coordenadas ABSOLUTOS
    "M302 S",       # activa extrusores en frio
    "M400", #HACE QUE LOS MOVIMIENTOS SEAN SINCRONIZADOS, LOS PONE EN LA COLA A TODOS
    "M280 P2 S90",
    "T1",
    "G1 E3 F100",
    "G1 Y-180 F1300", #no tocar
    "T0",      
    "G1 E30 Z23 F500",
    "M400",
    "M280 P2 S180",
    "G1 E-30 Z0 F500",#YA ESTA EN SU POSICION 0
    "T1",
    "G1 E-6 F100",
    "T0",
    "G1 E-30 Z-23 F500",
    "M400",
    "M280 P2 S90", ##SUELTA, DEBE VOLVER A REPOSO
    "G1 Z0 E30 F500",
    "T1",
    "G1 E3 F100",
    "G1 Y0 F1300"

    
    
]

def send_gcode():
    try:
        # Abrir conexión serie
        ser = serial.Serial(PORT, BAUDRATE, timeout=2)
        time.sleep(2)  # Esperar a que Marlin reinicie y esté listo
        
        print("Conectado a", PORT)
        
        for cmd in gcode_commands:
            ser.write((cmd + "\n").encode())  # Mandar comando
            print(">>", cmd)
            time.sleep(0.5)  # Pausa entre comandos (ajustable)
 # ---------------------
        # ESPERA FINAL PARA QUE SE EJECUTEN LOS ÚLTIMOS COMANDOS
        time.sleep(2)         # Espera extra 2 segundos
        ser.write(b"\n\n")    # Envía un par de saltos de línea extra
        ser.flush()           # Asegura que se envíe todo lo que queda en el buffer
        time.sleep(2)         # Otra espera por seguridad
        # ---------------------
        print("Programa terminado. Motores siguen energizados.")
        ser.close()

    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    send_gcode()