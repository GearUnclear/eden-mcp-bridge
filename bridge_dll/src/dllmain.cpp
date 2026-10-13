/**
 * arma3_mcp_bridge.dll
 *
 * Arma 3 extension that bridges the game's SQF scripting engine to an
 * external Python MCP server via a Windows named pipe.
 *
 * Exported entry points (called by Arma 3):
 *   RVExtension            – synchronous, single-string API (Arma ≥1.61)
 *   RVExtensionArgs        – multi-argument API (Arma ≥1.68)
 *   RVExtensionVersion     – version string (Arma ≥1.70)
 *   RVExtensionRegisterCallback – async callback registration (Arma ≥1.96)
 *
 * Threading model:
 *   - The SQF thread calls RVExtension / RVExtensionArgs.
 *     These calls MUST return in < 1 ms or Arma freezes.
 *     We enqueue the response in `g_responses` and return immediately with
 *     '{"queued":true}' so SQF can poll later.
 *
 *   - The pipe server thread reads requests from Python into g_commands and
 *     drains g_responses back to Python.
 *
 *   - SQF polls by calling RVExtension("poll"). We drain g_commands and
 *     return the first available command (or "" if nothing is ready).
 *
 *   - Commands use polling exclusively, avoiding duplicate callback delivery.
 */

#include <windows.h>

#include <atomic>
#include <cstring>
#include <mutex>
#include <string>

#include "message_queue.h"
#include "pipe_server.h"

// ---------------------------------------------------------------------------
// Globals
// ---------------------------------------------------------------------------

static bridge::MessageQueue g_commands;   // Python -> SQF
static bridge::MessageQueue g_responses;  // SQF -> Python

static bridge::PipeServer* g_pipe = nullptr;

// Arma's callback function pointer (registered via RVExtensionRegisterCallback)
using RVCallbackFn = int(__stdcall*)(const char* name,
                                      const char* function,
                                      const char* data);
static std::atomic<RVCallbackFn> g_callback{ nullptr };

static std::once_flag g_pipe_once;

// ---------------------------------------------------------------------------
// Lazy pipe startup
//
// We MUST NOT create the PipeServer or start its thread inside DllMain: doing
// work under the loader lock (especially CreateThread) makes Arma's LoadLibrary
// fail with ERROR_NO_SYSTEM_RESOURCES (1450). Instead we start the pipe lazily
// on the first RVExtension* call, which Arma issues only after LoadLibrary has
// returned — i.e. outside the loader lock. std::call_once makes this safe even
// if the SQF and callback-registration paths race.
// ---------------------------------------------------------------------------

static void ensure_pipe() {
    std::call_once(g_pipe_once, [] {
        g_pipe = new bridge::PipeServer(g_commands, g_responses);
        // Wire async callback: when Python sends an unsolicited event,
        // forward it to Arma via the registered callback function.
        g_pipe->set_callback([](const std::string& name,
                                 const std::string& func,
                                 const std::string& data) {
            RVCallbackFn cb = g_callback.load();
            if (cb) cb(name.c_str(), func.c_str(), data.c_str());
        });
        g_pipe->start();
    });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

static void write_output(char* output, int max_size, const std::string& s) {
    if (!output || max_size <= 0) return;
    std::strncpy(output, s.c_str(), static_cast<size_t>(max_size) - 1);
    output[max_size - 1] = '\0';
}

// Build a minimal JSON error response
static std::string make_error(const std::string& msg) {
    return "{\"ok\":false,\"error\":\"" + msg + "\"}";
}

// ---------------------------------------------------------------------------
// DLL entry point
// ---------------------------------------------------------------------------

BOOL WINAPI DllMain(HINSTANCE hinst, DWORD reason, LPVOID reserved) {
    switch (reason) {
    case DLL_PROCESS_ATTACH:
        // Keep DllMain trivial — the pipe server is started lazily on the first
        // RVExtension* call (see ensure_pipe). We don't need per-thread
        // notifications, so disable them to reduce loader-lock churn.
        DisableThreadLibraryCalls(hinst);
        break;

    case DLL_PROCESS_DETACH:
        // reserved != NULL => the whole process is terminating. In that case the
        // OS reclaims everything and joining the pipe thread under the loader
        // lock can deadlock, so skip cleanup. Only tear down on an explicit
        // FreeLibrary (reserved == NULL).
        if (reserved == nullptr && g_pipe) {
            g_pipe->stop();
            delete g_pipe;
            g_pipe = nullptr;
        }
        break;
    }
    return TRUE;
}

// ---------------------------------------------------------------------------
// RVExtensionVersion  (Arma ≥1.70)
// ---------------------------------------------------------------------------

extern "C" __declspec(dllexport)
void __stdcall RVExtensionVersion(char* output, int output_size) {
    write_output(output, output_size, "arma3_mcp_bridge 1.2.0-rc.1");
}

// ---------------------------------------------------------------------------
// RVExtension  –  single string API  (Arma ≥1.61)
//
// Called from SQF as:
//   "arma3_mcp_bridge" callExtension "some_json_or_command"
// ---------------------------------------------------------------------------

extern "C" __declspec(dllexport)
void __stdcall RVExtension(char* output, int output_size, const char* function) {
    if (!output || output_size <= 0) return;
    if (!function) {
        write_output(output, output_size, make_error("null function"));
        return;
    }

    // Start the pipe server on first use (safe here — outside the loader lock).
    ensure_pipe();

    std::string cmd(function);

    // --- Special commands (handled inline, no queuing) ---

    if (cmd == "ping") {
        write_output(output, output_size, "{\"ok\":true}");
        return;
    }

    if (cmd == "poll") {
        // Return the next command from Python, or empty string.
        bridge::Message msg;
        if (g_pipe->poll_command(msg, static_cast<size_t>(output_size))) {
            write_output(output, output_size, msg.json);
        } else {
            write_output(output, output_size, "");
        }
        return;
    }

    if (cmd == "editor_ready" || cmd == "editor_paused") {
        g_pipe->set_editor_ready(cmd == "editor_ready");
        write_output(output, output_size, "{\"ok\":true}");
        return;
    }

    if (cmd == "status") {
        // Report connection state
        std::string s = g_pipe ? "{\"ok\":true,\"pipe\":\"running\"}"
                                : "{\"ok\":false,\"pipe\":\"stopped\"}";
        write_output(output, output_size, s);
        return;
    }

    // Responses already include their correlation ID in the array payload.
    g_responses.push({ "", cmd });
    write_output(output, output_size, "{\"queued\":true}");
}

// ---------------------------------------------------------------------------
// RVExtensionArgs  –  multi-argument API  (Arma ≥1.68)
//
// Called from SQF as:
//   "arma3_mcp_bridge" callExtension ["cmd", ["arg1", "arg2", ...]]
//
// We serialise the args into a single JSON string and forward the same
// pipeline as RVExtension.
// ---------------------------------------------------------------------------

extern "C" __declspec(dllexport)
void __stdcall RVExtensionArgs(char*       output,
                                int         output_size,
                                const char* function,
                                const char** argv,
                                int         argc) {
    if (!function || argc < 1) {
        write_output(output, output_size, make_error("missing args"));
        return;
    }

    // argv[0] is the first arg; build a simple JSON array string
    std::string json = "{\"cmd\":\"";
    json += function;
    json += "\",\"args\":[";
    for (int i = 0; i < argc; ++i) {
        if (i > 0) json += ',';
        json += '"';
        json += argv[i] ? argv[i] : "";
        json += '"';
    }
    json += "]}";

    // Re-use the same single-string entry point logic
    RVExtension(output, output_size, json.c_str());
}

// ---------------------------------------------------------------------------
// RVExtensionRegisterCallback  (Arma ≥1.96)
//
// Arma calls this once at load time to give us a function pointer.
// We use it to push async events back to the game without SQF polling.
// ---------------------------------------------------------------------------

extern "C" __declspec(dllexport)
void __stdcall RVExtensionRegisterCallback(RVCallbackFn callback) {
    g_callback.store(callback);
    // Arma calls this at load time, after LoadLibrary has returned, so it's a
    // safe place to bring the pipe up even before the first SQF "ping".
    ensure_pipe();
}
