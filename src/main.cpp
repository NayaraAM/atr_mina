/*
 * Arquivo: main.cpp
 * Finalidade:
 * Este é o ponto de entrada principal do sistema embarcado do caminhão autônomo.
 * Ele é responsável pela inicialização, configuração e orquestração de todo o
 * sistema. Suas principais funções incluem:
 * 1. Configuração do ambiente: Criação de diretórios necessários (logs),
 * definição de handlers para sinais do sistema (Ctrl+C) e parsing de
 * argumentos da linha de comando (ID do caminhão, arquivo de rota).
 * 2. Inicialização de componentes globais: Instanciação dos buffers circulares
 * para comunicação entre threads, conexão com o broker MQTT e reinicialização
 * das estruturas globais de estado, comandos e atuadores.
 * 3. Gerenciamento de rotas: Carrega a rota inicial de um arquivo e inicia uma
 * thread dedicada (th_route_mgr) para gerenciar a navegação ponto a ponto,
 * publicando os setpoints sequencialmente via MQTT e permitindo atualizações
 * dinâmicas da rota em tempo de execução.
 * 4. Lançamento das threads de trabalho: Inicia as cinco threads principais do
 * sistema (TratamentoSensores, LogicaDeComando, MonitoramentoDeFalhas,
 * ControleDeNavegacao, ColetorDeDados), passando a elas as referências
 * necessárias para os buffers, cliente MQTT e estados globais.
 * 5. Loop principal e encerramento: Mantém o programa em execução até receber
 * um sinal de parada, momento em que coordena o encerramento gracioso de
 * todas as threads e a desconexão do broker MQTT antes de finalizar o processo.
 *
 * Bibliotecas Utilizadas:
 * - iostream, sstream: E/S padrão e manipulação de strings.
 * - thread, atomic, mutex: Suporte a concorrência e sincronização.
 * - csignal: Manipulação de sinais do sistema operacional (SIGINT).
 * - chrono: Funções de tempo e duração.
 * - filesystem: Operações no sistema de arquivos (criar diretórios).
 * - cmath: Funções matemáticas (cálculo de distância).
 * - Cabeçalhos do projeto: Inclui as definições de todas as estruturas e classes
 * utilizadas (BufferCircular, SensorData, Sensores, Threads, MqttClient,
 * Autuadores, Route).
 */

#include <iostream>
#include <thread>
#include <atomic>
#include <csignal>
#include <chrono>
#include <sstream>
#include <cstdlib>
#include <filesystem>
#include <cmath>

#include "BufferCircular.h"
#include "SensorData.h"
#include "Sensores.h"
#include "Threads.h"
#include "MqttClient.h"
#include "Autuadores.h"
#include "Route.h"

// =======================================================================
// NOTE: As variáveis ESTADO/COMANDO/ATUADOR são declaradas em Autuadores.h
// e DEFINIDAS em src/Autuadores.cpp (uma única definição do produto).
// =======================================================================

// Ponteiro usado pelo signal handler para sinalizar encerramento.
// Declarado aqui como ponteiro nulo até inicializarmos a flag no main.
static std::atomic<bool>* g_stop_ptr = nullptr;

void signal_handler(int)
{
    if (g_stop_ptr) {
        g_stop_ptr->store(true);
    }
    std::cout << "\n[MAIN] Encerrando (Ctrl+C)...\n";
}

int main(int argc, char** argv)
{
    std::cout << "=========================================\n";
    std::cout << "     Sistema ATR - Caminhão Autônomo     \n";
    std::cout << "=========================================\n";

    std::this_thread::sleep_for(std::chrono::seconds(3));
    
    // --------------------------------------------------------------
    // Flag local de encerramento (passada para as threads por ref)
    // e registro do handler via ponteiro global seguro para o handler.
    // --------------------------------------------------------------
    std::atomic<bool> stop_flag(false);
    g_stop_ptr = &stop_flag;
    std::signal(SIGINT, signal_handler);

    // --------------------------------------------------------------
    // Cria diretório de logs caso não exista
    // --------------------------------------------------------------
    try {
        std::filesystem::create_directories("logs");
    } catch (...) {
        std::cerr << "[MAIN] Erro ao criar diretório logs/\n";
    }

    // --------------------------------------------------------------
    // Instancia buffers circulares
    // --------------------------------------------------------------
    BufferCircular<SensorData> BUF_NAV(200);
    BufferCircular<SensorData> BUF_LOGIC(200);
    BufferCircular<SensorData> BUF_FALHAS(200);
    BufferCircular<SensorData> BUF_COLETOR(200);
    BufferCircular<std::string> BUF_CMDS(200);

    // --------------------------------------------------------------
    // Parse simples de argumentos: --truck-id=N e --route=PATH
    // --------------------------------------------------------------
    int truck_id = 1;
    std::string arg_route;
    for (int i = 1; i < argc; ++i) {
        std::string a(argv[i]);
        if (a.rfind("--truck-id=", 0) == 0) {
            try { truck_id = std::stoi(a.substr(11)); } catch(...) { }
        } else if (a.rfind("--route=", 0) == 0) {
            arg_route = a.substr(8);
        }
    }

    // --------------------------------------------------------------
    // Instancia cliente MQTT
    // Broker pode ser alterado pela variável de ambiente MQTT_BROKER
    // Use "mock" para executar sem broker (modo de teste/local).
    const char* broker_env = std::getenv("MQTT_BROKER");
    std::string broker = broker_env ? broker_env : "localhost";

    std::string client_id = std::string("caminhao") + std::to_string(truck_id) + "_cpp";
    MqttClient mqtt(broker, client_id);
    std::cout << "[MAIN] MQTT inicializado.\n";

    // --------------------------------------------------------------
    // Zera estados, comandos e atuadores (protegido por mutex global)
    // --------------------------------------------------------------
    {
        std::lock_guard<std::mutex> lock(state_mtx);

        // Estados
        ESTADO.e_automatico.store(false);
        ESTADO.e_defeito.store(false);

        // Comandos
        COMANDO.c_automatico.store(false);
        COMANDO.c_man.store(false);
        COMANDO.c_rearme.store(false);
        COMANDO.c_acelera.store(false);
        COMANDO.c_direita.store(false);
        COMANDO.c_esquerda.store(false);

        // Atuadores
        ATUADOR.o_aceleracao.store(0);
        ATUADOR.o_direcao.store(0);
    }

    // --------------------------------------------------------------
    // Carrega rota (se existir)
    // --------------------------------------------------------------
    Route route;
    const char* route_env = std::getenv("ROUTE_PATH");
    std::string route_path = route_env ? route_env : "routes/example.route";
    if (!arg_route.empty()) route_path = arg_route;
    if (std::filesystem::exists(route_path)) {
        if (route.loadFromFile(route_path)) {
            std::cout << "[MAIN] Rota carregada: " << route.size() << " waypoints from '" << route_path << "'\n";
        } else {
            std::cerr << "[MAIN] Falha ao carregar rota de '" << route_path << "'\n";
        }
    } else {
        std::cout << "[MAIN] Arquivo de rota não existe ('" << route_path << "'), continuando sem rota.\n";
    }

    // --------------------------------------------------------------
    // Publica rota completa em MQTT para interfaces (simulacao_mina.py) consumirem
    // Tópico: /mina/caminhoes/<id>/route
    // Payload: texto com mesmo formato de arquivo (cada linha: x y [speed])
    // --------------------------------------------------------------
    auto publish_route = [&](const Route &r) {
        std::ostringstream out;
        for (size_t i = 0; i < r.size(); ++i) {
            const Waypoint &wp = r[i];
            out << wp.x << " " << wp.y << " " << wp.speed;
            if (i + 1 < r.size()) out << "\n";
        }
        try { mqtt.publish(std::string("/mina/caminhoes/") + std::to_string(truck_id) + "/route", out.str()); } catch(...) {}
    };
    if (route.size() > 0) publish_route(route);

    // Inscrever nos tópicos que este processo consome (após definir truck_id)
    try {
        mqtt.subscribe_topic(std::string("/mina/caminhoes/") + std::to_string(truck_id) + "/comandos");
        mqtt.subscribe_topic(std::string("/mina/caminhoes/") + std::to_string(truck_id) + "/setpoints");
        mqtt.subscribe_topic(std::string("/mina/caminhoes/") + std::to_string(truck_id) + "/sim/defeito");
    } catch(...) {
        std::cerr << "[MAIN] Falha ao assinar tópicos de consumo (ignorado).\n";
    }

    // --------------------------------------------------------------
    // Lança threads
    // --------------------------------------------------------------
    std::cout << "[MAIN] Iniciando threads...\n";

    std::thread th_tratamento(
        TratamentoSensores_thread,
        std::ref(stop_flag),
        std::ref(BUF_NAV),
        std::ref(BUF_LOGIC),
        std::ref(BUF_FALHAS),
        std::ref(BUF_COLETOR),
        std::ref(mqtt),
        std::ref(ESTADO),
        std::ref(COMANDO),
        std::ref(ATUADOR),
        5,      // ordem média móvel
        50,     // período ms (mais suave)
        truck_id
    );

    std::thread th_logic(
        LogicaDeComando_thread,
        std::ref(stop_flag),
        std::ref(BUF_LOGIC),
        std::ref(BUF_CMDS),
        std::ref(mqtt),
        std::ref(ESTADO),
        std::ref(COMANDO),
        std::ref(ATUADOR),
        truck_id
    );

    std::thread th_falhas(
        MonitoramentoDeFalhas_thread,
        std::ref(stop_flag),
        std::ref(BUF_FALHAS),
        std::ref(mqtt),
        std::ref(ESTADO),
        truck_id
    );

    std::thread th_nav(
        ControleDeNavegacao_thread,
        std::ref(stop_flag),
        std::ref(BUF_NAV),
        std::ref(mqtt),
        std::ref(ESTADO),
        std::ref(COMANDO),
        std::ref(ATUADOR),
        truck_id
    );

    std::thread th_coletor(
        ColetorDeDados_thread,
        std::ref(stop_flag),
        std::ref(BUF_COLETOR),
        std::ref(BUF_LOGIC),
        std::ref(BUF_CMDS),
        std::ref(mqtt),
        std::ref(ESTADO),
        std::ref(COMANDO),
        std::ref(ATUADOR),
        truck_id
    );

    // --------------------------------------------------------------
    // Spawner: escuta tópico de gerência para criação dinâmica de caminhões
    // tópico: /mina/gerente/add_truck
    // payload esperado: "id=2,route=routes/other.route" ou "2 routes/other.route"
    // --------------------------------------------------------------
    /*std::thread th_spawner([&mqtt, &stop_flag, argc, argv]() {
        const std::string topic = "/mina/gerente/add_truck";
        try { mqtt.subscribe_topic(topic); } catch(...) {}
        // path para o executável (argv[0])
        std::string exe = argc > 0 ? std::string(argv[0]) : std::string("./atr_mina");
        while (!stop_flag.load()) {
            auto maybe = mqtt.try_pop_message(topic);
            if (maybe) {
                std::string pl = *maybe;
                int nid = -1;
                std::string nroute;
                auto find_token = [&](const std::string &k) -> std::string {
                    auto pos = pl.find(k);
                    if (pos == std::string::npos) return std::string();
                    size_t eq = pl.find('=', pos);
                    if (eq == std::string::npos) return std::string();
                    size_t start = eq + 1;
                    while (start < pl.size() && isspace((unsigned char)pl[start])) ++start;
                    size_t end = start;
                    while (end < pl.size() && pl[end] != ',' && pl[end] != ' ' && pl[end] != '\n' && pl[end] != '\r') ++end;
                    return pl.substr(start, end - start);
                };
                std::string sid = find_token("id");
                if (!sid.empty()) {
                    try { nid = std::stoi(sid); } catch(...) { nid = -1; }
                }
                std::string sroute = find_token("route");
                if (!sroute.empty()) nroute = sroute;
                if (nid == -1) {
                    std::istringstream iss(pl);
                    int maybeid; std::string maybe_route;
                    if (iss >> maybeid) {
                        nid = maybeid;
                        if (iss >> maybe_route) nroute = maybe_route;
                    }
                }

                const std::string ack_topic = "/mina/gerente/add_truck/ack";
                if (nid > 0) {
                    std::ostringstream cmd;
                    cmd << exe << " --truck-id=" << nid;
                    if (!nroute.empty()) cmd << " --route=" << nroute;
                    cmd << " &";
                    std::string scmd = cmd.str();
                    std::cerr << "[Spawner] Executing: " << scmd << "\n";
                    int rc = std::system(scmd.c_str());
                    if (rc == -1) {
                        std::cerr << "[Spawner] spawn failed (system returned -1)\n";
                        try { mqtt.publish(ack_topic, std::string("{\"id\":") + std::to_string(nid) + ",\"status\":\"error\",\"msg\":\"spawn_failed\"}"); } catch(...){}
                    } else {
                        // success (best-effort): publish ack with exit code
                        try { mqtt.publish(ack_topic, std::string("{\"id\":") + std::to_string(nid) + ",\"status\":\"ok\",\"cmd\":\"" + scmd + "\",\"rc\":" + std::to_string(rc) + "}"); } catch(...){}
                    }
                } else {
                    std::cerr << "[Spawner] mensagem invalida para add_truck: '" << pl << "'\n";
                    try { mqtt.publish(ack_topic, std::string("{\"id\":null,\"status\":\"error\",\"msg\":\"invalid_payload\",\"raw\":\"") + pl + "\"}"); } catch(...){}
                }
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(300));
        }
    });*/

    // --------------------------------------------------------------
    // Thread gerenciadora de rota (publica setpoints MQTT sequencialmente)
    // Não modifica a lógica interna das threads existentes — apenas publica
    // em /mina/caminhoes/<id>/setpoints para que o controlador já presente
    // receba os setpoints e navegue.
    // --------------------------------------------------------------
    std::thread th_route_mgr([&stop_flag, &mqtt, &route, truck_id]() {
        if (route.size() == 0) return; // nada a fazer

        const Waypoint &wp = route[0];
        std::ostringstream ss;
        ss << "x=" << (int)wp.x << ",y=" << (int)wp.y;
        mqtt.publish("/mina/caminhoes/.../setpoints", ss.str());


        // Inscreve nos tópicos de posição e rota para acompanhar progresso e receber atualizações
        try {
            mqtt.subscribe_topic(std::string("/mina/caminhoes/") + std::to_string(truck_id) + "/posicao");
            mqtt.subscribe_topic(std::string("/mina/caminhoes/") + std::to_string(truck_id) + "/route");
        } catch(...) {}

        size_t idx = 0;
        const int publish_interval_ms = 500; // atualiza setpoint a cada 500ms
        const double reach_threshold = 12.0; // distância (px) para considerar waypoint alcançado

        // pequena função para extrair inteiro do JSON simples {"x":123,...}
        auto extract_int = [](const std::string &s, const std::string &key, int &out) -> bool {
            auto pos = s.find(key);
            if (pos == std::string::npos) return false;
            size_t colon = s.find(':', pos);
            if (colon == std::string::npos) return false;
            size_t i = colon + 1;
            while (i < s.size() && isspace((unsigned char)s[i])) ++i;
            bool neg = false;
            if (i < s.size() && (s[i] == '+' || s[i] == '-')) { neg = (s[i] == '-'); ++i; }
            size_t start = i;
            while (i < s.size() && (isdigit((unsigned char)s[i]) || s[i] == '-')) ++i;
            if (i == start) return false;
            try { out = std::stoi(s.substr(start, i - start)); if (neg) out = -out; return true; } catch(...) { return false; }
        };

        int last_x = -1, last_y = -1;
        // Publish initial setpoint
        {
            const Waypoint &wp = route[0];
            std::ostringstream ss; ss << "x=" << static_cast<int>(std::round(wp.x)) << ",y=" << static_cast<int>(std::round(wp.y));
            mqtt.publish(std::string("/mina/caminhoes/") + std::to_string(truck_id) + "/setpoints", ss.str());
        }

        while (!stop_flag.load()) {
            // read route update messages (non-blocking)
            auto maybe_route = mqtt.try_pop_message(std::string("/mina/caminhoes/") + std::to_string(truck_id) + "/route");
            if (maybe_route) {
                std::string pl = *maybe_route;
                std::cerr << "[RouteMgr] received route payload (len=" << pl.size() << ")\n";
                // best-effort: parse payload as same text format used by files
                if (route.loadFromString(pl)) {
                    std::cerr << "[RouteMgr] route updated: " << route.size() << " waypoints\n";
                    idx = 0; // reinicia sequência
                    // republishes updated route for others
                    try { mqtt.publish(std::string("/mina/caminhoes/") + std::to_string(truck_id) + "/route", pl); } catch(...){}
                } else {
                    std::cerr << "[RouteMgr] failed to parse incoming route payload\n";
                }
            }

            // read position messages (non-blocking)
            auto maybe = mqtt.try_pop_message(std::string("/mina/caminhoes/") + std::to_string(truck_id) + "/posicao");
            if (maybe) {
                std::string pl = *maybe;
                int px = 0, py = 0;
                if (extract_int(pl, "x", px)) last_x = px;
                if (extract_int(pl, "y", py)) last_y = py;

                if (last_x >= 0 && last_y >= 0 && route.size() > 0) {
                    const Waypoint &cur = route[idx];
                    double dx = double(last_x) - cur.x;
                    double dy = double(last_y) - cur.y;
                    double dist = std::hypot(dx, dy);
                    if (dist <= reach_threshold) {
                        // avança waypoint
                        if (idx + 1 < route.size()) {
                            idx++;
                            const Waypoint &wp = route[idx];
                            std::ostringstream ss; ss << "x=" << static_cast<int>(std::round(wp.x)) << ",y=" << static_cast<int>(std::round(wp.y));
                            mqtt.publish(std::string("/mina/caminhoes/") + std::to_string(truck_id) + "/setpoints", ss.str());
                        } else {
                            // rota finalizada: publica último setpoint e para
                            // (opcional: loopar ou ficar no último)
                        }
                    }
                }
            }

            // periodic publish to ensure controller has current target
            if (route.size() > 0) {
                const Waypoint &wp = route[idx];
                std::ostringstream ss; ss << "x=" << static_cast<int>(std::round(wp.x)) << ",y=" << static_cast<int>(std::round(wp.y));
                mqtt.publish(std::string("/mina/caminhoes/") + std::to_string(truck_id) + "/setpoints", ss.str());
            }

            std::this_thread::sleep_for(std::chrono::milliseconds(publish_interval_ms));
        }
    });

    std::cout << "[MAIN] Todas as threads iniciadas.\n";
    std::cout << "[MAIN] Pressione Ctrl+C para encerrar.\n";

    // --------------------------------------------------------------
    // Loop principal ocioso
    // --------------------------------------------------------------
    while (!stop_flag.load()) {
        std::this_thread::sleep_for(std::chrono::milliseconds(300));
    }

    // --------------------------------------------------------------
    // Aguarda encerramento das threads
    // --------------------------------------------------------------
    std::cout << "[MAIN] Aguardando threads...\n";

    if (th_tratamento.joinable()) th_tratamento.join();
    if (th_logic.joinable())      th_logic.join();
    if (th_falhas.joinable())     th_falhas.join();
    if (th_nav.joinable())        th_nav.join();
    if (th_coletor.joinable())    th_coletor.join();
   /* if (th_spawner.joinable())    th_spawner.join();*/

    // Tenta desconectar MQTT (se disponível na sua API)
    try {
        mqtt.disconnect();
    } catch (...) {}

    std::cout << "[MAIN] Sistema finalizado com segurança.\n";
    return 0;
}
