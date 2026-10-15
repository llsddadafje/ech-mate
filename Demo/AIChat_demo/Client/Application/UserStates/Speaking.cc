#include "Speaking.h"
#include "../../Utils/user_log.h"
#include "../../Events/AppEvents.h"

// 静态成员变量定义
std::atomic<bool> SpeakingState::state_running_{false};//安全读写
std::thread SpeakingState::state_running_thread_;

void SpeakingState::Enter(Application* app) {
    std::string json_message = R"({"type": "state", "state": "speaking"})";
    //告诉服务器：当前进入 speaking 状态
    app->ws_client_.SendText(json_message);
    // start播放
    app->audio_processor_.startPlaying();
    // 启动线程，检查播放何时结束
    state_running_.store(true);
    state_running_thread_ = std::thread([app]() { Run(app); });//调用run
    USER_LOG_INFO("Into speaking state.");
}

void SpeakingState::Run(Application* app) {
    USER_LOG_INFO("Speaking state run.");
    while(state_running_.load() == true) {
            //每隔 500 ms 检查一次播放是否结束。
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
        if(app->get_tts_completed() && app->audio_processor_.playbackQueueIsEmpty()) {
            //因为播放队列为空，只表示数据已经被取走，
            //不代表扬声器已经播完。最后一块音频可能还在 PortAudio 或音频设备的缓冲区中。
            //因为收到“结束对话”的通知时，最后一句回复可能还没播放完
            std::this_thread::sleep_for(std::chrono::milliseconds(500));
            USER_LOG_INFO("Speaking end.");
            
            //判断整个对话是否结束
            //Speaking肯定建立在对话没有结束的基础上
            if(app->get_dialogue_completed() == false) {
                app->eventQueue_.Enqueue(static_cast<int>(AppEvent::speaking_end));
                 // 这次声音播完，接着听用户说话
            } else {
                app->eventQueue_.Enqueue(static_cast<int>(AppEvent::dialogue_end));
               // 整个对话结束，回去等待唤醒
            }
            app->set_tts_completed(false);
            app->set_dialogue_completed(false);
            break;
        }
    }
}

void SpeakingState::Exit(Application* app) {
    // clear playback audio queue
    //清空播放队列
    app->audio_processor_.clearPlaybackAudioQueue();
    // stop播放停止
    app->audio_processor_.stopPlaying();
    // stop state running
    state_running_.store(false);//标记运行标志 控制线程停止，以及保证跨线程读写安全。
    state_running_thread_.join();
    USER_LOG_INFO("Speaking exit.");
}
