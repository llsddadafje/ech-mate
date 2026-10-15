#include "Listening.h"
#include "../../Utils/user_log.h"
#include "../../Events/AppEvents.h"

// 静态成员变量定义
std::atomic<bool> ListeningState::state_running_{false};
std::thread ListeningState::state_running_thread_;

void ListeningState::Enter(Application* app) {
    std::string json_message = R"({"type": "state", "state": "listening"})";
    app->ws_client_.SendText(json_message);
    // clear首次接收server音频消息
    //服务器回复音频的首包通知，这里的 true 实际表示“等待首包”
    app->set_first_audio_msg_received(true);
    //启动后台录音
    app->audio_processor_.startRecording();
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    // clear recorded audio queue
    //清空队列，丢弃之前状态(会切换状态)可能残留的旧音频已经积累的录音数据。
    app->audio_processor_.clearRecordedAudioQueue();
    // running
    state_running_.store(true);
    //清空后执行run进行本轮对话的打包
    state_running_thread_ = std::thread([app]() { Run(app); });
    USER_LOG_INFO("Into listening state.");
}

void ListeningState::Run(Application* app) {
    while (state_running_.load() == true) {
        // need a time out
        // audio_frame 里现在就是取出的 PCM 音频数据
        // 后面用它进行 Opus 编码
        std::vector<int16_t> audio_frame;
        if(app->audio_processor_.recordedQueueIsEmpty() == false) {
        
            if(app->audio_processor_.getRecordedAudio(audio_frame)) {
                // 编码
                uint8_t opus_data[1536];//只是临时存放数据的(缓冲区)
                size_t opus_data_size;
                //注意这个编码传参是引用
                if (app->audio_processor_.encode(audio_frame, opus_data, opus_data_size)) {
                    // 打包
                    //协议头（自定义的发送数据的格式）
                    BinProtocol* packed_frame = app->audio_processor_.PackBinFrame(
                        opus_data, opus_data_size, app->get_ws_protocolVersion()
                    );
                            // opus_data,                     // Opus 音频数据
                            // opus_data_size,                // 音频数据的字节数
                            // app->get_ws_protocolVersion()  // 通信协议版本号

                    if (packed_frame) {
                        // 发送 按字节发送
                        //因为音频数组是不固定大小不计入，因此用opus_data_size
                        app->ws_client_.SendBinary(reinterpret_cast<uint8_t*>(packed_frame), sizeof(BinProtocol) + opus_data_size);
                    } else {
                        USER_LOG_WARN("Audio Packing failed");
                    }
                } else {
                    USER_LOG_WARN("Audio Encoding failed");
                }
            }
        }
    }
}

void ListeningState::Exit(Application* app) {
    // stop录音
    app->audio_processor_.stopRecording();
    // stop running
    state_running_.store(false);
    state_running_thread_.join();
    USER_LOG_INFO("Listening exit.");
}
