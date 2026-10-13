cmake_minimum_required(VERSION 3.20)
project(arma3_mcp_bridge VERSION 1.2.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Force x64 â€“ Arma 3 on modern Windows is 64-bit
if(NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
    message(FATAL_ERROR "Must build as x64. Use: cmake -B build -A x64")
endif()

add_library(arma3_mcp_bridge SHARED
    src/dllmain.cpp
    src/pipe_server.cpp
    src/message_queue.cpp
)

target_include_directories(arma3_mcp_bridge PRIVATE src)

# Win32 API only. advapi32 provides the token / SID / SDDL functions used to
# build the current-user-only pipe DACL in pipe_server.cpp.
target_link_libraries(arma3_mcp_bridge PRIVATE advapi32)

# Release: optimise, strip debug symbols
if(MSVC)
    target_compile_options(arma3_mcp_bridge PRIVATE
        $<$<CONFIG:Release>:/O2 /GL>
    )
    target_link_options(arma3_mcp_bridge PRIVATE
        $<$<CONFIG:Release>:/LTCG>
    )
else()
    # MinGW: static runtime so the DLL has no external MinGW dependencies
    target_compile_options(arma3_mcp_bridge PRIVATE
        $<$<CONFIG:Release>:-O2>
    )
    target_link_options(arma3_mcp_bridge PRIVATE
        -static-libgcc -static-libstdc++ -static
    )
endif()

# Copy DLL to addon directory after build
set(ADDON_DIR "${CMAKE_SOURCE_DIR}/../arma3_addon/addons/bridge")
add_custom_command(TARGET arma3_mcp_bridge POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        $<TARGET_FILE:arma3_mcp_bridge>
        "${ADDON_DIR}/arma3_mcp_bridge.dll"
    COMMENT "Copying DLL to addon directory"
)
