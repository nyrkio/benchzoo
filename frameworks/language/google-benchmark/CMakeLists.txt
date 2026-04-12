# CMake build for the benchzoo Google Benchmark sample benchmark.
#
# We fetch google/benchmark via FetchContent at configure time, pinned
# to a specific tag, so the captured fixture in CI is a function of a
# known upstream version. Bumping the version is a deliberate one-line
# edit in this file and the resulting change in the JSON output will
# show up in the PR diff — that is the whole point of pinning.
#
# Google Benchmark's own test suite and GoogleTest dependency are
# disabled; we only need the library and its benchmark_main entry
# point.

cmake_minimum_required(VERSION 3.16)
project(benchzoo_google_benchmark_sample CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(FetchContent)

# Pin to a specific release tag for reproducibility. Bump deliberately.
set(BENCHMARK_ENABLE_TESTING OFF CACHE BOOL "" FORCE)
set(BENCHMARK_ENABLE_GTEST_TESTS OFF CACHE BOOL "" FORCE)
set(BENCHMARK_ENABLE_INSTALL OFF CACHE BOOL "" FORCE)

FetchContent_Declare(
    benchmark
    GIT_REPOSITORY https://github.com/google/benchmark.git
    GIT_TAG        v1.9.1
    GIT_SHALLOW    TRUE
)
FetchContent_MakeAvailable(benchmark)

add_executable(sample_benchmark benchmarks.cc)
target_link_libraries(sample_benchmark
    PRIVATE
        benchmark::benchmark
        benchmark::benchmark_main
)
