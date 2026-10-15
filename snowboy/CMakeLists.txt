cmake_minimum_required(VERSION 3.16)
project(SnowboyLearning LANGUAGES CXX)

# 学习示例复用仓库已有的库和模型，无需下载，也无需构建完整的 AIChat。
set(SNOWBOY_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../Demo/AIChat_demo/Client/third_party/snowboy"
    CACHE PATH "Path to existing Snowboy library and resources")
get_filename_component(SNOWBOY_ROOT "${SNOWBOY_ROOT}" ABSOLUTE)

if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux" OR
   NOT CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|amd64|AMD64)$")
    message(FATAL_ERROR "This learning example currently targets x86_64 Linux, not the RV1106 board.")
endif()

set(SNOWBOY_LIBRARY "${SNOWBOY_ROOT}/lib/ubuntu64/libsnowboy-detect.a")
foreach(required_file IN ITEMS
        "${SNOWBOY_LIBRARY}"
        "${SNOWBOY_ROOT}/include/snowboy-detect.h"
        "${SNOWBOY_ROOT}/resources/common.res"
        "${SNOWBOY_ROOT}/resources/models/snowboy.umdl"
        "${SNOWBOY_ROOT}/resources/snowboy.raw")
    if(NOT EXISTS "${required_file}")
        message(FATAL_ERROR "Missing Snowboy file: ${required_file}")
    endif()
endforeach()

find_package(BLAS REQUIRED)
find_package(LAPACK REQUIRED)
find_package(Threads REQUIRED)

add_executable(file_detect file_detect.cc)
target_compile_features(file_detect PRIVATE cxx_std_17)
target_compile_options(file_detect PRIVATE -Wall -Wextra -Wpedantic)
# 仓库的预编译 Snowboy 库使用旧版 libstdc++ 字符串 ABI。
target_compile_definitions(file_detect PRIVATE
    _GLIBCXX_USE_CXX11_ABI=0
    SNOWBOY_RESOURCE_DIR="${SNOWBOY_ROOT}/resources")
target_include_directories(file_detect PRIVATE "${SNOWBOY_ROOT}/include")
target_link_libraries(file_detect PRIVATE
    "${SNOWBOY_LIBRARY}" ${LAPACK_LIBRARIES} ${BLAS_LIBRARIES} Threads::Threads)
