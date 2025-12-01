/*
 * Arquivo: BufferCircular.cpp
 * Finalidade:
 * Este arquivo de implementação (.cpp) está intencionalmente vazio.
 *
 * Motivo Técnico (C++ Templates):
 * A classe BufferCircular, definida no arquivo de cabeçalho correspondente
 * ("BufferCircular.h"), é uma classe template (template<typename T>).
 * Em C++, as definições completas de templates (incluindo a implementação
 * de seus métodos) devem estar disponíveis nos arquivos de cabeçalho onde
 * são declaradas.
 *
 * Isso é necessário porque o compilador precisa ter acesso ao código fonte
 * completo para gerar (instanciar) o código específico para cada tipo de dado
 * com o qual o template é usado no projeto (por exemplo,
 * BufferCircular<SensorData> em main.cpp ou BufferCircular<std::string> em
 * Threads.cpp) no momento da compilação.
 *
 * Se a implementação dos métodos fosse movida para este arquivo .cpp, o
 * compilador conseguiria compilar este arquivo, mas o ligador (linker)
 * falharia ao tentar conectar as chamadas feitas em outros arquivos às
 * implementações concretas, resultando em erros de "referência indefinida"
 * (undefined reference).
 *
 * Portanto, para manter o design genérico e funcional, toda a lógica do
 * buffer circular reside exclusivamente em BufferCircular.h.
 */

// Arquivo vazio intencionalmente (implementação template está no header).