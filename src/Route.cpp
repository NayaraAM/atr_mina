/*
 * Arquivo: Route.cpp
 * Finalidade:
 * Este arquivo contém a implementação dos métodos da classe Route, definida
 * em "Route.h". A classe Route é responsável pelo gerenciamento da coleção
 * de pontos de passagem (waypoints) que definem o caminho que o caminhão
 * autônomo deve seguir.
 *
 * Funcionalidades Implementadas:
 * - Gerenciamento do vetor interno de waypoints (adição, acesso, limpeza e
 * contagem de tamanho).
 * - Persistência de dados: Implementa a lógica para ler e escrever rotas em
 * arquivos de texto plano. O formato adotado é simples e legível, com um
 * ponto por linha contendo as coordenadas X, Y e, opcionalmente, a velocidade.
 * - Carregamento dinâmico: Além de arquivos, permite carregar uma rota a partir
 * de uma string, o que é útil para receber planos de rota via mensagens de
 * rede (MQTT).
 *
 * Bibliotecas Utilizadas:
 * - fstream: Para operações de entrada e saída em arquivos.
 * - sstream: Para processamento de strings (parsing de linhas de texto).
 * - iostream: Para operações de E/S padrão (embora pouco usada aqui).
 */

#include "Route.h"
#include <fstream>
#include <sstream>
#include <iostream>

// Adiciona um novo waypoint ao final da sequência atual.
void Route::addWaypoint(const Waypoint& wp) {
    waypoints.push_back(wp);
}

// Retorna o número total de waypoints na rota.
size_t Route::size() const {
    return waypoints.size();
}

// Operador de acesso (leitura): Retorna uma referência constante ao waypoint
// no índice especificado. Usa .at() para garantir verificação de limites (lança exceção se inválido).
const Waypoint& Route::operator[](size_t idx) const {
    return waypoints.at(idx);
}

// Operador de acesso (leitura/escrita): Retorna uma referência modificável ao
// waypoint no índice especificado. Usa .at() para verificação de limites.
Waypoint& Route::operator[](size_t idx) {
    return waypoints.at(idx);
}

// Remove todos os waypoints, esvaziando a rota.
void Route::clear() {
    waypoints.clear();
}

// Carrega uma rota a partir de um arquivo de texto no disco.
// Retorna true se o arquivo foi aberto e processado com sucesso.
bool Route::loadFromFile(const std::string& path) {
    std::ifstream ifs(path);
    if (!ifs.is_open()) return false; // Falha ao abrir o arquivo

    waypoints.clear(); // Limpa a rota atual antes de carregar a nova
    std::string line;
    // Lê o arquivo linha por linha
    while (std::getline(ifs, line)) {
        // Usa um stringstream para fazer o parsing dos valores numéricos na linha
        std::istringstream iss(line);
        double x, y, s = 0.0;
        // Tenta ler pelo menos X e Y. Se falhar, ignora a linha (permite linhas em branco ou mal formadas).
        if (!(iss >> x >> y)) continue;

        // Tenta ler a velocidade (s). Se existir, usa; senão, assume 0.0.
        if (iss >> s) {
            waypoints.emplace_back(x, y, s);
        } else {
            waypoints.emplace_back(x, y, 0.0);
        }
    }
    return true;
}

// Carrega uma rota a partir de uma string contendo dados multilinha.
// Útil para receber rotas inteiras via payload MQTT sem precisar salvar em disco.
bool Route::loadFromString(const std::string& content) {
    std::istringstream ifs(content); // Trata a string como um stream de entrada
    waypoints.clear();
    std::string line;
    while (std::getline(ifs, line)) {
        // Remove espaços em branco no início da linha (trim leading spaces)
        size_t p = 0;
        while (p < line.size() && isspace((unsigned char)line[p])) ++p;
        if (p == line.size()) continue; // Linha vazia ou só espaços
        if (line[p] == '#') continue;   // Ignora linhas de comentário iniciadas por '#'

        // Parsing da linha (similar ao loadFromFile)
        std::istringstream iss(line);
        double x, y, s = 0.0;
        if (!(iss >> x >> y)) continue; // pula linha inválida
        if (iss >> s) {
            waypoints.emplace_back(x, y, s);
        } else {
            waypoints.emplace_back(x, y, 0.0);
        }
    }
    return true;
}

// Salva a rota atual em um arquivo de texto no disco.
// Retorna true se a gravação foi bem-sucedida.
bool Route::saveToFile(const std::string& path) const {
    std::ofstream ofs(path);
    if (!ofs.is_open()) return false; // Falha ao criar/abrir o arquivo

    // Itera sobre os waypoints e escreve cada um em uma linha no formato "X Y Speed"
    for (const auto& wp : waypoints) {
        ofs << wp.x << " " << wp.y << " " << wp.speed << "\n";
    }
    return true;
}