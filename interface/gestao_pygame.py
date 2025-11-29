#!/usr/bin/env python3
import os
import sys
import time
import json
import threading
import math
import pygame
import paho.mqtt.client as mqtt

# --- CONFIGURAÇÕES ---
MQTT_BROKER = os.environ.get('MQTT_BROKER', 'localhost')
MQTT_PORT = int(os.environ.get('MQTT_PORT', '1883'))
WIN_W, WIN_H = 1000, 1000
WORLD_MIN, WORLD_MAX = 0, 1000

# --- CLASSE BOTÃO ---
class Button:
    def __init__(self, x, y, w, h, text, color, action_callback, param=None):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.color = color
        self.action = action_callback
        self.param = param
        self.font = pygame.font.SysFont("Arial", 14, bold=True)

    def draw(self, screen):
        # Sombra e Corpo
        pygame.draw.rect(screen, (50, 50, 50), (self.rect.x+2, self.rect.y+2, self.rect.w, self.rect.h), border_radius=5)
        pygame.draw.rect(screen, self.color, self.rect, border_radius=5)
        pygame.draw.rect(screen, (255, 255, 255), self.rect, 2, border_radius=5)
        # Texto Centralizado
        lbl = self.font.render(self.text, True, (255, 255, 255))
        screen.blit(lbl, (self.rect.centerx - lbl.get_width()//2, self.rect.centery - lbl.get_height()//2))

    def check_click(self, pos):
        if self.rect.collidepoint(pos):
            if self.param: self.action(self.param)
            else: self.action()
            return True
        return False

# --- MQTT MANAGER ---
class Manager:
    def __init__(self, broker, port):
        self.trucks = {}
        self.next_truck_id = 2 # Começa do 2, pois o 1 já nasce com o Docker
        self.lock = threading.Lock()
        
        # --- CORREÇÃO AQUI (Versão 2.0+) ---
        # Especificamos CallbackAPIVersion.VERSION1 para manter compatibilidade com o código atual
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "GestaoMinaVisual")
        
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        try:
            self.client.connect(broker, port, 60)
            self.client.loop_start()
        except:
            print("Erro conexão MQTT. Verifique se o Docker está rodando.")
            sys.exit(1)

    def on_connect(self, client, userdata, flags, rc):
        print(f"[Interface] Conectado (RC={rc})")
        client.subscribe('/mina/caminhoes/+/posicao')
        client.subscribe('/mina/caminhoes/+/estado')
        # Inscreve no ack do spawner para confirmar criação
        client.subscribe('/mina/gerente/add_truck/ack')

    def on_message(self, client, userdata, msg):
        try:
            topic = msg.topic.split('/')
            payload = msg.payload.decode()
            
            # Ack de criação de caminhão
            if "add_truck/ack" in topic:
                print(f"[Spawner] {payload}")
                return

            # Dados de Caminhão
            if len(topic) < 4: return
            tid = int(topic[2])
            kind = topic[3]
            data = json.loads(payload)

            with self.lock:
                if tid not in self.trucks:
                    self.trucks[tid] = {'x': 0, 'y': 0, 'ang': 0, 'temp': 0, 'defeito': False, 'automatico': False}
                s = self.trucks[tid]
                if kind == 'posicao':
                    s.update({'x': int(data.get('x',0)), 'y': int(data.get('y',0)), 'ang': int(data.get('ang',0))})
                elif kind == 'estado':
                    s.update({'temp': int(data.get('temp',0)), 'defeito': bool(data.get('defeito',0)), 'automatico': bool(data.get('automatico',0))})
        except: pass

    # --- COMANDOS ---
    def send_cmd(self, params):
        # params = (tid, payload, suffix)paw
        tid, payload, suffix = params
        topic = f'/mina/caminhoes/{tid}{suffix}'
        self.client.publish(topic, payload)
        print(f"[CMD] ID {tid} -> {payload}")

    def send_setpoint(self, tid, x, y):
        self.client.publish(f'/mina/caminhoes/{tid}/setpoints', f'x={x},y={y}')
        print(f"[CMD] Setpoint ID {tid} -> {x}, {y}")

    def spawn_truck(self):
        # Envia comando para o C++ criar um novo caminhão
        msg = f"id={self.next_truck_id},route=routes/example.route"
        self.client.publish("/mina/gerente/add_truck", msg)
        print(f"[GERENTE] Solicitando novo caminhão ID {self.next_truck_id}...")

        # Cria o registro visual imediatamente na interface
        self.trucks[self.next_truck_id] = {
            'x': 100, 'y': 100, 'ang': 0,
            'temp': 0, 'defeito': False, 'automatico': False
        }

        self.next_truck_id += 1

# --- FUNÇÕES VISUAIS ---
def world_to_px(x, y):
    px = int((x - WORLD_MIN) / (WORLD_MAX - WORLD_MIN) * WIN_W)
    py = int((y - WORLD_MIN) / (WORLD_MAX - WORLD_MIN) * WIN_H)
    return px, py

def px_to_world(px, py):
    x = int((px / WIN_W) * (WORLD_MAX - WORLD_MIN) + WORLD_MIN)
    y = int((1 - (py / WIN_H)) * (WORLD_MAX - WORLD_MIN) + WORLD_MIN)
    return x, y

def carregar_fundo():
    # Tenta vários caminhos possíveis para evitar erro de 'not found'
    paths = ["interface/assets/mapa_fundo.png", "assets/mapa_fundo.png", "mapa_fundo.png"]
    for p in paths:
        if os.path.exists(p):
            try: return pygame.image.load(p).convert()
            except: pass
    return None

# --- LOOP PRINCIPAL ---
def run():
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("Gestão da Mina - Controle Total")
    clock = pygame.time.Clock()
    
    mgr = Manager(MQTT_BROKER, MQTT_PORT)
    bg_img = carregar_fundo()
    if bg_img: bg_img = pygame.transform.scale(bg_img, (WIN_W, WIN_H))

    selected_id = None

    # Botão Global (Sempre visível no topo)
    btn_add = Button(10, 10, 180, 40, "+ NOVO CAMINHÃO", (0, 100, 0), mgr.spawn_truck)

    running = True
    while running:
        # Definir Botões de Contexto (Só aparecem quando seleciona caminhão)
        btns_context = []
        if selected_id is not None:
            Y_BAR = WIN_H - 60
            btns_context = [
                Button(20,  Y_BAR, 100, 40, "MANUAL",   (200, 140, 0), mgr.send_cmd, (selected_id, "c_man", "/comandos")),
                Button(130, Y_BAR, 100, 40, "AUTO",     (0, 180, 0),   mgr.send_cmd, (selected_id, "c_automatico", "/comandos")),
                Button(240, Y_BAR, 100, 40, "REARMAR",  (0, 100, 200), mgr.send_cmd, (selected_id, "c_rearme", "/comandos")),
                Button(350, Y_BAR, 120, 40, "CAUSAR FALHA", (200, 50, 50), mgr.send_cmd, (selected_id, "eletrica=1", "/sim/defeito"))
            ]

        # EVENTOS
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if event.button == 1:
                    # 1. Checa Botão Global
                    if btn_add.check_click((mx, my)): continue

                    # 2. Checa Botões de Contexto
                    clicked_ui = False
                    for b in btns_context:
                        if b.check_click((mx, my)): 
                            clicked_ui = True
                            break
                    if clicked_ui: continue

                    # 3. Checa Seleção de Caminhão
                    clicked_truck = False
                    with mgr.lock:
                        for tid, s in mgr.trucks.items():
                            tx, ty = world_to_px(s['x'], s['y'])
                            if (mx-tx)**2 + (my-ty)**2 <= 20**2:
                                selected_id = tid
                                clicked_truck = True
                                break
                    
                    # 4. Envia Setpoint (Se clicou no mapa vazio)
                    if not clicked_truck and selected_id and my < WIN_H - 80:
                        wx, wy = px_to_world(mx, my)
                        mgr.send_setpoint(selected_id, wx, wy)

        # DESENHO
        if bg_img: screen.blit(bg_img, (0,0))
        else: screen.fill((50,50,50))

        # Desenhar Caminhões
        with mgr.lock: items = list(mgr.trucks.items())
        for tid, s in items:
            px, py = world_to_px(s['x'], s['y'])
            ang = math.radians(s['ang'])
            cor = (255, 140, 0)
            if s['defeito']: cor = (255, 0, 0)
            elif s['automatico']: cor = (0, 200, 0)

            # Bola e Radar
            pygame.draw.circle(screen, cor, (px, py), 15)
            pygame.draw.circle(screen, (0,0,0), (px, py), 15, 2)
            ex, ey = px + 22*math.cos(ang), py + 22*math.sin(ang)
            pygame.draw.line(screen, (0,0,0), (px, py), (ex, ey), 3)

            # ID
            font = pygame.font.SysFont("Arial", 12, bold=True)
            lbl = font.render(str(tid), True, (255,255,255))
            screen.blit(lbl, (px-lbl.get_width()//2, py-lbl.get_height()//2))

            # Seleção
            if tid == selected_id:
                pygame.draw.circle(screen, (0,255,255), (px, py), 20, 2)

        # Desenhar UI
        btn_add.draw(screen) # Botão de adicionar sempre visível

        # Barra Inferior e Botões de Contexto
        if selected_id:
            pygame.draw.rect(screen, (30,30,30), (0, WIN_H-80, WIN_W, 80))
            for b in btns_context: b.draw(screen)
            
            # Texto Status
            s = mgr.trucks.get(selected_id, {})
            st = "AUTO" if s.get('automatico') else "MANUAL"
            if s.get('defeito'): st = "COM DEFEITO"
            info = font.render(f"ID: {selected_id} | Status: {st} | Temp: {s.get('temp',0)}C", True, (200,200,200))
            screen.blit(info, (500, WIN_H-50))

        pygame.display.flip()
        clock.tick(30)
    pygame.quit()

if __name__ == '__main__':
    run()