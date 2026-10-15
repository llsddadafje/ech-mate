#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if (( $# > 2 )); then
    printf '%s\n' 'Usage: bash generate_pmdl.sh [recording_directory] [zh|en]' >&2
    exit 1
fi
recording_dir="${1:-$script_dir/model}"
model_language="${2:-zh}"
if [[ "$model_language" != zh && "$model_language" != en ]]; then
    printf '%s\n' 'Language must be zh or en.' >&2
    exit 1
fi
if [[ ! -d "$recording_dir" ]]; then
    printf 'Recording directory does not exist: %s\n' "$recording_dir" >&2
    exit 1
fi
recording_dir="$(cd -- "$recording_dir" && pwd)"
for recording_name in record1.wav record2.wav record3.wav; do
    if [[ ! -s "$recording_dir/$recording_name" ]]; then
        printf 'Missing or empty recording: %s/%s\n' "$recording_dir" "$recording_name" >&2
        exit 1
    fi
done
if [[ -e "$recording_dir/my_wake.pmdl" ]]; then
    printf '%s\n' 'my_wake.pmdl already exists. Back it up or use another recording directory.' >&2
    exit 1
fi
if ! command -v docker >/dev/null 2>&1; then
    printf '%s\n' 'Docker is not installed. See PMDL_SETUP.md.' >&2
    exit 1
fi
if ! docker image inspect snowboy-pmdl >/dev/null 2>&1; then
    printf '%s\n' 'Cannot access image snowboy-pmdl. Build it first, and check Docker permissions.' >&2
    exit 1
fi

# 即使由 sudo 启动，输出模型也使用原用户的 uid/gid。
model_uid="${SUDO_UID:-$(id -u)}"
model_gid="${SUDO_GID:-$(id -g)}"
docker run --rm --user "$model_uid:$model_gid" \
    --mount "type=bind,source=$recording_dir,target=/data" \
    snowboy-pmdl \
    -r1=/data/record1.wav -r2=/data/record2.wav -r3=/data/record3.wav \
    "-lang=$model_language" -n=/data/my_wake.pmdl

if [[ ! -s "$recording_dir/my_wake.pmdl" ]]; then
    printf '%s\n' 'Generation finished without a non-empty model file.' >&2
    exit 1
fi
printf 'Generated model: %s/my_wake.pmdl\n' "$recording_dir"
