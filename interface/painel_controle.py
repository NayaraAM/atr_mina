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
import sys

BROKER = "localhost"
TRUCK_ID = 1

TOPIC_CMD = f"/mina/caminhoes/{TRUCK_ID}/comandos"
TOPIC_SETP = f"/mina/caminhoes/{TRUCK_ID}/setpoints"
TOPIC_SENSORES = f"/mina/caminhoes/{TRUCK_ID}/sensores"
TOPIC_ATUADORES = f"/mina/caminhoes/{TRUCK_ID}/atuadores"
TOPIC_EVENTOS = f"/mina/caminhoes/{TRUCK_ID}/eventos"
TOPIC_SIM_DEF = f"/mina/caminhoes/{TRUCK_ID}/sim/defeito"

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
        print("  [d] Injetar defeito elétrico (toggle)")
        print("  [h] Injetar defeito hidráulico (toggle)")
        print("  [x] Limpar defeitos (clear)")
        print("  [0] Sair")
        print("========================================\n")

        time.sleep(0.5)


# ============================================================
# ENVIO DE COMANDOS
# ============================================================

def send_cmd(client, cmd):
    client.publish(TOPIC_CMD, cmd)

def send_defeito(client, msg):
    client.publish(TOPIC_SIM_DEF, msg)

def painel():
    mqttc = mqtt.Client()
    mqttc.on_connect = on_connect
    mqttc.on_message = on_message

    mqttc.connect(BROKER, 1883, 60)

    # inicia thread de exibição
    threading.Thread(target=display_thread, daemon=True).start()

    mqttc.loop_start()

    # loop principal
    # Leitura de tecla única (sem ENTER) para comandos.
    # Mapeamento: '1'/'a' -> Automático, '2'/'m' -> Manual, '3'/'r' -> Rearme,
    # '4'/'w' -> Acelerar (toggle on), '5'/'z' -> Esquerda, '6'/'c' -> Direita,
    # 's' -> enviar setpoint simples solicitando x,y (com ENTER ainda para valores).
    import tty, termios, select

    def read_key(timeout=0.1):
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            rlist, _, _ = select.select([fd], [], [], timeout)
            if not rlist:
                return None
            ch = sys.stdin.read(1)
            if ch == '\x1b':  # possível sequência de escape
                # ler próximos bytes rapidamente
                rlist, _, _ = select.select([fd], [], [], 0.02)
                if not rlist:
                    return '\x1b'
                ch2 = sys.stdin.read(1)
                if ch2 != '[':
                    return ch2
                rlist, _, _ = select.select([fd], [], [], 0.02)
                if not rlist:
                    return None
                ch3 = sys.stdin.read(1)
                if ch3 == 'A':
                    return 'ARROW_UP'
                if ch3 == 'B':
                    return 'ARROW_DOWN'
                if ch3 == 'C':
                    return 'ARROW_RIGHT'
                if ch3 == 'D':
                    return 'ARROW_LEFT'
                return None
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    try:
        while True:
            key = read_key(0.2)
            if key:
                k = key.lower()
                if k in ('1', 'a'):
                    send_cmd(mqttc, "auto")
                elif k in ('2', 'm'):
                    send_cmd(mqttc, "man")
                elif k in ('3', 'r'):
                    send_cmd(mqttc, "rearme")
                elif k in ('4', 'w'):
                    send_cmd(mqttc, "acelera=1")
                elif k in ('5', 'z'):
                    send_cmd(mqttc, "esquerda=1")
                elif k in ('6', 'c'):
                    send_cmd(mqttc, "direita=1")
                elif k == 'd':
                    # injetar defeito elétrico
                    send_defeito(mqttc, "eletrica=1")
                elif k == 'h':
                    # injetar defeito hidráulico
                    send_defeito(mqttc, "hidraulica=1")
                elif k == 'x':
                    # limpar defeitos
                    send_defeito(mqttc, "clear")
                elif k == 's':
                    # solicita valores (usa input já que são numéricos)
                    try:
                        x = int(input("x: "))
                        y = int(input("y: "))
                        mqttc.publish(TOPIC_SETP, f"x={x},y={y}")
                    except Exception as e:
                        print("Valores inválidos.")
                elif k == '0' or ord(k) == 3:  # '0' ou Ctrl-C
                    print("Saindo...")
                    break
            # deixa loop de exibição continuar
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass

    mqttc.loop_stop()
    mqttc.disconnect()


if __name__ == "__main__":
    painel()
