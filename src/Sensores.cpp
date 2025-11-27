#include "Sensores.h"

Sensores::Sensores(int ordem)
{
    // Ordem mínima = 1
    ordem_ = (ordem <= 0 ? 1 : ordem);
    janela_.clear();
}

SensorData Sensores::filtrar(const SensorData& raw)
{
    // adiciona nova amostra na janela
    janela_.push_back(raw);

    // REMOVE a mais antiga, não a mais nova!
    if ((int)janela_.size() > ordem_)
        janela_.pop_front();

    const int n = janela_.size();

    // somatórios seguros
    int64_t sx = 0, sy = 0, sang = 0, st = 0;

    for (const auto& s : janela_) {
        sx += s.i_posicao_x;
        sy += s.i_posicao_y;
        sang += s.i_angulo_x;
        st += s.i_temperatura;
    }

    // saída filtrada
    SensorData out{};
    out.timestamp_ms     = raw.timestamp_ms;
    out.i_posicao_x      = static_cast<int>(sx / n);
    out.i_posicao_y      = static_cast<int>(sy / n);
    out.i_angulo_x       = static_cast<int>(sang / n);
    out.i_temperatura    = static_cast<int>(st / n);

    // falhas não passam pelo filtro (não faz sentido filtrar booleano)
    out.i_falha_eletrica   = raw.i_falha_eletrica;
    out.i_falha_hidraulica = raw.i_falha_hidraulica;

    return out;
}
