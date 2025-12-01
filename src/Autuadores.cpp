/*
 * Arquivo: Atuadores.cpp
 * Finalidade:
 * Este arquivo de implementação é responsável pela definição (instanciação) das
 * variáveis globais declaradas no arquivo de cabeçalho "Atuadores.h". Essas
 * variáveis representam o estado global compartilhado do caminhão, incluindo
 * seus estados operacionais (ESTADO), comandos recebidos (COMANDO) e valores
 * dos atuadores (ATUADOR). Além disso, define o mutex global (state_mtx) usado
 * para sincronizar o acesso a essas estruturas, embora o uso de tipos atômicos
 * (std::atomic) dentro das estruturas já forneça segurança de thread para
 * operações individuais em seus membros.
 *
 * Definições Globais:
 * - ESTADO: Instância global da estrutura EstadosCaminhao. Armazena o estado
 * atual do sistema (ex: modo automático, defeito, alerta de temperatura).
 * - COMANDO: Instância global da estrutura ComandosCaminhao. Armazena os
 * comandos pendentes a serem processados (ex: solicitação de modo manual,
 * comandos de movimento).
 * - ATUADOR: Instância global da estrutura AtuadoresCaminhao. Armazena os
 * valores atuais de controle para os atuadores físicos ou simulados (ex:
 * nível de aceleração, ângulo de direção).
 * - state_mtx: Instância global de std::mutex. Pode ser usado para proteger
 * operações mais complexas que envolvem múltiplas variáveis de estado ou
 * para garantir a consistência em seções críticas que vão além de simples
 * leituras/escritas atômicas.
 *
 * Inicialização:
 * Como essas variáveis são globais (com armazenamento estático), seus membros
 * (sendo do tipo std::atomic) são inicializados automaticamente com seus
 * valores padrão (false para booleanos e 0 para inteiros) antes do início da
 * execução da função main(). Portanto, não é necessária uma inicialização
 * explícita neste arquivo.
 */

#include "Autuadores.h" // Inclui o cabeçalho com as definições das estruturas e declarações extern
#include <mutex>        // Inclui a biblioteca para uso do std::mutex

// Definição das variáveis globais (alocação de memória)
EstadosCaminhao ESTADO;      // Estado global do caminhão
ComandosCaminhao COMANDO;    // Comandos globais pendentes
AtuadoresCaminhao ATUADOR;   // Valores globais dos atuadores
std::mutex state_mtx;        // Mutex global para sincronização adicional

// Observação: como o objeto é global, os campos atômicos já iniciam com valores padrão (false/0).
