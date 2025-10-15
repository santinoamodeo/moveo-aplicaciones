import serial
import time

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
    "G1 E1 F100",
    "G1 Y127 F1200", #no tocar
    "T0",      
    "G1 E-45 F500",
    "G1 Z-15 F500",
    
    #DEBE DE RETRAERSE 
    "T0",
    "G1 Z-40 F500 E40 F500",
    "M400", #HACE QUE LOS MOVIMIENTOS SEAN SINCRONIZADOS, LOS PONE EN LA COLA A TODOS
    "M280 P2 S160",#OBJETO AGARRAD0

    "T0",
    #SE VUELVE
    "G1 Z-24 F500 E-27 F500",  
   
    "G1 Y-85 F800",
    
    "M400",
    "M280 P2 S90",
    #SE RETRAE YA SOLTADO
    "T0",
    "G1 Z-15 F500 E-10 F500",
    "G1 Z0 F500",
    "G1 Y0 F800 E40",
    "M84"
    

     
      # Base +30 grados
    
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

        print("Programa terminado. Motores siguen energizados.")
        ser.close()

    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    send_gcode()