/*
 * Arquivo: SensorData.h
 * Finalidade:
 * Este arquivo de cabeçalho define a estrutura SensorData, que serve como o
 * "pacote de dados" padrão para representar o estado instantâneo dos sensores
 * do caminhão autônomo. Ela é usada para transportar informações vitais
 * entre as diferentes threads do sistema embarcado e também para a coleta de
 * dados e telemetria.
 *
 * Campos da Estrutura:
 * - timestamp_ms: Um carimbo de tempo (em milissegundos desde a época Unix)
 * que indica o momento exato em que os dados foram lidos ou gerados.
 * Essencial para análise de dados, sincronização e logs. Usamos uint64_t
 * para evitar estouro (overflow) em sistemas que rodam por longos períodos.
 *
 * Sensores Principais:
 * - i_posicao_x: A posição atual do caminhão no eixo X (coordenada).
 * - i_posicao_y: A posição atual do caminhão no eixo Y (coordenada).
 * - i_angulo_x: A orientação atual do caminhão (ângulo em graus, ex: 0-359).
 *
 * Dados de Estado e Falha:
 * - i_temperatura: A temperatura atual do motor ou sistema crítico.
 * - i_falha_eletrica: Flag booleana indicando se foi detectada uma falha no
 * sistema elétrico (true = falha, false = normal).
 * - i_falha_hidraulica: Flag booleana indicando se foi detectada uma falha no
 * sistema hidráulico (true = falha, false = normal).
 */

#pragma once
#include <cstdint> // Inclui a biblioteca para tipos inteiros de tamanho fixo (uint64_t)

struct SensorData
{
    uint64_t timestamp_ms = 0; // Carimbo de tempo em milissegundos

    // Sensores principais
    int i_posicao_x = 0; // Posição X atual
    int i_posicao_y = 0; // Posição Y atual
    int i_angulo_x = 0;  // Ângulo (orientação) atual

    // Estado e monitoramento
    int i_temperatura = 0; // Temperatura atual

    // Flags de falha
    bool i_falha_eletrica = false;   // Falha elétrica detectada?
    bool i_falha_hidraulica = false; // Falha hidráulica detectada?
};