#include "./StateMachine.h"
#include "../Utils/user_log.h"
#include <iostream>

StateMachine::StateMachine(int initialState)
    : currentState_(initialState) {//同时初始化值
        USER_LOG_INFO("State machine created.");
    }

StateMachine::~StateMachine() {
    USER_LOG_INFO("State machine destroyed.");
}


void StateMachine::Initialize() {//即startup的回调
        // 调用初始状态的 enter 回调
        // 按键查找当前状态，返回一个迭代器，可以理解为元素的位置标记：
        // - 找到了：返回对应元素的位置。
        // - 没找到：返回 stateActions_.end()。
        if (stateActions_.find(currentState_) != stateActions_.end()) {
            stateActions_[currentState_].first();//调用进入函数
        }
    }

//state保存着状态的Int值
void StateMachine::RegisterState(int state, EnterFunc_t on_enter, ExitFunc_t on_exit) {
    stateActions_[state] = std::make_pair(on_enter, on_exit);
}
//transitions_
void StateMachine::RegisterTransition(int from, int event, int to) {
    // If from is -1, it means the transition is from any state
    if(from == -1) {
        for(auto& state : stateActions_) {
            transitions_[state.first][event] = to;
        }
    } 
    else {
        transitions_[from][event] = to;
    }
}
//根据当前状态查找规则，再决定是否切换状态
bool StateMachine::HandleEvent(int event) {
    //// 取出当前状态对应的“事件 → 下一状态”表
    //possibleTransitions是内层的整个表的值
    // transitions_[3]
    //     ↓
    // possibleTransitions：整张内层表
    //     {  event->state
    //         0 → 0,
    //         3 → 2,
    //         4 → 6
    //     }
    // possibleTransitions[4] → 6
    auto& possibleTransitions = transitions_[currentState_];
     // 检查这个状态是否有处理该事件的规则
    if (possibleTransitions.find(event) == possibleTransitions.end()) {
        USER_LOG_WARN("Event: %d is not handled in current state.", event);
        return false;
    }
    // 找到事件对应的下一状态
    int nextState = possibleTransitions[event];
      // 执行状态切换
    ChangeState(nextState);
    return true;
}

int StateMachine::GetCurrentState() const {
    return currentState_;
}

void StateMachine::ChangeState(int newState) {
    // 1. 退出当前状态
    //state, <first(enter),second()exit> 
    //查找 key，找到返回迭代器，找不到返回 end()
    if (stateActions_.find(currentState_) != stateActions_.end()) {
        //查找当前的状态并找到回调函数

        stateActions_[currentState_].second();
    }

    // 2. 更新当前状态
    currentState_ = newState;

    //3. 进入新状态
    if (stateActions_.find(currentState_) != stateActions_.end()) {
        stateActions_[currentState_].first();
    }
}
