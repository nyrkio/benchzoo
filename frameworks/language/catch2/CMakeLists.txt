# CMake build for the benchzoo Catch2 sample benchmark.
#
# We fetch catchorg/Catch2 via FetchContent at configure time, pinned
# to a specific tag, so the captured fixture in CI is a function of a
# known upstream version. Bumping the version is a deliberate one-line
# edit in this file and the resulting change in the output will show
# up in the PR diff — that is the whole point of pinning.
#
# Catch2 v3 has first-class `BENCHMARK(...)` macros built in — the old
# v2-era `CATCH_CONFIG_ENABLE_BENCHMARKING` define is no longer
# required. Linking against `Catch2::Catch2WithMain` pulls in Catch2's
# own main() so we don't have to write one.

cmake_minimum_required(VERSION 3.16)
project(benchzoo_catch2_sample CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(FetchContent)

# Pin to a specific release tag for reproducibility. Bump deliberately.
FetchContent_Declare(
    Catch2
    GIT_REPOSITORY https://github.com/catchorg/Catch2.git
    GIT_TAG        v3.7.1
    GIT_SHALLOW    TRUE
)
FetchContent_MakeAvailable(Catch2)

add_executable(sample_benchmark benchmarks.cc)
target_link_libraries(sample_benchmark
    PRIVATE
        Catch2::Catch2WithMain
)
