/*
 * Arquivo: Atuadores.h
 * Finalidade:
 * Este arquivo de cabeçalho define as estruturas de dados e variáveis globais
 * responsáveis pelo controle do estado, comandos e atuadores do caminhão autônomo.
 * Ele serve como um ponto central para a comunicação entre as diferentes threads
 * do sistema embarcado, garantindo a consistência e a segurança no acesso a
 * informações críticas.
 *
 * Estruturas Definidas:
 * - EstadosCaminhao: Armazena o estado atual do caminhão (automático, defeito, alerta).
 * - ComandosCaminhao: Armazena os comandos recebidos (automático, manual, rearme, acelera, direita, esquerda).
 * - AtuadoresCaminhao: Armazena os valores dos atuadores (aceleração, direção).
 *
 * Variáveis Globais:
 * - ESTADO: Instância da estrutura EstadosCaminhao.
 * - COMANDO: Instância da estrutura ComandosCaminhao.
 * - ATUADOR: Instância da estrutura AtuadoresCaminhao.
 * - state_mtx: Mutex para sincronização do acesso às estruturas de estado, comandos e atuadores.
 *
 * Observações:
 * - As estruturas utilizam std::atomic para garantir a atomicidade das operações
 * de leitura e escrita em variáveis compartilhadas entre threads.
 * - O mutex state_mtx é utilizado para proteger o acesso concorrente a seções
 * críticas do código que envolvem as estruturas de estado, comandos e atuadores.
 */

#ifndef AUTUADORES_H
#define AUTUADORES_H

#include <atomic>  // Inclui a biblioteca para suporte a tipos atômicos
#include <mutex>   // Inclui a biblioteca para suporte a mutexes

// ---------- Estados ----------
struct EstadosCaminhao {
    std::atomic<bool> e_automatico; // Indica se o caminhão está em modo automático (true) ou manual (false)
    std::atomic<bool> e_defeito;    // Indica se o caminhão está com defeito (true) ou funcionando corretamente (false)
    std::atomic<bool> e_alerta_temperatura; // Indica se há um alerta de temperatura (true) ou não (false)
};

// ---------- Comandos ----------
struct ComandosCaminhao {
    std::atomic<bool> c_automatico; // Comando para ativar o modo automático
    std::atomic<bool> c_man;         // Comando para ativar o modo manual
    std::atomic<bool> c_rearme;      // Comando para rearmar o sistema após um defeito
    std::atomic<bool> c_acelera;     // Comando para acelerar o caminhão
    std::atomic<bool> c_direita;     // Comando para virar o caminhão para a direita
    std::atomic<bool> c_esquerda;    // Comando para virar o caminhão para a esquerda
};

// ---------- Atuadores ----------
struct AtuadoresCaminhao {
    std::atomic<int>  o_aceleracao; // Valor da aceleração do caminhão (0-100%)
    std::atomic<int>  o_direcao;    // Valor da direção do caminhão (-180 a 180 graus)
};

// >>>>>>> DECLARAÇÕES "extern"
extern EstadosCaminhao  ESTADO;  // Declaração externa da variável ESTADO
extern ComandosCaminhao COMANDO; // Declaração externa da variável COMANDO
extern AtuadoresCaminhao ATUADOR; // Declaração externa da variável ATUADOR
extern std::mutex state_mtx;   // Declaração externa do mutex state_mtx

#endif