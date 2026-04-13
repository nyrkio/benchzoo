# CMake build for the benchzoo CTest sample benchmark.
#
# CTest is CMake's own test runner: `add_test` registers a command
# with the build, and `ctest` runs every registered command and
# records per-test pass/fail plus wall-clock duration. Since CMake
# 3.21, `ctest --output-junit <file>` writes a standard junit XML
# report — the same `<testsuite>/<testcase>` shape Surefire / Jest /
# pytest produce — so any junit parser can consume CTest output with
# no CTest-specific knowledge.
#
# We don't need a C++ compiler at all for this sample: `add_test`
# takes an arbitrary command, and the canonical sample benchmark is
# already expressed as four shell scripts. Registering them
# directly keeps the build trivial and the CTest-vs-junit-XML mapping
# obvious: test `name` in CTest becomes `<testcase name="...">` in
# the junit XML, and `<testcase time="...">` is CTest's measured
# wall-clock seconds.
cmake_minimum_required(VERSION 3.21)
project(benchzoo_ctest_sample NONE)

enable_testing()

# Register the four canonical sample-benchmark tests. Each test is a
# `bash benchmarkN.sh` invocation; CTest reports whether bash exits 0
# and how long it took. WORKING_DIRECTORY pins execution to this
# source dir so the shell scripts resolve regardless of where `ctest`
# is invoked from.
foreach(n RANGE 1 4)
    add_test(
        NAME benchmark${n}
        COMMAND bash benchmark${n}.sh
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    )
endforeach()
