#include "message_queue.h"

namespace bridge {

void MessageQueue::push(Message msg) {
    {
        std::lock_guard<std::mutex> lock(mutex_);
        queue_.push(std::move(msg));
    }
    cv_.notify_one();
}

bool MessageQueue::try_pop(Message& out, int timeout_ms) {
    std::unique_lock<std::mutex> lock(mutex_);
    if (timeout_ms > 0) {
        cv_.wait_for(lock, std::chrono::milliseconds(timeout_ms),
                     [this] { return !queue_.empty(); });
    }
    if (queue_.empty()) return false;
    out = std::move(queue_.front());
    queue_.pop();
    return true;
}

void MessageQueue::clear() {
    std::lock_guard<std::mutex> lock(mutex_);
    while (!queue_.empty()) queue_.pop();
}

} // namespace bridge
