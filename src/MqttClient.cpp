/*
 * Arquivo: MqttClient.cpp
 * Finalidade:
 * Este arquivo contém a implementação da classe MqttClient, definida em
 * "MqttClient.h". Ele fornece um wrapper (camada de abstração) simplificado
 * e thread-safe sobre a biblioteca Paho MQTT C++, facilitando o uso de
 * funcionalidades MQTT (conectar, publicar, assinar, receber mensagens)
 * pelas threads do sistema embarcado.
 *
 * Funcionalidades Implementadas:
 * - Conexão/Desconexão: Gerencia a conexão com o broker MQTT, incluindo
 * um modo "MOCK" para testes sem broker real.
 * - Publicação: Método publish() para enviar mensagens de forma síncrona
 * (espera o envio ser confirmado).
 * - Assinatura: Método subscribe_topic() para se inscrever em tópicos e
 * receber mensagens.
 * - Recepção de Mensagens (Callback): Implementa a classe interna Callback,
 * cujo método message_arrived() é chamado automaticamente pela biblioteca
 * Paho quando uma nova mensagem chega.
 * - Armazenamento Seguro: As mensagens recebidas são armazenadas em filas
 * internas (std::unordered_map<std::string, std::queue<std::string>> queues_),
 * protegidas por um mutex (q_mtx_) para garantir que múltiplas threads possam
 * ler (consumir) e o callback possa escrever (produzir) mensagens simultaneamente
 * sem causar condições de corrida.
 * - Consumo Não Bloqueante: O método try_pop_message() permite que as threads
 * verifiquem se há mensagens em um tópico específico e as retirem da fila
 * de forma segura e sem bloquear a execução caso a fila esteja vazia.
 */

#include "MqttClient.h"
#include <iostream>

// Construtor: Inicializa o cliente e tenta conectar ao broker.
MqttClient::MqttClient(const std::string& broker_addr,
                       const std::string& client_id)
    : client_(broker_addr, client_id), // Inicializa o cliente Paho
      cb_(this) // Inicializa o callback com um ponteiro para este objeto MqttClient
{
    // Configurações de conexão: sessão limpa (não lembra de assinaturas anteriores)
    connOpts_.set_clean_session(true);

    // Define o objeto de callback que a biblioteca Paho usará.
    client_.set_callback(cb_);

    // Modo MOCK: Se o endereço for "mock" ou vazio, não tenta conectar de verdade.
    // Útil para testes unitários ou desenvolvimento sem rede.
    if (broker_addr.empty() || broker_addr == "mock") {
        std::cout << "[MQTT] Rodando em modo MOCK (sem conexão ao broker).\n";
        connected_ = false;
    } else {
        // Tenta conectar ao broker real.
        try {
            std::cout << "[MQTT] Conectando ao broker " << broker_addr << "...\n";
            // A chamada connect() é assíncrona, o wait() faz ela bloquear até terminar.
            client_.connect(connOpts_)->wait();
            std::cout << "[MQTT] Conectado.\n";
            connected_ = true;
        }
        catch (const mqtt::exception& e) {
            std::cerr << "[MQTT] Erro ao conectar: " << e.what() << "\n";
            connected_ = false;
            // Em um sistema real, poderia haver lógica de reconexão aqui.
        }
    }
}

// Destrutor: Garante a desconexão limpa ao destruir o objeto.
MqttClient::~MqttClient()
{
    try {
        if (connected_) client_.disconnect()->wait();
    } catch (...) {} // Ignora exceções no destrutor
}

// Desconecta explicitamente do broker.
void MqttClient::disconnect()
{
    try {
        if (connected_) {
            client_.disconnect()->wait();
            connected_ = false;
        }
    } catch (...) {}
}

// Retorna o estado da conexão.
bool MqttClient::is_connected() const
{
    return connected_;
}

// Publica uma mensagem em um tópico.
// Retorna true se bem-sucedido, false caso contrário.
bool MqttClient::publish(const std::string& topic, const std::string& msg)
{
    try {
        // Publica a mensagem. O wait() garante que a função só retorne após o envio.
        // QoS padrão (0) é usado aqui implicitamente.
        client_.publish(topic, msg)->wait();
        return true;
    } catch (...) {
        return false;
    }
}

// Inscreve-se em um tópico para receber mensagens.
void MqttClient::subscribe_topic(const std::string& topic)
{
    try {
        // Assina o tópico com QoS 1 (pelo menos uma vez). wait() bloqueia até confirmar.
        client_.subscribe(topic, 1)->wait();
        std::cout << "[MQTT] Subscribed to " << topic << "\n";
    }
    catch (const mqtt::exception& e) {
        std::cerr << "[MQTT] Erro ao assinar tópico " << topic
                  << ": " << e.what() << "\n";
    }
}

// Tenta consumir uma mensagem de um tópico específico.
// Retorna std::nullopt se a fila estiver vazia, não bloqueia a thread chamadora.
std::optional<std::string> MqttClient::try_pop_message(const std::string& topic)
{
    // Bloqueia o mutex para acesso seguro ao mapa de filas.
    std::lock_guard<std::mutex> lock(q_mtx_);
    // Procura a fila correspondente ao tópico.
    auto it = queues_.find(topic);
    // Se o tópico não existe no mapa ou a fila está vazia, retorna nullopt.
    if (it == queues_.end()) return std::nullopt;
    if (it->second.empty()) return std::nullopt;

    // Pega a mensagem da frente da fila.
    std::string m = it->second.front();
    // Remove a mensagem da fila.
    it->second.pop();
    // Retorna a mensagem.
    return m;
}

// --- Implementação da classe interna Callback ---

// Este método é chamado automaticamente pela biblioteca Paho quando uma mensagem chega.
void MqttClient::Callback::message_arrived(mqtt::const_message_ptr msg)
{
    // Bloqueia o mutex do objeto pai (MqttClient) para acesso seguro às filas.
    std::lock_guard<std::mutex> lock(parent_->q_mtx_);
    // Insere a mensagem na fila correspondente ao seu tópico.
    // O operador [] do mapa cria uma nova fila se o tópico ainda não existir.
    parent_->queues_[msg->get_topic()].push(msg->get_payload_str());
}