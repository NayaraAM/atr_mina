#!/usr/bin/env python3
"""
Gestão da Mina - Cliente de Terminal (CLI)

Este script é uma interface de linha de comando para o sistema de gestão da mina.
Ele se conecta ao broker MQTT, monitora o estado de todos os caminhões em tempo real
e permite que o operador envie comandos básicos para eles (criar, mudar modo, definir
setpoint, simular falha). É uma alternativa leve à interface gráfica (Pygame).

Funcionalidades:
- Monitoramento em tempo real de posição, temperatura e estado (auto/manual/defeito)
  de todos os caminhões.
- Criação dinâmica de novos caminhões (publicando em /mina/gerente/add_truck).
- Envio de setpoints de navegação para caminhões específicos.
- Troca de modo de operação (Manual/Automático).
- Simulação de falhas (ex: elétrica) para testar a resposta do caminhão.

Uso:
    Execute o script no terminal. Ele tentará se conectar ao broker MQTT padrão
    (localhost:1883) ou ao definido pelas variáveis de ambiente MQTT_BROKER e MQTT_PORT.
    Um menu interativo será exibido, atualizado a cada segundo com o estado dos caminhões.

Variáveis de Ambiente:
- MQTT_BROKER (opcional): Endereço do broker MQTT (padrão: "localhost").
- MQTT_PORT (opcional): Porta do broker MQTT (padrão: 1883).

Dependências:
- paho-mqtt: Biblioteca cliente MQTT para Python.
"""

import os
import time
import json
import threading
import paho.mqtt.client as mqtt

# Configuração do broker MQTT via variáveis de ambiente
MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))

class Manager:
    """
    Classe principal que gerencia a conexão MQTT e o estado dos caminhões.
    """
    def __init__(self, broker, port):
        # Dicionário para armazenar o estado atual de cada caminhão (ID -> estado)
        self.trucks = {}
        # Próximo ID de caminhão a ser criado (começa em 2, pois o 1 é criado pelo run_all.py)
        self.next_truck_id = 2
        # Mutex para proteger o acesso ao dicionário de caminhões (thread-safe)
        self.lock = threading.Lock()

        # Inicialização do cliente MQTT (compatibilidade com Paho v1 e v2)
        try:
            # Tenta a nova API (v2)
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "GestaoCLI")
        except:
            # Fallback para a API antiga (v1)
            self.client = mqtt.Client(client_id="GestaoCLI")

        # Define os callbacks para eventos de conexão e mensagem
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        print(f"[MQTT] Conectando ao broker {broker}:{port}...")
        # Conecta ao broker (bloqueante, com timeout de 60s)
        self.client.connect(broker, port, 60)
        # Inicia o loop de processamento de rede do cliente MQTT em uma thread separada
        self.client.loop_start()

    # -------------------------------------------------------
    # MQTT CALLBACKS
    # -------------------------------------------------------
    def on_connect(self, client, userdata, flags, rc):
        """
        Callback chamado quando a conexão com o broker é estabelecida.
        """
        print(f"[MQTT] Conectado (rc={rc})")
        # Assina os tópicos para receber atualizações de posição e estado de TODOS os caminhões
        client.subscribe("/mina/caminhoes/+/posicao")
        client.subscribe("/mina/caminhoes/+/estado")
        # Assina o tópico de confirmação de criação de caminhão (opcional, para debug)
        client.subscribe("/mina/gerente/add_truck/ack")

    def on_message(self, client, userdata, msg):
        """
        Callback chamado quando uma mensagem é recebida nos tópicos assinados.
        """
        topic = msg.topic.split("/")
        payload = msg.payload.decode()

        # Se for um ACK do spawner (criação de caminhão), apenas imprime
        if "add_truck/ack" in msg.topic:
            print(f"[Spawner ACK] {payload}")
            return

        # Verifica se o formato do tópico é válido (/mina/caminhoes/{id}/{tipo})
        if len(topic) < 4:
            return

        # Extrai o ID do caminhão e o tipo de mensagem (posicao ou estado)
        tid = int(topic[2])
        kind = topic[3]

        # Tenta fazer o parse do payload JSON
        try:
            data = json.loads(payload)
        except:
            data = {} # Payload inválido

        # Bloqueia o mutex para atualizar o dicionário de caminhões com segurança
        with self.lock:
            # Se o caminhão ainda não existe, cria uma entrada para ele com valores padrão
            if tid not in self.trucks:
                self.trucks[tid] = {
                    "x": int(data.get("x", 100)),
                    "y": int(data.get("y", 100)),
                    "ang": int(data.get("ang", 0)),
                    "temp": int(data.get("temp", 0)),
                    "defeito": bool(data.get("defeito", False)),
                    "automatico": bool(data.get("automatico", False))
                }

            s = self.trucks[tid] # Referência ao estado do caminhão

            # Atualiza os dados com base no tipo de mensagem recebida
            if kind == "posicao":
                s.update({
                    "x": int(data.get("x", s["x"])),
                    "y": int(data.get("y", s["y"])),
                    "ang": int(data.get("ang", s["ang"]))
                })

            elif kind == "estado":
                s.update({
                    "temp": int(data.get("temp", s["temp"])),
                    "defeito": bool(data.get("defeito", s["defeito"])),
                    "automatico": bool(data.get("automatico", s["automatico"]))
                })

    # -------------------------------------------------------
    # COMANDOS AO CAMINHÃO
    # -------------------------------------------------------

    def send_cmd(self, tid, cmd):
        """Envia um comando genérico para um caminhão específico."""
        topic = f"/mina/caminhoes/{tid}/comandos"
        self.client.publish(topic, cmd)
        print(f"[CMD] Enviado para {tid}: {cmd}")

    def send_setpoint(self, tid, x, y):
        """Envia um novo setpoint (destino) para um caminhão."""
        topic = f"/mina/caminhoes/{tid}/setpoints"
        self.client.publish(topic, f"x={x},y={y}")
        print(f"[SETPOINT] Caminhão {tid} -> ({x}, {y})")

    def spawn_truck(self):
        """
        Solicita a criação de um novo caminhão.
        Publica uma mensagem no tópico do gerente, incluindo a rota padrão.
        """
        tid = self.next_truck_id

        # Publica a solicitação para o spawner (run_all.py)
        msg = f"id={tid},route=routes/example.route"
        self.client.publish("/mina/gerente/add_truck", msg)
        print(f"[GERENTE] Solicitação de criação do caminhão {tid} enviada.")

        # Adiciona o caminhão visualmente na lista (será atualizado quando conectar)
        with self.lock:
            self.trucks[tid] = {
                "x": 100, "y": 100, "ang": 0,
                "temp": 0, "defeito": False, "automatico": False
            }

        # Envia o conteúdo da rota para o novo caminhão via MQTT
        # (O C++ espera a rota no tópico /mina/caminhoes/{tid}/route)
        try:
            path = "routes/example.route"
            if os.path.exists(path):
                with open(path) as f:
                    route_txt = f.read()
                self.client.publish(f"/mina/caminhoes/{tid}/route", route_txt)
                print(f"[GERENTE] Conteúdo da rota enviado para caminhão {tid}.")
            else:
                print("[ERRO] Arquivo de rota não existe.")
        except Exception as e:
            print("[ERRO] Falha ao enviar rota:", e)

        self.next_truck_id += 1

    # -------------------------------------------------------
    # EXIBIR ESTADO NA TELA
    # -------------------------------------------------------
    def print_state(self):
        """Imprime o estado atual de todos os caminhões e o menu de opções."""
        os.system("clear") # Limpa a tela do terminal (Linux/macOS)
        print("=== SISTEMA DE GESTÃO DA MINA (CLI) ===\n")

        with self.lock:
            if not self.trucks:
                print("Nenhum caminhão conectado.")
                return

            # Imprime o estado de cada caminhão ordenado pelo ID
            for tid, s in sorted(self.trucks.items()):
                status = "AUTO" if s["automatico"] else "MANUAL"
                if s["defeito"]:
                    status = "DEFEITO!" # Defeito tem prioridade na exibição

                print(f"ID {tid}: pos=({s['x']},{s['y']}) ang={s['ang']} temp={s['temp']} | {status}")

        # Imprime o menu de comandos
        print("\nComandos:")
        print("[1] Adicionar caminhão")
        print("[2] Enviar setpoint")
        print("[3] Modo manual")
        print("[4] Modo automático")
        print("[5] Causar falha elétrica")
        print("[0] Sair")


# -------------------------------------------------------
# LOOP INTERATIVO
# -------------------------------------------------------

def main():
    """Função principal do script."""
    mgr = Manager(MQTT_BROKER, MQTT_PORT)

    # Loop principal: atualiza a tela e lê a entrada do usuário
    while True:
        time.sleep(1) # Atualiza a cada 1 segundo
        mgr.print_state()

        # Lê a opção do usuário com um pequeno timeout (simulado pelo sleep acima)
        op = input("\nEscolha: ").strip()

        if op == "0":
            print("Encerrando...")
            return # Sai do loop e termina o programa

        elif op == "1":
            mgr.spawn_truck()

        elif op == "2":
            try:
                tid = int(input("ID: "))
                x = int(input("X: "))
                y = int(input("Y: "))
                mgr.send_setpoint(tid, x, y)
            except ValueError: print("Entrada inválida.")

        elif op == "3":
            try:
                tid = int(input("ID: "))
                mgr.send_cmd(tid, "c_man")
            except ValueError: print("Entrada inválida.")

        elif op == "4":
            try:
                tid = int(input("ID: "))
                mgr.send_cmd(tid, "c_automatico")
            except ValueError: print("Entrada inválida.")

        elif op == "5":
            try:
                tid = int(input("ID: "))
                # Publica diretamente no tópico de simulação de defeito
                mgr.client.publish(f"/mina/caminhoes/{tid}/sim/defeito", "eletrica=1")
            except ValueError: print("Entrada inválida.")

        else:
            # Se nenhuma opção válida foi escolhida, apenas continua o loop (atualiza a tela)
            pass

if __name__ == "__main__":
    main()