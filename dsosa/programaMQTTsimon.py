import paho.mqtt.client as mqtt
import subprocess
import sys
import os

# Variable global para guardar el último mensaje recibido
mensajeMQTT = None

# Nombre del archivo en la misma carpeta
EJERCICIO2_PATH = "ejercicioCompletoV2.py"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(" Conectado al broker MQTT (broker.hivemq.com).")
        client.subscribe("apuCrack")
    else:
        print(f" Error de conexión. Código: {rc}")
def on_message(client, userdata, msg):
    global mensajeMQTT
    try:
        payload = msg.payload.decode("utf-8").strip()
    except Exception as e:
        print("Error decodificando payload:", e)
        return

    # Guardamos siempre el último mensaje recibido
    mensajeMQTT = payload

    if payload == "1":
        print("llego 1")
        # Verificamos que exista el archivo antes de intentar ejecutarlo
        if not os.path.exists(EJERCICIO2_PATH):
            print(f" No se encontró {EJERCICIO2_PATH}. Revisa la ruta y el nombre.")
            return
        try:
            # Ejecuta el script en un proceso separado con el mismo intérprete
            subprocess.Popen([sys.executable, EJERCICIO2_PATH])
            print(f" Ejecutando {EJERCICIO2_PATH} en un proceso separado.")
        except Exception as e:
            print("Error al lanzar el script:", e)
    else:
        print(f" Mensaje recibido en {msg.topic}: {payload}")

# --- Configuración del cliente ---
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

# Conectar al broker público HiveMQ
client.connect("broker.hivemq.com", 1883, 60)

# Mantener la conexión activa (bloqueante)
client.loop_forever()
