# Snowboy 学习示例

本目录从“检测录音文件”开始学习 Snowboy，复用项目自带的库、模型和测试音频。无需连接 AIChat 服务器或打开麦克风。当前编译配置面向 x86_64 Linux 电脑；RV1106 板端需要另配交叉编译工具链。

项目里的实时麦克风采集、音频队列与唤醒检测流程，以及相关学习问答，见 [PCM 到 Snowboy 检测流程与问答](2026-10-02_PCM到Snowboy检测流程与问答.md)。

服务端发送音频、客户端接收解包与播放，以及本轮播放结束后的状态切换，见 [服务端发送音频到客户端播放结束流程与问答](2026-10-08_服务端发送音频到客户端播放结束流程与问答.md)。

VAD 返回值、VAD/ASR 独立缓冲区、对话轮次控制、LLM 历史与流式生成器，以及 TTS 音频和完成回调，见 [VAD 返回值到 ASR 与流式对话 TTS 流程及问答](2026-10-13_VAD返回值到ASR与流式对话TTS流程及问答.md)。

自己生成个人唤醒词模型，请看 [PMDL_SETUP.md](PMDL_SETUP.md)。本目录已经下载 Seasalt 分支，并提供中文模型生成的 Docker 配置和脚本。

## 1. 编译和运行

```bash
cd /home/mango/ai/Echo-Mate/snowboy
bash build.sh
./build/file_detect
```

默认模型是 `snowboy.umdl`，识别说出的英文单词 “snowboy”；默认输入是项目自带的 `snowboy.raw`。使用的是资源绝对路径，因此编译后的程序可以从其他工作目录启动。

期望输出：

```text
Audio requirements: 16000 Hz, 1 channel(s), 16 bits
Wake detected! Hotword index: 1
Total detections: 1
```

如果新电脑缺少编译依赖，在 Ubuntu/Debian 上安装：

```bash
sudo apt-get install build-essential cmake libblas-dev liblapack-dev
```

## 2. 读懂检测过程

打开 `file_detect.cc`，依次找下面三个操作：

```cpp
// 加载公共资源及训练好的唤醒词模型。
snowboy::SnowboyDetect detector(resource_path, model_path);

// 灵敏度越高，越容易触发，也可能增加误唤醒。
detector.SetSensitivity("0.5");

// 向同一个检测器连续输入音频片段。
int result = detector.RunDetection(frame.data(), samples, is_last_frame);
```

这里的 `is_last_frame` 表示文件是否结束；实际程序使用 `processed_bytes == audio_bytes`。实时麦克风流通常传 `false`。

| 返回值 | 含义 |
| --- | --- |
| 大于 0 | 检测到唤醒词；数值是从 1 开始的唤醒词编号 |
| 0 | 无事件 |
| -2 | 静音 |
| -1 | 检测错误 |

音频采用 16 kHz、单声道、16 位有符号小端裸 PCM。40 ms 音频对应 640 个样本、1280 字节。`int16_t` 数组接口的长度参数是样本数，而不是字节数。检测器会保留跨帧状态，不要每读一帧就重新创建检测器。

## 3. 用自己的录音练习

录制包含 “snowboy” 的音频，转换成裸 PCM：

```bash
ffmpeg -i /你的路径/录音.wav -ar 16000 -ac 1 -c:a pcm_s16le -f s16le /tmp/my-snowboy.raw
./build/file_detect /tmp/my-snowboy.raw
```

也可以用 ALSA 直接录制 5 秒裸 PCM，再检测（使用默认录音设备）：

```bash
arecord -r 16000 -c 1 -f S16_LE -t raw -d 5 /tmp/my-snowboy.raw
./build/file_detect /tmp/my-snowboy.raw
```

WAV 有文件头，不能直接作为本例的裸 PCM 输入；程序会拒绝常见的 RIFF/WAV 文件。裸 PCM 本身不记录采样率和声道数，所以转换时必须确保格式正确。

## 4. 改模型和灵敏度

参数顺序：

```text
file_detect [音频.raw [模型文件 [灵敏度]]]
```

例如，使用同一段录音比较不同灵敏度：

```bash
./build/file_detect /tmp/my-snowboy.raw ../Demo/AIChat_demo/Client/third_party/snowboy/resources/models/snowboy.umdl 0.4
./build/file_detect /tmp/my-snowboy.raw ../Demo/AIChat_demo/Client/third_party/snowboy/resources/models/snowboy.umdl 0.6
```

建议测试三种录音：正常说唤醒词、远距离说唤醒词、不包含唤醒词的日常讲话。记录检测次数，比较漏检和误唤醒。

模型文件定义实际唤醒词；改文件名不会改变识别内容。`.pmdl` 是个人模型，`.umdl` 是通用模型。本例只支持包含一个唤醒词的模型，音频增益为 1，前端处理关闭；换其他通用模型时应按该模型的说明调整 `ApplyFrontend()`。

原官方已公告于 2020 年底停止网站和 API 服务，旧教程中的官网训练流程已不可依赖。先学习使用已有模型，自定义新词需要另外确认可用的训练工具。公告：https://github.com/Kitt-AI/snowboy

## 5. 对照 Echo-Mate 的实时唤醒

查看 `../Demo/AIChat_demo/Client/Application/UserStates/Idle.cc`：

1. 进入 Idle 状态，开启麦克风录音。
2. 从录音队列中获取 `std::vector<int16_t>`。
3. 调用 `SnowboyDetectRunDetection()`，它通过 C 包装接口调用同一个 Snowboy 检测引擎。
4. 返回值大于 0 时，发送 `wake_detected` 事件。

从文件检测过渡到麦克风检测，核心变化是音频来源；模型加载、连续输入音频、判断返回值的流程相同。
