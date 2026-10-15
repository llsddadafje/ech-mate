import dashscope
dashscope.base_websocket_api_url = (
    "wss://ws-6ns27tvfzwkmq8zg.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference"
)

class Settings:
    protocol_version = 2
    # LLM API 密钥
    dashscope.api_key = "sk-ws-H.EEIYEPH.7Z6x.MEYCIQDXb71BjZY4w7BRcC1-IaTE1I6MJ_hpenQNq2Etsib0NgIhAOlhZS7zip5rz3yg3JGQbcYvrrVICOsso32dLFeiEBAk"

    # 模型选择
    INTENT_MODEL = "qwen-flash"       # 专门用于意图识别
    CHAT_MODEL = "qwen-flash"         # 用于常规对话

    # CosyVoice 模型和音色必须配套设置
    TTS_MODEL = "cosyvoice-v2"
    TTS_VOICE = "longxiaochun_v2"

    # device
    ASR_DEVICE = "cpu"            # ASR 模型使用的设备
    # ASR_DEVICE = "cuda"            # ASR 模型使用的设备
    VAD_DEVICE = "cpu"            # ASR 模型使用的设备

    # 超时设置
    API_TIMEOUT = 10  # 秒

    def Set_API_Key(self, aliyun_api_key):
        dashscope.api_key = aliyun_api_key

global_settings = Settings()
