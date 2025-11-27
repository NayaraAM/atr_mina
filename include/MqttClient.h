#pragma once
#include <string>
#include <queue>
#include <mutex>
#include <unordered_map>
#include <optional>
#include <thread>
#include <atomic>
#include <condition_variable>

#include <mqtt/async_client.h>   // PAHO MQTT C++

/**
 * Classe MqttClient
 * -----------------
 * Wrapper simplificado para o PAHO MQTT C++ que:
 *   - Assina tópicos dinamicamente
 *   - Armazena mensagens recebidas em filas thread-safe
 *   - Permite try_pop_message(topic) em qualquer thread
 *   - Publica mensagens com publish(topic, payload)
 *
 * Diferença desta versão:
 *   ✔ Não bloqueia
 *   ✔ Mais resiliente a erros
 *   ✔ Suporta múltiplos tópicos simultaneamente
 *   ✔ Usa filas separadas por tópico
 */
class MqttClient
{
public:
    MqttClient(const std::string& broker_addr,
               const std::string& client_id);

    ~MqttClient();

    // Desconecta do broker (não lança)
    void disconnect();

    // Retorna verdadeiro se o cliente estiver conectado ao broker
    bool is_connected() const;

    bool publish(const std::string& topic, const std::string& msg);

    // Consome uma mensagem se houver — não bloqueia
    std::optional<std::string> try_pop_message(const std::string& topic);

    // Inscreve-se dinamicamente (a maioria das threads usa isso)
    void subscribe_topic(const std::string& topic);

private:
    mqtt::async_client client_;
    mqtt::connect_options connOpts_;

    // Filas por tópico
    std::unordered_map<std::string, std::queue<std::string>> queues_;
    std::mutex q_mtx_;

    // Callback interno PAHO
    class Callback : public virtual mqtt::callback
    {
    public:
        Callback(MqttClient* parent) : parent_(parent) {}
        void message_arrived(mqtt::const_message_ptr msg) override;

    private:
        MqttClient* parent_;
    };

    Callback cb_;
    bool connected_ = false;
};
