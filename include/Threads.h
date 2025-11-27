#ifndef THREADS_H
#define THREADS_H

#include <atomic>
#include <string>
#include "SensorData.h"
#include "BufferCircular.h"
#include "MqttClient.h"
#include "Autuadores.h"

// --------------------------------------------------------------------
// Declaração das 5 threads principais do sistema ATR
// --------------------------------------------------------------------

void TratamentoSensores_thread(
    std::atomic<bool>& stop_flag,
    BufferCircular<SensorData>& buf_nav,
    BufferCircular<SensorData>& buf_logic,
    BufferCircular<SensorData>& buf_falhas,
    BufferCircular<SensorData>& buf_coletor,
    MqttClient& mqtt,
    EstadosCaminhao& estados,
    ComandosCaminhao& comandos,
    AtuadoresCaminhao& atuadores,
    int ordem_media_movel,
    int periodo_ms,
    int truck_id
);

void LogicaDeComando_thread(
    std::atomic<bool>& stop_flag,
    BufferCircular<SensorData>& buf_logic,
    BufferCircular<std::string>& buf_cmds,
    MqttClient& mqtt,
    EstadosCaminhao& estados,
    ComandosCaminhao& comandos,
    AtuadoresCaminhao& atuadores,
    int truck_id
);

void MonitoramentoDeFalhas_thread(
    std::atomic<bool>& stop_flag,
    BufferCircular<SensorData>& buf_falhas,
    MqttClient& mqtt,
    EstadosCaminhao& estados,
    int truck_id
);

void ControleDeNavegacao_thread(
    std::atomic<bool>& stop_flag,
    BufferCircular<SensorData>& buf_nav,
    MqttClient& mqtt,
    EstadosCaminhao& estados,
    ComandosCaminhao& comandos,
    AtuadoresCaminhao& atuadores,
    int truck_id
);

void ColetorDeDados_thread(
    std::atomic<bool>& stop_flag,
    BufferCircular<SensorData>& buf_coletor,
    BufferCircular<SensorData>& buf_logic,
    BufferCircular<std::string>& buf_cmds,
    MqttClient& mqtt,
    EstadosCaminhao& estados,
    ComandosCaminhao& comandos,
    AtuadoresCaminhao& atuadores,
    int truck_id
);

#endif
