#include "Idle.h"
#include "../../Utils/user_log.h"
#include "../../third_party/snowboy/include/snowboy-detect-c-wrapper.h"
#include "../../Events/AppEvents.h"

// 静态成员变量定义
std::atomic<bool> IdleState::state_running_{false};
std::thread IdleState::state_running_thread_;

void IdleState::Enter(Application* app) {//调用 IdleState 这个类里面的函数
    std::string json_message = R"({"type": "state", "state": "idle"})";
    app->ws_client_.SendText(json_message);//对象.  指针->
    // clear recorded audio queue
    app->audio_processor_.clearRecordedAudioQueue();
    // 开启录音
    app->audio_processor_.startRecording();
    // start state running
    state_running_.store(true);
    state_running_thread_ = std::thread([app]() { Run(app); });//把对应的run创建为线程
    USER_LOG_INFO("Into Idle state.");
}

void IdleState::Run(Application* app) {
    USER_LOG_INFO("Idle state run.");
    SnowboyDetect* detector = SnowboyDetectConstructor("third_party/snowboy/resources/common.res",
                                                     "third_party/snowboy/resources/models/echo.pmdl");
    SnowboyDetectSetSensitivity(detector, "0.5");
    SnowboyDetectSetAudioGain(detector, 1);
    SnowboyDetectApplyFrontend(detector, false);
    std::vector<int16_t> data;
    while (state_running_.load() == true) {
        if(app->audio_processor_.recordedQueueIsEmpty() == false) {
            //从录音队列取出一块PCM音频
            app->audio_processor_.getRecordedAudio(data);
            // 检测唤醒词 // 把这一块音频交给Snowboy
            //这些是在板子上实现的
            int result = SnowboyDetectRunDetection(detector, data.data(), data.size(), false);
            if (result > 0) {
                // 检测到唤醒词，发送唤醒事件
                USER_LOG_INFO("Wake detected.");
                app->eventQueue_.Enqueue(static_cast<int>(AppEvent::wake_detected));
                break;
            }
        }
    }
    SnowboyDetectDestructor(detector);//释放检测器
}

void IdleState::Exit(Application* app) {//退出空闲状态
    // stop录音
    app->audio_processor_.stopRecording();
    // stop running 是为了通知当前状态的工作线程退出
    state_running_.store(false);
    state_running_thread_.join();
    //下次再调用idle重新创建线程
    // playing waked up sound
    //退出前指定本地语音
    std::string waked_sound_path = "third_party/audio/waked.pcm";//本地机器人声音
//   是为了用户唤醒机器人后，播放一段本地提示音，让用户知道“已经唤醒，可以说话了”。
    auto audioQueue = app->audio_processor_.loadAudioFromFile(waked_sound_path, 40);//把音频读取；出来分割成40ms一帧
    while (!audioQueue.empty()) {//把一个音频队列里的音频帧，逐个取出来，放入播放队列，然后从原队列删除
        const auto& frame = audioQueue.front();
        app->audio_processor_.addFrameToPlaybackQueue(frame);
        audioQueue.pop();
    }
    // 本地提示音没有服务器发送 tts.end，因此需要在加载完成后手动设置。 
    // 否则标志一直是 false，即使提示音播放结束，Speaking 的完成判断也无法通过
    // ，就不能正常进入 Listening。
    app->set_tts_completed(true);
    std::this_thread::sleep_for(std::chrono::milliseconds(200));
    USER_LOG_INFO("Idle State exit.");
}