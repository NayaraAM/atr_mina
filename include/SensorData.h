#pragma once
#include <cstdint>

struct SensorData
{
    uint64_t timestamp_ms = 0;

    // Sensores principais
    int i_posicao_x = 0;
    int i_posicao_y = 0;
    int i_angulo_x = 0;

    int i_temperatura = 0;

    bool i_falha_eletrica = false;
    bool i_falha_hidraulica = false;
};
