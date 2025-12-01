/*
 * Arquivo: BufferCircular.h
 * Finalidade:
 * Este arquivo de cabeçalho define a classe de template BufferCircular, que
 * implementa um buffer circular (ring buffer) genérico e seguro para uso em
 * ambientes multitarefa (thread-safe). O buffer circular é uma estrutura de
 * dados eficiente para comunicação entre threads produtoras (que inserem dados)
 * e consumidoras (que removem dados), permitindo que elas trabalhem em
 * velocidades diferentes sem bloquear excessivamente uma à outra.
 *
 * Características:
 * - Thread-safe: Utiliza mutex e variáveis de condição para sincronizar o
 * acesso concorrente aos dados.
 * - Genérico: Pode armazenar qualquer tipo de dado (template<typename T>).
 * - Capacidade fixa: O tamanho do buffer é definido na criação e não muda.
 * - Sobrescrita: Se o buffer estiver cheio e um novo dado for inserido (push_force),
 * o dado mais antigo é sobrescrito.
 * - Operações bloqueantes e não bloqueantes: Oferece métodos para inserir e
 * remover dados com diferentes comportamentos (esperar, não esperar, esperar com timeout).
 *
 * Métodos Principais:
 * - push_force(const T& v) / push_force(T&& v): Insere um elemento no buffer.
 * Se estiver cheio, sobrescreve o elemento mais antigo. Não bloqueia.
 * - push_wait(const T& v) / push_wait(T&& v): Insere um elemento no buffer.
 * Se estiver cheio, bloqueia a thread até que haja espaço.
 * - try_pop(T& out): Tenta remover o elemento mais antigo do buffer. Retorna
 * true se conseguiu, false se o buffer estava vazio. Não bloqueia.
 * - pop_wait(T& out): Remove o elemento mais antigo do buffer. Se estiver
 * vazio, bloqueia a thread até que haja um elemento disponível.
 * - size(): Retorna o número atual de elementos no buffer.
 * - capacity(): Retorna a capacidade total do buffer.
 * - empty(): Retorna true se o buffer estiver vazio, false caso contrário.
 * - clear(): Esvazia o buffer.
 */

#pragma once

// BufferCircular.h
// Header-only, thread-safe circular buffer (ring buffer) para uso em multi-threads.
// Implementação simples, com push (sobrescreve quando cheio) e try_pop (não bloqueante).
// ... (restante dos comentários originais)

#include <vector>
#include <mutex>
#include <condition_variable>
#include <chrono>
#include <optional>
#include <cstddef>
#include <stdexcept>

template<typename T>
class BufferCircular
{
public:
    // Construtor: Inicializa o buffer com a capacidade especificada.
    explicit BufferCircular(size_t cap)
    {
        if (cap == 0) throw std::invalid_argument("BufferCircular capacity must be > 0");
        data_.resize(cap); // Aloca espaço para os elementos
        cap_ = cap;        // Define a capacidade
        head_ = 0;         // Inicializa o índice de escrita
        tail_ = 0;         // Inicializa o índice de leitura
        count_ = 0;        // Inicializa o contador de elementos
    }

    // push_force (copia): Insere um elemento, sobrescrevendo se necessário.
    void push_force(const T& v)
    {
        std::lock_guard<std::mutex> lg(mtx_); // Bloqueia o mutex
        data_[head_] = v; // Copia o elemento para a posição atual de escrita
        head_ = (head_ + 1) % cap_; // Avança o índice de escrita circularmente
        if (count_ < cap_) {
            ++count_; // Incrementa o contador se não estava cheio
        } else {
            // Se estava cheio, o elemento mais antigo foi sobrescrito,
            // então avança o índice de leitura circularmente.
            tail_ = (tail_ + 1) % cap_;
        }
        cv_.notify_one(); // Notifica uma thread consumidora que há dados
    }

    // push_force (move): Versão para mover elementos (mais eficiente para tipos complexos).
    void push_force(T&& v)
    {
        std::lock_guard<std::mutex> lg(mtx_); // Bloqueia o mutex
        data_[head_] = std::move(v); // Move o elemento para a posição atual de escrita
        head_ = (head_ + 1) % cap_; // Avança o índice de escrita circularmente
        if (count_ < cap_) {
            ++count_; // Incrementa o contador se não estava cheio
        } else {
            // Se estava cheio, o elemento mais antigo foi sobrescrito,
            // então avança o índice de leitura circularmente.
            tail_ = (tail_ + 1) % cap_;
        }
        cv_.notify_one(); // Notifica uma thread consumidora que há dados
    }

    // push_wait_for: Insere um elemento, esperando até o timeout se estiver cheio.
    template<typename Rep, typename Period>
    bool push_wait_for(const T& v, const std::chrono::duration<Rep, Period>& timeout)
    {
        std::unique_lock<std::mutex> lk(mtx_); // Bloqueia o mutex
        // Espera até que haja espaço ou o tempo limite expire
        if (!not_full_cv_.wait_for(lk, timeout, [this]{ return count_ < cap_; })) return false;
        data_[head_] = v; // Copia o elemento
        head_ = (head_ + 1) % cap_; // Avança o índice de escrita
        ++count_; // Incrementa o contador
        cv_.notify_one(); // Notifica uma thread consumidora
        return true;
    }

    // push_wait_for (move): Versão para mover elementos.
    template<typename Rep, typename Period>
    bool push_wait_for(T&& v, const std::chrono::duration<Rep, Period>& timeout)
    {
        std::unique_lock<std::mutex> lk(mtx_); // Bloqueia o mutex
        // Espera até que haja espaço ou o tempo limite expire
        if (!not_full_cv_.wait_for(lk, timeout, [this]{ return count_ < cap_; })) return false;
        data_[head_] = std::move(v); // Move o elemento
        head_ = (head_ + 1) % cap_; // Avança o índice de escrita
        ++count_; // Incrementa o contador
        cv_.notify_one(); // Notifica uma thread consumidora
        return true;
    }

    // push_wait: Insere um elemento, esperando indefinidamente se estiver cheio.
    void push_wait(const T& v)
    {
        std::unique_lock<std::mutex> lk(mtx_); // Bloqueia o mutex
        // Espera até que haja espaço
        not_full_cv_.wait(lk, [this]{ return count_ < cap_; });
        data_[head_] = v; // Copia o elemento
        head_ = (head_ + 1) % cap_; // Avança o índice de escrita
        ++count_; // Incrementa o contador
        cv_.notify_one(); // Notifica uma thread consumidora
    }

    // push_wait (move): Versão para mover elementos.
    void push_wait(T&& v)
    {
        std::unique_lock<std::mutex> lk(mtx_); // Bloqueia o mutex
        // Espera até que haja espaço
        not_full_cv_.wait(lk, [this]{ return count_ < cap_; });
        data_[head_] = std::move(v); // Move o elemento
        head_ = (head_ + 1) % cap_; // Avança o índice de escrita
        ++count_; // Incrementa o contador
        cv_.notify_one(); // Notifica uma thread consumidora
    }

    // try_pop: Tenta remover o elemento mais antigo. Não bloqueia.
    bool try_pop(T& out)
    {
        std::lock_guard<std::mutex> lg(mtx_); // Bloqueia o mutex
        if (count_ == 0) return false; // Retorna false se vazio
        out = std::move(data_[tail_]); // Move o elemento para a variável de saída
        tail_ = (tail_ + 1) % cap_; // Avança o índice de leitura circularmente
        --count_; // Decrementa o contador
        not_full_cv_.notify_one(); // Notifica uma thread produtora que há espaço
        return true;
    }

    // try_peek: Tenta obter o elemento mais antigo sem remover. Não bloqueia.
    bool try_peek(T& out) const
    {
        std::lock_guard<std::mutex> lg(mtx_); // Bloqueia o mutex
        if (count_ == 0) return false; // Retorna false se vazio
        out = data_[tail_]; // Copia o elemento para a variável de saída
        return true;
    }

    // pop_wait_for: Remove o elemento mais antigo, esperando até o timeout se estiver vazio.
    template<typename Rep, typename Period>
    bool pop_wait_for(T& out, const std::chrono::duration<Rep, Period>& timeout)
    {
        std::unique_lock<std::mutex> lg(mtx_); // Bloqueia o mutex
        // Espera até que haja dados ou o tempo limite expire
        if (!cv_.wait_for(lg, timeout, [this]{ return count_ > 0; })) return false;
        out = std::move(data_[tail_]); // Move o elemento
        tail_ = (tail_ + 1) % cap_; // Avança o índice de leitura
        --count_; // Decrementa o contador
        not_full_cv_.notify_one(); // Notifica uma thread produtora
        return true;
    }

    // pop_wait: Remove o elemento mais antigo, esperando indefinidamente se estiver vazio.
    void pop_wait(T& out)
    {
        std::unique_lock<std::mutex> lg(mtx_); // Bloqueia o mutex
        // Espera até que haja dados
        cv_.wait(lg, [this]{ return count_ > 0; });
        out = std::move(data_[tail_]); // Move o elemento
        tail_ = (tail_ + 1) % cap_; // Avança o índice de leitura
        --count_; // Decrementa o contador
        not_full_cv_.notify_one(); // Notifica uma thread produtora
    }

    // size: Retorna o número atual de elementos no buffer.
    size_t size() const
    {
        std::lock_guard<std::mutex> lg(mtx_); // Bloqueia o mutex
        return count_;
    }

    // capacity: Retorna a capacidade total do buffer.
    size_t capacity() const noexcept { return cap_; }

    // empty: Retorna true se o buffer estiver vazio.
    bool empty() const { return size() == 0; }

    // clear: Esvazia o buffer.
    void clear()
    {
        std::lock_guard<std::mutex> lg(mtx_); // Bloqueia o mutex
        head_ = tail_ = count_ = 0; // Reseta os índices e o contador
        cv_.notify_all(); // Notifica todas as threads consumidoras (que podem estar esperando dados)
        not_full_cv_.notify_all(); // Notifica todas as threads produtoras (que podem estar esperando espaço)
    }

private:
    std::vector<T> data_; // Vetor para armazenar os elementos
    size_t cap_ = 0;      // Capacidade total do buffer
    size_t head_ = 0;     // Índice onde o próximo elemento será escrito
    size_t tail_ = 0;     // Índice do elemento mais antigo (próximo a ser lido)
    size_t count_ = 0;    // Número atual de elementos no buffer

    mutable std::mutex mtx_; // Mutex para sincronização
    std::condition_variable cv_; // Variável de condição para notificar consumidores (buffer não vazio)
    std::condition_variable not_full_cv_; // Variável de condição para notificar produtores (buffer não cheio)
};