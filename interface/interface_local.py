#!/usr/bin/env python3
import pygame
import paho.mqtt.client as mqtt
import json
import threading
import time
import sys

BROKER = "localhost"
TOPIC_CMD = "/mina/caminhoes/1/comandos"
TOPIC_SENS = "/mina/caminhoes/1/sensores"
TOPIC_EST = "/mina/caminhoes/1/estado"

# =====================================================================
#               ESTADO LOCAL DA INTERFACE
# =====================================================================
estado = {
    "modo_auto": False,
    "defeito": False,
    "aceleracao": 0,
    "direcao": 0,
    "x": 0,
    "y": 0,
    "ang": 0,
    "temp": 0,
    "falha_elet": False,
    "falha_hidr": False
}

lock_estado = threading.Lock()

# =====================================================================
#               MQTT CALLBACKS
# =====================================================================
def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] Conectado. rc={rc}")
    client.subscribe(TOPIC_SENS)
    client.subscribe(TOPIC_EST)

def on_message(client, userdata, msg):
    global estado
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)

        with lock_estado:
            if msg.topic == TOPIC_SENS:
                estado["x"] = data.get("x", 0)
                estado["y"] = data.get("y", 0)
                estado["ang"] = data.get("ang", 0)
                estado["temp"] = data.get("temp", 0)
                estado["falha_elet"] = data.get("falha_elet", False)
                estado["falha_hidr"] = data.get("falha_hidr", False)

            elif msg.topic == TOPIC_EST:
                estado["modo_auto"] = data.get("automatico", False)
                estado["defeito"] = data.get("defeito", False)
                estado["aceleracao"] = data.get("aceleracao", 0)
                estado["direcao"] = data.get("direcao", 0)

        print(f"[MSG] {msg.topic} => {payload}")

    except Exception as e:
        print(f"[ERRO] Falha ao processar mensagem: {e}")

# =====================================================================
#               MQTT THREAD
# =====================================================================
def mqtt_thread():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    print("[MQTT] Conectando ao broker...")
    client.connect(BROKER, 1883, 60)

    client.loop_forever()


# =====================================================================
#               PUBLICAÇÃO DE COMANDOS
# =====================================================================
def enviar_comando(cmd):
    client = mqtt.Client()
    client.connect(BROKER, 1883, 60)
    client.publish(TOPIC_CMD, cmd)
    client.disconnect()
    print(f"[COMANDO] enviado: {cmd}")


# =====================================================================
#               INTERFACE GRÁFICA pygame
# =====================================================================

# cores
PRETO = (0, 0, 0)
BRANCO = (255, 255, 255)
VERDE = (0, 200, 0)
VERMELHO = (200, 0, 0)
AZUL = (0, 70, 200)
CINZA = (70, 70, 70)

pygame.init()
FONT = pygame.font.SysFont("Arial", 22)

def desenhar_botao(surface, texto, x, y, cor):
    pygame.draw.rect(surface, cor, (x, y, 180, 50))
    label = FONT.render(texto, True, BRANCO)
    surface.blit(label, (x + 15, y + 12))
    return pygame.Rect(x, y, 180, 50)


def interface_local():
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Interface Local - Caminhão 1")

    clock = pygame.time.Clock()

    # botões
    btn_auto = None
    btn_man = None
    btn_rearme = None
    btn_acel = None
    btn_esq = None
    btn_dir = None

    while True:
        screen.fill(CINZA)

        # ===================== DESENHA BOTÕES =====================
        btn_auto = desenhar_botao(screen, "Automático", 50, 50, AZUL)
        btn_man = desenhar_botao(screen, "Manual", 50, 120, AZUL)
        btn_rearme = desenhar_botao(screen, "Rearme", 50, 190, VERMELHO)

        btn_acel = desenhar_botao(screen, "Acelerar", 50, 280, VERDE)
        btn_esq = desenhar_botao(screen, "← Esquerda", 50, 350, VERDE)
        btn_dir = desenhar_botao(screen, "Direita →", 50, 420, VERDE)

        # ===================== MOSTRA INFORMAÇÕES =====================
        with lock_estado:
            text = [
                f"Modo auto: {estado['modo_auto']}",
                f"Defeito: {estado['defeito']}",
                f"Aceleração: {estado['aceleracao']}",
                f"Direção: {estado['direcao']}",
                f"X={estado['x']}  Y={estado['y']}",
                f"Ângulo={estado['ang']}",
                f"Temp={estado['temp']} C",
                f"Falha elétrica={estado['falha_elet']}",
                f"Falha hidráulica={estado['falha_hidr']}",
            ]

        y = 50
        for linha in text:
            label = FONT.render(linha, True, BRANCO)
            screen.blit(label, (350, y))
            y += 35

        # ===================== EVENTOS =====================
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse = pygame.mouse.get_pos()

                if btn_auto.collidepoint(mouse):
                    enviar_comando("auto")

                if btn_man.collidepoint(mouse):
                    enviar_comando("man")

                if btn_rearme.collidepoint(mouse):
                    enviar_comando("rearme")

                if btn_acel.collidepoint(mouse):
                    enviar_comando("acelera")

                if btn_esq.collidepoint(mouse):
                    enviar_comando("esquerda")

                if btn_dir.collidepoint(mouse):
                    enviar_comando("direita")

        pygame.display.update()
        clock.tick(30)


# =====================================================================
#                    PROGRAMA PRINCIPAL
# =====================================================================
if __name__ == "__main__":
    # inicia MQTT em paralelo
    threading.Thread(target=mqtt_thread, daemon=True).start()

    # inicia interface pygame
    interface_local()
