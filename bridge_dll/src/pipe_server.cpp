#include "pipe_server.h"
#include <cassert>
#include <string>
#include <vector>
#include <sddl.h>
#include "request_header.h"

#ifdef _MSC_VER
#pragma comment(lib, "advapi32.lib")
#endif

namespace bridge {

namespace {

// Builds a SECURITY_ATTRIBUTES whose DACL grants full access to the CURRENT
// user (and SYSTEM) only, and nothing else. Without this the pipe is created
// with the default DACL, which lets other local accounts open it. Combined
// with PIPE_REJECT_REMOTE_CLIENTS on the pipe, this keeps the bridge reachable
// only by processes running as the same user on this machine.
//
// On success, fills `sa` and returns a PSECURITY_DESCRIPTOR the caller must
// LocalFree after the CreateNamedPipe call. Returns nullptr on failure (caller
// should then fail closed rather than fall back to a default DACL).
PSECURITY_DESCRIPTOR build_current_user_sa(SECURITY_ATTRIBUTES& sa) {
    HANDLE token = nullptr;
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token))
        return nullptr;

    DWORD len = 0;
    GetTokenInformation(token, TokenUser, nullptr, 0, &len);
    if (len == 0) { CloseHandle(token); return nullptr; }

    std::vector<BYTE> buf(len);
    if (!GetTokenInformation(token, TokenUser, buf.data(), len, &len)) {
        CloseHandle(token);
        return nullptr;
    }
    CloseHandle(token);

    auto* tu = reinterpret_cast<TOKEN_USER*>(buf.data());
    LPWSTR sidStr = nullptr;
    if (!ConvertSidToStringSidW(tu->User.Sid, &sidStr))
        return nullptr;

    // SDDL DACL: Protected (no inherited ACEs); grant File-All to the current
    // user SID and to SYSTEM (SY) only.
    std::wstring sddl = L"D:P(A;;FA;;;";
    sddl += sidStr;
    sddl += L")(A;;FA;;;SY)";
    LocalFree(sidStr);

    PSECURITY_DESCRIPTOR psd = nullptr;
    if (!ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl.c_str(), SDDL_REVISION_1, &psd, nullptr)) {
        return nullptr;
    }

    sa.nLength = sizeof(SECURITY_ATTRIBUTES);
    sa.lpSecurityDescriptor = psd;
    sa.bInheritHandle = FALSE;
    return psd;
}

} // namespace

// -------------------------------------------------------------------------
// Construction / destruction
// -------------------------------------------------------------------------

PipeServer::PipeServer(MessageQueue& inbound, MessageQueue& outbound)
    : inbound_(inbound), outbound_(outbound) {}

PipeServer::~PipeServer() { stop(); }

void PipeServer::set_callback(CallbackFn fn) { callback_ = std::move(fn); }

void PipeServer::set_editor_ready(bool ready) {
    std::lock_guard<std::mutex> lock(session_mutex_);
    editor_ready_ = ready;
    // Pending edits belong to the old editor state. Fail them rather than
    // executing them after Preview has reconstructed the scenario.
    Message pending;
    while (inbound_.try_pop(pending)) {
        outbound_.push({pending.id, error_response(pending.id, "Editor changed; command cancelled. Inspect state before retrying.")});
    }
}

bool PipeServer::poll_command(Message& out, size_t max_size) {
    std::lock_guard<std::mutex> lock(session_mutex_);
    if (!editor_ready_) return false;
    while (inbound_.try_pop(out)) {
        if (out.json.size() < max_size) return true;
        outbound_.push({out.id, error_response(out.id, "Command exceeds Arma extension output buffer")});
    }
    return false;
}

void PipeServer::accept_command(const std::string& line) {
    std::string id, cmd;
    if (!request_header(line, id, cmd)) return;
    std::lock_guard<std::mutex> lock(session_mutex_);
    if (editor_ready_) {
        inbound_.push({id, line});
    } else if (cmd == "ping") {
        // Transport remains alive in Preview, although editing is suspended.
        outbound_.push({id, "[" + json_string(id) + ",\"respond\",[[\"ok\",true],[\"editor_open\",false],[\"version\",\"1.2.0-rc.1\"]]]"});
    } else {
        outbound_.push({id, error_response(id, "Eden is paused or closed. Return to the editor before editing.")});
    }
}

// -------------------------------------------------------------------------
// Start / stop
// -------------------------------------------------------------------------

void PipeServer::start() {
    if (running_.load()) return;
    running_.store(true);
    thread_ = CreateThread(nullptr, 0, thread_proc, this, 0, nullptr);
    if (!thread_) { thread_ = INVALID_HANDLE_VALUE; running_.store(false); }
}

void PipeServer::stop() {
    if (!running_.load()) return;
    running_.store(false);
    // I/O is bounded, so let the owner thread cancel/close its own handle.
    // Closing it here races the thread's stack-allocated OVERLAPPED objects.
    if (thread_ != INVALID_HANDLE_VALUE) {
        WaitForSingleObject(thread_, 5000);
        CloseHandle(thread_);
        thread_ = INVALID_HANDLE_VALUE;
    }
}

DWORD WINAPI PipeServer::thread_proc(LPVOID param) {
    reinterpret_cast<PipeServer*>(param)->run();
    return 0;
}

// -------------------------------------------------------------------------
// Main I/O loop
// -------------------------------------------------------------------------

void PipeServer::run() {
    while (running_.load()) {
        if (!create_pipe()) {
            Sleep(1000);
            continue;
        }
        if (!wait_for_client()) {
            close_pipe();
            continue;
        }
        serve_client();
        close_pipe();
        // Never deliver commands/responses from a disconnected MCP session to
        // its replacement. The queue lock also serialises editor transitions.
        std::lock_guard<std::mutex> lock(session_mutex_);
        inbound_.clear();
        outbound_.clear();
    }
}

// -------------------------------------------------------------------------
// Pipe lifecycle
// -------------------------------------------------------------------------

bool PipeServer::create_pipe() {
    // Restrict the pipe to the current user. Fail closed if we can't build the
    // DACL — never silently fall back to the permissive default DACL.
    SECURITY_ATTRIBUTES sa{};
    PSECURITY_DESCRIPTOR psd = build_current_user_sa(sa);
    if (!psd) return false;

    // A custom local pipe supports isolated diagnostics without touching the
    // live game's pipe. Keep the current-user DACL and reject remote names.
    wchar_t configured[512]{};
    DWORD length = GetEnvironmentVariableW(L"ARMA3_BRIDGE_PIPE", configured, 512);
    std::wstring pipe_name = PIPE_NAME;
    if (length > 0 && length < 512 && std::wstring(configured).find(L"\\\\.\\pipe\\") == 0)
        pipe_name = configured;
    pipe_ = CreateNamedPipeW(
        pipe_name.c_str(),
        PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED,
        PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT | PIPE_REJECT_REMOTE_CLIENTS,
        1,           // max instances (one Python client at a time)
        BUFFER_SIZE,
        BUFFER_SIZE,
        0,
        &sa          // current-user-only DACL (see build_current_user_sa)
    );

    LocalFree(psd);  // the SD has been copied into the kernel object
    return pipe_ != INVALID_HANDLE_VALUE;
}

bool PipeServer::wait_for_client() {
    // ConnectNamedPipe blocks until Python connects (or returns immediately if
    // a client is already waiting). Poll running_ with a timeout approach.
    OVERLAPPED ov{};
    ov.hEvent = CreateEvent(nullptr, TRUE, FALSE, nullptr);
    if (!ov.hEvent) return false;

    BOOL ok = ConnectNamedPipe(pipe_, &ov);
    DWORD err = ok ? ERROR_SUCCESS : GetLastError();

    bool connected = false;
    if (ok || err == ERROR_PIPE_CONNECTED) {
        connected = true;
    } else if (err == ERROR_IO_PENDING) {
        // Wait with periodic running_ checks
        while (running_.load()) {
            DWORD wait = WaitForSingleObject(ov.hEvent, 500);
            if (wait == WAIT_OBJECT_0) {
                DWORD transferred = 0;
                connected = GetOverlappedResult(pipe_, &ov, &transferred, FALSE) != FALSE;
                break;
            }
            if (wait == WAIT_FAILED) break;
        }
        if (!connected) {
            CancelIoEx(pipe_, &ov);
            DWORD transferred = 0;
            GetOverlappedResult(pipe_, &ov, &transferred, TRUE);
        }
    }

    CloseHandle(ov.hEvent);
    return connected;
}

void PipeServer::close_pipe() {
    if (pipe_ != INVALID_HANDLE_VALUE) {
        // FlushFileBuffers blocks until the client reads everything. A dead
        // MCP process must not be able to stall the reconnect loop forever.
        CancelIoEx(pipe_, nullptr);
        DisconnectNamedPipe(pipe_);
        CloseHandle(pipe_);
        pipe_ = INVALID_HANDLE_VALUE;
    }
}

// -------------------------------------------------------------------------
// Client session: bidirectional NDJSON exchange
// -------------------------------------------------------------------------

void PipeServer::serve_client() {
    // Alternate bounded overlapped reads/writes. Preserve partial NDJSON
    // frames across ReadFile calls; byte pipes do not preserve write boundaries.

    std::string line;
    while (running_.load()) {
        // --- Drain SQF responses to Python ---
        Message out_msg;
        while (outbound_.try_pop(out_msg)) {
            if (!write_line(out_msg.json)) return;
        }

        // --- Read one line from Python (non-blocking via overlapped) ---
        // We use overlapped I/O with a 100ms wait so we can still check running_
        OVERLAPPED ov{};
        ov.hEvent = CreateEvent(nullptr, TRUE, FALSE, nullptr);
        if (!ov.hEvent) return;

        char buf[BUFFER_SIZE];
        DWORD bytes_read = 0;
        BOOL ok = ReadFile(pipe_, buf, sizeof(buf) - 1, nullptr, &ov);
        DWORD err = GetLastError();

        if (!ok && err == ERROR_IO_PENDING) {
            DWORD wait = WaitForSingleObject(ov.hEvent, 100);
            if (wait == WAIT_OBJECT_0) {
                ok = GetOverlappedResult(pipe_, &ov, &bytes_read, FALSE);
            } else {
                CancelIoEx(pipe_, &ov);
                GetOverlappedResult(pipe_, &ov, &bytes_read, TRUE);
                // Cancellation can race a successful read. Preserve those
                // bytes instead of silently dropping a completed request.
                ok = bytes_read > 0;
                if (!ok) {
                    CloseHandle(ov.hEvent);
                    if (wait != WAIT_TIMEOUT) return;
                    continue;
                }
            }
        } else if (ok) {
            bytes_read = ov.InternalHigh ? (DWORD)ov.InternalHigh : 0;
            GetOverlappedResult(pipe_, &ov, &bytes_read, FALSE);
        }

        CloseHandle(ov.hEvent);

        if (!ok || bytes_read == 0) return; // client disconnected

        line.append(buf, bytes_read);
        size_t pos = 0, newline;
        while ((newline = line.find('\n', pos)) != std::string::npos) {
            std::string json_line = line.substr(pos, newline - pos);
            // Trim \r if present
            if (!json_line.empty() && json_line.back() == '\r')
                json_line.pop_back();
            if (!json_line.empty()) {
                accept_command(json_line);
            }
            pos = newline + 1;
        }
        line.erase(0, pos);
        if (line.size() > BUFFER_SIZE) return; // malformed/oversized unfinished frame
    }
}

bool PipeServer::write_line(const std::string& line) {
    std::string data = line + "\n";
    OVERLAPPED ov{};
    ov.hEvent = CreateEvent(nullptr, TRUE, FALSE, nullptr);
    if (!ov.hEvent) return false;

    DWORD written = 0;
    BOOL ok = WriteFile(pipe_, data.data(), (DWORD)data.size(), nullptr, &ov);
    DWORD err = GetLastError();

    if (!ok && err == ERROR_IO_PENDING) {
        DWORD wait = WaitForSingleObject(ov.hEvent, 1000);
        if (wait == WAIT_OBJECT_0) {
            ok = GetOverlappedResult(pipe_, &ov, &written, FALSE);
        } else {
            CancelIoEx(pipe_, &ov);
            GetOverlappedResult(pipe_, &ov, &written, TRUE);
            ok = FALSE;
        }
    } else if (ok) {
        GetOverlappedResult(pipe_, &ov, &written, FALSE);
    }

    CloseHandle(ov.hEvent);
    return ok && written == data.size();
}

} // namespace bridge
