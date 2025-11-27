#include "MqttClient.h"
#include <iostream>

MqttClient::MqttClient(const std::string& broker_addr,
                       const std::string& client_id)
    : client_(broker_addr, client_id),
      cb_(this)
{
    connOpts_.set_clean_session(true);

    client_.set_callback(cb_);

    // Se o endereço do broker for "mock" ou vazio, não tenta conectar
    if (broker_addr.empty() || broker_addr == "mock") {
        std::cout << "[MQTT] Rodando em modo MOCK (sem conexão ao broker).\n";
        connected_ = false;
    } else {
        try {
            std::cout << "[MQTT] Conectando ao broker " << broker_addr << "...\n";
            client_.connect(connOpts_)->wait();
            std::cout << "[MQTT] Conectado.\n";
            connected_ = true;
        }
        catch (const mqtt::exception& e) {
            std::cerr << "[MQTT] Erro ao conectar: " << e.what() << "\n";
            connected_ = false;
        }
    }
}

MqttClient::~MqttClient()
{
    try {
        if (connected_) client_.disconnect()->wait();
    } catch (...) {}
}

void MqttClient::disconnect()
{
    try {
        if (connected_) {
            client_.disconnect()->wait();
            connected_ = false;
        }
    } catch (...) {}
}

bool MqttClient::is_connected() const
{
    return connected_;
}

bool MqttClient::publish(const std::string& topic, const std::string& msg)
{
    try {
        client_.publish(topic, msg)->wait();
        return true;
    } catch (...) {
        return false;
    }
}

void MqttClient::subscribe_topic(const std::string& topic)
{
    try {
        client_.subscribe(topic, 1)->wait();
        std::cout << "[MQTT] Subscribed to " << topic << "\n";
    }
    catch (const mqtt::exception& e) {
        std::cerr << "[MQTT] Erro ao assinar tópico " << topic
                  << ": " << e.what() << "\n";
    }
}

std::optional<std::string> MqttClient::try_pop_message(const std::string& topic)
{
    std::lock_guard<std::mutex> lock(q_mtx_);
    auto it = queues_.find(topic);
    if (it == queues_.end()) return std::nullopt;
    if (it->second.empty()) return std::nullopt;

    std::string m = it->second.front();
    it->second.pop();
    return m;
}

void MqttClient::Callback::message_arrived(mqtt::const_message_ptr msg)
{
    std::lock_guard<std::mutex> lock(parent_->q_mtx_);
    parent_->queues_[msg->get_topic()].push(msg->get_payload_str());
}
