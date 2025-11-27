# Use Ubuntu 24.04
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
# Variável para permitir pip global no Ubuntu 24.04 (Corrige o erro de ambiente)
ENV PIP_BREAK_SYSTEM_PACKAGES=1

WORKDIR /workspace

# 1. Instalação de Pacotes
# Incluindo libpaho-mqtt-dev (C++) e python3-pip (Python)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    g++ \
    cmake \
    git \
    mosquitto \
    mosquitto-clients \
    libpaho-mqtt-dev \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# 2. Copia o projeto
COPY . /workspace

# 3. Configura Python (Instalação Global)
# Removemos a criação de venv. Instalamos direto no sistema.
RUN pip3 install --no-cache-dir paho-mqtt

# 4. Compilação do C++
RUN mkdir -p /workspace/build && cd /workspace/build && \
    cmake .. && \
    make -j$(nproc)

# 5. Cria pasta de logs
RUN mkdir -p /workspace/logs

# Expõe porta MQTT
EXPOSE 1883

# 6. Entrypoint
# Inicia o Mosquitto em background e depois roda o executável C++
RUN echo '#!/bin/bash\nservice mosquitto start\n./build/atr_mina' > /entrypoint.sh \
    && chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]