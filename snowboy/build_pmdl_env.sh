#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v docker >/dev/null 2>&1; then
    printf '%s\n' 'Docker is not installed. See PMDL_SETUP.md for installation steps.' >&2
    exit 1
fi
if ! docker info >/dev/null 2>&1; then
    printf '%s\n' 'Cannot access Docker. Check the service, or run: sudo bash build_pmdl_env.sh' >&2
    exit 1
fi
if [[ ! -f "$script_dir/seasalt-src/examples/Python/generate_pmdl.py" ]]; then
    printf '%s\n' 'Missing seasalt-src. See PMDL_SETUP.md for the download command.' >&2
    exit 1
fi

build_args=()
if [[ -n "${SNOWBOY_BUILD_PROXY:-}" ]]; then
    # RUN 步骤在容器中执行，使用主机网络才能访问主机的 127.0.0.1 代理。
    # Docker 服务的代理负责拉镜像；下面的构建参数负责 apt/pip 下载。
    build_args+=(--network=host
        --build-arg "HTTP_PROXY=$SNOWBOY_BUILD_PROXY"
        --build-arg "HTTPS_PROXY=$SNOWBOY_BUILD_PROXY"
        --build-arg "http_proxy=$SNOWBOY_BUILD_PROXY"
        --build-arg "https_proxy=$SNOWBOY_BUILD_PROXY"
        --build-arg "NO_PROXY=localhost,127.0.0.1,::1"
        --build-arg "no_proxy=localhost,127.0.0.1,::1")
fi
docker build --tag snowboy-pmdl --file "$script_dir/Dockerfile.pmdl" \
    "${build_args[@]}" "$@" "$script_dir"
