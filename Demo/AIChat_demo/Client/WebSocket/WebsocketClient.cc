#include "../WebSocket/WebsocketClient.h"
#include "../Utils/user_log.h"
#include <websocketpp/common/asio.hpp>

// WebSocketClient 构造函数
WebSocketClient::WebSocketClient(const std::string& address, int port, const std::string& token, const std::string& deviceId, int protocolVersion) {
    ws_client_.init_asio();
    ws_client_.set_open_handler(bind(&WebSocketClient::on_open, this, std::placeholders::_1));
    //_1：占位符，之后接收连接句柄 hdl。
    // _2：占位符，之后接收消息智能指针 msg。
    ws_client_.set_message_handler(bind(&WebSocketClient::on_message, this, std::placeholders::_1, std::placeholders::_2));
    ws_client_.set_close_handler(bind(&WebSocketClient::on_close, this, std::placeholders::_1)); // 设置关闭处理器
    ws_client_.set_fail_handler([this](websocketpp::connection_hdl hdl) {
        USER_LOG_ERROR("ws failed handle.");
        is_connected_ = false;
    });
    ws_client_.set_access_channels(websocketpp::log::alevel::none); // 设置日志级别
    ws_client_.set_error_channels(websocketpp::log::elevel::warn); // 设置日志级别

    uri_ = "ws://" + address + ":" + std::to_string(port);

    headers_["Authorization"] = "Bearer " + token;
    headers_["Device-Id"] = deviceId;//验证信息
    headers_["Protocol-Version"] = std::to_string(protocolVersion);

} 

WebSocketClient::~WebSocketClient() {
    Close();
    Terminate();
}

// 会独立运行run()的，主要是避免阻塞
void WebSocketClient::Run() {
    ws_client_.start_perpetual();
    thread_ = std::make_shared<std::thread>([this]() {
        ws_client_.run();
        USER_LOG_INFO("WebSocket client thread ended.");
    });
}

// 连接函数
void WebSocketClient::Connect() {
    if (is_connected_) {
        USER_LOG_INFO("Already connected.");
        return;
    }
    websocketpp::lib::error_code ec;
    client_t::connection_ptr con = ws_client_.get_connection(uri_, ec);
    if (ec) {
        USER_LOG_ERROR("Could not create connection: %s", ec.message().c_str());
        return;
    }

USER_LOG_INFO("========== Sending Headers ==========");
  for (const auto& header : headers_) {

    USER_LOG_INFO("%s: %s",
        header.first.c_str(),
        header.second.c_str());

    con->append_header(header.first, header.second);
}
USER_LOG_INFO("====================================");
// #开始进行三次握手
    connection_hdl_ = con->get_handle();
    ws_client_.connect(con);
}

void WebSocketClient::Terminate() {
    try {
        ws_client_.stop_perpetual();
        thread_->join();
    }
    catch (const websocketpp::exception& e) {
        // 捕获并处理异常
        USER_LOG_ERROR("WebSocket Exception: %s", e.what());
    }
}

void WebSocketClient::Close() {
    try {
        if(is_connected_){
            ws_client_.close(connection_hdl_, websocketpp::close::status::going_away, "Client is being destroyed");
        }
    } catch (const std::exception& e) {
        USER_LOG_ERROR("Error closing connection: %s", e.what());
    }
    
}

// 发送文本消息
void WebSocketClient::SendText(const std::string& message) {
    if (!is_connected_) {
        USER_LOG_WARN("WebSocket not connected, skip text message.");
        return;
    }

    try {
        ws_client_.send(
            connection_hdl_,
            message,
            websocketpp::frame::opcode::text
        );
    }
    catch (const std::exception& e) {
        USER_LOG_ERROR("SendText failed: %s", e.what());
        is_connected_ = false;
    }
}

// 发送二进制数据
void WebSocketClient::SendBinary(const uint8_t* data, size_t size) {
    if (!is_connected_) {
        return;
    }

    try {
        ws_client_.send(
            connection_hdl_,
            data,
            size,
            websocketpp::frame::opcode::binary
        );
    }
    catch (const std::exception& e) {
        USER_LOG_ERROR("SendBinary failed: %s", e.what());
        is_connected_ = false;
    }
}

// 设置消息回调
void WebSocketClient::SetMessageCallback(message_callback_t callback) {
    on_message_ = callback;
}

// 设置关闭回调
void WebSocketClient::SetCloseCallback(close_callback_t callback) {
    on_close_ = callback;
}

// 连接打开的回调
void WebSocketClient::on_open(websocketpp::connection_hdl hdl) {
    connection_hdl_ = hdl;
    USER_LOG_INFO("Connection established.");
    is_connected_ = true;
}

// 消息接收的回调  区分文本消息还是二进制消息
void WebSocketClient::on_message(websocketpp::connection_hdl hdl, client_t::message_ptr msg) {
    // #获取消息类型的操作码判断类型
    if (msg->get_opcode() == websocketpp::frame::opcode::text) {
        // 处理文本消息，传递给外部回调
        //on_message_就是appliaction中设置的ws_msg_handle
        if (on_message_) {//是否设置了回调
            on_message_(msg->get_payload(), false); // false 表示是文本消息
        }
    } else if (msg->get_opcode() == websocketpp::frame::opcode::binary) {
        // 处理二进制消息，传递给外部回调
        if (on_message_) {
            //get_payload获取msg的内容,msg是库给的消息的指针，指向传输的消息
            on_message_(msg->get_payload(), true); // true 表示是二进制消息
        }
    }
}

// 连接关闭的回调
void WebSocketClient::on_close(websocketpp::connection_hdl hdl) {
    USER_LOG_WARN("Connection closed.");
    if (on_close_) {  // 调用用户设置的关闭回调
        on_close_();
    }
    is_connected_ = false;
}
