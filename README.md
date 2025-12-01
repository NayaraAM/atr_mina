# ATR-MINA — Sistema Embarcado para Caminhão Autônomo 🚛⛏️

Este projeto implementa um sistema embarcado simulado para controle de um caminhão autônomo (AGV) utilizado em mineração.  
A arquitetura integra **C++17**, **Python (Pygame)** e **MQTT**, com execução unificada via **Docker Compose**.

---

## 📂 Arquitetura Geral

O sistema é composto por três módulos principais:

### 1) Núcleo Embarcado (C++17)
Responsável por:
- Simulação de sensores
- Filtragem (média móvel)
- Navegação automática (controlador PI/P)
- Lógica de comando (manual/automático)
- Monitoramento de falhas
- Publicação de telemetria via MQTT
- Execução concorrente com múltiplas threads

Binário:  


atr_mina --truck-id=X --route=routes/example.route


---

### 2) Interface Gráfica (Python + Pygame)
Mostra:
- Mapa da mina (fundo)
- Caminhões representados como círculos
- Direção, cor, estado, falhas
- Menu interativo com botões (manual, automático, rearmar, falha)
- Clique no mapa → envia setpoint para o caminhão

Arquivo principal:


interface/gestao_pygame.py


---

### 3) Comunicação — MQTT (Mosquitto)
- `/mina/caminhoes/<id>/posicao`  
- `/mina/caminhoes/<id>/sensores`  
- `/mina/caminhoes/<id>/estado`  
- `/mina/caminhoes/<id>/comandos`  
- `/mina/gerente/add_truck`  
- `/mina/caminhoes/<id>/route`

Cliente C++: **Eclipse Paho MQTT**  
Cliente Python: **paho-mqtt**

---

## 🚀 Execução (recomendado: Docker)

### 1) Build + Run
```bash
docker-compose up --build


Isso irá:

iniciar o Mosquitto

compilar e rodar o núcleo embarcado

disponibilizar a interface Python

2) Executar interface localmente (caso queira ver a janela sem docker)
cd interface
source venv/bin/activate   # se usar virtualenv
python3 gestao_pygame.py


Estrutura do Projeto atr_mina/
│
├── src/                   # Código C++ (núcleo embarcado)
├── include/               # Headers C++
├── interface/             # Interface gráfica Python
│   ├── gestao_pygame.py
│   ├── assets/
│   │   └── mapa_fundo.png
│   └── ...
│
├── routes/
│   └── example.route
│
├── docker-compose.yml
├── Dockerfile
├── CMakeLists.txt
└── README.md