#include "Route.h"
#include <fstream>
#include <sstream>
#include <iostream>

void Route::addWaypoint(const Waypoint& wp) {
    waypoints.push_back(wp);
}

size_t Route::size() const {
    return waypoints.size();
}

const Waypoint& Route::operator[](size_t idx) const {
    return waypoints.at(idx);
}

Waypoint& Route::operator[](size_t idx) {
    return waypoints.at(idx);
}

void Route::clear() {
    waypoints.clear();
}

bool Route::loadFromFile(const std::string& path) {
    std::ifstream ifs(path);
    if (!ifs.is_open()) return false;

    waypoints.clear();
    std::string line;
    while (std::getline(ifs, line)) {
        // permitir comentários e linhas em branco
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

bool Route::loadFromString(const std::string& content) {
    std::istringstream ifs(content);
    waypoints.clear();
    std::string line;
    while (std::getline(ifs, line)) {
        // trim leading spaces
        size_t p = 0;
        while (p < line.size() && isspace((unsigned char)line[p])) ++p;
        if (p == line.size()) continue;
        if (line[p] == '#') continue; // comentário
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

bool Route::saveToFile(const std::string& path) const {
    std::ofstream ofs(path);
    if (!ofs.is_open()) return false;
    for (const auto& wp : waypoints) {
        ofs << wp.x << " " << wp.y << " " << wp.speed << "\n";
    }
    return true;
}
