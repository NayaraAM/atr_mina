#ifndef ROUTE_H
#define ROUTE_H

#include <vector>
#include <string>

struct Waypoint {
    double x{0.0};
    double y{0.0};
    double speed{0.0};

    Waypoint() = default;
    Waypoint(double _x, double _y, double _s = 0.0) : x(_x), y(_y), speed(_s) {}
};

class Route {
public:
    Route() = default;

    void addWaypoint(const Waypoint& wp);
    size_t size() const;
    const Waypoint& operator[](size_t idx) const;
    Waypoint& operator[](size_t idx);

    bool loadFromFile(const std::string& path); // formato texto: x y [speed] por linha
    bool loadFromString(const std::string& content); // carrega a partir de um payload de texto (mesmo formato de arquivo)
    bool saveToFile(const std::string& path) const;
    void clear();

private:
    std::vector<Waypoint> waypoints;
};

#endif // ROUTE_H
