#!/usr/bin/env python3
"""
Gestão da Mina - Interface Gráfica (Pygame)

Este script implementa a interface gráfica principal do sistema de gestão da mina
utilizando a biblioteca Pygame. Ele permite a visualização em tempo real da posição
e do estado de todos os caminhões no mapa, além de oferecer controles interativos
para adicionar novos caminhões, enviar setpoints (clicando no mapa) e enviar
comandos específicos (Manual, Automático, Rearmar, Simular Falha) para um caminhão
selecionado.

A comunicação com o sistema embarcado (C++) e com o spawner de processos é feita
exclusivamente via MQTT, garantindo o desacoplamento entre a interface e a lógica
de controle.

Funcionalidades Principais:
1.  Visualização do Mapa: Exibe um mapa de fundo (se disponível) e a posição de
    todos os caminhões conectados. A cor de cada caminhão indica seu estado
    (Laranja=Manual, Verde=Automático, Vermelho=Defeito).
2.  Adição de Caminhões: Um botão "+ NOVO CAMINHÃO" permite solicitar a criação
    de um novo processo de caminhão ao spawner (run_all.py) via MQTT.
3.  Seleção e Controle: Ao clicar em um caminhão, ele é selecionado (destacado com
    um círculo ciano). Uma barra de ferramentas inferior aparece, oferecendo
    botões para enviar comandos específicos ao caminhão selecionado.
4.  Envio de Setpoints: Com um caminhão selecionado, clicar em qualquer ponto
    do mapa (fora da barra de ferramentas) envia as coordenadas desse ponto como
    um novo setpoint de navegação para o caminhão.
5.  Monitoramento de Estado: A barra de ferramentas inferior exibe o estado atual
    (Modo, Defeito, Temperatura) do caminhão selecionado.

Arquitetura:
-   Classe Button: Implementa botões interativos na interface Pygame.
-   Classe Manager: Gerencia a conexão MQTT, assina os tópicos relevantes
    (/posicao, /estado, /sensores, /ack) e mantém um dicionário atualizado com o
    estado de todos os caminhões.
-   Função run(): Loop principal do Pygame, responsável por desenhar a interface,
    processar eventos de entrada (cliques do mouse, fechamento da janela) e
    atualizar a tela.
"""

import os
import sys
import time
import json
import threading
import math
import pygame
import paho.mqtt.client as mqtt

# --- CONFIGURAÇÕES ---
# Obtém o endereço e a porta do broker MQTT das variáveis de ambiente,
# usando valores padrão se não estiverem definidas.
MQTT_BROKER = os.environ.get('MQTT_BROKER', 'localhost')
MQTT_PORT = int(os.environ.get('MQTT_BROKER_PORT', '1883')) # Corrigido para MQTT_BROKER_PORT

# Dimensões da janela Pygame
WIN_W, WIN_H = 1000, 1000
# Limites do mundo virtual (coordenadas usadas pelos caminhões)
WORLD_MIN, WORLD_MAX = 0, 1000

# --- CLASSE BOTÃO ---
class Button:
    """
    Classe simples para representar e gerenciar botões na interface Pygame.
    """
    def __init__(self, x, y, w, h, text, color, action_callback, param=None):
        # Retângulo que define a área do botão
        self.rect = pygame.Rect(x, y, w, h)
        # Texto a ser exibido no botão
        self.text = text
        # Cor de fundo do botão
        self.color = color
        # Função a ser chamada quando o botão é clicado
        self.action = action_callback
        # Parâmetro opcional a ser passado para a função de ação
        self.param = param
        # Tenta carregar uma fonte do sistema; usa uma padrão se falhar
        try:
            self.font = pygame.font.SysFont("Arial", 14, bold=True)
        except Exception:
            self.font = None # Será criada no método draw se necessário

    def draw(self, screen):
        """Desenha o botão na tela."""
        # Garante que a fonte esteja carregada
        if not self.font:
            try:
                self.font = pygame.font.SysFont("Arial", 14, bold=True)
            except Exception:
                self.font = pygame.font.Font(None, 14)

        # Desenha uma sombra para dar efeito de profundidade
        pygame.draw.rect(screen, (50, 50, 50), (self.rect.x+2, self.rect.y+2, self.rect.w, self.rect.h), border_radius=5)
        # Desenha o corpo principal do botão
        pygame.draw.rect(screen, self.color, self.rect, border_radius=5)
        # Desenha uma borda branca
        pygame.draw.rect(screen, (255, 255, 255), self.rect, 2, border_radius=5)
        # Renderiza e centraliza o texto no botão
        lbl = self.font.render(self.text, True, (255, 255, 255))
        screen.blit(lbl, (self.rect.centerx - lbl.get_width()//2, self.rect.centery - lbl.get_height()//2))

    def check_click(self, pos):
        """Verifica se um clique ocorreu dentro da área do botão."""
        if self.rect.collidepoint(pos):
            # Executa a ação associada, passando o parâmetro se ele existir
            if self.param is not None:
                self.action(self.param)
            else:
                self.action()
            return True # Indica que o botão foi clicado
        return False

# --- MQTT MANAGER ---
class Manager:
    """
    Gerencia a comunicação MQTT e o estado dos caminhões para a interface.
    """
    def __init__(self, broker, port):
        # Dicionário para armazenar o estado de cada caminhão (ID -> estado)
        self.trucks = {}
        # Próximo ID de caminhão a ser criado (o controle de IDs é feito aqui)
        # O ID 1 geralmente é criado na inicialização pelo run_all.py
        self.next_truck_id = 1
        # Mutex para acesso seguro ao dicionário de caminhões em ambiente multithread
        self.lock = threading.Lock()

        # Inicialização do cliente MQTT com fallback para versões diferentes da biblioteca Paho
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "GestaoMinaVisual")
        except Exception:
            self.client = mqtt.Client(client_id="GestaoMinaVisual")

        # Define os callbacks MQTT
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        # Tenta conectar ao broker
        try:
            self.client.connect(broker, port, 60)
            # Inicia o loop de processamento de rede em uma thread separada
            self.client.loop_start()
        except Exception:
            print(f"Erro conexão MQTT. Verifique se o broker está rodando ({broker}:{port}).")
            sys.exit(1)

    def on_connect(self, client, userdata, flags, rc):
        """Callback chamado quando a conexão com o broker é estabelecida."""
        print(f"[Interface] Conectado (RC={rc})")
        # Assina os tópicos de interesse para receber atualizações dos caminhões e do spawner
        client.subscribe('/mina/caminhoes/+/posicao')
        client.subscribe('/mina/caminhoes/+/estado')
        client.subscribe('/mina/caminhoes/+/sensores')
        client.subscribe('/mina/gerente/add_truck/ack')

    def on_message(self, client, userdata, msg):
        """Callback chamado quando uma mensagem MQTT é recebida."""
        try:
            topic_parts = msg.topic.split('/')
            payload = msg.payload.decode(errors='ignore')

            # Tratamento de mensagens de ACK do spawner (confirmação de criação de caminhão)
            if msg.topic.endswith("/add_truck/ack") or "/add_truck/ack" in msg.topic:
                print(f"[Spawner ACK] {payload}")
                return

            # Validação básica do formato do tópico (/mina/caminhoes/{id}/{tipo})
            if len(topic_parts) < 4:
                return
            tid = int(topic_parts[2]) # ID do caminhão
            kind = topic_parts[3]    # Tipo da mensagem (posicao, estado, sensores)

            # Tenta parsear o payload JSON
            try:
                data = json.loads(payload)
            except Exception:
                data = {} # Payload inválido ou vazio

            # Atualiza o estado do caminhão de forma thread-safe
            with self.lock:
                # Se o caminhão ainda não existe no dicionário, cria uma entrada inicial
                if tid not in self.trucks:
                    self.trucks[tid] = {
                        'x': int(data.get('x', 100)),
                        'y': int(data.get('y', 100)),
                        'ang': int(data.get('ang', 0)),
                        'temp': int(data.get('temp', 0)) if data.get('temp') is not None else 0,
                        'defeito': bool(data.get('defeito', False)),
                        'automatico': bool(data.get('automatico', False))
                    }

                s = self.trucks[tid]
                # Atualiza os campos correspondentes ao tipo de mensagem recebida
                if kind == 'posicao' or kind == 'sensores':
                    s.update({
                        'x': int(data.get('x', s.get('x', 0))),
                        'y': int(data.get('y', s.get('y', 0))),
                        'ang': int(data.get('ang', s.get('ang', 0)))
                    })
                elif kind == 'estado':
                    s.update({
                        'temp': int(data.get('temp', s.get('temp', 0))),
                        'defeito': bool(data.get('defeito', s.get('defeito', False))),
                        'automatico': bool(data.get('automatico', s.get('automatico', False)))
                    })
        except Exception:
            pass # Ignora erros de processamento de mensagem para não travar a interface

    # --- FUNÇÕES PARA ENVIO DE COMANDOS ---
    def send_cmd(self, params):
        """Envia um comando genérico para um caminhão específico."""
        tid, payload, suffix = params
        topic = f'/mina/caminhoes/{tid}{suffix}'
        self.client.publish(topic, payload)
        print(f"[CMD] {topic} <- {payload}")

    def send_setpoint(self, tid, x, y):
        """Envia um novo setpoint de posição para um caminhão."""
        topic = f'/mina/caminhoes/{tid}/setpoints'
        payload = f'x={x},y={y}'
        self.client.publish(topic, payload)
        print(f"[CMD] {topic} <- {payload}")

    def spawn_truck(self):
        """Solicita a criação de um novo caminhão e publica sua rota inicial."""
        truck_id = self.next_truck_id

        # 1. Solicita ao spawner (run_all.py) a criação do processo do caminhão
        msg = f"id={truck_id},route=routes/example.route"
        self.client.publish("/mina/gerente/add_truck", msg)
        print(f"[GERENTE] solicitou criação do caminhão {truck_id}")

        # 2. Adiciona o caminhão visualmente ao mapa imediatamente (feedback pro usuário)
        with self.lock:
            self.trucks[truck_id] = {
                'x': 100, 'y': 100, 'ang': 0, 'temp': 0,
                'defeito': False, 'automatico': False
            }

        # 3. Lê e publica o conteúdo completo do arquivo de rota para o caminhão
        #    (O código C++ espera receber a rota pelo tópico MQTT)
        route_path = "routes/example.route"
        if os.path.exists(route_path):
            try:
                with open(route_path, 'r') as f:
                    content = f.read()
                self.client.publish(f"/mina/caminhoes/{truck_id}/route", content)
                print(f"[GERENTE] rota publicada p/ truck {truck_id} (len={len(content)})")
            except Exception as e:
                print(f"[GERENTE] falha ao ler/publicar rota: {e}")
        else:
            # Rota de fallback caso o arquivo não exista (um quadrado simples)
            fallback = "100 100 30\n900 100 30\n900 900 30\n100 900 30\n100 100 30\n"
            self.client.publish(f"/mina/caminhoes/{truck_id}/route", fallback)
            print(f"[GERENTE] rota fallback publicada p/ truck {truck_id}")

        # 4. Incrementa o ID para o próximo caminhão
        self.next_truck_id += 1

# --- FUNÇÕES AUXILIARES VISUAIS ---
def world_to_px(x, y):
    """Converte coordenadas do mundo (0-1000) para pixels da tela."""
    px = int((x - WORLD_MIN) / (WORLD_MAX - WORLD_MIN) * WIN_W)
    py = int((1 - (y - WORLD_MIN) / (WORLD_MAX - WORLD_MIN)) * WIN_H)
    return px, py

def px_to_world(px, py):
    """Converte coordenadas de pixels da tela para do mundo (0-1000)."""
    x = int((px / WIN_W) * (WORLD_MAX - WORLD_MIN) + WORLD_MIN)
    y = int((1 - (py / WIN_H)) * (WORLD_MAX - WORLD_MIN) + WORLD_MIN)
    return x, y

def carregar_fundo():
    """Tenta carregar a imagem de fundo do mapa de vários caminhos possíveis."""
    paths = ["interface/assets/mapa_fundo.png", "assets/mapa_fundo.png", "mapa_fundo.png"]
    for p in paths:
        if os.path.exists(p):
            try:
                return pygame.image.load(p).convert()
            except Exception:
                pass
    return None

# --- LOOP PRINCIPAL DO PYGAME ---
def run():
    """Função principal que executa o loop da interface gráfica."""
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("Gestão da Mina - Controle Total")
    clock = pygame.time.Clock()

    # Carrega uma fonte padrão para desenhar textos
    try:
        font = pygame.font.SysFont("Arial", 12, bold=True)
    except Exception:
        font = pygame.font.Font(None, 12)

    # Inicializa o gerenciador MQTT
    mgr = Manager(MQTT_BROKER, MQTT_PORT)

    # Carrega e dimensiona a imagem de fundo
    bg_img = carregar_fundo()
    if bg_img:
        bg_img = pygame.transform.scale(bg_img, (WIN_W, WIN_H))

    selected_id = None # ID do caminhão atualmente selecionado
    # Botão para adicionar novos caminhões (sempre visível)
    btn_add = Button(10, 10, 180, 40, "+ NOVO CAMINHÃO", (0, 100, 0), mgr.spawn_truck)

    running = True
    while running:
        # Lista de botões de contexto (aparecem apenas quando um caminhão está selecionado)
        btns_context = []
        if selected_id is not None:
            Y_BAR = WIN_H - 60 # Posição vertical da barra inferior
            btns_context = [
                Button(20,  Y_BAR, 100, 40, "MANUAL",   (200, 140, 0), mgr.send_cmd, (selected_id, "c_man", "/comandos")),
                Button(130, Y_BAR, 100, 40, "AUTO",     (0, 180, 0),   mgr.send_cmd, (selected_id, "c_automatico", "/comandos")),
                Button(240, Y_BAR, 100, 40, "REARMAR",  (0, 100, 200), mgr.send_cmd, (selected_id, "c_rearme", "/comandos")),
                Button(350, Y_BAR, 120, 40, "CAUSAR FALHA", (200, 50, 50), mgr.send_cmd, (selected_id, "eletrica=1", "/sim/defeito"))
            ]

        # Processamento de eventos do Pygame
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False # Encerra o loop se a janela for fechada
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if event.button == 1: # Clique com o botão esquerdo
                    # 1. Verifica clique no botão de adicionar caminhão
                    if btn_add.check_click((mx, my)):
                        continue

                    # 2. Verifica clique nos botões de contexto (se houver caminhão selecionado)
                    clicked_ui = False
                    for b in btns_context:
                        if b.check_click((mx, my)):
                            clicked_ui = True
                            break
                    if clicked_ui:
                        continue

                    # 3. Verifica clique em um caminhão no mapa para selecioná-lo
                    clicked_truck = False
                    with mgr.lock:
                        for tid, s in mgr.trucks.items():
                            tx, ty = world_to_px(s['x'], s['y'])
                            # Verifica se o clique foi dentro do raio do caminhão (20px)
                            if (mx-tx)**2 + (my-ty)**2 <= 20**2:
                                selected_id = tid
                                clicked_truck = True
                                break

                    # 4. Se clicou no mapa (não em UI nem em caminhão) e tem seleção, envia SETPOINT
                    #    (e garante que o clique não foi na área da barra inferior)
                    if not clicked_truck and selected_id and my < WIN_H - 80:
                        wx, wy = px_to_world(mx, my)
                        mgr.send_setpoint(selected_id, wx, wy)

        # --- DESENHO DA INTERFACE ---
        # Desenha o fundo
        if bg_img:
            screen.blit(bg_img, (0,0))
        else:
            screen.fill((50,50,50))

        # Desenha os caminhões
        with mgr.lock:
            items = list(mgr.trucks.items())
        for tid, s in items:
            px, py = world_to_px(s['x'], s['y'])
            ang = math.radians(s['ang'])
            # Define a cor com base no estado (Defeito > Automático > Manual)
            cor = (255, 140, 0) # Laranja (Manual)
            if s.get('defeito'): cor = (255, 0, 0) # Vermelho (Defeito)
            elif s.get('automatico'): cor = (0, 200, 0) # Verde (Automático)

            # Desenha o corpo do caminhão
            pygame.draw.circle(screen, cor, (px, py), 15)
            pygame.draw.circle(screen, (0,0,0), (px, py), 15, 2) # Borda preta
            # Desenha uma linha indicando a direção (heading)
            ex, ey = px + 22*math.cos(ang), py + 22*math.sin(ang)
            pygame.draw.line(screen, (0,0,0), (px, py), (ex, ey), 3)

            # Desenha o ID do caminhão sobre ele
            lbl = font.render(str(tid), True, (255,255,255))
            screen.blit(lbl, (px-lbl.get_width()//2, py-lbl.get_height()//2))

            # Se for o caminhão selecionado, desenha um destaque
            if tid == selected_id:
                pygame.draw.circle(screen, (0,255,255), (px, py), 20, 2)

        # Desenha o botão de adicionar caminhão
        btn_add.draw(screen)

        # Desenha a barra inferior de contexto se houver um caminhão selecionado
        if selected_id:
            pygame.draw.rect(screen, (30,30,30), (0, WIN_H-80, WIN_W, 80)) # Fundo da barra
            for b in btns_context:
                b.draw(screen)
            # Exibe informações do caminhão selecionado na barra
            s = mgr.trucks.get(selected_id, {})
            st = "AUTO" if s.get('automatico') else "MANUAL"
            if s.get('defeito'): st = "COM DEFEITO"
            info = font.render(f"ID: {selected_id} | Status: {st} | Temp: {s.get('temp',0)}C", True, (200,200,200))
            screen.blit(info, (500, WIN_H-50))

        # Atualiza a tela
        pygame.display.flip()
        # Limita a taxa de quadros a 30 FPS
        clock.tick(30)

    # Encerra o Pygame ao sair do loop
    pygame.quit()

# Ponto de entrada do script
if __name__ == '__main__':
    run()