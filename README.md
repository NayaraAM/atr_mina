# Mina_ATR_V2# ATR MINA — Sistema de Automação em Tempo Real
Trabalho Final — Automação em Tempo Real  
Engenharia de Controle e Automação — UFMG  

Este projeto implementa a arquitetura de sensores, lógica, falhas, navegação e coleta de dados
para um caminhão de mina (AGV simplificado), incluindo suporte completo a **MQTT** para comunicação
com:


O projeto é totalmente modular, compilável por **CMake**, executável via **Docker**, e utiliza:


# 📁 Estrutura do Projeto
atr_mina/
│
├── CMakeLists.txt
├── Dockerfile
├── README.md
│
├── include/
│ ├── Autuadores.h
│ ├── BufferCircular.h
│ ├── MqttClient.h
│ ├── SensorData.h
│ ├── Sensores.h
│ └── Threads.h
│
├── src/
│ ├── Autuadores.cpp (definido dentro de main.cpp)
│ ├── BufferCircular.cpp (header-only)
│ ├── MqttClient.cpp
│ ├── SensorData.cpp
│ ├── Sensores.cpp
│ ├── Threads.cpp
│ └── main.cpp
│
└── logs/
└── logs_caminhao.txt

## Build

```markdown
# Mina_ATR_V2 — ATR MINA (Sistema de Automação em Tempo Real)
Trabalho Final — Automação em Tempo Real
Engenharia de Controle e Automação — UFMG

Descrição
---------
Projeto que implementa a arquitetura acadêmica simplificada de um caminhão autônomo de mina.
O foco é a implementação das tarefas críticas em tempo real (sensores, lógica, falhas,
navegação e coleta de dados) e a integração por buffers circulares e mensagens MQTT.

Etapas do desenvolvimento
-------------------------
- **Etapa 1 (inicial — obrigatória para a entrega parcial):** definição da arquitetura
	e implementação das tarefas centrais (em azul na Figura 1 do enunciado). Nesta etapa
	implementamos o `BufferCircular` (200 posições), as threads de tratamento de sensores,
	lógica de comando, monitoramento de falhas, controle de navegação e coletor de dados.
	A comunicação com um broker MQTT é opcional para execução — existe suporte a modo
	`mock` para rodar sem broker.
- **Etapa 2 (complementar / conclusão):** interfaces de Gestão da Mina e Simulação (cliente
	e servidor MQTT, GUIs). Estas interfaces estão disponíveis em `interface/` e são
	implementadas em Python (p.ex. `interface/gestao_mina.py`), mas sua execução não é
	obrigatória para validar a Etapa 1.

Principais características
-------------------------
- `BufferCircular` configurado com capacidade instanciada em `main.cpp` (ex.: 200 posições).
- Buffer thread-safe usando `std::mutex` + `std::condition_variable` com operações
	de `push`, `try_pop` e `pop_wait_for` (bloqueante com timeout).
- Tarefas implementadas em `src/Threads.cpp`:
	- `TratamentoSensores_thread`
	- `LogicaDeComando_thread`
	- `MonitoramentoDeFalhas_thread`
	- `ControleDeNavegacao_thread`
	- `ColetorDeDados_thread`
- Gravação de logs em `logs/logs_caminhao.txt` (formato Tabela 3) e CSV detalhado
	em `logs/logs_caminhao_detailed.csv`.

# Estrutura do Projeto
```
atr_mina/
├── CMakeLists.txt
├── Dockerfile
├── README.md
├── include/        # headers (Autuadores, BufferCircular, MqttClient, etc.)
├── src/            # implementação C++ (threads, main, mqtt wrapper)
├── interface/      # GUIs e clientes (Python) – Etapa 2
└── logs/           # arquivos de saída (gerados em tempo de execução)
```

Build
-----
Para compilar o projeto (CMake):

```bash
mkdir -p build && cd build
cmake ..
make -j$(nproc)
```

Execução (Etapa 1 — modo recomendado para avaliação)
--------------------------------------------------
- Executar sem broker (modo `mock`) — útil para avaliação da Etapa 1:

```bash
export MQTT_BROKER=mock
cd build
./atr_mina
```

- Executar com broker MQTT ativo (Etapa 2 / integrações):

```bash
export MQTT_BROKER=localhost
cd build
./atr_mina
```

Observações:
- O modo `mock` faz com que o cliente MQTT não tente conectar-se a um broker,
	permitindo testar todas as threads e buffers sem infraestrutura externa.
- As interfaces em `interface/` correspondem à Etapa 2; mantenha-as como apoio
	(não são obrigatórias para validar a Etapa 1).

Submissão
---------
Use o script de empacotamento para gerar um ZIP pronto para envio:

```bash
./scripts/package_submission.sh
```

Isso gera `atr_mina_submission.zip` contendo o projeto pronto para avaliação.

Documentação adicional
----------------------
Veja `docs/INSTRUCTIONS.md` para um checklist detalhado de conformidade com o enunciado.
Recomenda-se gerar um PDF desse documento e da figura de arquitetura (`docs/architecture.svg`)
antes da submissão.

Simulação e injeção de defeitos
-------------------------------
O projeto inclui uma interface de simulação em `interface/painel_controle.py` que exibe
telemetria e permite controlar o caminhão em modo manual/automático. A interface também
permite injetar defeitos na simulação para testar o monitoramento de falhas:

- Tecla `d`: injetar defeito elétrico (publica em `/mina/caminhoes/1/sim/defeito` "eletrica=1")
- Tecla `h`: injetar defeito hidráulico (publica "hidraulica=1")
- Tecla `x`: limpar defeitos (publica "clear")

A thread `TratamentoSensores_thread` lê esse tópico e aplicará flags de falha nas leituras
de sensores geradas (campos `i_falha_eletrica` / `i_falha_hidraulica`), permitindo que
`MonitoramentoDeFalhas_thread` detecte e publique eventos/alterações em `estados`.


