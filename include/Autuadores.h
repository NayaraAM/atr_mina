#ifndef AUTUADORES_H
#define AUTUADORES_H

#include <atomic>
#include <mutex>   // <<<<<< ADICIONE ISSO

// ---------- Estados ----------
struct EstadosCaminhao {
    std::atomic<bool> e_automatico;
    std::atomic<bool> e_defeito;
    std::atomic<bool> e_alerta_temperatura;
};

// ---------- Comandos ----------
struct ComandosCaminhao {
    std::atomic<bool> c_automatico;
    std::atomic<bool> c_man;
    std::atomic<bool> c_rearme;
    std::atomic<bool> c_acelera;
    std::atomic<bool> c_direita;
    std::atomic<bool> c_esquerda;
};

// ---------- Atuadores ----------
struct AtuadoresCaminhao {
    std::atomic<int>  o_aceleracao;
    std::atomic<int>  o_direcao;
};

// >>>>>>> DECLARAÇÕES "extern"
extern EstadosCaminhao  ESTADO;
extern ComandosCaminhao COMANDO;
extern AtuadoresCaminhao ATUADOR;
extern std::mutex state_mtx;   // agora funciona

#endif
