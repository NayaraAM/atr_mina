#!/usr/bin/env python3
"""
Gestao da Mina - backend
- Assina tópicos MQTT `/mina/caminhoes/+/posicao` e `/mina/caminhoes/+/estado`
- Mantém posições e estados em memória
- Serve frontend e envia atualizações via Socket.IO
- Recebe requisições de setpoint do frontend e publica no tópico `/mina/caminhoes/{id}/setpoints`
"""
import os
import time
import json
import threading
import subprocess
import sys
import socket
import json
from collections import defaultdict

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import paho.mqtt.client as mqtt

# Config
MQTT_BROKER = os.environ.get('MQTT_BROKER', 'localhost')
MQTT_PORT = int(os.environ.get('MQTT_PORT', '1883'))
MQTT_KEEPALIVE = 60

app = Flask(__name__, template_folder='templates', static_folder='static')
socketio = SocketIO(app, cors_allowed_origins='*')

# In-memory store: truck_id -> state dict
trucks = defaultdict(lambda: {
    'x': None, 'y': None, 'ang': None, 'temp': None,
    'automatico': None, 'defeito': None, 'atuadores': None,
    'last_ts': None
})

MQTT_CLIENT = None

def mqtt_on_connect(client, userdata, flags, rc):
    print('[gestao] mqtt connected rc=', rc)
    # subscribe to position and estado topics for all trucks
    client.subscribe('/mina/caminhoes/+/posicao')
    client.subscribe('/mina/caminhoes/+/estado')

def try_parse_json(payload):
    try:
        return json.loads(payload)
    except Exception:
        return None

def mqtt_on_message(client, userdata, msg):
    topic = msg.topic
    pl = msg.payload.decode('utf-8', errors='ignore')
    # topic examples: /mina/caminhoes/1/posicao  or /mina/caminhoes/1/estado
    parts = topic.strip('/').split('/')
    if len(parts) < 4:
        return
    try:
        truck_id = int(parts[2])
    except Exception:
        return

    kind = parts[3]
    if kind == 'posicao':
        j = try_parse_json(pl)
        if isinstance(j, dict):
            updated = False
            if 'x' in j:
                trucks[truck_id]['x'] = int(j['x'])
                updated = True
            if 'y' in j:
                trucks[truck_id]['y'] = int(j['y'])
                updated = True
            if 'ang' in j:
                trucks[truck_id]['ang'] = int(j['ang'])
                updated = True
            if updated:
                trucks[truck_id]['last_ts'] = int(time.time() * 1000)
                # broadcast update
                socketio.emit('truck_update', {'truck_id': truck_id, 'state': trucks[truck_id]})
    elif kind == 'estado':
        j = try_parse_json(pl)
        if isinstance(j, dict):
            # copy relevant fields
            if 'x' in j: trucks[truck_id]['x'] = int(j['x'])
            if 'y' in j: trucks[truck_id]['y'] = int(j['y'])
            if 'ang' in j: trucks[truck_id]['ang'] = int(j['ang'])
            if 'temp' in j: trucks[truck_id]['temp'] = int(j['temp'])
            if 'automatico' in j: trucks[truck_id]['automatico'] = bool(int(j.get('automatico',0)))
            if 'defeito' in j: trucks[truck_id]['defeito'] = bool(int(j.get('defeito',0)))
            trucks[truck_id]['last_ts'] = int(time.time() * 1000)
            socketio.emit('truck_update', {'truck_id': truck_id, 'state': trucks[truck_id]})

def start_mqtt():
    global MQTT_CLIENT
    MQTT_CLIENT = mqtt.Client()
    MQTT_CLIENT.on_connect = mqtt_on_connect
    MQTT_CLIENT.on_message = mqtt_on_message
    try:
        MQTT_CLIENT.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
    except Exception as e:
        print('[gestao] erro conectando MQTT:', e)
        return
    MQTT_CLIENT.loop_start()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/trucks')
def api_trucks():
    # return snapshot
    snapshot = {tid: dict(state) for tid, state in trucks.items()}
    return jsonify(snapshot)


@app.route('/api/setpoint', methods=['POST'])
def api_setpoint():
    data = request.get_json(force=True)
    if not data:
        return jsonify({'error': 'payload json required'}), 400
    tid = data.get('truck_id')
    x = data.get('x')
    y = data.get('y')
    try:
        tid = int(tid)
        x = int(x)
        y = int(y)
    except Exception:
        return jsonify({'error': 'truck_id,x,y must be integers'}), 400

    topic = f'/mina/caminhoes/{tid}/setpoints'
    payload = f'x={x},y={y}'
    try:
        if MQTT_CLIENT:
            MQTT_CLIENT.publish(topic, payload)
        else:
            print('[gestao] MQTT not connected, would publish:', topic, payload)
        return jsonify({'ok': True, 'topic': topic, 'payload': payload})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@socketio.on('connect')
def on_connect():
    # send full snapshot on new client
    snapshot = {tid: dict(state) for tid, state in trucks.items()}
    socketio.emit('snapshot', snapshot)


def run_app(host='0.0.0.0', port=5005):
    # start MQTT in background thread
    t = threading.Thread(target=start_mqtt, daemon=True)
    t.start()
    # Use eventlet if available; socketio will choose automatically if installed
    print(f'[gestao] starting web server on {host}:{port} (MQTT broker {MQTT_BROKER}:{MQTT_PORT})')
    socketio.run(app, host=host, port=port)


if __name__ == '__main__':
    run_app()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestão da Mina — Versão FINAL (otimizada e estável)
---------------------------------------------------
Funções principais:
 - Assinatura MQTT dos tópicos /mina/caminhoes/+/posicao e eventos
 - Exibição dos caminhões com smoothing (trajetória e sprite)
 - Seleção de caminhões por clique ou por teclas 1..9
 - Envio de setpoint por clique no mapa
 - Envio de comandos Auto / Manual / Rearme / Stop
 - Painel lateral completo com lista, eventos e botões
 - Rotas e zonas do mapa (estático)
"""

import pygame
import paho.mqtt.client as mqtt
import threading
import json
import time
from collections import deque
import math
import os

# ============================================================
# MQTT
# ============================================================
BROKER = "localhost"
PORT = 1883

TOPIC_POSICAO = "/mina/caminhoes/+/posicao"
TOPIC_EVENTOS = "/mina/caminhoes/+/eventos"
TOPIC_SETPOINT_FMT = "/mina/caminhoes/{}/setpoints"
TOPIC_COMANDOS_FMT = "/mina/caminhoes/{}/comandos"

# ============================================================
# JANELA
# ============================================================
WIDTH, HEIGHT = 1200, 800
MAP_LEFT, MAP_TOP = 20, 20
MAP_W, MAP_H = 820, 760
MAP_RECT = pygame.Rect(MAP_LEFT, MAP_TOP, MAP_W, MAP_H)
PANEL_X = MAP_LEFT + MAP_W + 20
PANEL_W = WIDTH - PANEL_X - 20

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Gestão da Mina — Sistema ATR")
font = pygame.font.SysFont("DejaVuSans", 16)
small_font = pygame.font.SysFont("DejaVuSans", 14)
title_font = pygame.font.SysFont("DejaVuSans", 20, bold=True)
clock = pygame.time.Clock()

# ============================================================
# MUNDO (0..1000)
# ============================================================
WORLD_MIN = 0
WORLD_MAX = 1000

def world_to_map(wx, wy):
    mx = MAP_LEFT + (wx - WORLD_MIN) / (WORLD_MAX - WORLD_MIN) * MAP_W
    my = MAP_TOP + (wy - WORLD_MIN) / (WORLD_MAX - WORLD_MIN) * MAP_H
    return int(mx), int(my)

def map_to_world(mx, my):
    wx = WORLD_MIN + (mx - MAP_LEFT) / MAP_W * (WORLD_MAX - WORLD_MIN)
    wy = WORLD_MIN + (my - MAP_TOP) / MAP_H * (WORLD_MAX - WORLD_MIN)
    return max(0, min(1000, int(wx))), max(0, min(1000, int(wy)))

# ============================================================
# CAMINHÕES
# ============================================================
caminhoes = {}
caminhoes_lock = threading.Lock()

PALETTE = [
    (0,200,0), (0,120,255), (255,140,0), (180,0,200),
    (200,200,0), (0,200,200), (200,80,80), (100,220,100)
]

def get_color(cid):
    return PALETTE[(cid - 1) % len(PALETTE)]

# ============================================================
# SPRITE DE CAMINHÃO
# ============================================================
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
SPRITE_PATH = os.path.join(ASSETS_DIR, "truck.png")
USE_SPRITE = False
SPRITE = None
SPRITE_SIZE = (40, 40)

if os.path.isfile(SPRITE_PATH):
    try:
        SPRITE = pygame.transform.smoothscale(
            pygame.image.load(SPRITE_PATH).convert_alpha(),
            SPRITE_SIZE
        )
        USE_SPRITE = True
    except:
        USE_SPRITE = False

def draw_truck(surface, x, y, ang, color):
    if USE_SPRITE:
        img = pygame.transform.rotate(SPRITE, -ang)
        r = img.get_rect(center=(x,y))
        surface.blit(img, r)
    else:
        pygame.draw.circle(surface, color, (x,y), 14)
        pygame.draw.circle(surface, (255,255,255), (x,y), 14, 2)

# ============================================================
# MQTT CALLBACKS
# ============================================================
mqtt_client = mqtt.Client()

def mqtt_on_connect(client, userdata, flags, rc):
    global mqtt_connected
    print("[MQTT] Conectado rc=", rc)
    mqtt_connected = True
    client.subscribe(TOPIC_POSICAO)
    client.subscribe(TOPIC_EVENTOS)
    client.subscribe("/mina/caminhoes/+/sensores")

def mqtt_on_message(client, userdata, msg):
    parts = msg.topic.split("/")
    # ['', 'mina', 'caminhoes', ID, tipo]
    try:
        cid = int(parts[3])
    except:
        return

    with caminhoes_lock:
        if cid not in caminhoes:
            caminhoes[cid] = {
                "x": 0, "y": 0, "ang": 0,
                "disp_x": 0.0, "disp_y": 0.0,
                "trail": deque(maxlen=150),
                "events": deque(maxlen=40),
                "color": get_color(cid)
            }

    if parts[-1] == "posicao":
        try:
            data = json.loads(msg.payload.decode())
            x = int(data["x"])
            y = int(data["y"])
            ang = int(data["ang"])
        except:
            return

        with caminhoes_lock:
            t = caminhoes[cid]
            t["x"], t["y"], t["ang"] = x, y, ang
            t["trail"].append((x,y))

    elif parts[-1] == "eventos":
        try:
            data = json.loads(msg.payload.decode())
            txt = json.dumps(data)
        except:
            txt = msg.payload.decode()

        with caminhoes_lock:
            caminhoes[cid]["events"].appendleft(txt)

    elif parts[-1] == "sensores":
        try:
            data = json.loads(payload)
            x = int(data.get("x", 0))
            y = int(data.get("y", 0))
            ang = int(data.get("ang", 0))
            ts = int(time.time() * 1000)
        except:
            return

        with caminhoes_lock:
            if cid not in caminhoes:
                caminhoes[cid] = {
                    "x": x, "y": y, "ang": ang, "ts": ts,
                    "trail": deque(maxlen=200),
                    "events": deque(maxlen=50),
                    "color": get_color_for_id(cid),
                    "selected": False,
                    "disp_x": float(x), "disp_y": float(y)
                }
            truck = caminhoes[cid]
            truck["x"] = x
            truck["y"] = y
            truck["ang"] = ang
            truck["ts"] = ts
            truck["trail"].append((x, y, ts))


# =========================
# INICIAR MQTT
# =========================
def start_mqtt():
    mqtt_client.on_connect = mqtt_on_connect
    mqtt_client.on_message = mqtt_on_message
    mqtt_client.connect(BROKER, PORT, 60)
    mqtt_client.loop_start()

start_mqtt()

# ============================================================
# PUBLICAÇÃO
# ============================================================
def publicar_setpoint(cid, wx, wy):
    topic = TOPIC_SETPOINT_FMT.format(cid)
    payload = f"x={wx},y={wy}"
    mqtt_client.publish(topic, payload)

def publicar_comando(cid, cmd):
    topic = TOPIC_COMANDOS_FMT.format(cid)
    mqtt_client.publish(topic, cmd)

# ============================================================
# SELEÇÃO
# ============================================================
selected_id = None

def select_by_click(px, py):
    with caminhoes_lock:
        for cid, t in caminhoes.items():
            cx, cy = world_to_map(t["x"], t["y"])
            if math.hypot(px - cx, py - cy) < 22:
                return cid
    return None

# ============================================================
# MAPA (rotas e zonas)
# ============================================================
ROUTES = [
    [(50,200),(200,200),(400,300),(700,350),(900,350)],
]

ZONES = [
    {"name":"Carga","rect":(80,80,150,130)},
    {"name":"Descarga","rect":(760,560,160,140)},
]

def draw_map(surface):
    pygame.draw.rect(surface, (50,50,50), MAP_RECT)

    for x in range(MAP_LEFT, MAP_LEFT+MAP_W, 50):
        pygame.draw.line(surface, (70,70,70), (x,MAP_TOP), (x,MAP_TOP+MAP_H))
    for y in range(MAP_TOP, MAP_TOP+MAP_H, 50):
        pygame.draw.line(surface, (70,70,70), (MAP_LEFT,y), (MAP_LEFT+MAP_W,y))

    for zone in ZONES:
        rx,ry,rw,rh = zone["rect"]
        x1,y1 = world_to_map(rx,ry)
        x2,y2 = world_to_map(rx+rw, ry+rh)
        rect = pygame.Rect(x1,y1,x2-x1,y2-y1)
        pygame.draw.rect(surface, (200,80,80,100), rect)
        lbl = small_font.render(zone["name"], True, (255,255,255))
        surface.blit(lbl, (rect.x+6, rect.y+6))

    for route in ROUTES:
        pts = [world_to_map(x,y) for (x,y) in route]
        pygame.draw.lines(surface, (120,120,200), False, pts, 3)

# ============================================================
# UI — Painel
# ============================================================
BUTTONS = []

def init_buttons():
    bx = PANEL_X + 10
    by = MAP_TOP + 160
    bw = PANEL_W - 20
    h = 32
    gap = 6

    labels = [
        ("AUTO",  lambda: send_cmd("auto")),
        ("MANUAL",lambda: send_cmd("man")),
        ("REARME",lambda: send_cmd("rearme")),
        ("STOP",  lambda: send_cmd("stop")),
        ("ADD TRUCK", lambda: add_truck_default()),
    ]

    for i,(lbl,func) in enumerate(labels):
        r = pygame.Rect(bx,by+i*(h+gap),bw,h)
        BUTTONS.append({"label":lbl,"rect":r,"action":func})

def send_cmd(cmd):
    if selected_id:
        publicar_comando(selected_id, cmd)


def add_truck_default():
    # decide next id and use default route
    with caminhoes_lock:
        ids = sorted(caminhoes.keys())
    try:
        next_id = (max(ids) + 1) if ids else 1
    except Exception:
        next_id = 1
    # send command directly over UNIX socket to run_all
    socket_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "run_all.sock"))
    route = "routes/example.route"
    cmd = f"addtruck {next_id} {route}\n"
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(socket_path)
        s.sendall(cmd.encode())
        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n" in chunk:
                break
        s.close()
        try:
            resp = json.loads(data.decode())
            # display a short message in the UI
            global last_ipc_msg, last_ipc_ts
            last_ipc_msg = json.dumps(resp)
            last_ipc_ts = time.time()
            print("ipc response:", resp)
        except Exception:
            print("ipc response (raw):", data.decode())
    except Exception as e:
        print("failed to send ipc addtruck:", e)
        try:
            s.close()
        except Exception:
            pass

def draw_buttons(surface):
    for b in BUTTONS:
        pygame.draw.rect(surface, (40,40,40), b["rect"])
        pygame.draw.rect(surface, (120,120,120), b["rect"], 2)
        txt = font.render(b["label"], True, (240,240,240))
        surface.blit(txt, (b["rect"].x+8, b["rect"].y+4))

def draw_panel():
    pygame.draw.rect(screen, (25,25,25), (PANEL_X, MAP_TOP, PANEL_W, MAP_H))

    screen.blit(title_font.render("Gestão da Mina",True,(220,220,220)),
                (PANEL_X+10, MAP_TOP+10))

    screen.blit(font.render("Caminhões:",True,(200,200,200)),
                (PANEL_X+10, MAP_TOP+60))

    with caminhoes_lock:
        ids = sorted(caminhoes.keys())
        y = MAP_TOP + 90
        for cid in ids:
            t = caminhoes[cid]
            col = t["color"]
            pygame.draw.rect(screen, col, (PANEL_X+10, y+4, 12,12))
            sel = " <" if cid == selected_id else ""
            text = font.render(f"{cid}  x={t['x']} y={t['y']}{sel}", True,(230,230,230))
            screen.blit(text,(PANEL_X+30, y))
            y += 26

    screen.blit(font.render("Eventos:",True,(200,200,200)),
                (PANEL_X+10, MAP_TOP+260))

    with caminhoes_lock:
        evs = caminhoes[selected_id]["events"] if selected_id in caminhoes else []

    y = MAP_TOP + 290
    for ev in list(evs)[:12]:
        screen.blit(small_font.render(ev,True,(180,180,180)),
                    (PANEL_X+10, y))
        y += 18

    draw_buttons(screen)

# ============================================================
# DESENHO DOS CAMINHÕES
# ============================================================
def draw_trucks():
    smoothing = 0.15

    with caminhoes_lock:
        for cid,t in caminhoes.items():
            t["disp_x"] += (t["x"] - t["disp_x"]) * smoothing
            t["disp_y"] += (t["y"] - t["disp_y"]) * smoothing

            cx, cy = world_to_map(t["disp_x"], t["disp_y"])
            draw_truck(screen, cx, cy, t["ang"], t["color"])
            lbl = small_font.render(f"{cid}", True,(255,255,255))
            screen.blit(lbl, (cx+12,cy-12))

            pts = [world_to_map(x,y) for (x,y) in t["trail"]]
            if len(pts) > 2:
                pygame.draw.lines(screen, (100,100,100), False, pts, 2)

# ============================================================
# MAIN
# ============================================================
init_buttons()

running = True
last_ipc_msg = None
last_ipc_ts = 0
while running:
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            running = False

        elif ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_q:
                running = False
            if pygame.K_1 <= ev.key <= pygame.K_9:
                num = ev.key - pygame.K_0
                if num in caminhoes:
                    selected_id = num

        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            mx, my = ev.pos

            for b in BUTTONS:
                if b["rect"].collidepoint(mx,my):
                    b["action"]()
                    break
            else:
                if MAP_RECT.collidepoint(mx,my):
                    sel = select_by_click(mx,my)
                    if sel:
                        selected_id = sel
                    else:
                        if selected_id:
                            wx,wy = map_to_world(mx,my)
                            publicar_setpoint(selected_id, wx, wy)

    screen.fill((15,15,15))
    draw_map(screen)
    draw_trucks()
    draw_panel()
    # show IPC message briefly
    if last_ipc_msg and (time.time() - last_ipc_ts) < 5.0:
        txt = small_font.render(last_ipc_msg, True, (255,255,0))
        screen.blit(txt, (PANEL_X+10, MAP_TOP+MAP_H-24))

    pygame.display.flip()
    clock.tick(30)

mqtt_client.loop_stop()
pygame.quit()
