# Echo-Mate：从麦克风 PCM 到 Snowboy 检测的流程与问答

整理日期：2026-10-02。

本文根据当前项目代码和我们的学习问答整理，重点是“麦克风采集 → PCM 音频块 → 录音队列 → Snowboy 检测 → 唤醒事件”。不展开模型训练、Docker 环境或服务端识别实现。

代码示例是原代码的教学节选，增加了说明性注释；标注省略的地方不代表原程序没有错误处理。本文没有修改业务源码。文件链接及行号以整理时的代码为准，后续修改可能使行号变化。

## 1. 先记住这句话

**PortAudio 负责提供录音数据；项目回调把一块数据保存为 `vector` 并放入队列；待机线程从队列取出音频，交给 Snowboy 检测。**

```text
声音
  ↓ 麦克风及音频设备：将声音转换为数字采样
PortAudio：提供 16 kHz、单声道、16 位 PCM
  ↓ 按配置，每次回调提供约 40 ms 的数据
AudioProcess::recordCallback()
  ↓ 复制到项目自己持有的 vector<int16_t>
recordedAudioQueue：按顺序保存多个音频块
  ↓ AudioProcess::getRecordedAudio() 取出最早的一块
IdleState::Run()
  ↓ SnowboyDetectRunDetection()
Snowboy：检测唤醒词
  ↓ result > 0
eventQueue_：放入 wake_detected 事件编号
```

这里有两个不同的队列：

- `recordedAudioQueue`：存放 PCM 音频块。
- `eventQueue_`：存放事件编号，例如 `wake_detected`，不存放 PCM。

## 2. 相关文件与分工

| 文件 | 关键函数或内容 | 职责 |
| --- | --- | --- |
| [AudioProcess.h](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/Audio/AudioProcess.h:14) | 类声明、录音队列及同步成员 | 声明音频处理接口和成员变量 |
| [AudioProcess.cc](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/Audio/AudioProcess.cc:63) | `startRecording()`、`recordCallback()`、`getRecordedAudio()`、`stopRecording()` | 启动采集、复制音频、入队、出队、停止采集 |
| [Idle.cc](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/Application/UserStates/Idle.cc:10) | `IdleState::Enter()`、`Run()`、`Exit()` | 控制待机录音，调用 Snowboy，产生唤醒事件 |
| [snowboy-detect-c-wrapper.cc](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/third_party/snowboy/snowboy-detect-c-wrapper.cc:22) | `SnowboyDetectRunDetection()` | 将 C 风格接口调用转交给 Snowboy C++ 检测器 |
| [snowboy-detect.h](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/third_party/snowboy/include/snowboy-detect.h:46) | 检测接口、返回值和输入格式说明 | 说明检测器的使用约定 |
| [StateConfig.cc](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/Application/StateConfig.cc:25) | `StateConfig::Configure()` | 注册状态的进入/退出函数和切换规则 |
| [StateMachine.cc](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/StateMachine/StateMachine.cc:37) | `HandleEvent()`、`ChangeState()` | 根据事件切换状态，调用 `Exit()` 和 `Enter()` |
| [Application.cc](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/Application/Application.cc:32) | `Application::Run()` | 读取事件队列，将事件交给状态机 |
| [Listening.cc](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/Application/UserStates/Listening.cc:9) | `ListeningState::Enter()`、`Run()`、`Exit()` | 唤醒后采集讲话，Opus 编码并发送到服务端 |
| [ui.c](/home/mango/ai/Echo-Mate/Demo/DeskBot_demo/gui_app/ui.c:163) | 音频参数默认配置 | 设置 16000 Hz、单声道、40 ms 音频块 |

注意 `.h` 中通常是函数声明，`.cc` 中是函数实现。`startRecording()` 只是声明在头文件中，不是在头文件里完成采集。

## 3. 音频块是什么？640 个采样点和 1280 字节如何计算？

### 3.1 采样点、音频块、容器、队列

- 采样点：某个采样时刻的信号幅度，用一个数字表示，不是一个字或一个音节。
- 音频块：连续一小段时间的采样点集合。本文说的“PCM 帧”就是项目中的一块音频。
- `vector<int16_t>`：保存这一块音频的连续采样数组。
- `queue<vector<int16_t>>`：按先后顺序保存多块音频。

```text
一个 vector：
[120, 235, 180, -90, ...]  共 640 个采样点，代表 40 ms 声音

录音队列：
[第1块 vector] → [第2块 vector] → [第3块 vector] → ...
```

队列不是把所有块拼成一个越来越大的数组，每个元素仍是一块独立音频。

### 3.2 当前参数和计算

项目默认配置节选，所在文件：[ui.c](/home/mango/ai/Echo-Mate/Demo/DeskBot_demo/gui_app/ui.c:163)。

```cpp
ui_system_para.aichat_app_info.sample_rate = 16000; // 每秒16000个采样时刻
ui_system_para.aichat_app_info.channels = 1;        // 单声道
ui_system_para.aichat_app_info.frame_duration = 40; // 一块音频的时长：40毫秒
```

`AudioProcess` 构造函数也有相同的默认值；上面是界面侧默认配置，实际运行参数仍取决于传入值。

```text
40 ms = 40 ÷ 1000 = 0.04 秒

一块的采样点数量 = 采样率 × 时长 × 声道数
                 = 16000 × 0.04 × 1
                 = 640 个

int16_t 占 16 位；8 位 = 1 字节
每个采样点占用 = 16 ÷ 8 = 2 字节

一块的 PCM 数据大小 = 640 × 2 = 1280 字节
```

这里仅计算 PCM 有效数据，不包含 `vector`、队列的管理开销，也不包含 WAV 文件头；不是 Opus 压缩后的大小。

补充：PortAudio 的 `framesPerBuffer` 中，音频 frame 指一个采样时刻所有声道的样本。当前单声道时，它正好等于采样点数量；多声道时数组元素数量是 `framesPerBuffer × channels`。不要把这个 frame 和本文的“40 ms 音频块”混为一谈。

## 4. 第一步：进入待机状态，启动持续采集

所在文件：[Idle.cc](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/Application/UserStates/Idle.cc:10)。

```cpp
void IdleState::Enter(Application* app) {
    // 省略：通知服务端当前状态为idle。

    // 丢弃之前残留的录音块，准备检测新的音频。
    app->audio_processor_.clearRecordedAudioQueue();

    // 启动一次持续采集过程，不是只读取一块音频。
    app->audio_processor_.startRecording();

    // 开启待机检测线程：这个线程负责从队列取数据并调用Snowboy。
    state_running_.store(true);
    state_running_thread_ = std::thread([app]() { Run(app); });

    // 省略日志。
}
```

`IdleState` 是“待机状态”类。待机并不意味着什么都不做，而是暂时不进行对话，同时持续采集音频，等待唤醒词。

`startRecording()` 是进入状态时调用一次，不是每 40 ms 调用一次。

## 5. 第二步：PortAudio 打开音频流并注册回调

所在文件：[AudioProcess.cc 的 startRecording()](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/Audio/AudioProcess.cc:63)。

下面保留正常启动路径，省略重复启动检查、错误判断及日志。

```cpp
// 初始化PortAudio。
PaError err = Pa_Initialize();

PaStreamParameters inputParameters;
inputParameters.device = Pa_GetDefaultInputDevice(); // 选择默认录音设备
inputParameters.channelCount = channels;             // 当前配置为1
inputParameters.sampleFormat = paInt16;              // 16位有符号整数PCM
inputParameters.suggestedLatency =
    Pa_GetDeviceInfo(inputParameters.device)->defaultLowInputLatency;
inputParameters.hostApiSpecificStreamInfo = nullptr;

err = Pa_OpenStream(
    &recordStream,       // 输出参数：保存打开后的音频流句柄
    &inputParameters,    // 输入设备参数：麦克风
    nullptr,             // 该音频流不负责播放
    sample_rate,         // 当前配置为16000 Hz
    sample_rate / 1000 * frame_duration_ms, // 当前为640个采样时刻
    paClipOff,
    recordCallback,      // 注册回调：PortAudio收到数据时调用它
    this                // 当前AudioProcess对象，回调通过userData取回
);

err = Pa_StartStream(recordStream); // 正式启动持续采集
isRecording = true;
```

此后麦克风持续采集，PortAudio 按设置的块大小提供数据并调用 `recordCallback()`。

不是项目写一个 `sleep(40 ms)`，到点再录一下。40 ms 是每块音频覆盖的时间长度，系统调度不保证回调严格每隔 40 ms 执行一次。正常连续采集时，块与块之间不是人为留出空白。

### PortAudio 和项目代码的边界

- PortAudio：初始化音频系统、选择设备、打开/启停音频流、提供输入缓冲区、调用回调。
- 项目的 `recordCallback()`：复制数据、管理 `vector`、操作录音队列。
- 音频设备和驱动：承担底层采集；不能根据这段代码确认底层是否还有额外音频处理。

PortAudio 不直接操作项目的录音队列，也不检测唤醒词。

## 6. 第三步：回调复制 PCM 到 vector，并入队

队列及相关成员声明在 [AudioProcess.h](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/Audio/AudioProcess.h:155)。

```cpp
std::queue<std::vector<int16_t>> recordedAudioQueue; // 每个元素是一块音频
std::mutex recordedAudioMutex;                      // 用于保护队列读写
std::condition_variable recordedAudioCV;            // 用于通知等待数据的线程
PaStream* recordStream;                             // PortAudio录音流
bool isRecording;                                  // 项目维护的录音状态
```

回调实现位于 [AudioProcess.cc 的 recordCallback()](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/Audio/AudioProcess.cc:171)。

```cpp
int AudioProcess::recordCallback(
    const void* inputBuffer,
    void* outputBuffer,
    unsigned long framesPerBuffer,
    const PaStreamCallbackTimeInfo* timeInfo,
    PaStreamCallbackFlags statusFlags,
    void* userData
) {
    // 录音回调不使用输出缓冲区；当前实现也未处理时间和状态信息。
    (void) outputBuffer;
    (void) timeInfo;
    (void) statusFlags;

    // 取回Pa_OpenStream()时传入的this，找到当前音频处理对象。
    AudioProcess* audioProcess = static_cast<AudioProcess*>(userData);

    // 把输入缓冲区按16位整数数组读取；此强制转换本身不转换音频。
    const int16_t* input = static_cast<const int16_t*>(inputBuffer);

    // 分配一块音频的存储。当前是640 × 1 = 640个int16_t。
    std::vector<int16_t> frame(framesPerBuffer * audioProcess->channels);

    // 将PortAudio提供的PCM复制到项目自己的存储中。
    std::copy(
        input,
        input + framesPerBuffer * audioProcess->channels,
        frame.begin()
    );

    {
        // 锁住队列，避免入队与受锁保护的取队操作同时修改它。
        std::lock_guard<std::mutex> lock(audioProcess->recordedAudioMutex);

        // 队列达到750块时先丢弃最旧的一块，限制积压。
        if (audioProcess->recordedAudioQueue.size() >= 750) {
            audioProcess->recordedAudioQueue.pop();
        }

        // 把整个vector作为一个队列元素保存，不是逐个采样点入队。
        audioProcess->recordedAudioQueue.push(frame);
    }

    // 通知可能正在getRecordedAudio()中等待音频的线程。
    audioProcess->recordedAudioCV.notify_one();

    return paContinue; // 告诉PortAudio继续运行音频流
}
```

### 为什么必须保存数据，而不能只保存 inputBuffer 指针？

`inputBuffer` 的内存由 PortAudio 管理。不能把它的指针留在队列中，指望另一个线程稍后仍能读取同一块数据；回调返回后，缓冲区可能被复用。因此项目需要保存自己的数据副本。

### 为什么用 vector 加 queue？

`vector` 负责“一块音频的连续存储”，`queue` 负责“多块音频按顺序等待处理”。录音端不需要同步等待 Snowboy 完成检测，队列可以吸收两边处理速度的短暂差异。

当然也可以写成 `queue<int16_t>`，但那样一块音频要逐个入队 640 个采样点；检测时还需要取出并组织成连续数组。当前设计直接以整块为单位管理更方便。

`vector` 不是唯一选择，数组或其他自有缓冲区也可以承担保存音频块的角色。关键是要拥有这块数据，并保留传递给检测器所需的格式和顺序。

当前 `push(frame)` 还会复制这个 `vector`；“先建容器再入队”并不一定要写成两句，可以通过移动或直接构造减少复制。但这些属于实现优化，本文保留当前源码行为，没有修改代码。

## 7. 第四步：检测线程从录音队列取出一块音频

所在文件：[AudioProcess.cc 的 getRecordedAudio()](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/Audio/AudioProcess.cc:152)。

```cpp
bool AudioProcess::getRecordedAudio(std::vector<int16_t>& recordedData) {
    // 与入队使用同一把互斥锁。
    std::unique_lock<std::mutex> lock(recordedAudioMutex);

    // 等到有数据，或者项目状态表明已停止录音。
    // 条件变量等待期间会释放锁，让录音回调能继续入队。
    recordedAudioCV.wait(lock, [this] {
        return !recordedAudioQueue.empty() || !isRecording;
    });

    if (recordedAudioQueue.empty()) {
        return false; // 此时没有可返回的音频块
    }

    // 将队首vector与调用者的vector交换，取得最早的一块音频。
    recordedData.swap(recordedAudioQueue.front());

    // 移除交换后的队首元素，完成一次出队。
    recordedAudioQueue.pop();
    return true;
}
```

这里的 `swap()` 是交换容器内容，不是再把所有采样点逐个复制一遍。

## 8. 第五步：IdleState::Run() 调用 Snowboy

所在文件：[Idle.cc 的 IdleState::Run()](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/Application/UserStates/Idle.cc:23)。

```cpp
void IdleState::Run(Application* app) {
    // 省略日志。

    // 创建一次检测器，加载公共资源和项目当前的个人唤醒词模型。
    SnowboyDetect* detector = SnowboyDetectConstructor(
        "third_party/snowboy/resources/common.res",
        "third_party/snowboy/resources/models/echo.pmdl"
    );

    SnowboyDetectSetSensitivity(detector, "0.5"); // 检测灵敏度
    SnowboyDetectSetAudioGain(detector, 1);       // 固定增益1，不额外放大
    SnowboyDetectApplyFrontend(detector, false); // 关闭可选音频增强前端

    std::vector<int16_t> data; // 接收从队列取出的音频块

    while (state_running_.load() == true) {
        if (app->audio_processor_.recordedQueueIsEmpty() == false) {
            // 由项目取出音频，Snowboy本身不直接读取队列。
            app->audio_processor_.getRecordedAudio(data);

            int result = SnowboyDetectRunDetection(
                detector,
                data.data(), // 指向连续PCM采样数组
                data.size(), // 数组元素数：当前通常为640，不是1280字节
                false        // 不是一句话或文件的结束标记，继续处理实时流
            );

            if (result > 0) {
                // 省略日志。
                // 放入的是唤醒事件编号，不是PCM音频块。
                app->eventQueue_.Enqueue(
                    static_cast<int>(AppEvent::wake_detected)
                );
                break;
            }
        }
    }

    SnowboyDetectDestructor(detector); // 本轮待机检测结束，释放检测器
}
```

检测器在循环外创建。同一个检测器连续处理前后音频块，保留跨块检测所需的状态；一块 40 ms 音频不需要包含完整唤醒词。不要为了每块音频重新创建检测器。

当前业务代码仍然加载 `echo.pmdl`。学习目录里的 `snowboy/model/my_wake.pmdl` 不会因为生成或文件测试成功而自动接入这个流程。

### 8.1 C 风格封装最终调用了什么？

所在文件：[snowboy-detect-c-wrapper.cc](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/third_party/snowboy/snowboy-detect-c-wrapper.cc:22)。

```cpp
int SnowboyDetectRunDetection(
    SnowboyDetect* detector,
    const int16_t* const data,
    const int array_length,
    bool is_end
) {
    assert(detector != NULL);
    assert(data != NULL);

    // 只是接口转接，未在这里重新编码或复制音频到另一个队列。
    return reinterpret_cast<snowboy::SnowboyDetect*>(detector)
        ->RunDetection(data, array_length, is_end);
}
```

因此调用链是：

```text
IdleState::Run()
  → SnowboyDetectRunDetection()
  → snowboy::SnowboyDetect::RunDetection()
```

### 8.2 检测返回值

依据本地 [snowboy-detect.h](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/third_party/snowboy/include/snowboy-detect.h:59)。

| 返回值 | 意义 |
| --- | --- |
| `-2` | 静音 |
| `-1` | 检测错误 |
| `0` | 没有事件 |
| `1` | 第一个唤醒词触发 |
| `2` 等正整数 | 对应编号的唤醒词触发 |

当前代码使用 `result > 0` 判断是否唤醒。

## 9. 谁决定什么时候启动和停止录音？

### 9.1 直接调用位置

| 时机 | 调用者 | 调用的函数 |
| --- | --- | --- |
| 进入待机，等待唤醒词 | [IdleState::Enter()](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/Application/UserStates/Idle.cc:10) | `startRecording()` |
| 离开待机 | [IdleState::Exit()](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/Application/UserStates/Idle.cc:48) | `stopRecording()` |
| 进入聆听，接收用户讲话 | [ListeningState::Enter()](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/Application/UserStates/Listening.cc:9) | `startRecording()` |
| 离开聆听 | [ListeningState::Exit()](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/Application/UserStates/Listening.cc:51) | `stopRecording()` |

这解释了为什么命名为“启动录音”，而不是“读取音频”：它控制一个持续采集过程。读取已经采集好的一块数据则是 `getRecordedAudio()`。

这里“录音”不意味着一定写入文件；当前唤醒路径使用内存队列。

### 9.2 谁调用状态的 Enter() 和 Exit()？

[StateConfig::Configure()](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/Application/StateConfig.cc:25)先注册回调：

```cpp
// 这里只是登记函数；注册本身不会立即执行IdleState::Enter()。
state_machine.RegisterState(
    static_cast<int>(AppState::idle),
    [app]() { IdleState::Enter(app); },
    [app]() { IdleState::Exit(app); }
);
```

[Application::Run()](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/Application/Application.cc:32)启动事件处理线程，从 `eventQueue_` 取出事件并调用 `HandleEvent()`。它根据规则确定新状态，随后调用 [ChangeState()](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/StateMachine/StateMachine.cc:53)。

```cpp
void StateMachine::ChangeState(int newState) {
    // second保存退出回调：先离开旧状态。
    if (stateActions_.find(currentState_) != stateActions_.end()) {
        stateActions_[currentState_].second();
    }

    currentState_ = newState;

    // first保存进入回调：再进入新状态。
    if (stateActions_.find(currentState_) != stateActions_.end()) {
        stateActions_[currentState_].first();
    }
}
```

进入待机的调用关系可以记为：

```text
启动完成事件 startup_done
  → Application事件线程读取事件
  → StateMachine::HandleEvent()
  → StateMachine::ChangeState(idle)
  → IdleState::Enter()
  → AudioProcess::startRecording()
  → PortAudio持续采集并调用recordCallback()
```

停止采集时，[AudioProcess::stopRecording()](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/Audio/AudioProcess.cc:121)的正常路径是：

```cpp
// 省略状态检查和错误处理。
Pa_StopStream(recordStream);  // 停止采集
Pa_CloseStream(recordStream); // 关闭录音流
Pa_Terminate();               // 释放本次初始化对应的PortAudio资源
isRecording = false;
```

## 10. 送入 Snowboy 前，音频到底经过了什么处理？

当前待机路径中，应用层做的是：

```text
获取指定格式的PCM → 按块复制 → 入队 → 出队 → 调用检测器
```

没有在这段调用链中额外执行 Opus 编码、重采样、降噪滤波或幅度归一化。复制到 `vector` 不改变采样值，排队也不是音频编码。

`SnowboyDetectSetAudioGain(detector, 1)` 不额外放大音频；`SnowboyDetectApplyFrontend(detector, false)` 关闭 Snowboy 可选的音频增强前端。接口说明列举了自动增益控制和噪声抑制等前端处理，并建议个人模型关闭该前端，见 [snowboy-detect.h](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/third_party/snowboy/include/snowboy-detect.h:126)。

这不意味着 Snowboy 内部没有识别处理。接口说明指出它内部包含 VAD；模型检测所需的内部计算不能与“外部未进行 Opus 编码或降噪”混为一谈。

### Opus 编码发生在哪里？

发生在唤醒后的 [ListeningState::Run()](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/Application/UserStates/Listening.cc:25)，不是 `IdleState::Run()`。

```cpp
// 节选：聆听状态从同一录音队列取出PCM。
if (app->audio_processor_.getRecordedAudio(audio_frame)) {
    uint8_t opus_data[1536];
    size_t opus_data_size;

    // 在聆听路径中执行PCM → Opus编码。
    if (app->audio_processor_.encode(
            audio_frame, opus_data, opus_data_size)) {
        // 省略：协议打包、WebSocket发送和错误处理。
    }
}
```

```text
待机 Idle：       PCM → 录音队列 → Snowboy
聆听 Listening： PCM → 录音队列 → Opus编码 → WebSocket发送
```

在不同状态下，音频块有不同用途；不是每个块都会先后走完这两条路径。

## 11. 检测到唤醒词之后的边界

本篇的核心流程在 `wake_detected` 入队时结束。但后续不等于“完全不再涉及音频”。

[StateConfig.cc](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/Application/StateConfig.cc:43)配置的是：

```text
Idle（检测唤醒词）
  ↓ wake_detected
Speaking（播放唤醒提示音）
  ↓ speaking_end
Listening（接收用户讲话）
```

[IdleState::Exit()](/home/mango/ai/Echo-Mate/Demo/AIChat_demo/Client/Application/UserStates/Idle.cc:48)停止录音和检测线程，读取 `third_party/audio/waked.pcm` 并放入播放队列；Speaking 状态启动播放。提示音播放完成后，Listening 状态再次启动采集。

因此：唤醒事件处理本身不携带或检测 PCM，但状态切换所触发的进入/退出函数还会管理录音和播放。

## 12. 我们问过的问题与澄清

下面保留这部分学习讨论中的问题原意或原句。重复追问归在同一项；插件界面等与音频链路无关的问题不纳入本文。

### Q1：“snowboy在这个项目中如何用的？”

Snowboy 在待机状态中进行本地唤醒词检测，不负责完整语音转文字或生成回答。当前加载的是 `echo.pmdl`，学习测试模型不会自动替换它。

### Q2：“音频队列如何得到的？”

队列是 `AudioProcess` 的成员。PortAudio 调用 `recordCallback()` 后，由项目回调把每次收到的 PCM 保存成 `vector` 并入队，不是 Snowboy 生成队列。

### Q3：“IdleState 是什么？16000 × 0.04 = 640 个采样点，640 × 2 字节 = 1280 字节，这个是怎么算的？”

IdleState 是待机状态类。16000 Hz 表示每秒 16000 个采样时刻，40 ms 是 0.04 秒，单声道得到 640 个采样点；每点 16 位，也就是 2 字节，总共 1280 字节。完整推导见第 3 节。

### Q4：“为什么频率设置为16khz而不是32khz？”

这里说的是采样率，不是声音本身的频率。当前 Snowboy 检测器所要求的输入是 16 kHz、单声道、16 位，之前的文件测试也输出了该要求。接口提供 `SampleRate()`、`NumChannels()`、`BitsPerSample()` 查询需求。

不能仅把录音参数改为 32 kHz，就把数据原样交给按 16 kHz 工作的检测器；若用 32 kHz 采集，应先正确重采样。32 kHz 的原始数据量是 16 kHz 的两倍，并不保证当前模型检测效果更好。

从采样理论看，16 kHz 采样能表示的频率上限约为 8 kHz，32 kHz 对应约 16 kHz；高采样率能保留更多高频细节，但本项目首先需要满足模型输入要求。

### Q5：“声音传到snowboy之前经过了怎么样的处理？”

应用层进行指定格式采集、按块复制、入队和出队，然后直接送进检测器。未在该路径额外编码、重采样或降噪；Snowboy 可选前端也关闭了。不能据此推断设备或驱动完全没有处理，也不能推断 Snowboy 内部不做识别计算。

### Q6：“为什么是先放到容器再放进队列，而不是直接放进队列？还有经过opus编码了吗”

`vector` 保存一块连续数据，队列保存多个块的顺序。数据需要有自己的存储，因为 PortAudio 的输入缓冲区会复用。可以在入队时直接构造容器，并不是必须先写一个局部变量。送给 Snowboy 的音频没有经过 Opus，Opus 用于 Listening 状态的网络发送。

### Q7：“PCM帧是这么得到的？”

PCM 来自采集链路；PortAudio 按配置提供一块音频，回调保存这一块。`vector` 不负责把模拟声音变成 PCM，`static_cast` 也不进行采样或格式转换。

### Q8：“portaudio起到什么作用”“portaudio是如何用的在这个项目中？”

它是程序和音频设备之间的桥梁，负责打开、启动、停止音频流以及通过回调交接录音/播放数据。项目在 `AudioProcess` 中封装它，录音回调接收数据，播放回调填入输出数据。

### Q9：“他是负责把pcm复制到容器再放到队列中吗”“啊？我糊涂了，那portaudio操作的是什么？”

PortAudio 操作音频设备和缓冲区，并调用项目注册的回调。复制到 `vector`、放入队列是项目的 `recordCallback()` 做的。虽然回调由 PortAudio 调用，但回调内部的代码属于项目。

### Q10：“就是从麦克风那里读取音频pcm帧，再放到容器中，最后把整个块整合到队列中”

基本正确，但“整合”应理解为把整块作为一个元素入队，不是把全部音频拼成一个大块。每个 `vector` 仍保存自己的 40 ms 音频。

### Q11：“这些操作都是在audioprocess这个文件中吗”

具体采集、复制、入队和出队在 `AudioProcess.cc`，声明和队列成员在 `AudioProcess.h`。决定什么时候采集，以及把取出的音频送给 Snowboy，则在 `Idle.cc`。

### Q12：“因为采样数据是一小块一小块的，等凑好了一起放进队列中吗，为什么这样设计呢？”

不是先积攒很多个 40 ms 小块再统一入队，而是每收到一个块就保存并入队。麦克风采样是连续的，PortAudio 按块提供回调输入。分块兼顾实时响应和调用开销，队列把采集和检测线程连接起来。

### Q13：“那你不是说把每一个放进容器再放进队列吗”

之前“每一个”的表达不够准确。正确说法是：640 个采样点组成一个 `vector`，整个 `vector` 作为一个元素入队。不是每个采样点对应一个 `vector`，也不是每个采样点单独入队。

### Q14：“那就是40ms为一块音频数据放到vector中，再把vector中的音频数据放到队列中？为什么这么设计？”

是，但应说“整个 vector 入队”。`vector` 提供连续存储，队列提供顺序和缓冲：检测第 1 块时，第 2 块可以先入队等待。若每个采样点入队，单声道每秒需要处理 16000 次入队；40 ms 一块通常每秒约 25 次。

### Q15：“为什么不直接放到队列中，而是多一步放到容器中呢？”

队列需要确定元素类型。当前元素类型就是 `vector<int16_t>`，代表一块音频，不是额外做一遍音频处理。可以直接在队列中构造 `vector`，或使用别的自有音频块结构，但仍需保存 PCM，不能只存临时缓冲区指针。

### Q16：“是每40ms取一次音频数据吗？”（多次确认）

可以理解为通常每约 40 ms 收到一块录音，但不是主程序定时去“录一下”。PortAudio 持续采集，按配置给回调一块覆盖 40 ms 的数据；回调执行时间受调度影响，不保证严格的 40 ms 定时。Snowboy 出队也不是另设一个固定 40 ms 定时器。

### Q17：“为什么audioprocess.h中定义启动录音和停止录音呢……应该叫做读取音频”

头文件里是声明。“启动/停止录音”控制持续采集的生命周期，不代表一定保存文件；“读取一块音频”是 `getRecordedAudio()`。如果想避免“录音=保存文件”的歧义，`startCapture()`、`stopCapture()` 是更明确的命名选择，但本文未重命名。

### Q18：“什么时候会用启动录音？”

进入 Idle 时开启采集，供 Snowboy 检测唤醒词；进入 Listening 时开启采集，供后续编码和发送。因此待机时就已经在采集，不是唤醒后才第一次打开麦克风。

### Q19：“这些东西是在哪个函数中调用的？”

`IdleState::Enter()` 和 `ListeningState::Enter()` 调用 `startRecording()`；各自的 `Exit()` 调用 `stopRecording()`。状态机根据事件调用进入/退出回调，详见第 9 节。

### Q20：“之后是snowboy检测队列中的音频吗，在哪个文件？”

在 `Idle.cc` 的 `IdleState::Run()`：项目先调用 `getRecordedAudio(data)` 取出音频，再调用 `SnowboyDetectRunDetection()`。Snowboy 不直接读取队列。

### Q21：“后面就是唤醒事件进行处理了，不牵涉到音频了吧”

唤醒事件只是一个编号，不包含音频；但处理事件会触发状态切换，退出待机、播放提示音、重新开始聆听，因此后续仍涉及音频。结束的是这一轮 Snowboy 唤醒检测，不是全部音频工作。

## 13. 阅读当前源码时的注意事项

本文描述的是当前实现，不代表实时音频代码的完整最佳实践。阅读时注意：

- `recordCallback()` 会动态创建 `vector`、复制、加锁及操作队列；这些操作不是 PortAudio 自动完成的音频算法。
- 当前 `push(frame)` 会复制容器，优化讨论不能误当作已经实施的改动。
- 入队和 `getRecordedAudio()` 的出队使用了互斥锁，但头文件的 `recordedQueueIsEmpty()` 直接调用 `empty()`，没有加同一把锁。不要把本篇“使用锁”理解成已证明所有访问都线程安全。
- 当前 Idle 检测循环没有检查 `getRecordedAudio()` 的返回值；它是对现有行为的展示，不是改进后的示例。
- 队列只是暂时缓冲，不是无限存储；当前到 750 块会丢弃最旧音频。40 ms 配置下，750 块对应约 30 秒音频容量，不表示程序会等待 30 秒再检测。
- 40 ms 是项目的分块配置，不是 Snowboy 必须且只能接受的块时长；模型要求的采样率、声道数和采样格式则必须匹配。

## 14. 最后用三句话记住

1. PortAudio 提供 PCM，项目回调保存 PCM；两者不要混为一谈。
2. `vector` 装一块音频，`queue` 让多块音频排队；不是等整句话录完再检测。
3. `IdleState::Run()` 取出 PCM 并调用 Snowboy；唤醒事件随后交给状态机处理。
