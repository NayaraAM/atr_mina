import paho.mqtt.client as mqtt
import json

def on_connect(client, userdata, flags, rc):
    print(f"CONNECTED with Result Code {rc}")
    client.subscribe("/mina/caminhoes/+/posicao")

def on_message(client, userdata, msg):
    print(f"[DADO RECEBIDO] Tópico: {msg.topic} | Payload: {msg.payload.decode()}")

# Correção para Paho MQTT v2.0+
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "DebugSniffer")
client.on_connect = on_connect
client.on_message = on_message

try:
    print("Tentando conectar ao localhost:1883...")
    client.connect("localhost", 1883, 60)
    client.loop_forever()
except Exception as e:
    print(f"ERRO CRÍTICO DE CONEXÃO: {e}")