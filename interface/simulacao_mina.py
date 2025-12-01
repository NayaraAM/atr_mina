#!/usr/bin/env python3
"""
Simulador de Caminhão de Mineração - interface/simulacao_mina.py

Finalidade:
Este script atua como um simulador "gêmeo digital" do caminhão. Ele implementa
uma física simplificada para gerar dados de sensores (posição, velocidade,
temperatura, ângulo) e responder aos comandos dos atuadores (aceleração, direção).
Serve para testar o sistema de controle e monitoramento sem a necessidade de um
hardware real.

Funcionalidades Principais:
1.  Simulação Física (physics_step):
    - Calcula a nova velocidade baseada na aceleração comandada e na inércia.
    - Calcula a nova posição (X, Y) e ângulo baseados na velocidade e direção.
    - Simula o aquecimento do motor baseado na velocidade e em falhas.
    - Responde a comandos de injeção de falhas (elétrica/hidráulica).

2.  Interface MQTT (Loop Principal):
    - Publica periodicamente (5Hz) o estado simulado no tópico /sensores.
    - Assina o tópico /atuadores para receber os comandos do controlador (C++).
    - Assina o tópico /sim/defeito para receber injeções de falha do painel.
    - Assina o tópico /route para receber o arquivo de rota (para visualização/debug).

3.  Comandos de Terminal:
    - Permite enviar arquivos de rota manualmente via stdin (comando 'sendroute').
    - Permite encerrar a simulação (comando 'exit').

Arquitetura:
-   Usa `paho.mqtt.client` para comunicação.
-   Usa `threading` para rodar a física e a publicação em paralelo com a leitura do stdin.
-   Usa `json` para formatar as mensagens de telemetria.
"""

import time
import json
import threading
import random
import sys
import math
from datetime import datetime
import paho.mqtt.client as mqtt

# Configurações
BROKER = "localhost"
TRUCK_ID = 1 # ID do caminhão simulado

# Tópicos MQTT
TOPIC_SENSORES = f"/mina/caminhoes/{TRUCK_ID}/sensores"
TOPIC_ATUADORES = f"/mina/caminhoes/{TRUCK_ID}/atuadores"
TOPIC_SIM_DEF = f"/mina/caminhoes/{TRUCK_ID}/sim/defeito"
TOPIC_ROUTE = f"/mina/caminhoes/{TRUCK_ID}/route"

# Estado interno da simulação
state = {
    'pos_x': 500.0, # Posição inicial X
    'pos_y': 500.0, # Posição inicial Y
    'ang': 0.0,     # Ângulo (graus)
    'vel': 0.0,     # Velocidade (m/s)
    'temp': 40.0,   # Temperatura inicial
    'o_acel': 0,    # Atuador de aceleração (recebido)
    'o_dir': 0,     # Atuador de direção (recebido)
    'e_auto': 1,    # Estado automático (recebido)
    'e_defeito': 0, # Estado de defeito (calculado)
    'fe': 0,        # Falha elétrica injetada
    'fh': 0,        # Falha hidráulica injetada
}

# Mutex para proteger o acesso ao estado compartilhado
lock = threading.Lock()

# ============================================================
# MQTT CALLBACKS
# ============================================================

def on_connect(client, userdata, flags, rc):
    """Callback de conexão."""
    print('[sim] conectado mqtt rc=', rc)
    client.subscribe(TOPIC_ATUADORES)
    client.subscribe(TOPIC_SIM_DEF)
    client.subscribe(TOPIC_ROUTE)

def on_message(client, userdata, msg):
    """Callback de mensagem recebida."""
    payload = msg.payload.decode(errors='ignore')
    topic = msg.topic

    with lock:
        # Processa arquivo de rota (apenas para log/debug aqui)
        if topic == TOPIC_ROUTE:
            print('[sim] received route payload (len=%d)' % len(payload))
            # Parse simplificado apenas para validar/mostrar contagem de waypoints
            wps = []
            for line in payload.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split()
                try:
                    x = float(parts[0]); y = float(parts[1]); s = float(parts[2]) if len(parts) > 2 else 0.0
                    wps.append((x,y,s))
                except Exception:
                    continue
            state['route'] = wps
            print('[sim] route has %d waypoints' % len(wps))
            return

        # Processa comandos dos atuadores vindos do controlador C++
        if topic == TOPIC_ATUADORES:
            try:
                j = json.loads(payload)
                if 'o_acel' in j: state['o_acel'] = float(j['o_acel'])
                if 'o_dir' in j: state['o_dir'] = float(j['o_dir'])
                if 'e_auto' in j: state['e_auto'] = int(j['e_auto'])
            except Exception:
                # Fallback para formato chave=valor (legado/debug)
                for part in payload.split(','):
                    if '=' in part:
                        k,v = part.split('=',1)
                        k=k.strip(); v=v.strip()
                        if k=='o_acel': state['o_acel']=float(v)
                        if k=='o_dir': state['o_dir']=float(v)
                        if k=='e_auto': state['e_auto']=int(v)

        # Processa injeção de falhas vinda do painel de controle
        elif topic == TOPIC_SIM_DEF:
            if 'clear' in payload:
                state['fe']=0; state['fh']=0; state['e_defeito']=0
                print('[sim] defeitos limpos')
            else:
                if 'eletrica' in payload:
                    state['fe'] = 1
                if 'hidraulica' in payload:
                    state['fh'] = 1
                state['e_defeito'] = 1 if (state['fe'] or state['fh']) else 0
                print('[sim] defeito atualizado fe=%d fh=%d' % (state['fe'], state['fh']))

# ============================================================
# FÍSICA DA SIMULAÇÃO
# ============================================================

def physics_step(dt=0.1):
    """Atualiza o estado físico do caminhão (velocidade, posição, temperatura)."""
    with lock:
        # Limita os comandos aos valores físicos possíveis
        a_cmd = max(-100, min(100, float(state.get('o_acel',0))))
        dir_cmd = max(-180, min(180, float(state.get('o_dir',0))))

        # 1. Dinâmica da Velocidade
        # Aceleração (simplificada): comando * constante * dt
        dv = a_cmd * 0.01 * dt
        state['vel'] += dv
        # Limites de velocidade (física)
        if state['vel'] > 5.0: state['vel'] = 5.0
        if state['vel'] < -2.0: state['vel'] = -2.0

        # 2. Dinâmica Angular
        # Taxa de giro proporcional ao comando de direção
        state['ang'] += dir_cmd * 0.1 * dt
        state['ang'] %= 360.0 # Normaliza 0-360

        # 3. Dinâmica de Posição (Cinemática)
        rad = state['ang'] * 3.14159265 / 180.0
        # X = X0 + V * cos(ang) * dt
        state['pos_x'] += state['vel'] * dt * math.cos(rad)
        # Y = Y0 + V * sin(ang) * dt
        state['pos_y'] += state['vel'] * dt * math.sin(rad)

        # 4. Dinâmica de Temperatura
        # Aquece com velocidade e falha elétrica, resfria passivamente
        temp = state['temp'] + (abs(state['vel']) * 0.05) + (state['fe'] * 0.5)
        temp -= 0.01 * dt # Resfriamento
        state['temp'] = max(20.0, min(120.0, temp))

def publish_sensors(client):
    """Publica o estado atual como dados de sensores no MQTT."""
    with lock:
        t = int(time.time() * 1000)
        # Adiciona um pequeno ruído gaussiano para realismo
        noise = lambda s: s + random.gauss(0, max(0.1, abs(s)*0.01))
        payload = {
            'timestamp_ms': t,
            'truck_id': TRUCK_ID,
            'x': round(noise(state['pos_x']),2),
            'y': round(noise(state['pos_y']),2),
            'ang': round(noise(state['ang']),2),
            'temp': round(noise(state['temp']),2),
            'fe': int(state['fe']),
            'fh': int(state['fh']),
            # Echo dos atuadores/estados para debug
            'o_acel': int(state['o_acel']),
            'o_dir': int(state['o_dir']),
            'e_auto': int(state['e_auto']),
            'e_defeito': int(state['e_defeito']),
        }
    client.publish(TOPIC_SENSORES, json.dumps(payload))

# ============================================================
# MAIN
# ============================================================

def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(BROKER, 1883, 60)
    except:
        print(f"[ERRO] Não foi possível conectar ao broker {BROKER}")
        return
    client.loop_start()

    try:
        # Thread de background para simulação física e publicação
        def publisher_loop():
            while True:
                physics_step(0.2)       # Passo de simulação
                publish_sensors(client) # Publicação
                time.sleep(0.2)         # 5 Hz

        pub_thread = threading.Thread(target=publisher_loop, daemon=True)
        pub_thread.start()

        print('[sim] Comandos de terminal:')
        print('  sendroute <file>   -> publica arquivo de rota em', TOPIC_ROUTE)
        print('  exit               -> sai')

        # Loop principal para comandos de terminal (stdin)
        while True:
            try:
                line = sys.stdin.readline()
                if not line: # EOF
                    time.sleep(0.1)
                    continue
                line = line.strip()
                if not line:
                    continue
                if line == 'exit':
                    break
                if line.startswith('sendroute '):
                    fname = line.split(' ',1)[1].strip()
                    try:
                        with open(fname,'r') as f:
                            content = f.read()
                        client.publish(TOPIC_ROUTE, content)
                        print('[sim] route published from', fname)
                    except Exception as e:
                        print('[sim] failed to read route file:', e)
                else:
                    print('[sim] comando desconhecido:', line)
            except KeyboardInterrupt:
                break
    except KeyboardInterrupt:
        pass

    client.loop_stop()
    client.disconnect()

if __name__ == '__main__':
    main()