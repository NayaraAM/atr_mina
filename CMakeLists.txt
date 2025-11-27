cmake_minimum_required(VERSION 3.10)
project(ATR_MINA)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)

# ============================================================
# PAHO MQTT C (1.3.12) — SOMENTE ASYNC (paho-mqtt3a-static)
# ============================================================
set(PAHO_WITH_SSL OFF CACHE BOOL "" FORCE)
set(PAHO_ENABLE_TESTING OFF CACHE BOOL "" FORCE)
set(PAHO_BUILD_SAMPLES OFF CACHE BOOL "" FORCE)
set(PAHO_BUILD_STATIC ON CACHE BOOL "" FORCE)
set(PAHO_BUILD_SHARED OFF CACHE BOOL "" FORCE)
set(PAHO_BUILD_SYNC OFF CACHE BOOL "" FORCE)

FetchContent_Declare(
    paho_c
    URL https://github.com/eclipse/paho.mqtt.c/archive/refs/tags/v1.3.12.tar.gz
)

FetchContent_MakeAvailable(paho_c)

# ============================================================
# PAHO MQTT C++ (1.3.2) — compatível com paho-c 1.3.12
# ============================================================
set(PAHO_BUILD_STATIC ON CACHE BOOL "" FORCE)
set(PAHO_BUILD_SHARED OFF CACHE BOOL "" FORCE)
set(PAHO_ENABLE_TESTING OFF CACHE BOOL "" FORCE)
set(PAHO_BUILD_SAMPLES OFF CACHE BOOL "" FORCE)

FetchContent_Declare(
    paho_cpp
    URL https://github.com/eclipse/paho.mqtt.cpp/archive/refs/tags/v1.3.2.tar.gz
)

FetchContent_MakeAvailable(paho_cpp)

# ============================================================
# GoogleTest (opcional para testes unitários)
# ============================================================
include(FetchContent)
FetchContent_Declare(
    googletest
    URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.tar.gz
)
# For Windows: prevent overriding the parent project's compiler/linker settings
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

# ============================================================
# YOUR PROJECT
# ============================================================
include_directories(include)

file(GLOB SOURCES "src/*.cpp")

add_executable(atr_mina ${SOURCES})

target_link_libraries(atr_mina
    paho-mqtt3a-static       # async C lib
    paho-mqttpp3-static      # C++ wrapper
    pthread
)

enable_testing()

# --- tests --------------------------------------------------
file(GLOB TEST_SOURCES "tests/*.cpp")
if(TEST_SOURCES)
    add_executable(test_route ${TEST_SOURCES} src/Route.cpp)
    target_include_directories(test_route PRIVATE ${CMAKE_SOURCE_DIR}/include)
    target_link_libraries(test_route gtest_main pthread)
    add_test(NAME route_tests COMMAND test_route)
endif()
