/*
 * Arquivo: Route.h
 * Finalidade:
 * Este arquivo de cabeçalho define a estrutura Waypoint e a classe Route,
 * responsáveis por gerenciar a rota que o caminhão autônomo deve seguir.
 * Uma rota é composta por uma sequência de pontos de passagem (waypoints),
 * cada um contendo coordenadas espaciais (x, y) e, opcionalmente, uma velocidade
 * alvo para aquele trecho. A classe Route fornece funcionalidades para
 * criar, armazenar, acessar, carregar (de arquivo ou string) e salvar
 * (em arquivo) esses pontos.
 *
 * Estrutura Waypoint:
 * - Representa um único ponto na rota.
 * - Campos:
 * - x: Coordenada X do ponto.
 * - y: Coordenada Y do ponto.
 * - speed: Velocidade alvo ao passar por este ponto (opcional, padrão 0.0).
 * - Construtores: Padrão e com parâmetros para fácil inicialização.
 *
 * Classe Route:
 * - Gerencia uma coleção de Waypoints.
 * - Métodos Públicos:
 * - addWaypoint(const Waypoint& wp): Adiciona um novo waypoint ao final da rota.
 * - size() const: Retorna o número total de waypoints na rota.
 * - operator[](size_t idx): Sobrecarga do operador de acesso para obter um
 * waypoint específico pelo índice (versões const e não-const).
 * - loadFromFile(const std::string& path): Carrega waypoints de um arquivo de texto.
 * O formato esperado é "x y [speed]" por linha.
 * - loadFromString(const std::string& content): Carrega waypoints de uma string,
 * seguindo o mesmo formato do arquivo de texto. Útil para receber rotas via MQTT.
 * - saveToFile(const std::string& path) const: Salva a rota atual em um arquivo de texto.
 * - clear(): Limpa todos os waypoints da rota atual.
 * - Membros Privados:
 * - waypoints: Um std::vector que armazena a sequência de objetos Waypoint.
 */

#ifndef ROUTE_H
#define ROUTE_H

#include <vector> // Inclui a biblioteca para uso do std::vector
#include <string> // Inclui a biblioteca para uso do std::string

// Estrutura que representa um ponto de passagem na rota
struct Waypoint {
    double x{0.0};     // Coordenada X
    double y{0.0};     // Coordenada Y
    double speed{0.0}; // Velocidade alvo (opcional)

    Waypoint() = default; // Construtor padrão
    // Construtor com parâmetros para inicialização conveniente
    Waypoint(double _x, double _y, double _s = 0.0) : x(_x), y(_y), speed(_s) {}
};

// Classe que gerencia uma rota completa (sequência de waypoints)
class Route {
public:
    Route() = default; // Construtor padrão

    // Adiciona um waypoint ao final da rota
    void addWaypoint(const Waypoint& wp);

    // Retorna o número de waypoints na rota
    size_t size() const;

    // Acesso a um waypoint pelo índice (somente leitura)
    const Waypoint& operator[](size_t idx) const;

    // Acesso a um waypoint pelo índice (leitura e escrita)
    Waypoint& operator[](size_t idx);

    // Carrega a rota a partir de um arquivo de texto
    // Formato: x y [speed] por linha
    bool loadFromFile(const std::string& path);

    // Carrega a rota a partir de uma string (mesmo formato do arquivo)
    bool loadFromString(const std::string& content);

    // Salva a rota atual em um arquivo de texto
    bool saveToFile(const std::string& path) const;

    // Limpa todos os waypoints da rota
    void clear();

private:
    // Vetor que armazena a sequência de waypoints
    std::vector<Waypoint> waypoints;
};

#endif // ROUTE_H