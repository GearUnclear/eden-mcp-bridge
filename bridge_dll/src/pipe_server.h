#pragma once
#include "message_queue.h"
#include <atomic>
#include <functional>
#include <string>
#include <windows.h>

namespace bridge {

/**
 * Named-pipe server that runs on its own thread.
 *
 * Lifecycle:
 *   PipeServer server;
 *   server.set_callback(fn);   // optional: called for async events to SQF
 *   server.start();            // spawns I/O thread, creates pipe
 *   ...
 *   server.stop();             // signals thread to exit, waits for it
 *
 * The pipe name is \\.\pipe\arma3_mcp_bridge (configurable via PIPE_NAME).
 */
class PipeServer {
public:
    static constexpr wchar_t PIPE_NAME[] = L"\\\\.\\pipe\\arma3_mcp_bridge";
    static constexpr DWORD   BUFFER_SIZE = 65536;

    using CallbackFn = std::function<void(const std::string& name,
                                          const std::string& function,
                                          const std::string& data)>;

    PipeServer(MessageQueue& inbound, MessageQueue& outbound);
    ~PipeServer();

    void set_callback(CallbackFn fn);
    void start();
    void stop();
    void set_editor_ready(bool ready);
    bool poll_command(Message& out, size_t max_size);

private:
    MessageQueue& inbound_;    // Python -> SQF
    MessageQueue& outbound_;   // SQF -> Python
    std::mutex session_mutex_;
    bool editor_ready_{ false };

    CallbackFn    callback_;
    std::atomic<bool> running_{ false };
    HANDLE        thread_{ INVALID_HANDLE_VALUE };
    HANDLE        pipe_{ INVALID_HANDLE_VALUE };

    static DWORD WINAPI thread_proc(LPVOID param);
    void run();

    bool create_pipe();
    bool wait_for_client();
    void serve_client();
    void close_pipe();
    void accept_command(const std::string& line);

    // Write a '\n'-terminated line; returns false on disconnect
    bool write_line(const std::string& line);
};

} // namespace bridge
