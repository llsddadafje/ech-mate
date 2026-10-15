#ifndef EVENT_QUEUE_H
#define EVENT_QUEUE_H

#include <queue>
#include <mutex>
#include <condition_variable>
#include <optional>

template <typename T>
class EventQueue {
public:
    void Enqueue(const T& event) {
        std::lock_guard<std::mutex> lock(mutex_);//创建一个叫 lock 的锁对象，它管
        //理 mutex_lock 对象的生命周期就是整个 Enqueue() 函数结束之前。
        queue_.push(event);
        cond_var_.notify_one();
    
    }

    std::optional<T> Dequeue() {
        std::unique_lock<std::mutex> lock(mutex_);
        cond_var_.wait(lock, [this]() { return !queue_.empty(); });
        T event = queue_.front();
        queue_.pop();
        return event;
    }

    bool IsEmpty() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return queue_.empty();
    }

private:
    std::queue<T> queue_;//事件队列
    mutable std::mutex mutex_;
    std::condition_variable cond_var_;
};

#endif // EVENT_QUEUE_H