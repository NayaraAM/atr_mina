#!/usr/bin/env python3
"""
Simulador simples para a mina.
- Publica telemetria em `/mina/caminhoes/{id}/sensores` (JSON)
- Escuta atuadores em `/mina/caminhoes/{id}/atuadores` (JSON ou string)
- Escuta comandos de defeito em `/mina/caminhoes/{id}/sim/defeito` (como o painel)

Uso: python3 interface/simulacao_mina.py
"""
import time
import json
import threading
import random
import sys
from datetime import datetime
import paho.mqtt.client as mqtt

BROKER = "localhost"
TRUCK_ID = 1

TOPIC_SENSORES = f"/mina/caminhoes/{TRUCK_ID}/sensores"
TOPIC_ATUADORES = f"/mina/caminhoes/{TRUCK_ID}/atuadores"
TOPIC_SIM_DEF = f"/mina/caminhoes/{TRUCK_ID}/sim/defeito"
TOPIC_ROUTE = f"/mina/caminhoes/{TRUCK_ID}/route"

# Estado da simulação
state = {
    'pos_x': 500.0,
    'pos_y': 500.0,
    'ang': 0.0,    # graus
    'vel': 0.0,
    'temp': 40.0,
    'o_acel': 0,
    'o_dir': 0,
    'e_auto': 1,
    'e_defeito': 0,
    'fe': 0,
    'fh': 0,
}

lock = threading.Lock()

def on_connect(client, userdata, flags, rc):
    print('[sim] conectado mqtt rc=', rc)
    client.subscribe(TOPIC_ATUADORES)
    client.subscribe(TOPIC_SIM_DEF)
    client.subscribe(TOPIC_ROUTE)

def on_message(client, userdata, msg):
    payload = msg.payload.decode(errors='ignore')
    topic = msg.topic
    with lock:
        if topic == TOPIC_ROUTE:
            # payload is text with lines 'x y [speed]'
            print('[sim] received route payload (len=%d)' % len(payload))
            # parse and store minimal route for debug/display
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
            # store for potential use (not used by physics)
            state['route'] = wps
            print('[sim] route has %d waypoints' % len(wps))
            return

        if topic == TOPIC_ATUADORES:
            # espera JSON ou chave=valor
            try:
                j = json.loads(payload)
                # atualiza controles se presentes
                if 'o_acel' in j:
                    state['o_acel'] = float(j['o_acel'])
                if 'o_dir' in j:
                    state['o_dir'] = float(j['o_dir'])
                if 'e_auto' in j:
                    state['e_auto'] = int(j['e_auto'])
            except Exception:
                # parse simples k=v,k2=v2
                for part in payload.split(','):
                    if '=' in part:
                        k,v = part.split('=',1)
                        k=k.strip(); v=v.strip()
                        if k=='o_acel': state['o_acel']=float(v)
                        if k=='o_dir': state['o_dir']=float(v)
                        if k=='e_auto': state['e_auto']=int(v)

        elif topic == TOPIC_SIM_DEF:
            # mensagens do painel: 'eletrica=1', 'hidraulica=1', 'clear'
            if 'clear' in payload:
                state['fe']=0; state['fh']=0; state['e_defeito']=0
                print('[sim] defeitos limpos')
            else:
                if 'eletrica' in payload:
                    try:
                        if '=' in payload:
                            v = int(payload.split('=')[1])
                        else:
                            v = 1
                        state['fe'] = 1 if v else 0
                    except:
                        state['fe'] = 1
                if 'hidraulica' in payload:
                    try:
                        if '=' in payload:
                            v = int(payload.split('=')[1])
                        else:
                            v = 1
                        state['fh'] = 1 if v else 0
                    except:
                        state['fh'] = 1
                state['e_defeito'] = 1 if (state['fe'] or state['fh']) else 0
                print('[sim] defeito atualizado fe=%d fh=%d' % (state['fe'], state['fh']))

def physics_step(dt=0.1):
    # integra dinâmica simples: aceleração controla velocidade, direcional altera ângulo
    with lock:
        # aceleração de comando [-100..100]
        a_cmd = max(-100, min(100, float(state.get('o_acel',0))))
        dir_cmd = max(-180, min(180, float(state.get('o_dir',0))))
        # mapa simples: aceleração -> delta vel
        dv = a_cmd * 0.01 * dt
        state['vel'] += dv
        # limit vel
        if state['vel'] > 5.0: state['vel'] = 5.0
        if state['vel'] < -2.0: state['vel'] = -2.0

        # atualização angular baseada em dir_cmd
        state['ang'] += dir_cmd * 0.1 * dt
        state['ang'] %= 360.0

        # posição
        rad = state['ang'] * 3.14159265 / 180.0
        state['pos_x'] += state['vel'] * dt * round(math.cos(rad), 6) if 'math' in globals() else state['vel'] * dt
        state['pos_y'] += state['vel'] * dt * round(math.sin(rad), 6) if 'math' in globals() else 0

        # temperatura sobe com velocidade e defeito elétrico
        temp = state['temp'] + (abs(state['vel']) * 0.05) + (state['fe'] * 0.5)
        # resfriamento passivo
        temp -= 0.01 * dt
        state['temp'] = max(20.0, min(120.0, temp))

def publish_sensors(client):
    # publica JSON com ruído
    with lock:
        t = int(time.time() * 1000)
        noise = lambda s: s + random.gauss(0, max(0.1, abs(s)*0.01))
        payload = {
            'timestamp_ms': t,
            'truck_id': TRUCK_ID,
            'pos_x': round(noise(state['pos_x']),2),
            'pos_y': round(noise(state['pos_y']),2),
            'ang': round(noise(state['ang']),2),
            'temp': round(noise(state['temp']),2),
            'fe': int(state['fe']),
            'fh': int(state['fh']),
            'o_acel': int(state['o_acel']),
            'o_dir': int(state['o_dir']),
            'e_auto': int(state['e_auto']),
            'e_defeito': int(state['e_defeito']),
        }
    client.publish(TOPIC_SENSORES, json.dumps(payload))

def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, 1883, 60)
    client.loop_start()

    try:
        # background publishing thread so we can accept simple stdin commands
        def publisher_loop():
            while True:
                physics_step(0.2)
                publish_sensors(client)
                time.sleep(0.2)

        pub_thread = threading.Thread(target=publisher_loop, daemon=True)
        pub_thread.start()

        print('[sim] comandos: \n  sendroute <file>   -> publica arquivo de rota em', TOPIC_ROUTE)
        print('  exit               -> sai')
        # simples loop de stdin para enviar rota ou sair
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
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
    import math
    main()
