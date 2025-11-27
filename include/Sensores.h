#pragma once
#include <deque>
#include "SensorData.h"

class Sensores {
public:
    explicit Sensores(int ordem);

    SensorData filtrar(const SensorData& raw);

private:
    int ordem_;
    std::deque<SensorData> janela_;
};
