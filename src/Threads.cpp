/*
 * Arquivo: Threads.cpp
 * Finalidade:
 * Este arquivo contém a implementação das cinco funções principais que são
 * executadas como threads no sistema embarcado do caminhão autônomo. Ele
 * concentra toda a lógica operacional do sistema, incluindo a simulação da
 * física e sensores, o processamento de comandos, o controle de navegação
 * (piloto automático), o monitoramento de falhas e a coleta de dados. As
 * threads interagem entre si e com o mundo externo através de buffers
 * circulares e do cliente MQTT, implementando a arquitetura de software do
 * projeto.
 *
 * Resumo das Threads:
 * 1. TratamentoSensores_thread: Simula a dinâmica física do caminhão (movimento,
 * aceleração), gera dados de sensores com ruído, aplica filtragem de média
 * móvel e distribui os dados processados para as outras threads via buffers.
 * Também trata a injeção de defeitos simulados.
 * 2. LogicaDeComando_thread: Processa comandos recebidos via MQTT (ex: mudança
 * de modo auto/manual, rearme de falhas, setpoints diretos) e atualiza o
 * estado global do caminhão.
 * 3. MonitoramentoDeFalhas_thread: Analisa os dados dos sensores para detectar
 * condições críticas (temperatura alta, falhas elétricas/hidráulicas),
 * atualiza o estado de defeito e publica eventos de alerta/falha via MQTT.
 * 4. ControleDeNavegacao_thread: Implementa a lógica de controle. No modo manual,
 * aplica os comandos incrementais do operador. No modo automático, usa um
 * controlador proporcional (P) para direção e proporcional-integral (PI)
 * para velocidade para seguir o setpoint atual da rota, garantindo uma
 * transição suave entre os modos. Publica os valores dos atuadores via MQTT.
 * 5. ColetorDeDados_thread: Responsável pela telemetria e registro. Lê os dados
 * do caminhão, grava logs em arquivos de texto e CSV, e publica as informações
 * de estado, posição e eventos via MQTT para as interfaces externas. Também
 * atua como um ponto central para receber comandos da interface local e
 * encaminhá-los para a thread de lógica.
 */

// src/Threads.cpp
// Versão "Acadêmica" — Threads do Sistema ATR (Tratamento, Lógica, Falhas, Navegação, Coletor).
// Requer headers: Threads.h, Autuadores.h, Sensores.h, SensorData.h, BufferCircular.h, MqttClient.h

#include "Threads.h"
#include "Autuadores.h"
#include "Sensores.h"
#include "SensorData.h"
#include "BufferCircular.h"
#include "MqttClient.h"

#include <thread>
#include <chrono>
#include <fstream>
#include <sstream>
#include <iostream>
#include <random>
#include <cmath>
#include <string>
#include <atomic>
#include <filesystem>

namespace fs = std::filesystem;

using namespace std;
using namespace std::chrono_literals;

// -------------------------------------------
// util: timestamp em ms (steady clock)
// -------------------------------------------
static int64_t now_ms() {
    using namespace std::chrono;
    return duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count();
}

// -------------------------------------------
// Helper: extrai inteiro de strings simples
// aceita formatos: "x=123" ou "\"x\":123" ou "x= 123"
// -------------------------------------------
static bool extract_int_arg(const std::string &s, const std::string &key, int &out) {
    auto pos = s.find(key);
    if (pos == std::string::npos) return false;
    size_t eq = s.find('=', pos);
    size_t colon = s.find(':', pos);
    size_t start = std::string::npos;
    if (eq != std::string::npos) start = eq + 1;
    else if (colon != std::string::npos) start = colon + 1;
    else return false;
    while (start < s.size() && isspace((unsigned char)s[start])) ++start;
    size_t i = start;
    if (i < s.size() && (s[i] == '-' || s[i] == '+')) ++i;
    while (i < s.size() && isdigit((unsigned char)s[i])) ++i;
    if (i == start) return false;
    try {
        out = stoi(s.substr(start, i - start));
        return true;
    } catch(...) { return false; }
}

// -------------------------------------------
// THREAD 1: TratamentoSensores + Simulação
// - simula dinâmica (px,py,heading,velocity)
// - gera SensorData com ruído
// - aplica filtro média móvel (classe Sensores)
// - empurra buffers circulares usados pelas demais threads
// - publica /sensores e /posicao quando há nova leitura filtrada
// -------------------------------------------
void TratamentoSensores_thread(
    std::atomic<bool>& stop_flag,
    BufferCircular<SensorData>& buf_nav,
    BufferCircular<SensorData>& buf_logic,
    BufferCircular<SensorData>& buf_falhas,
    BufferCircular<SensorData>& buf_coletor,
    MqttClient& mqtt,
    EstadosCaminhao& /*estados*/,         
    ComandosCaminhao& /*comandos*/,
    AtuadoresCaminhao& atuadores,
    int ordem_media_movel,
    int periodo_ms,
    int truck_id
) {
    Sensores filtro(ordem_media_movel);

    // RNG (ruído)
    std::mt19937 rng((unsigned)std::chrono::steady_clock::now().time_since_epoch().count());
    std::normal_distribution<double> noise_pos(0.0, 0.9);   // posição
    std::normal_distribution<double> noise_ang(0.0, 1.2);   // ângulo
    std::normal_distribution<double> noise_temp(0.0, 1.2);  // temperatura

    // estado do mundo (0..1000)
    double px = 100.0;
    double py = 100.0;
    double heading = 0.0;   // graus
    double velocity = 0.0;  // unidades (px/s)
    double last_time = static_cast<double>(now_ms());

    // para evitar publicar repetidamente a mesma leitura
    uint64_t last_published_ts = 0;

    // parâmetros dinâmicos (acadêmicos -> balanceados)
    const double accel_scale = 0.6;   // conversão de comando % -> px/s^2
    const double heading_gain = 1.8;  // rapidez de alinhamento do heading
    const double max_vel = 160.0;
    const double min_vel = -30.0;

    while (!stop_flag.load()) {
        double tnow = static_cast<double>(now_ms());
        double dt_ms = tnow - last_time;
        if (dt_ms <= 0.0) dt_ms = static_cast<double>(periodo_ms);
        double dt = dt_ms / 1000.0;
        last_time = tnow;

        // leitura snapshot dos atuadores
        int o_acel = atuadores.o_aceleracao.load(); // -100..100
        int o_dir  = atuadores.o_direcao.load();    // -180..180

        // checa pedidos de injeção de defeito (feito pela interface de simulação)
        auto maybe_def = mqtt.try_pop_message("/mina/caminhoes/" + std::to_string(truck_id) + "/sim/defeito");
        if (maybe_def) {
            std::string pl = *maybe_def;
            std::string low = pl;
            for (char &c : low) c = std::tolower((unsigned char)c);
            // payload esperado: "eletrica=1" ou "hidraulica=1" ou "clear"
            if (low.find("eletrica") != std::string::npos && (low.find("1") != std::string::npos || low.find("true") != std::string::npos)) {
                // set flag temporária na próxima amostra
                // vamos gravar em atuadores (mais simples): usar campos de comando não utilizados
                // trataremos via sinalização local -> aplicamos diretamente no raw gerado abaixo
            }
        }
        // dinâmica: aceleração proporcional ao comando
        double accel = static_cast<double>(o_acel) * accel_scale;
        velocity += accel * dt;

        // limites
        if (velocity > max_vel) velocity = max_vel;
        if (velocity < min_vel) velocity = min_vel;

        // heading: suaviza em direção a o_dir (erro curto)
        auto norm180 = [](double a) {
            while (a > 180.0) a -= 360.0;
            while (a <= -180.0) a += 360.0;
            return a;
        };
        double desired_heading = static_cast<double>(o_dir);
        double hdg_err = norm180(desired_heading - heading);
        double hdg_rate = hdg_err * heading_gain; // deg/s
        // small limit
        if (hdg_rate > 90.0) hdg_rate = 90.0;
        if (hdg_rate < -90.0) hdg_rate = -90.0;
        heading += hdg_rate * dt;
        // normalize heading 0..360
        heading = fmod(heading, 360.0);
        if (heading < 0.0) heading += 360.0;

        // posição
        double rad = heading * M_PI / 180.0;
        px += velocity * cos(rad) * dt;
        py += velocity * sin(rad) * dt;
        // clamp mundo
        if (px < 0.0) px = 0.0;
        if (px > 1000.0) px = 1000.0;
        if (py < 0.0) py = 0.0;
        if (py > 1000.0) py = 1000.0;

        // gera raw com ruído
        SensorData raw{};
        raw.timestamp_ms = static_cast<uint64_t>(now_ms());
        raw.i_posicao_x = static_cast<int>(std::round(px + noise_pos(rng)));
        raw.i_posicao_y = static_cast<int>(std::round(py + noise_pos(rng)));
        // ângulo: manter 0..359
        int angv = static_cast<int>(std::round(fmod(heading + noise_ang(rng) + 360.0, 360.0)));
        if (angv < 0) angv += 360;
        raw.i_angulo_x = angv;
        // temperatura: modelo simples dependente de velocidade/aceleração
        double base_temp = 70.0 + std::max(0.0, std::abs(velocity) * 0.04) + std::abs(accel) * 0.02;
        raw.i_temperatura = static_cast<int>(std::round(base_temp + noise_temp(rng)));
        raw.i_falha_eletrica = false;
        raw.i_falha_hidraulica = false;

        // Aplicar qualquer injeção de defeito solicitada via tópicos de simulação
        auto maybe_def2 = mqtt.try_pop_message("/mina/caminhoes/" + std::to_string(truck_id) + "/sim/defeito");
        if (maybe_def2) {
            std::string pl = *maybe_def2;
            std::string low = pl;
            for (char &c : low) c = std::tolower((unsigned char)c);
            if (low.find("eletrica") != std::string::npos) {
                if (low.find("0") != std::string::npos || low.find("clear") != std::string::npos || low.find("false") != std::string::npos) {
                    raw.i_falha_eletrica = false;
                } else {
                    raw.i_falha_eletrica = true;
                }
            }
            if (low.find("hidraulica") != std::string::npos) {
                if (low.find("0") != std::string::npos || low.find("clear") != std::string::npos || low.find("false") != std::string::npos) {
                    raw.i_falha_hidraulica = false;
                } else {
                    raw.i_falha_hidraulica = true;
                }
            }
            // comando especial 'all' / 'clear'
            if (low.find("all") != std::string::npos) {
                if (low.find("0") != std::string::npos || low.find("clear") != std::string::npos) {
                    raw.i_falha_eletrica = false; raw.i_falha_hidraulica = false;
                } else {
                    raw.i_falha_eletrica = true; raw.i_falha_hidraulica = true;
                }
            }
        }

        // filtra
        SensorData filtrado = filtro.filtrar(raw);

        // empurra buffers (somente quando há nova leitura filtrada)
        // Usamos timestamp para decidir se é nova leitura
        if (filtrado.timestamp_ms != last_published_ts) {
            // push bloqueante: espera até haver espaço para evitar perda de dados
            buf_nav.push_wait(filtrado);
            buf_logic.push_wait(filtrado);
            buf_falhas.push_wait(filtrado);
            buf_coletor.push_wait(filtrado);

            // publish sensores JSON
            std::ostringstream ss;
            ss << "{"
               << "\"x\":" << filtrado.i_posicao_x << ","
               << "\"y\":" << filtrado.i_posicao_y << ","
               << "\"ang\":" << filtrado.i_angulo_x << ","
               << "\"temp\":" << filtrado.i_temperatura
               << "}";
            std::string topic_sens = "/mina/caminhoes/" + std::to_string(truck_id) + "/sensores";
            mqtt.publish(topic_sens, ss.str());

            // publish position simplified (para a interface)
            std::ostringstream sp;
            sp << "{"
               << "\"x\":" << filtrado.i_posicao_x << ","
               << "\"y\":" << filtrado.i_posicao_y << ","
               << "\"ang\":" << filtrado.i_angulo_x
               << "}";
            std::string topic_pos = "/mina/caminhoes/" + std::to_string(truck_id) + "/posicao";
            mqtt.publish(topic_pos, sp.str());

            last_published_ts = filtrado.timestamp_ms;
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(periodo_ms));
    }
}

// -------------------------------------------
// THREAD 2: Lógica de Comando
// - lê tópico /comandos e atualiza flags em ComandosCaminhao / EstadosCaminhao
// - aceita setpoints diretos e rearmar
// -------------------------------------------
void LogicaDeComando_thread(
    std::atomic<bool>& stop_flag,
    BufferCircular<SensorData>& buf_logic,
    BufferCircular<std::string>& buf_cmds,
    MqttClient& mqtt,
    EstadosCaminhao& estados,
    ComandosCaminhao& comandos,
    AtuadoresCaminhao& /*atuadores*/,
    int truck_id
) {
    const std::string topic_cmd = "/mina/caminhoes/" + std::to_string(truck_id) + "/comandos";

    while (!stop_flag.load()) {
        // consumir última leitura (não bloqueante) — pode ser usada para decisões se preciso
        SensorData sd;
        // espera por nova leitura por curto período para evitar polling intenso
        buf_logic.pop_wait_for(sd, 50ms);

        // Consome comandos vindos do buffer de comandos (inseridos pelo Coletor
        // quando a interface publica em /comandos). Usamos wait.
        std::string cmdpl;
        if (buf_cmds.pop_wait_for(cmdpl, 50ms)) {
            std::string pl = cmdpl;
            std::cerr << "[Logica] popped from buf_cmds: '" << pl << "'\n";
            std::string low = pl;
            for (char &c : low) c = std::tolower((unsigned char)c);

            // modos
            if (low.find("c_man") != std::string::npos || low.find("man") != std::string::npos) {
                comandos.c_man.store(true);
                estados.e_automatico.store(false);
            }
            if (low.find("c_automatico") != std::string::npos || low.find("auto") != std::string::npos) {
                comandos.c_automatico.store(true);
                estados.e_automatico.store(true);
            }

            // rearme
            if (low.find("c_rearme") != std::string::npos || low.find("rearme") != std::string::npos) {
                comandos.c_rearme.store(true);
                estados.e_defeito.store(false);
            }

            // acelera / direções (on/off)
            if (low.find("c_acelera") != std::string::npos || low.find("acelera") != std::string::npos) {
                if (low.find("on") != std::string::npos || low.find("true") != std::string::npos || low.find("1") != std::string::npos)
                    comandos.c_acelera.store(true);
                else
                    comandos.c_acelera.store(false);
            }
            if (low.find("c_direita") != std::string::npos || low.find("direita") != std::string::npos) {
                if (low.find("on") != std::string::npos || low.find("true") != std::string::npos || low.find("1") != std::string::npos)
                    comandos.c_direita.store(true);
                else
                    comandos.c_direita.store(false);
            }
            if (low.find("c_esquerda") != std::string::npos || low.find("esquerda") != std::string::npos) {
                if (low.find("on") != std::string::npos || low.find("true") != std::string::npos || low.find("1") != std::string::npos)
                    comandos.c_esquerda.store(true);
                else
                    comandos.c_esquerda.store(false);
            }

            // setpoint direto (x=...,y=...)
            int vx, vy;
            if (extract_int_arg(pl, "x", vx) && extract_int_arg(pl, "y", vy)) {
                std::ostringstream sp; sp << "x=" << vx << ",y=" << vy;
                mqtt.publish("/mina/caminhoes/" + std::to_string(truck_id) + "/setpoints", sp.str());
            }
            } else {
            // fallback: se nada no buffer de comandos, ainda podemos checar MQTT
            auto maybe = mqtt.try_pop_message(topic_cmd);
            if (maybe) {
                std::string pl = *maybe;
                // encaminhar para o buffer para unificar o caminho
                    std::cerr << "[Logica] mqtt->comandos received, forwarding to buf_cmds: '" << pl << "'\n";
                    try { buf_cmds.push_wait(pl); } catch(...) { std::cerr << "[Logica] push to buf_cmds failed\n"; }
            }
        }

        std::this_thread::sleep_for(30ms);
    }
}

// -------------------------------------------
// THREAD 3: Monitoramento de Falhas
// - lê buffer de falhas filtrado e publica eventos (temp > 95 ou flags)
// -------------------------------------------
void MonitoramentoDeFalhas_thread(
    std::atomic<bool>& stop_flag,
    BufferCircular<SensorData>& buf_falhas,
    MqttClient& mqtt,
    EstadosCaminhao& estados,
    int truck_id
) {
    while (!stop_flag.load()) {
        SensorData sd;
        if (!buf_falhas.pop_wait_for(sd, 100ms)) {
            continue;
        }

        bool temp_alert = sd.i_temperatura > 95;   // nível de alerta
        bool temp_defect = sd.i_temperatura > 120; // nível de defeito
        bool falha_ele  = sd.i_falha_eletrica;
        bool falha_hid  = sd.i_falha_hidraulica;

        // Atualiza estados: alerta (T>95) e defeito (T>120 ou falhas)
        estados.e_alerta_temperatura.store(temp_alert);
        if (temp_defect || falha_ele || falha_hid) {
            estados.e_defeito.store(true);
        } else {
            // se não há condição de defeito, mantém e_defeito como está (não reset automático)
        }

        // Publica evento sempre que há alerta/defeito/falha
        if (temp_alert || temp_defect || falha_ele || falha_hid) {
            std::ostringstream ss;
            ss << "{"
               << "\"temp\":" << sd.i_temperatura << ","
               << "\"alert_temp\":" << (temp_alert ? 1 : 0) << ","
               << "\"defect_temp\":" << (temp_defect ? 1 : 0) << ","
               << "\"falha_ele\":" << (falha_ele ? 1 : 0) << ","
               << "\"falha_hid\":" << (falha_hid ? 1 : 0) << ","
               << "\"ts\":" << sd.timestamp_ms
               << "}";
            mqtt.publish("/mina/caminhoes/" + std::to_string(truck_id) + "/eventos", ss.str());
            // also publish a manager-level failure event for orchestration/monitoring
            try {
                std::ostringstream mgr;
                mgr << "{"
                    << "\"truck_id\":" << truck_id << ","
                    << "\"temp\":" << sd.i_temperatura << ","
                    << "\"alert_temp\":" << (temp_alert?1:0) << ","
                    << "\"defect_temp\":" << (temp_defect?1:0) << ","
                    << "\"falha_ele\":" << (falha_ele?1:0) << ","
                    << "\"falha_hid\":" << (falha_hid?1:0) << ","
                    << "\"ts\":" << sd.timestamp_ms
                    << "}";
                mqtt.publish("/mina/gerente/falhas", mgr.str());
            } catch(...) {}
        }

        std::this_thread::sleep_for(40ms);
    }
}

// -------------------------------------------
// THREAD 4: Controle de Navegação (Acadêmico)
// - modo manual: aplica comandos incrementais (operator intent)
// - modo automático: controlador PI para velocidade + P para direção
// - bumpless transfer ao habilitar controller
// -------------------------------------------
void ControleDeNavegacao_thread(
    std::atomic<bool>& stop_flag,
    BufferCircular<SensorData>& buf_nav,
    MqttClient& mqtt,
    EstadosCaminhao& estados,
    ComandosCaminhao& comandos,
    AtuadoresCaminhao& atuadores,
    int truck_id
) {
    const std::string topic_setp = "/mina/caminhoes/" + std::to_string(truck_id) + "/setpoints";
    int setpoint_x = 500, setpoint_y = 500;

    double integrador_v = 0.0;
    bool controller_enabled = false;

    // control gains (acadêmico, ajustáveis)
    const double Kp_ang = 1.1;   // ganho direção (P)
    const double Kp_v   = 1.0;   // ganho proporcional velocidade
    const double Ki_v   = 0.12;  // ganho integral velocidade
    const double Ts_sec = 0.1;   // período de controle (100 ms)

    // anti-windup: integrador limits
    const double INT_MIN = -200.0;
    const double INT_MAX = 200.0;

    int period_ms = static_cast<int>(Ts_sec * 1000.0);

    // last sensor used to estimate speed (numerical differentiation)
    SensorData last_sd{};
    double last_disp_time = static_cast<double>(now_ms());
    double estimated_speed = 0.0; // px/s

    bool prev_auto = estados.e_automatico.load();
    while (!stop_flag.load()) {
        // read latest sensor (wait for a short time)
        SensorData sd;
        bool have_sd = buf_nav.pop_wait_for(sd, 100ms);

        // update setpoint if MQTT sent
        auto maybe_sp = mqtt.try_pop_message(topic_setp);
        if (maybe_sp) {
            std::string pl = *maybe_sp;
            std::cerr << "[Controle] setpoint msg: '" << pl << "'\n";
            int vx, vy;
            if (extract_int_arg(pl, "x", vx)) setpoint_x = vx;
            if (extract_int_arg(pl, "y", vy)) setpoint_y = vy;
        }

        // estimate speed from successive sensor samples (if available)
        double now_t = static_cast<double>(now_ms());
        if (have_sd && last_sd.timestamp_ms != 0 && sd.timestamp_ms != last_sd.timestamp_ms) {
            double dt = (double)(sd.timestamp_ms - last_sd.timestamp_ms) / 1000.0;
            if (dt > 0.0001) {
                double dx = double(sd.i_posicao_x - last_sd.i_posicao_x);
                double dy = double(sd.i_posicao_y - last_sd.i_posicao_y);
                estimated_speed = std::hypot(dx, dy) / dt;
            }
        }
        if (have_sd) {
            last_sd = sd;
            last_disp_time = now_t;
        }

        bool is_auto = estados.e_automatico.load();
        if (is_auto != prev_auto) {
            std::cerr << "[Controle] automatic mode changed: " << (prev_auto?"ON":"OFF") << " -> " << (is_auto?"ON":"OFF") << "\n";
            prev_auto = is_auto;
        }
        bool is_def = estados.e_defeito.load();

        if (is_def) {
            // zero outputs in emergency
            atuadores.o_aceleracao.store(0);
            // keep direction as is
            std::ostringstream ss;
            ss << "{\"o_acel\":0,\"o_dir\":" << atuadores.o_direcao.load()
               << ",\"e_automatico\":" << (is_auto?1:0) << ",\"e_defeito\":1}";
            mqtt.publish("/mina/caminhoes/" + std::to_string(truck_id) + "/atuadores", ss.str());
            std::this_thread::sleep_for(std::chrono::milliseconds(period_ms));
            continue;
        }

        if (!is_auto) {
            // Garantir que o controlador automático esteja desabilitado em modo manual
            // Isso força re-inicialização (bumpless) quando voltar ao modo automático.
            controller_enabled = false;

            // Ajustar setpoints para posição atual enquanto em manual para evitar
            // comportamento indesejado ao trocar manual->automático (bumpless transfer).
            if (have_sd) {
                setpoint_x = sd.i_posicao_x;
                setpoint_y = sd.i_posicao_y;
            } else if (last_sd.timestamp_ms != 0) {
                setpoint_x = last_sd.i_posicao_x;
                setpoint_y = last_sd.i_posicao_y;
            }

            // Lê os valores atuais dos atuadores.
            int acel = atuadores.o_aceleracao.load();
            int dir  = atuadores.o_direcao.load();

            /// Lógica de Aceleração/Frenagem Manual:
            // Se o comando de aceleração estiver ativo, incrementa a aceleração (até 100).
            // Caso contrário, decrementa a aceleração (simulando freio motor ou atrito) até -100.
            if (comandos.c_acelera.load()) acel = std::min(100, acel + 6);
            else acel = std::max(-100, acel - 3); // decay when not pressed

            // Lógica de Direção Manual:
            // Se o comando de direita estiver ativo, decrementa o ângulo (vira à direita, até -180).
            // Se o comando de esquerda estiver ativo, incrementa o ângulo (vira à esquerda, até 180).
            if (comandos.c_direita.load()) dir = std::max(-180, dir - 5);
            if (comandos.c_esquerda.load()) dir = std::min(180, dir + 5);

            // Atualiza os valores globais dos atuadores com os novos valores calculados.
            atuadores.o_aceleracao.store(acel);
            atuadores.o_direcao.store(dir);

            // Publica o snapshot atual dos atuadores via MQTT em formato JSON.
            std::ostringstream ss;
            ss << "{\"o_acel\":" << acel << ",\"o_dir\":" << dir
               << ",\"e_automatico\":0,\"e_defeito\":0}";
            mqtt.publish("/mina/caminhoes/" + std::to_string(truck_id) + "/atuadores", ss.str());

            // Aguarda o próximo ciclo de controle.
            std::this_thread::sleep_for(std::chrono::milliseconds(period_ms));
            continue;
        }

        // Automatic mode: controller
        if (!controller_enabled) {
            // Bumpless transfer: Inicializa o integrador do controlador PI com um valor
            // proporcional à aceleração atual. Isso evita um "tranco" no integrador
            // quando o controle automático é ativado, garantindo uma transição suave.
            integrador_v = static_cast<double>(atuadores.o_aceleracao.load()) * 0.1;
            controller_enabled = true;
        }

        // Se não houver leitura do sensor disponível, aguarda e tenta novamente no próximo ciclo.
        if (!have_sd) {
            std::this_thread::sleep_for(std::chrono::milliseconds(period_ms));
            continue;
        }

        // Medições atuais do sensor.
        int current_x = sd.i_posicao_x;
        int current_y = sd.i_posicao_y;
        int current_ang = sd.i_angulo_x;

        // Calcula a diferença (erro) de posição entre o setpoint e a posição atual.
        int dx = setpoint_x - current_x;
        int dy = setpoint_y - current_y;
        // Calcula a distância euclidiana até o setpoint.
        double dist = std::hypot((double)dx, (double)dy);

        // --- Controlador de Direção (Proporcional - P) ---
        double desired_ang = current_ang;
        // Se estiver longe do alvo (> 1.0), calcula o ângulo desejado para apontar para ele.
        if (dist > 1.0) {
            desired_ang = atan2((double)dy, (double)dx) * 180.0 / M_PI;
            if (desired_ang < 0) desired_ang += 360.0; // Normaliza para 0-359
        }
        // Função auxiliar para normalizar o erro angular entre -180 e 180 graus.
        auto wrap180 = [](double a) {
            while (a > 180.0) a -= 360.0;
            while (a <= -180.0) a += 360.0;
            return a;
        };
        // Calcula o erro angular e aplica o ganho proporcional (Kp_ang).
        double ang_err = wrap180(desired_ang - current_ang);
        int out_dir = static_cast<int>(current_ang + std::round(Kp_ang * ang_err));
        // Normaliza o ângulo de saída para o intervalo -180 a 180.
        if (out_dir > 180) out_dir -= 360;
        if (out_dir < -180) out_dir += 360;

        // --- Controlador de Velocidade (Proporcional-Integral - PI) ---
        // Define a velocidade desejada proporcional à distância até o alvo (máx 80.0).
        double desired_speed = std::min(80.0, dist * 0.4);
        double current_speed = estimated_speed; // Velocidade estimada anteriormente
        double error_v = desired_speed - current_speed; // Erro de velocidade

        // Atualização discreta do integrador com proteção anti-windup (limites).
        integrador_v += error_v * Ki_v * Ts_sec;
        if (integrador_v > INT_MAX) integrador_v = INT_MAX;
        if (integrador_v < INT_MIN) integrador_v = INT_MIN;

        // Calcula a saída de aceleração (comando P + I).
        double out_acc = Kp_v * error_v + integrador_v;
        int out_acc_i = static_cast<int>(std::round(out_acc));
        // Limita a aceleração de saída ao intervalo -100 a 100.
        if (out_acc_i > 100) out_acc_i = 100;
        if (out_acc_i < -100) out_acc_i = -100;

        // Atualiza os valores globais dos atuadores.
        atuadores.o_aceleracao.store(out_acc_i);
        atuadores.o_direcao.store(out_dir);

        // Publica os atuadores calculados via MQTT.
        std::ostringstream ss;
        ss << "{\"o_acel\":" << out_acc_i << ",\"o_dir\":" << out_dir
           << ",\"e_automatico\":1,\"e_defeito\":0}";
        mqtt.publish("/mina/caminhoes/" + std::to_string(truck_id) + "/atuadores", ss.str());

        // Aguarda o próximo ciclo de controle.
        std::this_thread::sleep_for(std::chrono::milliseconds(period_ms));
    }
}

// -------------------------------------------
// THREAD 5: Coletor de Dados
// - grava logs Tabela 3 (timestamp, id, estado, pos, evento)
// - grava csv detalhado (sensores+atuadores)
// - publica /logs simplificado
// -------------------------------------------
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
) {
    // criar pasta logs se não existir
    try { fs::create_directories("logs");} catch(...) {}

    std::ofstream fout("logs/logs_caminhao.txt", std::ios::app);

    // Verifica se o CSV já existe e se o cabeçalho contém a nova coluna.
    fs::path detailed_path = "logs/logs_caminhao_detailed.csv";
    try {
        if (fs::exists(detailed_path)) {
            // lê primeira linha para checar cabeçalho existente
            std::ifstream fin(detailed_path);
            std::string first;
            if (std::getline(fin, first)) {
                if (first.find("e_alerta_temp") == std::string::npos) {
                    // cabeçalho antigo: criar arquivo temporário com novo cabeçalho e copiar conteúdo
                    // Pula o primeiro (velho) cabeçalho e anexa ",0" a cada linha histórica
                    fs::path tmp = detailed_path.string() + ".tmp";
                    std::ofstream fout_tmp(tmp, std::ios::trunc);
                    fout_tmp << "timestamp_ms,truck_id,pos_x,pos_y,ang,temp,fe,fh,o_acel,o_dir,e_auto,e_defeito,e_alerta_temp\n";
                    // volta ao começo e copia o conteúdo pulando o antigo cabeçalho
                    fin.clear(); fin.seekg(0);
                    std::string line;
                    bool is_first_line = true;
                    while (std::getline(fin, line)) {
                        if (is_first_line) { is_first_line = false; continue; }
                        if (!line.empty()) {
                            fout_tmp << line << ",0\n";
                        } else {
                            fout_tmp << "\n";
                        }
                    }
                    fout_tmp.close();
                    fin.close();
                    // substitui o arquivo original (best-effort)
                    try { fs::rename(tmp, detailed_path); } catch(...) { /* best-effort */ }
                } else {
                    fin.close();
                }
            } else {
                fin.close();
            }
        }
    } catch(...) {
        // se houver qualquer erro, continuamos e faremos um best-effort mais adiante
    }

    // Best-effort adicional: detectar presença de um cabeçalho duplicado/antigo
    // ou linhas históricas sem a coluna e_alerta_temp e reescrever o arquivo de forma segura.
    try {
        std::ifstream fincheck(detailed_path);
        if (fincheck) {
            std::vector<std::string> lines;
            std::string l;
            while (std::getline(fincheck, l)) lines.push_back(l);
            fincheck.close();

            bool need_rewrite = false;
            const std::string old_head = "timestamp_ms,truck_id,pos_x,pos_y,ang,temp,fe,fh,o_acel,o_dir,e_auto,e_defeito";
            for (size_t i = 0; i < lines.size(); ++i) {
                if (lines[i] == old_head) { need_rewrite = true; break; }
                // linhas de dados com número de colunas menor que 13
                if (!lines[i].empty() && lines[i].find(',') != std::string::npos) {
                    size_t commas = std::count(lines[i].begin(), lines[i].end(), ',');
                    if (commas < 12) { need_rewrite = true; break; }
                }
            }

            if (need_rewrite) {
                fs::path tmp = detailed_path.string() + ".tmp";
                std::ofstream fout_tmp(tmp, std::ios::trunc);
                fout_tmp << "timestamp_ms,truck_id,pos_x,pos_y,ang,temp,fe,fh,o_acel,o_dir,e_auto,e_defeito,e_alerta_temp\n";
                // percorre linhas e copia: pula qualquer cabeçalho antigo e garante 13 campos
                for (size_t i = 0; i < lines.size(); ++i) {
                    const std::string &line = lines[i];
                    if (line == old_head) continue;
                    if (line.rfind("timestamp_ms", 0) == 0) continue; // pula qualquer linha de cabeçalho
                    if (line.empty()) { fout_tmp << "\n"; continue; }
                    size_t commas = std::count(line.begin(), line.end(), ',');
                    std::string out = line;
                    if (commas == 11) {
                        // já têm 12 campos (11 vírgulas) -> falta e_alerta_temp
                        out += ",0";
                    }
                    // se tiver outros casos, apenas escreve a linha como está (best-effort)
                    fout_tmp << out << "\n";
                }
                fout_tmp.close();
                try { fs::rename(tmp, detailed_path); } catch(...) { /* best-effort */ }
            }
        }
    } catch(...) { /* ignorar erros de reparo */ }

    // agora abrimos o stream de append normalmente
    std::ofstream fout_detailed(detailed_path, std::ios::app);
    try {
        if (!fs::exists(detailed_path) || fs::file_size(detailed_path) == 0) {
            fout_detailed << "timestamp_ms,truck_id,pos_x,pos_y,ang,temp,fe,fh,o_acel,o_dir,e_auto,e_defeito,e_alerta_temp\n";
            fout_detailed.flush();
        }
    } catch(...) {
        try { fout_detailed << "timestamp_ms,truck_id,pos_x,pos_y,ang,temp,fe,fh,o_acel,o_dir,e_auto,e_defeito,e_alerta_temp\n"; } catch(...) {}
    }

    while (!stop_flag.load()) {
        SensorData sd;
        if (!buf_coletor.pop_wait_for(sd, 200ms)) {
            continue;
        }

        bool is_auto = estados.e_automatico.load();
        bool is_def  = estados.e_defeito.load();

        // descrição do evento: se houver alerta de temperatura global, priorizar "ALERTA_TEMP"
        std::string desc_str;
        if (estados.e_alerta_temperatura.load()) {
            desc_str = "ALERTA_TEMP";
        } else {
            std::ostringstream desc;
            if (sd.i_falha_eletrica) desc << "FALHA_ELETRICA;";
            if (sd.i_falha_hidraulica) desc << "FALHA_HIDRAULICA;";
            if (sd.i_temperatura > 120) desc << "DEFEITO_TEMPERATURA;";
            if (desc.str().empty()) desc_str = "OK";
            else desc_str = desc.str();
        }

        // Tabela 3
           std::ostringstream line;
           // Formato Tabela 3: timestamp_ms,truck_id,estado,pos_x,pos_y,descricao
           line << sd.timestamp_ms << "," << truck_id << "," << (is_auto?"AUTOMATICO":"MANUAL") << ","
               << sd.i_posicao_x << "," << sd.i_posicao_y << "," << desc_str;
        fout << line.str() << "\n";
        fout.flush();

        // csv detalhado
        fout_detailed << sd.timestamp_ms << "," << truck_id << ","
                  << sd.i_posicao_x << "," << sd.i_posicao_y << "," << sd.i_angulo_x << ","
                  << sd.i_temperatura << "," << sd.i_falha_eletrica << "," << sd.i_falha_hidraulica << ","
                  << atuadores.o_aceleracao.load() << "," << atuadores.o_direcao.load() << ","
                  << (is_auto?1:0) << "," << (is_def?1:0) << "," << (estados.e_alerta_temperatura.load()?1:0) << "\n";
        fout_detailed.flush();

        // publicar log simplificado
        std::ostringstream ss;
        ss << sd.timestamp_ms << "," << truck_id << "," << sd.i_posicao_x << "," << sd.i_posicao_y << "," << sd.i_angulo_x;
        mqtt.publish("/mina/caminhoes/" + std::to_string(truck_id) + "/logs", ss.str());

        // publicar estado atual para Interface Local
        try {
            std::ostringstream estj;
            estj << "{"
                 << "\"automatico\":" << (is_auto?1:0) << ","
                 << "\"defeito\":" << (is_def?1:0) << ","
                 << "\"aceleracao\":" << atuadores.o_aceleracao.load() << ","
                 << "\"direcao\":" << atuadores.o_direcao.load() << ","
                 << "\"x\":" << sd.i_posicao_x << ","
                 << "\"y\":" << sd.i_posicao_y << ","
                 << "\"ang\":" << sd.i_angulo_x << ","
                 << "\"temp\":" << sd.i_temperatura << ","
                 << "\"falha_elet\":" << (sd.i_falha_eletrica?1:0) << ","
                 << "\"falha_hidr\":" << (sd.i_falha_hidraulica?1:0)
                 << "}";
            mqtt.publish("/mina/caminhoes/" + std::to_string(truck_id) + "/estado", estj.str());
        } catch(...) {}

        // Também checar comandos vindos da Interface Local e atualizar flags locais
        // (faz papel similar ao LogicaDeComando_thread caso a interface publique direto no tópico)
        auto maybe_cmd = mqtt.try_pop_message("/mina/caminhoes/" + std::to_string(truck_id) + "/comandos");
        if (maybe_cmd) {
            std::string pl = *maybe_cmd;
            std::cerr << "[Coletor] mqtt->comandos received: '" << pl << "'\n";
            std::string low = pl;
            for (char &c : low) c = std::tolower((unsigned char)c);

            if (low.find("c_man") != std::string::npos || low.find("man") != std::string::npos) {
                comandos.c_man.store(true);
                estados.e_automatico.store(false);
            }
            if (low.find("c_automatico") != std::string::npos || low.find("auto") != std::string::npos) {
                comandos.c_automatico.store(true);
                estados.e_automatico.store(true);
            }
            if (low.find("c_rearme") != std::string::npos || low.find("rearme") != std::string::npos) {
                comandos.c_rearme.store(true);
                estados.e_defeito.store(false);
            }
            if (low.find("c_acelera") != std::string::npos || low.find("acelera") != std::string::npos) {
                if (low.find("on") != std::string::npos || low.find("true") != std::string::npos || low.find("1") != std::string::npos)
                    comandos.c_acelera.store(true);
                else
                    comandos.c_acelera.store(false);
            }
            if (low.find("c_direita") != std::string::npos || low.find("direita") != std::string::npos) {
                if (low.find("on") != std::string::npos || low.find("true") != std::string::npos || low.find("1") != std::string::npos)
                    comandos.c_direita.store(true);
                else
                    comandos.c_direita.store(false);
            }
            if (low.find("c_esquerda") != std::string::npos || low.find("esquerda") != std::string::npos) {
                if (low.find("on") != std::string::npos || low.find("true") != std::string::npos || low.find("1") != std::string::npos)
                    comandos.c_esquerda.store(true);
                else
                    comandos.c_esquerda.store(false);
            }
            // Empurra payload de comando (string) para buffer dedicado
            try {
                buf_cmds.push_wait(pl);
                std::cerr << "[Coletor] forwarded to buf_cmds: '" << pl << "'\n";
                // also record a diagnostic entry in the textual log to make debugging visible
                try {
                    fout << "DBG_CMD," << sd.timestamp_ms << "," << truck_id << "," << pl << "\n";
                    fout.flush();
                } catch(...) {}
            } catch(...) { std::cerr << "[Coletor] push to buf_cmds failed\n"; }
        }

        std::this_thread::sleep_for(40ms);
    }

    fout.close(); 
    fout_detailed.close();
}
