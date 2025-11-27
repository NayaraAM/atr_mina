#pragma once

// BufferCircular.h
// Header-only, thread-safe circular buffer (ring buffer) para uso em multi-threads.
// Implementação simples, com push (sobrescreve quando cheio) e try_pop (não bloqueante).
//
// Recursos:
//  - push(const T&)  : copia
//  - push(T&&)       : move
//  - try_pop(T&)     : tenta remover o item mais antigo (não bloqueante)
//  - try_peek(T&)    : obtém uma cópia do item mais antigo sem remover
//  - size(), capacity(), empty()
//
// Observação:
//  - A implementação usa mutex para sincronização (std::mutex).
//  - Projetado para simplicidade e segurança; desempenho é adequado para cenários didáticos.
//  - Para uso intensivo com requisitos muito altos de throughput, considerar implementação lock-free.

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
    explicit BufferCircular(size_t cap)
    {
        if (cap == 0) throw std::invalid_argument("BufferCircular capacity must be > 0");
        data_.resize(cap);
        cap_ = cap;
        head_ = 0;
        tail_ = 0;
        count_ = 0;
    }

    // copia
    void push(const T& v)
    {
        std::lock_guard<std::mutex> lg(mtx_);
        data_[head_] = v;
        head_ = (head_ + 1) % cap_;
        if (count_ < cap_) {
            ++count_;
        } else {
            // sobrescreve o mais antigo
            tail_ = (tail_ + 1) % cap_;
        }
    }

    // move
    void push(T&& v)
    {
        std::lock_guard<std::mutex> lg(mtx_);
        data_[head_] = std::move(v);
        head_ = (head_ + 1) % cap_;
        if (count_ < cap_) {
            ++count_;
        } else {
            tail_ = (tail_ + 1) % cap_;
        }
        cv_.notify_one();
    }

    // push bloqueante com timeout (retorna false se timeout)
    template<typename Rep, typename Period>
    bool push_wait_for(const T& v, const std::chrono::duration<Rep, Period>& timeout)
    {
        std::unique_lock<std::mutex> lk(mtx_);
        if (!not_full_cv_.wait_for(lk, timeout, [this]{ return count_ < cap_; })) return false;
        data_[head_] = v;
        head_ = (head_ + 1) % cap_;
        ++count_;
        cv_.notify_one();
        return true;
    }

    template<typename Rep, typename Period>
    bool push_wait_for(T&& v, const std::chrono::duration<Rep, Period>& timeout)
    {
        std::unique_lock<std::mutex> lk(mtx_);
        if (!not_full_cv_.wait_for(lk, timeout, [this]{ return count_ < cap_; })) return false;
        data_[head_] = std::move(v);
        head_ = (head_ + 1) % cap_;
        ++count_;
        cv_.notify_one();
        return true;
    }

    // push bloqueante indefinido (espera até haver espaço)
    void push_wait(const T& v)
    {
        std::unique_lock<std::mutex> lk(mtx_);
        not_full_cv_.wait(lk, [this]{ return count_ < cap_; });
        data_[head_] = v;
        head_ = (head_ + 1) % cap_;
        ++count_;
        cv_.notify_one();
    }

    void push_wait(T&& v)
    {
        std::unique_lock<std::mutex> lk(mtx_);
        not_full_cv_.wait(lk, [this]{ return count_ < cap_; });
        data_[head_] = std::move(v);
        head_ = (head_ + 1) % cap_;
        ++count_;
        cv_.notify_one();
    }

    // tenta remover o item mais antigo; retorna true se havia item
    bool try_pop(T& out)
    {
        std::lock_guard<std::mutex> lg(mtx_);
        if (count_ == 0) return false;
        out = std::move(data_[tail_]); // move se possível
        tail_ = (tail_ + 1) % cap_;
        --count_;
        not_full_cv_.notify_one();
        return true;
    }

    // tenta obter (pegar) o item mais antigo sem remover
    bool try_peek(T& out) const
    {
        std::lock_guard<std::mutex> lg(mtx_);
        if (count_ == 0) return false;
        out = data_[tail_];
        return true;
    }

    // espera até que haja um item ou timeout; retorna true se obteve o item
    template<typename Rep, typename Period>
    bool pop_wait_for(T& out, const std::chrono::duration<Rep, Period>& timeout)
    {
        std::unique_lock<std::mutex> lg(mtx_);
        if (!cv_.wait_for(lg, timeout, [this]{ return count_ > 0; })) return false;
        out = std::move(data_[tail_]);
        tail_ = (tail_ + 1) % cap_;
        --count_;
        not_full_cv_.notify_one();
        return true;
    }

    // espera indefinidamente até obter um item
    void pop_wait(T& out)
    {
        std::unique_lock<std::mutex> lg(mtx_);
        cv_.wait(lg, [this]{ return count_ > 0; });
        out = std::move(data_[tail_]);
        tail_ = (tail_ + 1) % cap_;
        --count_;
        not_full_cv_.notify_one();
    }

    // retorna número atual de elementos
    size_t size() const
    {
        std::lock_guard<std::mutex> lg(mtx_);
        return count_;
    }

    // capacidade do buffer
    size_t capacity() const noexcept { return cap_; }

    bool empty() const { return size() == 0; }

    // limpa conteúdo (thread-safe)
    void clear()
    {
        std::lock_guard<std::mutex> lg(mtx_);
        head_ = tail_ = count_ = 0;
        cv_.notify_all();
        not_full_cv_.notify_all();
    }

private:
    std::vector<T> data_;
    size_t cap_ = 0;
    size_t head_ = 0;   // posição onde próximo elemento será escrito
    size_t tail_ = 0;   // posição do elemento mais antigo
    size_t count_ = 0;  // número de elementos atualmente no buffer

    mutable std::mutex mtx_;
    std::condition_variable cv_;
    std::condition_variable not_full_cv_;
};
