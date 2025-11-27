#!/usr/bin/env python3
# painel_controle.py
#
# Painel de Controle CLI para o Caminhão ATR.
# Envia comandos via MQTT e exibe telemetria em tempo real.

import paho.mqtt.client as mqtt
import threading
import time
import json
import os

BROKER = "localhost"
TRUCK_ID = 1

TOPIC_CMD = f"/mina/caminhoes/{TRUCK_ID}/comandos"
TOPIC_SETP = f"/mina/caminhoes/{TRUCK_ID}/setpoints"
TOPIC_SENSORES = f"/mina/caminhoes/{TRUCK_ID}/sensores"
TOPIC_ATUADORES = f"/mina/caminhoes/{TRUCK_ID}/atuadores"
TOPIC_EVENTOS = f"/mina/caminhoes/{TRUCK_ID}/eventos"

# Estado local para exibição
last_sensor = {}
last_atuadores = {}
last_evento = None

# ============================================================
# MQTT - CALLBACKS
# ============================================================

def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] Conectado ao broker ({rc})")
    client.subscribe(TOPIC_SENSORES)
    client.subscribe(TOPIC_ATUADORES)
    client.subscribe(TOPIC_EVENTOS)

def on_message(client, userdata, msg):
    global last_sensor, last_atuadores, last_evento

    payload = msg.payload.decode()

    if msg.topic == TOPIC_SENSORES:
        try:
            last_sensor = json.loads(payload)
        except:
            pass

    elif msg.topic == TOPIC_ATUADORES:
        try:
            last_atuadores = json.loads(payload)
        except:
            pass

    elif msg.topic == TOPIC_EVENTOS:
        last_evento = payload


# ============================================================
# THREAD DE EXIBIÇÃO EM TEMPO REAL
# ============================================================

def display_thread():
    while True:
        os.system("clear")
        print("========================================")
        print("     PAINEL DE CONTROLE - CAMINHÃO 1    ")
        print("========================================\n")

        print(">>> SENSORES:")
        print(last_sensor if last_sensor else "Aguardando dados...")

        print("\n>>> ATUADORES:")
        print(last_atuadores if last_atuadores else "Aguardando dados...")

        print("\n>>> EVENTOS:")
        print(last_evento if last_evento else "Nenhum")

        print("\n========================================")
        print("  COMANDOS DISPONÍVEIS:")
        print("  [1] Modo Automático")
        print("  [2] Modo Manual")
        print("  [3] Rearme")
        print("  [4] Acelerar")
        print("  [5] Virar Esquerda")
        print("  [6] Virar Direita")
        print("  [7] Enviar Setpoint (x,y)")
        print("  [0] Sair")
        print("========================================\n")

        time.sleep(0.5)


# ============================================================
# ENVIO DE COMANDOS
# ============================================================

def send_cmd(client, cmd):
    client.publish(TOPIC_CMD, cmd)

def painel():
    mqttc = mqtt.Client()
    mqttc.on_connect = on_connect
    mqttc.on_message = on_message

    mqttc.connect(BROKER, 1883, 60)

    # inicia thread de exibição
    threading.Thread(target=display_thread, daemon=True).start()

    mqttc.loop_start()

    # loop principal
    while True:
        op = input(">> Comando: ").strip()

        if op == "1":
            send_cmd(mqttc, "auto")

        elif op == "2":
            send_cmd(mqttc, "man")

        elif op == "3":
            send_cmd(mqttc, "rearme")

        elif op == "4":
            send_cmd(mqttc, "acelera=1")

        elif op == "5":
            send_cmd(mqttc, "esquerda=1")

        elif op == "6":
            send_cmd(mqttc, "direita=1")

        elif op == "7":
            try:
                x = int(input("x: "))
                y = int(input("y: "))
                mqttc.publish(TOPIC_SETP, f"x={x},y={y}")
            except:
                print("Valores inválidos.")

        elif op == "0":
            print("Saindo...")
            break

        else:
            print("Opção inválida.")

    mqttc.loop_stop()
    mqttc.disconnect()


if __name__ == "__main__":
    painel()
