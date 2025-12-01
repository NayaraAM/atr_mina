#!/usr/bin/env python3
"""
Interface Local (Cockpit) do Caminhão Autônomo

Este script implementa uma interface gráfica (GUI) usando a biblioteca Pygame para
simular o painel de controle local de um caminhão autônomo específico (neste caso,
o caminhão com ID 1).

Funcionalidades Principais:
1.  Visualização de Estado: Exibe em tempo real os dados críticos do caminhão,
    como posição (X, Y, ângulo), temperatura, status dos atuadores (aceleração,
    direção) e o modo de operação atual (Automático/Manual, Com Defeito).
2.  Controle Manual: Fornece botões interativos que permitem ao operador enviar
    comandos diretos para o caminhão, incluindo:
    -   Mudar entre modos Automático e Manual.
    -   Rearmar o sistema após uma falha.
    -   Controlar a aceleração e a direção (quando em modo manual).

Arquitetura:
-   Comunicação MQTT: O script funciona como um cliente MQTT. Ele assina os
    tópicos de sensores (/sensores) e estado (/estado) do caminhão 1 para receber
    atualizações e publica comandos no tópico /comandos para controlar o veículo.
-   Multithreading: Uma thread dedicada (mqtt_thread) gerencia a conexão e o loop
    de mensagens MQTT em segundo plano, garantindo que a interface gráfica permaneça
    responsiva.
-   Interface Gráfica (Pygame): O loop principal (interface_local) desenha a tela,
    exibe os dados e processa os eventos de clique nos botões.
-   Sincronização: Um Lock (lock_estado) é usado para proteger o acesso ao
    dicionário 'estado', que é compartilhado entre a thread MQTT (que o atualiza)
    e a thread principal do Pygame (que o lê para exibir na tela).
"""

import pygame
import paho.mqtt.client as mqtt
import json
import threading
import time
import sys

# Endereço do broker MQTT
BROKER = "localhost"
# Tópicos MQTT específicos para o caminhão 1
TOPIC_CMD = "/mina/caminhoes/1/comandos"  # Para enviar comandos
TOPIC_SENS = "/mina/caminhoes/1/sensores" # Para receber dados dos sensores
TOPIC_EST = "/mina/caminhoes/1/estado"    # Para receber o estado geral

# =====================================================================
#               ESTADO LOCAL DA INTERFACE
# =====================================================================
# Dicionário que armazena a última cópia conhecida dos dados do caminhão.
# É atualizado pela thread MQTT e lido pela interface gráfica.
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

# Mutex para garantir acesso thread-safe ao dicionário 'estado'.
lock_estado = threading.Lock()

# =====================================================================
#               MQTT CALLBACKS
# =====================================================================
def on_connect(client, userdata, flags, rc):
    """Callback chamado quando a conexão MQTT é estabelecida."""
    print(f"[MQTT] Conectado. rc={rc}")
    # Assina os tópicos para receber dados do caminhão 1
    client.subscribe(TOPIC_SENS)
    client.subscribe(TOPIC_EST)

def on_message(client, userdata, msg):
    """Callback chamado quando uma mensagem MQTT é recebida."""
    global estado
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)

        # Bloqueia o mutex para atualizar o estado com segurança
        with lock_estado:
            if msg.topic == TOPIC_SENS:
                # Atualiza dados dos sensores (posição, temperatura, falhas)
                estado["x"] = data.get("x", 0)
                estado["y"] = data.get("y", 0)
                estado["ang"] = data.get("ang", 0)
                estado["temp"] = data.get("temp", 0)
                estado["falha_elet"] = data.get("falha_elet", False)
                estado["falha_hidr"] = data.get("falha_hidr", False)

            elif msg.topic == TOPIC_EST:
                # Atualiza o estado operacional e dos atuadores
                estado["modo_auto"] = data.get("automatico", False)
                estado["defeito"] = data.get("defeito", False)
                estado["aceleracao"] = data.get("aceleracao", 0)
                estado["direcao"] = data.get("direcao", 0)

        # print(f"[MSG] {msg.topic} => {payload}") # Debug (comentado para reduzir poluição)

    except Exception as e:
        print(f"[ERRO] Falha ao processar mensagem: {e}")

# =====================================================================
#               MQTT THREAD
# =====================================================================
def mqtt_thread():
    """Função da thread que gerencia a conexão MQTT em segundo plano."""
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    print("[MQTT] Conectando ao broker...")
    try:
        client.connect(BROKER, 1883, 60)
        # loop_forever bloqueia esta thread, processando mensagens continuamente
        client.loop_forever()
    except Exception as e:
        print(f"[ERRO] Não foi possível conectar ao broker MQTT: {e}")
        sys.exit(1)


# =====================================================================
#               PUBLICAÇÃO DE COMANDOS
# =====================================================================
def enviar_comando(cmd):
    """Função auxiliar para enviar um comando simples via MQTT."""
    # Cria um cliente temporário para enviar uma única mensagem
    # (Poderia ser otimizado usando o cliente da thread principal, mas isso
    # exigiria um design mais complexo com filas thread-safe)
    try:
        client = mqtt.Client()
        client.connect(BROKER, 1883, 60)
        client.publish(TOPIC_CMD, cmd)
        client.disconnect()
        print(f"[COMANDO] enviado: {cmd}")
    except Exception as e:
        print(f"[ERRO] Falha ao enviar comando '{cmd}': {e}")


# =====================================================================
#               INTERFACE GRÁFICA pygame
# =====================================================================

# Definição de cores (RGB)
PRETO = (0, 0, 0)
BRANCO = (255, 255, 255)
VERDE = (0, 200, 0)
VERMELHO = (200, 0, 0)
AZUL = (0, 70, 200)
CINZA = (70, 70, 70)

# Inicialização do Pygame e da fonte
pygame.init()
try:
    FONT = pygame.font.SysFont("Arial", 22)
except:
    FONT = pygame.font.Font(None, 22)

def desenhar_botao(surface, texto, x, y, cor):
    """Função auxiliar para desenhar um botão e retornar seu retângulo de colisão."""
    pygame.draw.rect(surface, cor, (x, y, 180, 50))
    label = FONT.render(texto, True, BRANCO)
    surface.blit(label, (x + 15, y + 12))
    return pygame.Rect(x, y, 180, 50)


def interface_local():
    """Loop principal da interface gráfica Pygame."""
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Interface Local - Caminhão 1")

    clock = pygame.time.Clock()

    # Variáveis para armazenar os retângulos dos botões
    btn_auto = None
    btn_man = None
    btn_rearme = None
    btn_acel = None
    btn_esq = None
    btn_dir = None

    while True:
        screen.fill(CINZA) # Limpa a tela com a cor de fundo

        # ===================== DESENHA BOTÕES =====================
        # Desenha os botões de controle de modo e rearme
        btn_auto = desenhar_botao(screen, "Automático", 50, 50, AZUL)
        btn_man = desenhar_botao(screen, "Manual", 50, 120, AZUL)
        btn_rearme = desenhar_botao(screen, "Rearme", 50, 190, VERMELHO)

        # Desenha os botões de controle manual (movimento)
        btn_acel = desenhar_botao(screen, "Acelerar", 50, 280, VERDE)
        btn_esq = desenhar_botao(screen, "← Esquerda", 50, 350, VERDE)
        btn_dir = desenhar_botao(screen, "Direita →", 50, 420, VERDE)

        # ===================== MOSTRA INFORMAÇÕES =====================
        # Lê o estado atual (com lock) e prepara as linhas de texto para exibição
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

        # Renderiza e exibe cada linha de texto na tela
        y = 50
        for linha in text:
            label = FONT.render(linha, True, BRANCO)
            screen.blit(label, (350, y))
            y += 35

        # ===================== EVENTOS =====================
        # Processa a fila de eventos do Pygame
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit() # Encerra o programa ao fechar a janela

            if event.type == pygame.MOUSEBUTTONDOWN:
                # Verifica se o clique do mouse ocorreu sobre algum botão
                mouse = pygame.mouse.get_pos()

                if btn_auto.collidepoint(mouse):
                    enviar_comando("auto")

                if btn_man.collidepoint(mouse):
                    enviar_comando("man")

                if btn_rearme.collidepoint(mouse):
                    enviar_comando("rearme")

                if btn_acel.collidepoint(mouse):
                    enviar_comando("acelera") # Comando para incrementar aceleração

                if btn_esq.collidepoint(mouse):
                    enviar_comando("esquerda") # Comando para virar à esquerda

                if btn_dir.collidepoint(mouse):
                    enviar_comando("direita") # Comando para virar à direita

        pygame.display.update() # Atualiza a tela
        clock.tick(30) # Limita a taxa de quadros a 30 FPS


# =====================================================================
#                     PROGRAMA PRINCIPAL
# =====================================================================
if __name__ == "__main__":
    # Inicia a thread MQTT em modo daemon (será encerrada quando a thread principal terminar)
    threading.Thread(target=mqtt_thread, daemon=True).start()

    # Inicia o loop principal da interface gráfica
    interface_local()