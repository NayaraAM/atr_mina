/*
 * Arquivo: MqttClient.h
 * Finalidade:
 * Este arquivo de cabeçalho define a classe MqttClient, que atua como um
 * wrapper (encapsulador) simplificado e thread-safe para a biblioteca Paho MQTT C++.
 * O objetivo principal é fornecer uma interface fácil de usar para que as
 * diferentes threads do sistema embarcado possam publicar e assinar tópicos MQTT,
 * permitindo a comunicação com sistemas externos (como a interface de gestão ou
 * a interface local) de forma assíncrona e sem bloqueios.
 *
 * Características Principais:
 * - Assinatura Dinâmica: Permite que qualquer thread assine novos tópicos
 * durante a execução (subscribe_topic).
 * - Filas por Tópico: Armazena as mensagens recebidas em filas separadas para
 * cada tópico, garantindo que as mensagens de diferentes assuntos não se
 * misturem.
 * - Thread-safe: Utiliza um mutex (q_mtx_) para proteger o acesso concorrente
 * às filas de mensagens (queues_), permitindo que múltiplas threads leiam
 * e escrevam simultaneamente de forma segura.
 * - Não Bloqueante: O método try_pop_message permite que as threads consumidoras
 * verifiquem se há novas mensagens em um tópico sem bloquear sua execução
 * caso a fila esteja vazia.
 * - Publicação: Oferece um método simples (publish) para enviar mensagens
 * para um tópico específico.
 * - Resiliência: Projetado para ser mais robusto a erros e desconexões.
 *
 * Componentes Internos:
 * - client_: Instância do cliente assíncrono Paho MQTT.
 * - connOpts_: Opções de conexão MQTT.
 * - queues_: Um mapa (unordered_map) que associa cada tópico a uma fila (queue)
 * de strings, armazenando as mensagens recebidas.
 * - q_mtx_: Mutex para sincronizar o acesso ao mapa queues_.
 * - Callback: Uma classe interna que herda de mqtt::callback, responsável por
 * receber as mensagens do broker MQTT e colocá-las na fila correta.
 * - cb_: Instância da classe Callback.
 * - connected_: Flag que indica se o cliente está conectado ao broker.
 */

#pragma once
#include <string>
#include <queue>
#include <mutex>
#include <unordered_map>
#include <optional>
#include <thread>
#include <atomic>
#include <condition_variable>

#include <mqtt/async_client.h>   // Inclui a biblioteca Paho MQTT C++

/**
 * Classe MqttClient
 * -----------------
 * Wrapper simplificado para o PAHO MQTT C++ que:
 * ... (restante dos comentários originais)
 */
class MqttClient
{
public:
    // Construtor: Inicializa o cliente MQTT com o endereço do broker e o ID do cliente.
    MqttClient(const std::string& broker_addr,
               const std::string& client_id);

    // Destrutor: Garante a desconexão limpa do broker.
    ~MqttClient();

    // Desconecta do broker (não lança exceções).
    void disconnect();

    // Retorna verdadeiro se o cliente estiver conectado ao broker.
    bool is_connected() const;

    // Publica uma mensagem em um tópico específico. Retorna true se bem-sucedido.
    bool publish(const std::string& topic, const std::string& msg);

    // Tenta consumir uma mensagem de um tópico. Retorna std::nullopt se a fila estiver vazia (não bloqueia).
    std::optional<std::string> try_pop_message(const std::string& topic);

    // Inscreve-se dinamicamente em um tópico para receber mensagens.
    void subscribe_topic(const std::string& topic);

private:
    mqtt::async_client client_; // Cliente assíncrono Paho MQTT
    mqtt::connect_options connOpts_; // Opções de conexão

    // Mapa de filas por tópico: topic -> queue<message>
    std::unordered_map<std::string, std::queue<std::string>> queues_;
    std::mutex q_mtx_; // Mutex para proteger o acesso ao mapa queues_

    // Callback interno PAHO para tratar eventos (como chegada de mensagens)
    class Callback : public virtual mqtt::callback
    {
    public:
        Callback(MqttClient* parent) : parent_(parent) {}
        // Chamado quando uma mensagem chega do broker
        void message_arrived(mqtt::const_message_ptr msg) override;

    private:
        MqttClient* parent_; // Ponteiro para o objeto MqttClient pai
    };

    Callback cb_; // Instância do callback
    bool connected_ = false; // Estado da conexão
};