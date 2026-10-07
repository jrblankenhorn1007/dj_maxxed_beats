# Standalone CMake build for the ChaosOsc SuperCollider server plugin.
#
#   cmake -S plugin/ChaosOsc -B plugin/ChaosOsc/build
#   cmake --build plugin/ChaosOsc/build --config Release
#   ctest --test-dir plugin/ChaosOsc/build -C Release --output-on-failure
#   cmake --install plugin/ChaosOsc/build --config Release --prefix "<SC Extensions dir>"
#
# Produces <prefix>/ChaosOsc/{ChaosOsc.scx|ChaosOsc.so, Classes/, HelpSource/}.
# See README.md next to this file (or scripts/install_chaososc.py) for the
# full build/install guide.
cmake_minimum_required(VERSION 3.16)

# macOS defaults (set before project() so compiler checks use them): build a
# universal binary for the same minimum macOS as the official universal
# SuperCollider 3.14.1 app, unless the user chose otherwise via -D or the
# CMAKE_OSX_ARCHITECTURES / MACOSX_DEPLOYMENT_TARGET environment variables.
if(CMAKE_HOST_APPLE)
    if(NOT DEFINED CMAKE_OSX_ARCHITECTURES AND "$ENV{CMAKE_OSX_ARCHITECTURES}" STREQUAL "")
        set(CMAKE_OSX_ARCHITECTURES "arm64;x86_64" CACHE STRING
            "macOS architectures to build (default: universal, like the official SuperCollider app)")
    endif()
    if(NOT DEFINED CMAKE_OSX_DEPLOYMENT_TARGET AND "$ENV{MACOSX_DEPLOYMENT_TARGET}" STREQUAL "")
        set(CMAKE_OSX_DEPLOYMENT_TARGET "11.0" CACHE STRING
            "Minimum macOS version (default: 11.0, like the official SuperCollider 3.14.1 app)")
    endif()
endif()

project(ChaosOsc LANGUAGES CXX)

get_property(CHAOSOSC_MULTI_CONFIG GLOBAL PROPERTY GENERATOR_IS_MULTI_CONFIG)
if(NOT CHAOSOSC_MULTI_CONFIG AND NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type (default: Release)" FORCE)
endif()

if(CMAKE_INSTALL_PREFIX_INITIALIZED_TO_DEFAULT)
    # Never default to a system prefix; pass --prefix "<SC Extensions dir>".
    set(CMAKE_INSTALL_PREFIX "${CMAKE_BINARY_DIR}/install" CACHE PATH
        "Install prefix; ChaosOsc installs into <prefix>/ChaosOsc" FORCE)
endif()

option(CHAOSOSC_WARNINGS_AS_ERRORS "Treat ChaosOsc compiler warnings as errors" ON)
option(CHAOSOSC_BUILD_TESTS "Build the ChaosOsc DSP-core unit tests and register them with CTest" ON)
set(SC_PATH "" CACHE PATH
    "SuperCollider source root providing include/plugin_interface and include/common (default: fetch the pinned SuperCollider 3.14.1 plugin API headers)")

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# --- SuperCollider plugin API headers --------------------------------------
get_filename_component(CHAOSOSC_PLUGINS_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/.." ABSOLUTE)
set(CHAOSOSC_FETCH_SCRIPT "${CHAOSOSC_PLUGINS_ROOT}/fetch_sc_plugin_api.py")

if(SC_PATH)
    file(TO_CMAKE_PATH "${SC_PATH}" CHAOSOSC_SC_PATH)
    set(CHAOSOSC_SC_INCLUDE_ROOT "${CHAOSOSC_SC_PATH}/include")
    if(NOT EXISTS "${CHAOSOSC_SC_INCLUDE_ROOT}/plugin_interface/SC_PlugIn.hpp")
        message(FATAL_ERROR
            "SC_PATH='${SC_PATH}' is not a SuperCollider source root: "
            "${CHAOSOSC_SC_INCLUDE_ROOT}/plugin_interface/SC_PlugIn.hpp does not exist. "
            "Pass the root of a SuperCollider source checkout (the directory that "
            "contains include/plugin_interface and include/common), or omit SC_PATH "
            "to fetch the pinned SuperCollider 3.14.1 plugin API headers.")
    endif()
    set(CHAOSOSC_SC_HEADER_SOURCE "SC_PATH=${CHAOSOSC_SC_PATH}")
else()
    if(NOT EXISTS "${CHAOSOSC_FETCH_SCRIPT}")
        message(FATAL_ERROR
            "${CHAOSOSC_FETCH_SCRIPT} was not found, so the pinned SuperCollider "
            "plugin API headers cannot be fetched. Pass -DSC_PATH=<SuperCollider source root>.")
    endif()
    file(STRINGS "${CHAOSOSC_FETCH_SCRIPT}" CHAOSOSC_SC_COMMIT_LINE
         REGEX "^SC_COMMIT = \"[0-9a-f]+\"" LIMIT_COUNT 1)
    string(REGEX MATCH "[0-9a-f][0-9a-f]+" CHAOSOSC_SC_API_COMMIT "${CHAOSOSC_SC_COMMIT_LINE}")
    if(NOT CHAOSOSC_SC_API_COMMIT)
        message(FATAL_ERROR "Could not read SC_COMMIT from ${CHAOSOSC_FETCH_SCRIPT}.")
    endif()
    set(CHAOSOSC_SC_INCLUDE_ROOT
        "${CHAOSOSC_PLUGINS_ROOT}/.sc-plugin-api-cache/${CHAOSOSC_SC_API_COMMIT}/include")
    set(CHAOSOSC_SC_FETCH_STAMP "${CMAKE_CURRENT_BINARY_DIR}/sc-plugin-api-${CHAOSOSC_SC_API_COMMIT}.stamp")
    if(NOT EXISTS "${CHAOSOSC_SC_FETCH_STAMP}"
       OR NOT EXISTS "${CHAOSOSC_SC_INCLUDE_ROOT}/plugin_interface/SC_PlugIn.hpp")
        find_package(Python3 COMPONENTS Interpreter)
        if(NOT Python3_Interpreter_FOUND)
            message(FATAL_ERROR
                "Python 3 is required to fetch the pinned SuperCollider plugin API headers "
                "(plugin/fetch_sc_plugin_api.py). Install Python 3, or pass "
                "-DSC_PATH=<SuperCollider source root> to use local headers instead.")
        endif()
        message(STATUS "ChaosOsc: fetching SuperCollider plugin API headers at ${CHAOSOSC_SC_API_COMMIT}")
        execute_process(
            COMMAND "${Python3_EXECUTABLE}" "${CHAOSOSC_FETCH_SCRIPT}"
            RESULT_VARIABLE CHAOSOSC_FETCH_RESULT)
        if(NOT CHAOSOSC_FETCH_RESULT EQUAL 0)
            message(FATAL_ERROR
                "Fetching the SuperCollider plugin API headers failed (${CHAOSOSC_FETCH_RESULT}). "
                "It needs network access to raw.githubusercontent.com; retry when online, or pass "
                "-DSC_PATH=<SuperCollider source root> to use local headers instead.")
        endif()
        file(WRITE "${CHAOSOSC_SC_FETCH_STAMP}" "${CHAOSOSC_SC_API_COMMIT}\n")
    endif()
    set(CHAOSOSC_SC_HEADER_SOURCE "pinned SuperCollider 3.14.1 plugin API ${CHAOSOSC_SC_API_COMMIT}")
endif()

set(CHAOSOSC_SC_INCLUDE_DIRS
    "${CHAOSOSC_SC_INCLUDE_ROOT}/plugin_interface"
    "${CHAOSOSC_SC_INCLUDE_ROOT}/common")
message(STATUS "ChaosOsc: SuperCollider plugin API headers (${CHAOSOSC_SC_HEADER_SOURCE}):")
foreach(dir IN LISTS CHAOSOSC_SC_INCLUDE_DIRS)
    message(STATUS "  ${dir}")
endforeach()

# --- Project warnings (SC headers are SYSTEM includes, so only ours count) --
add_library(chaososc_warnings INTERFACE)
if(MSVC)
    target_compile_options(chaososc_warnings INTERFACE /W4)
    if(CHAOSOSC_WARNINGS_AS_ERRORS)
        target_compile_options(chaososc_warnings INTERFACE /WX)
    endif()
else()
    target_compile_options(chaososc_warnings INTERFACE -Wall -Wextra)
    if(CHAOSOSC_WARNINGS_AS_ERRORS)
        target_compile_options(chaososc_warnings INTERFACE -Werror)
    endif()
endif()

# --- Plugin module -----------------------------------------------------------
file(GLOB CHAOSOSC_PLUGIN_SOURCES CONFIGURE_DEPENDS
     "${CMAKE_CURRENT_SOURCE_DIR}/Source/*.cpp"
     "${CMAKE_CURRENT_SOURCE_DIR}/Source/*.hpp"
     "${CMAKE_CURRENT_SOURCE_DIR}/Source/*.h")
add_library(ChaosOsc MODULE ${CHAOSOSC_PLUGIN_SOURCES})
target_include_directories(ChaosOsc SYSTEM PRIVATE ${CHAOSOSC_SC_INCLUDE_DIRS})
target_link_libraries(ChaosOsc PRIVATE chaososc_warnings)
if(MSVC AND MSVC_VERSION GREATER_EQUAL 1929)
    # Keep MSVC quiet inside the SYSTEM (/external:I) SC headers regardless
    # of the generator's default external warning level.
    target_compile_options(ChaosOsc PRIVATE /external:W0)
endif()
# scsynth loads <name>.scx (macOS, Windows) or <name>.so (Linux) without a
# "lib" prefix; only PluginLoad's exported C entry points stay visible.
set_target_properties(ChaosOsc PROPERTIES
    PREFIX ""
    CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN ON)
if(APPLE OR WIN32)
    set_target_properties(ChaosOsc PROPERTIES SUFFIX ".scx")
else()
    set_target_properties(ChaosOsc PROPERTIES SUFFIX ".so")
endif()

# --- DSP-core unit tests -----------------------------------------------------
enable_testing()
if(CHAOSOSC_BUILD_TESTS)
    add_executable(test_chaos_osc_core Tests/test_chaos_osc_core.cpp)
    target_link_libraries(test_chaos_osc_core PRIVATE chaososc_warnings)
    add_test(NAME chaos_osc_core COMMAND test_chaos_osc_core)
endif()

# --- Install: <prefix>/ChaosOsc is a complete SuperCollider extension folder --
install(TARGETS ChaosOsc LIBRARY DESTINATION ChaosOsc)
install(DIRECTORY Classes/ DESTINATION ChaosOsc/Classes PATTERN ".DS_Store" EXCLUDE)
install(DIRECTORY HelpSource/ DESTINATION ChaosOsc/HelpSource PATTERN ".DS_Store" EXCLUDE)
install(FILES README.md DESTINATION ChaosOsc)
if(EXISTS "${CHAOSOSC_PLUGINS_ROOT}/../LICENSE")
    install(FILES "${CHAOSOSC_PLUGINS_ROOT}/../LICENSE" DESTINATION ChaosOsc)
endif()

get_target_property(CHAOSOSC_SUFFIX ChaosOsc SUFFIX)
message(STATUS "ChaosOsc: plugin module ChaosOsc${CHAOSOSC_SUFFIX}; installs to "
               "<prefix>/ChaosOsc (prefix: ${CMAKE_INSTALL_PREFIX})")
if(APPLE)
    message(STATUS "ChaosOsc: macOS architectures '${CMAKE_OSX_ARCHITECTURES}', "
                   "deployment target '${CMAKE_OSX_DEPLOYMENT_TARGET}'")
endif()
