#! /bin/bash

set -eou pipefail

VERSIONS=(
    1.15.2
    1.14.0
    1.13.0
    1.12.0
)

for version in "${VERSIONS[@]}"; do

    wget --continue -L https://github.com/google/googletest/archive/refs/tags/v${version}.tar.gz
    tar -xf v${version}.tar.gz

    OUT_DIR="_generated/gtest-${version}"
    mkdir -p ${OUT_DIR}/gtest

    # created fused source
    python -m fuse \
      googletest-${version}/googletest/src/gtest-all.cc \
      ${OUT_DIR}/gtest/gtest-all.cpp \
      googletest-${version}/googletest googletest-${version}/googletest/include

    # create fused header
    python -m fuse \
      googletest-${version}/googletest/include/gtest/gtest.h \
      ${OUT_DIR}/gtest/gtest.h \
      googletest-${version}/googletest googletest-${version}/googletest/include

    # test compilation
    g++ --std=c++14 -I ${OUT_DIR} googletest-${version}/googletest/src/gtest_main.cc ${OUT_DIR}/gtest/gtest-all.cpp
    ./a.out

    # Include license file
    cp googletest-${version}/LICENSE ${OUT_DIR}/LICENSE

    # Include Readme
    cat << EOF > ${OUT_DIR}/README
This is a fused version of googletest ${version} created by github.com/cwpearson/fused-gtest.
EOF
done

