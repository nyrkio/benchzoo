#!/bin/bash
# Configure, build, and run the CTest sample benchmark, capturing the
# junit XML report to ./output.xml for artifact upload.
#
# `cmake --build build` is a no-op here (the project has no compiled
# targets — `project(... NONE)` disables all language toolchains) but
# is kept for parity with other CMake-based frameworks in benchzoo
# and because a future revision might add compiled test executables.
#
# `ctest --output-junit <file>` was added in CMake 3.21. The path is
# resolved relative to the build directory, so `../output.xml` lands
# the file next to run.sh — same convention as every other framework
# in benchzoo (`output.<ext>` at the framework root for artifact
# upload).
set -euo pipefail

cd "$(dirname "$0")"
chmod +x benchmark1.sh benchmark2.sh benchmark3.sh benchmark4.sh

cmake -S . -B build
cmake --build build
cd build && ctest --output-junit ../output.xml
