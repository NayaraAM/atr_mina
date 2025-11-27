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

# --- AUXILIARES ---
def world_to_px(x, y):
    px = int((x - WORLD_MIN) / (WORLD_MAX - WORLD_MIN) * WIN_W)
    py = int((1 - (y - WORLD_MIN) / (WORLD_MAX - WORLD_MIN)) * WIN_H)
    return px, py

def px_to_world(px, py):
    x = int((px / WIN_W) * (WORLD_MAX - WORLD_MIN) + WORLD_MIN)
    y = int((1 - (py / WIN_H)) * (WORLD_MAX - WORLD_MIN) + WORLD_MIN)
    return x, y

def carregar_fundo():
    paths = ["interface/assets/mapa_fundo.png", "assets/mapa_fundo.png", "mapa_fundo.png"]
    for p in paths:
        if os.path.exists(p):
            try:
                img = pygame.image.load(p).convert()
                return pygame.transform.scale(img, (WIN_W, WIN_H))
            except: pass
    return None

# --- MQTT MANAGER ---
class Manager:
    def __init__(self, broker, port):
        self.trucks = {}
        self.lock = threading.Lock()
        self.client = mqtt.Client("GestaoMinaVisual")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        try:
            self.client.connect(broker, port, 60)
            self.client.loop_start()
        except:
            print("Erro conexão MQTT. Verifique se o Docker está rodando.")
            sys.exit(1)

    def on_connect(self, client, userdata, flags, rc):
        print(f"[Interface] Conectado ao Broker (RC={rc})")
        client.subscribe('/mina/caminhoes/+/posicao')
        client.subscribe('/mina/caminhoes/+/estado')

    def on_message(self, client, userdata, msg):
        try:
            topic = msg.topic.split('/')
            if len(topic) < 4: return
            tid = int(topic[2])
            kind = topic[3]
            data = json.loads(msg.payload.decode())

            with self.lock:
                if tid not in self.trucks:
                    self.trucks[tid] = {'x': 0, 'y': 0, 'ang': 0, 'temp': 0, 'defeito': False, 'automatico': False}
                
                s = self.trucks[tid]
                if kind == 'posicao':
                    s['x'], s['y'], s['ang'] = int(data.get('x',0)), int(data.get('y',0)), int(data.get('ang',0))
                elif kind == 'estado':
                    s.update({
                        'temp': int(data.get('temp',0)),
                        'defeito': bool(data.get('defeito',0)),
                        'automatico': bool(data.get('automatico',0))
                    })
        except: pass

    def send_setpoint(self, tid, x, y):
        self.client.publish(f'/mina/caminhoes/{tid}/setpoints', f'x={x},y={y}')
        print(f"[CMD] Setpoint ID {tid} -> {x}, {y}")

# --- MAIN LOOP ---
def run():
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("Mina - Visão Radar")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 12, bold=True)
    
    mgr = Manager(MQTT_BROKER, MQTT_PORT)
    bg = carregar_fundo()
    selected_id = None

    running = True
    while running:
        # Eventos
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if event.button == 1: # Clique Esq
                    clicked = False
                    with mgr.lock:
                        for tid, s in mgr.trucks.items():
                            tx, ty = world_to_px(s['x'], s['y'])
                            if (mx-tx)**2 + (my-ty)**2 <= 20**2:
                                selected_id = tid
                                clicked = True; break
                    if not clicked and selected_id:
                        wx, wy = px_to_world(mx, my)
                        mgr.send_setpoint(selected_id, wx, wy)

        # Desenhar Fundo
        if bg: screen.blit(bg, (0,0))
        else: screen.fill((50,50,50))

        # Desenhar Caminhões
        with mgr.lock: items = list(mgr.trucks.items())
        
        for tid, s in items:
            px, py = world_to_px(s['x'], s['y'])
            ang_rad = math.radians(s['ang'])
            
            # Cor
            cor = (255, 140, 0) # Laranja
            if s['defeito']: cor = (255, 0, 0)
            elif s['automatico']: cor = (0, 200, 0)

            # Desenho Radar (Bola + Linha)
            pygame.draw.circle(screen, cor, (px, py), 15)
            pygame.draw.circle(screen, (0,0,0), (px, py), 15, 2)
            end_x = px + 22 * math.cos(ang_rad) # Nariz
            end_y = py + 22 * math.sin(ang_rad)
            pygame.draw.line(screen, (0,0,0), (px, py), (end_x, end_y), 3)

            # Texto ID
            lbl = font.render(str(tid), True, (255,255,255))
            screen.blit(lbl, (px-lbl.get_width()//2, py-lbl.get_height()//2))

            # Seleção
            if tid == selected_id:
                pygame.draw.circle(screen, (0,255,255), (px, py), 20, 2)
                
            # Temp Alerta
            if s['temp'] > 95:
                t = font.render(f"{s['temp']}C", True, (255,0,0))
                screen.blit(t, (px+10, py-20))

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()

if __name__ == '__main__':
    run()