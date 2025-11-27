# Instruções e Checklist — Trabalho Final ATR (2025/2)

Este arquivo mapeia os requisitos do enunciado para o estado atual do projeto e fornece instruções para completar o que falta.

## 1) Requisitos do enunciado (mapa)

- Tarefas concorrentes (navegação, sensores, falhas, interface): Implementadas em `src/Threads.cpp`, `src/Sensores.cpp`, `src/Threads.cpp`, `interface/`.
- Mecanismos de sincronização: uso de `std::mutex`, `std::atomic`, e `condition_variable` em vários módulos (ver `include/Threads.h`).
- Modos de operação (manual/automático): variáveis em `include/Autuadores.h` e lógica em `src/Threads.cpp` / `src/LogicaDeComando`.
- Comunicação via MQTT: implementado em `include/MqttClient.h` / `src/MqttClient.cpp` (suporta modo `mock`).
- Buffer circular: `include/BufferCircular.h` e `src/BufferCircular.cpp`.
- Interface local e Gestão da Mina: pasta `interface/` contém código Python; a Etapa 2 pode usar essas ferramentas.

## 2) Itens que já implementei/ajustei

- Adicionado suporte a modo "mock" para MQTT (use `MQTT_BROKER=mock`) para executar o sistema sem broker instalado.
- `main.cpp` agora lê `MQTT_BROKER` da variável de ambiente.
- `MqttClient` protege chamadas de `disconnect()` e mantém flag `connected_`.
- Documentação: `README.md`, `docs/INSTRUCTIONS.md` e script de empacotamento.

## 3) Pendências recomendadas (para conformidade total)

- Gerar PDF de documentação técnica a partir deste `docs/INSTRUCTIONS.md` incluindo:
  - Arquitetura (Figura 1) e diagrama das tarefas (pode ser feito em draw.io e exportado em PDF).
  - Papéis dos integrantes.
  - Descrição de métodos críticos (filtro média móvel, controle PID simplificado, buffer circular).
- Testes automatizados: adicionar testes unitários para `BufferCircular` e `MqttClient` (mock).
- Scripts de demonstração/cenários (scripts que rodem simulação e interface juntos para vídeo).
- Verificar e padronizar mensagens de log e formato dos arquivos de log conforme Tabela 3 do enunciado.

## 4) Como empacotar para entrega

1. Verifique execução e logs:

```bash
export MQTT_BROKER=mock
mkdir -p build && cd build
cmake .. && make -j$(nproc)
./atr_mina
```

2. Gere PDF de documentação a partir deste arquivo (por exemplo, usando pandoc):

```bash
pandoc docs/INSTRUCTIONS.md -o docs/INSTRUCTIONS.pdf
```

3. Empacote com o script:

```bash
./scripts/package_submission.sh
```

## 5) Observações finais

Se quiser, eu posso:
- Gerar a figura da arquitetura (SVG/PDF) a partir de um esboço.
- Criar um modo de teste automatizado que execute um cenário de simulação e grave um vídeo curto.
- Implementar testes unitários e configurar um workflow GitHub Actions para validar build e testes.

Diga qual item prefere que eu priorize em seguida e eu realizo as mudanças.
