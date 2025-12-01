/*
 * Arquivo: Sensores.cpp
 * Finalidade:
 * Este arquivo contém a implementação da classe Sensores, que é responsável
 * por aplicar um filtro de média móvel aos dados brutos lidos dos sensores
 * do caminhão. A filtragem é crucial para suavizar as leituras, reduzindo o
 * ruído inerente aos sensores e fornecendo dados mais estáveis e confiáveis
 * para as outras partes do sistema, como a lógica de navegação.
 *
 * Construtor (Sensores::Sensores(int ordem)):
 * - Inicializa a classe com a ordem do filtro (número de amostras para a média).
 * - Valida a ordem: garante que seja pelo menos 1, pois uma ordem 0 ou negativa
 * não faz sentido para um filtro de média móvel.
 * - Limpa o deque (janela_) que armazenará o histórico das amostras.
 *
 * Método filtrar(const SensorData& raw):
 * - Recebe um objeto SensorData contendo as leituras brutas (raw) mais recentes.
 * - Adiciona essa nova amostra ao final do deque (janela_).
 * - Mantém o tamanho da janela: Se o número de amostras no deque exceder a
 * ordem do filtro, remove a amostra mais antiga (do início do deque) usando
 * pop_front(), garantindo que a média seja calculada apenas sobre as N
 * amostras mais recentes.
 * - Calcula a média: Itera sobre todas as amostras na janela e soma seus valores
 * para posição (X, Y), ângulo e temperatura. Usa int64_t para as somas para
 * evitar estouro (overflow) durante a soma. Divide as somas pelo número de
 * amostras na janela para obter a média.
 * - Cria o objeto de saída: Prepara um novo objeto SensorData (out) com os
 * valores filtrados (médias calculadas). Mantém o timestamp da amostra mais
 * recente e copia os valores das flags de falha (elétrica e hidráulica)
 * diretamente dos dados brutos, pois não faz sentido aplicar filtro de média
 * a valores booleanos.
 * - Retorna: O objeto SensorData com os dados filtrados.
 */

#include "Sensores.h" 

// Construtor: Inicializa o filtro com a ordem especificada.
Sensores::Sensores(int ordem)
{
    // Ordem mínima = 1. Se ordem <= 0, força para 1.
    ordem_ = (ordem <= 0 ? 1 : ordem);
    janela_.clear(); // Garante que a janela comece vazia.
}

// Método filtrar: Aplica o filtro de média móvel aos dados brutos.
SensorData Sensores::filtrar(const SensorData& raw)
{
    // 1. Adiciona a nova amostra ao histórico (final do deque).
    janela_.push_back(raw);

    // 2. Mantém o tamanho da janela: Se exceder a ordem, remove a mais antiga.
    // REMOVE a mais antiga (frente do deque), não a mais nova!
    if ((int)janela_.size() > ordem_)
        janela_.pop_front();

    const int n = janela_.size(); // Número atual de amostras na janela.

    // 3. Somatórios seguros: Usa int64_t para evitar overflow durante a soma.
    int64_t sx = 0, sy = 0, sang = 0, st = 0;

    // Itera sobre todas as amostras na janela e acumula os valores.
    for (const auto& s : janela_) {
        sx += s.i_posicao_x;
        sy += s.i_posicao_y;
        sang += s.i_angulo_x;
        st += s.i_temperatura;
    }

    // 4. Cria o objeto de saída com os dados filtrados.
    SensorData out{};
    out.timestamp_ms     = raw.timestamp_ms; // Mantém o timestamp da amostra mais recente.
    out.i_posicao_x      = static_cast<int>(sx / n); // Calcula a média da posição X.
    out.i_posicao_y      = static_cast<int>(sy / n); // Calcula a média da posição Y.
    out.i_angulo_x       = static_cast<int>(sang / n); // Calcula a média do ângulo.
    out.i_temperatura    = static_cast<int>(st / n); // Calcula a média da temperatura.

    // 5. Copia as flags de falha diretamente (não aplica filtro).
    // Falhas não passam pelo filtro (não faz sentido filtrar booleano).
    out.i_falha_eletrica   = raw.i_falha_eletrica;
    out.i_falha_hidraulica = raw.i_falha_hidraulica;

    return out; // Retorna o objeto com os dados filtrados.
}