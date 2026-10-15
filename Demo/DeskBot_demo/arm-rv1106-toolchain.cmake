set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR arm)

set(TOOLCHAIN_ROOT
    /home/mango/ai/Echo-Mate/SDK/rv1106-sdk/tools/linux/toolchain/arm-rockchip830-linux-uclibcgnueabihf)

set(CMAKE_C_COMPILER
    ${TOOLCHAIN_ROOT}/bin/arm-rockchip830-linux-uclibcgnueabihf-gcc)

set(CMAKE_CXX_COMPILER
    ${TOOLCHAIN_ROOT}/bin/arm-rockchip830-linux-uclibcgnueabihf-g++)

set(CMAKE_SYSROOT
    ${TOOLCHAIN_ROOT}/arm-rockchip830-linux-uclibcgnueabihf/sysroot)

set(CMAKE_FIND_ROOT_PATH
    ${CMAKE_SYSROOT})

# 程序在宿主机找
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)

# 头文件和库只能在目标板 sysroot 找
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)

