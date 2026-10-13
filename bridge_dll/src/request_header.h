#pragma once
#include <cctype>
#include <string>

namespace bridge {

// Read only the first two strings of the inert SQF array protocol. SQF quotes
// are doubled, not backslash-escaped. The full payload is parsed by SQF later.
inline bool request_header(const std::string& line, std::string& id, std::string& cmd) {
    size_t pos = 0;
    auto space = [&] {
        while (pos < line.size() && std::isspace(static_cast<unsigned char>(line[pos]))) ++pos;
    };
    auto token = [&](char expected) {
        space();
        if (pos == line.size() || line[pos] != expected) return false;
        ++pos;
        return true;
    };
    auto string = [&](std::string& out) {
        out.clear();
        if (!token('"')) return false;
        while (pos < line.size()) {
            char ch = line[pos++];
            if (ch == '"') {
                if (pos < line.size() && line[pos] == '"') { ++pos; out += '"'; }
                else return true;
            } else {
                if (static_cast<unsigned char>(ch) < 0x20) return false;
                out += ch;
            }
        }
        return false;
    };
    if (!token('[') || !string(id) || !token(',') || !string(cmd)) return false;
    space();
    return pos < line.size() && (line[pos] == ',' || line[pos] == ']');
}

inline std::string json_string(const std::string& value) {
    std::string out = "\"";
    for (char ch : value) {
        if (ch == '"' || ch == '\\') out += '\\';
        out += ch;
    }
    return out + '"';
}

inline std::string error_response(const std::string& id, const std::string& error) {
    return "[" + json_string(id) + ",\"respond\",[[\"ok\",false],[\"error\"," + json_string(error) + "]]]";
}

} // namespace bridge
