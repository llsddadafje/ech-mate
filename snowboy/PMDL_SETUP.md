# 准备 Snowboy 个人模型生成环境

Seasalt 源码已下载到本目录的 `seasalt-src/`，当前下载版本为 `e69b1fa`。它包含 `generate_pmdl.py`、Ubuntu 16.04/Python 2.7 的预编译生成库，以及 `resources/pmdl/zh/` 中文注册资源。

上游地址：https://github.com/seasalt-ai/snowboy

上游的 `seasalt-src/Dockerfile` 保持原样。本目录另外提供 `Dockerfile.pmdl`：复用已下载源码，固定 Python 2 兼容依赖，只安装生成模型所需的 NumPy/SciPy，并在构建时检查原生库加载。音频录制在主机完成，容器里不需要 PyAudio。

当前主机是 Ubuntu 22.04 x86_64，已安装 Docker。首次构建在拉取基础镜像时网络超时；已验证主机的 `http://127.0.0.1:7897` 代理能访问 Docker Hub，但 Docker 服务没有代理设置。加载服务配置要求 sudo 密码，因此这里尚未完成镜像构建，也没有生成新模型。

## 1. 在主机安装 Docker

在自己的终端输入 sudo 密码，执行：

```bash
sudo apt-get update
sudo apt-get install -y docker.io
sudo systemctl start docker
sudo docker info
```

这些命令安装主机上的 Docker 服务；Ubuntu 16.04 基础镜像由下一步自动下载。

## 2. 构建生成环境

```bash
cd /home/mango/ai/Echo-Mate/snowboy
sudo bash build_pmdl_env.sh
```

镜像名称是 `snowboy-pmdl`。构建需要联网下载基础镜像和依赖。Ubuntu 16.04/Python 2 已较老，若仓库或依赖源不可用，应按构建日志处理；这些脚本尚未经过真实 Docker 构建验证。

### 当前主机拉取 Docker Hub 超时的处理

已准备 `docker-http-proxy.conf`，让 Docker 服务使用当前主机上已验证可用的 HTTP 代理。此配置针对当前代理端口 7897；更换电脑或代理端口时需相应调整。按照 Docker 官方的 systemd 配置方式：
https://docs.docker.com/engine/daemon/proxy/

在本目录执行（会重新加载配置并重启 Docker 服务）：

```bash
sudo install -D -m 0644 docker-http-proxy.conf /etc/systemd/system/docker.service.d/echo-mate-proxy.conf
sudo systemctl daemon-reload
sudo systemctl restart docker
sudo docker pull ubuntu:16.04
sudo env SNOWBOY_BUILD_PROXY=http://127.0.0.1:7897 bash build_pmdl_env.sh
```

Docker 服务的代理用于拉取镜像；`SNOWBOY_BUILD_PROXY` 用于构建期间的 apt/pip 下载。脚本为此启用主机网络，使构建容器能访问主机的 127.0.0.1 代理。这仅用于当前 x86_64 Linux 环境，代理需要在下载期间保持运行。

`DEPRECATED: The legacy builder is deprecated` 是构建器的弃用警告，本次停止构建的原因是基础镜像下载超时。

如果需要重新获取源码，仅在 `seasalt-src` 不存在时执行：

```bash
git clone --depth 1 https://github.com/seasalt-ai/snowboy.git seasalt-src
```

## 3. 准备录音

```bash
mkdir -p model
```

在 `model/` 中准备 `record1.wav`、`record2.wav`、`record3.wav`。同一个人每个文件只说一次相同唤醒词；要求 16 kHz、单声道、16-bit PCM WAV。每段开头结尾可以留少量静音。

已有录音可分别转换，例如：

```bash
ffmpeg -i /你的路径/录音1.wav -ar 16000 -ac 1 -c:a pcm_s16le model/record1.wav
```

此处的输入是带 WAV 文件头的音频，与学习示例读取的裸 PCM 不同。

## 4. 生成中文个人模型

```bash
sudo bash generate_pmdl.sh
```

默认中文 `zh`，默认输出为 `model/my_wake.pmdl`。脚本拒绝覆盖已有模型，并让生成文件归属于启动 sudo 的原用户。

英文或其他录音目录可这样指定：

```bash
sudo bash generate_pmdl.sh /绝对路径/录音目录 en
```

## 5. 用单独的录音测试模型

建议先使用该分支对应语言的检测资源，验证生成模型和运行库是否兼容；不要仅凭文件扩展名认定与原项目资源完全匹配。

例如在容器中用分支的检测接口，加载中文 `common.res` 并检测另一段同格式 WAV：

```bash
sudo docker run --rm \
  --mount "type=bind,source=$PWD/model,target=/data,readonly" \
  --entrypoint python2.7 \
  snowboy-pmdl -c '
from scipy.io import wavfile
from pmdl.snowboy_pmdl import SnowboyDetect
d = SnowboyDetect("resources/pmdl/zh/common.res", "/data/my_wake.pmdl")
d.SetSensitivity("0.5")
d.SetAudioGain(1.0)
rate, audio = wavfile.read("/data/test.wav")
assert rate == 16000 and audio.ndim == 1 and audio.dtype.name == "int16"
count = 0
for start in range(0, len(audio), 640):
    result = d.RunDetection(audio[start:start + 640].tobytes())
    if result > 0:
        count += 1
        print("Wake detected! Hotword index: %d" % result)
    elif result == -1:
        raise RuntimeError("Detection error")
print("Total detections: %d" % count)
'
```

`test.wav` 应是额外录制的测试音频；不是前面用于注册的三个文件。返回值大于 0 表示检测到唤醒词，0 表示无事件，-2 表示静音，-1 表示错误。该容器检测命令也需要等镜像构建成功后实际验证。
