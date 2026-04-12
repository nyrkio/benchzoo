#!/bin/bash
# Run the vanilla JUnit 5 sample-benchmark via Maven Surefire and copy
# the resulting junit XML out to ./output.xml for artifact upload.
#
# Surefire writes one XML file per test class to
# target/surefire-reports/TEST-<class>.xml. We have exactly one test
# class (SampleTest), so the glob below matches exactly one file. If a
# future revision adds more test classes, this will need to either
# aggregate them or upload the whole directory.
set -euo pipefail

cd "$(dirname "$0")"

mvn -q test

cp target/surefire-reports/TEST-*.xml output.xml
