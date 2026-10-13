#pragma once
#include <condition_variable>
#include <mutex>
#include <queue>
#include <string>

namespace bridge {

struct Message {
    std::string id;    // UUID from JSON "id" field
    std::string json;  // full raw JSON line
};

/**
 * Thread-safe FIFO queue used to pass messages between
 * the Arma SQF thread (RVExtension) and the pipe I/O thread.
 */
class MessageQueue {
public:
    void push(Message msg);

    /**
     * Try to pop one message.
     * @param out   receives the message if available
     * @param timeout_ms  0 = non-blocking; >0 = wait up to N ms
     * @return true if a message was returned
     */
    bool try_pop(Message& out, int timeout_ms = 0);

    void clear();

private:
    std::queue<Message> queue_;
    std::mutex          mutex_;
    std::condition_variable cv_;
};

} // namespace bridge
