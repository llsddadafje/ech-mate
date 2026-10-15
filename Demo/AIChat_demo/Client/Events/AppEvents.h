#ifndef APP_EVENTS_H
#define APP_EVENTS_H

enum class AppEvent {
    fault_happen,//0
    fault_solved,//1
    startup_done,//2
    to_stop,//3
    wake_detected,
    vad_no_speech,
    vad_end,
    asr_received,
    speaking_msg_received,
    speaking_end,
    dialogue_end,
    // Add more events here...
};

#endif // APP_EVENTS_H