/*
 * Arquivo: Sensores.h
 * Finalidade:
 * Este arquivo de cabeçalho define a classe Sensores, responsável pelo
 * processamento e filtragem dos dados brutos lidos dos sensores do caminhão.
 * O principal objetivo desta classe é implementar um filtro de média móvel
 * para suavizar as leituras e reduzir o ruído, proporcionando dados mais
 * estáveis e confiáveis para as outras partes do sistema (como a navegação).
 * A classe mantém um histórico recente das leituras (uma janela) para
 * calcular a média.
 *
 * Métodos Públicos:
 * - Sensores(int ordem): Construtor da classe. Recebe como parâmetro a 'ordem'
 * do filtro, que determina o número de amostras passadas a serem consideradas
 * no cálculo da média móvel. Uma ordem maior resulta em uma filtragem mais
 * suave, mas pode introduzir um atraso maior na resposta do sistema.
 * - filtrar(const SensorData& raw): Método principal de processamento. Recebe
 * um objeto SensorData contendo as leituras brutas (raw) mais recentes.
 * Ele adiciona essa leitura à janela histórica, remove a leitura mais antiga
 * se a janela exceder a ordem definida, calcula a média dos valores na janela
 * e retorna um novo objeto SensorData com os valores filtrados.
 *
 * Membros Privados:
 * - ordem_: Armazena a ordem do filtro (tamanho da janela) definida no construtor.
 * - janela_: Um deque (double-ended queue) que armazena o histórico recente
 * de objetos SensorData. É usado para manter as amostras necessárias para
 * o cálculo da média móvel. O uso de um deque permite a inserção e remoção
 * eficientes em ambas as extremidades.
 */

#pragma once
#include <deque>     // Inclui a biblioteca para uso do std::deque
#include "SensorData.h" // Inclui a definição da estrutura SensorData

class Sensores {
public:
    // Construtor: Inicializa a classe com a ordem do filtro especificada.
    explicit Sensores(int ordem);

    // Método filtrar: Processa os dados brutos e retorna os dados filtrados.
    SensorData filtrar(const SensorData& raw);

private:
    int ordem_; // A ordem do filtro de média móvel (tamanho da janela)
    std::deque<SensorData> janela_; // Histórico recente das leituras dos sensores
};