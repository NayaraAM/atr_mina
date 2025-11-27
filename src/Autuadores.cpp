#include "Autuadores.h"
#include <mutex>   

EstadosCaminhao ESTADO;
ComandosCaminhao COMANDO;
AtuadoresCaminhao ATUADOR;
std::mutex state_mtx;

// Inicializar novo campo (valor padrão false)
// Observação: como o objeto é global, os campos atômicos já iniciam com valores padrão (false/0).
