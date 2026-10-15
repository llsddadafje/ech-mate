#ifndef STATE_MACHINE_H_
#define STATE_MACHINE_H_

#include <functional>
#include <unordered_map>
#include <string>

using EnterFunc_t = std::function<void()>;
using ExitFunc_t = std::function<void()>;

// StateMachine class declaration
class StateMachine {
public:
    StateMachine(int initialState);
    ~StateMachine();

    /**
     * @brief 初始化状态机。
     * 
     */
    void Initialize();

    /**
     * @brief 注册状态。
     * 
     * @param state 状态
     * @param on_enter 进入状态时的回调函数
     * @param on_exit 退出状态时的回调函数
     */
    void RegisterState(int state, EnterFunc_t on_enter, ExitFunc_t on_exit);

    /**
     * @brief 注册状态转换。
     * 
     * @param from 起始状态，-1表示任意状态
     * @param event 事件
     * @param to 目标状态
     */
    void RegisterTransition(int from, int event, int to);

    /**
     * @brief 处理事件。
     * 
     * @param event 事件
     * @return true 处理成功
     * @return false 处理失败
     */
    bool HandleEvent(int event);

    /**
     * @brief 获取当前状态。
     * 
     * @return int 当前状态
     */
    int GetCurrentState() const;

private:
    void ChangeState(int newState);

    int currentState_;
    //哈希表
    // std::unordered_map<键的类型, 值的类型> 变量名;
    // std::pair：把两个值放在一起
    // std::pair<EnterFunc_t, ExitFunc_t>
    // .first   // 第一个：进入状态的回调EnterFunc_t
    // .second  // 第二个：退出状态的回调ExitFunc_t
    //状态函数 进入和退出
    std::unordered_map<int, std::pair<EnterFunc_t, ExitFunc_t>> stateActions_;
    //规定各个状态切换的顺序即必须行听状态到说状态，以及触发的事件
    //嵌套哈希表 外层状态编号 内层事件编号
    // transitions_ = {
    // {3, {           // 当前状态：idle
    //     {0, 0},     // fault_happen → fault
    //     {3, 2},     // to_stop → stopping
    //     {4, 6}      // listening->wake_detected → speaking
    // }}
    // };  
    //其中的transitions_[3]就是{3,transitions_[3][4]这个4就是{4,6}中的4.
    std::unordered_map<int, std::unordered_map<int, int>> transitions_;
};

#endif  // STATE_MACHINE_H_