#Programa para conectar brazo con Mqtt

# Celular y pc se conectan al mismo servidor de mqtt
# Celular envia mensaje a un topico como publicador, pc recibe ese mensaje como lector
# Transforma ese mensaje que viene en JSON a G-Code que es el que maneja el Marlin
#Dependiendo el mensaje el brazo inicia una secuencia de movimientos

import json
from paho.mqtt.client import Client
from Brazo import Arm

# ===== CONFIG =====
PORT = "COM3"                 # Puerto del Mega
BAUD = 115200                 # Baudios de Marlin
BROKER = "broker.hivemq.com"  # Broker público (Podes usar otro broker si tenes)
BROKER_PORT = 1883            # 1883 sin TLS (8883 con TLS)

# Prefijo único para no chocar en broker público
TOPIC_BASE  = "BrazoOctavio"  
TOPIC_CMD   = f"{TOPIC_BASE}/cmd"     # recibe casos de comando o JSON
TOPIC_ESTOP = f"{TOPIC_BASE}/estop"   # {"soft":true} -> M410
TOPIC_STAT  = f"{TOPIC_BASE}/status"  # publica estado

#Crea una instancia de clase Arm, y configura puerto, baudios y nombre
arm = Arm(PORT, BAUD, name="Brazo1")

#Se suscribe a los topicos de comando y publica "Listo" como respuesta
def on_connect(cli, userdata, flags, rc):
    print(f"[MQTT] Conectado rc={rc}. Sub: {TOPIC_CMD}, {TOPIC_ESTOP}")
    cli.subscribe([(TOPIC_CMD,1),(TOPIC_ESTOP,2)])
    cli.publish(TOPIC_STAT, json.dumps({"state":"Listo"}), retain=False)

#Cuando llega un mensaje Mqtt, interpreta el payload y ejecuta el movimiento indicado, publica "listo" o en su defecto "error" 
def on_message(cli, userdata, msg):
    try:
        if msg.topic == TOPIC_ESTOP:
            arm.estop_soft()
            cli.publish(TOPIC_STAT, json.dumps({"state":"estopped"}))
            return

        payload_raw = msg.payload.decode("utf-8").strip()

        # 1) Si es JSON, usamos type/macro/move_delta
        try:
            payload = json.loads(payload_raw)
            t = (payload.get("type") or "").lower()
            if t == "move_delta":
                arm.move_delta(payload.get("axes", {}), payload.get("feed", 1200))
            elif t == "macro":
                arm.run_macro(payload.get("name",""))
            else:
                # Si viene otro JSON raro, intentá como macro por nombre
                arm.run_macro(payload_raw)
        except json.JSONDecodeError:
            # 2) Si NO es JSON, tratá el texto como nombre de macro directamente
            arm.run_macro(payload_raw)

        cli.publish(TOPIC_STAT, json.dumps({"state":"Listo"}))

    except Exception as e:
        print("[ERR]", e)
        cli.publish(TOPIC_STAT, json.dumps({"state":"error","msg":str(e)}))

#Inicia el brazo y el cliente, registra callbacks, se conecta al broker y se queda esperando un mensaje
def main():
    arm.open()
    cli = Client(client_id="brazo_pc_bridge", clean_session=True)
    # Si tu broker requiere auth/TLS:
    # cli.username_pw_set("USUARIO","CLAVE")
    # cli.tls_set(); BROKER_PORT = 8883
    cli.on_connect = on_connect
    cli.on_message = on_message
    cli.connect(BROKER, BROKER_PORT, 60)
    print(f"[INFO] MQTT en {BROKER}:{BROKER_PORT}")
    print(f"      Topics: cmd={TOPIC_CMD}   estop={TOPIC_ESTOP}   status={TOPIC_STAT}")
    try:
        cli.loop_forever()
    except KeyboardInterrupt:
        arm.estop_soft()
    finally:
        arm.close(reenable_endstops=True, keep_on=True)

#Si ejecutas este archivo directamente corre el "main()", si lo importas desde otra modulo, no lo ejecuta
if __name__ == "__main__":
    main()

