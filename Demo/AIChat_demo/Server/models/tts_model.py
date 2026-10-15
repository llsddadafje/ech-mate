import dashscope#阿里云
from dashscope.api_entities.dashscope_response import SpeechSynthesisResponse
from dashscope.audio.tts_v2 import *
import time
from tools.logger import logger
from config.settings import global_settings


class TTSModel:

#里的 TTS SDK 使用你设置的 dashscope.api_key 作为访问凭证。
# 官方示例也是先设置它，再创建 SpeechSynthesizer
    def __init__(self):
        logger.info(
        f"TTS DashScope config: "
        f"ws_url={dashscope.base_websocket_api_url}, "
        f"model={global_settings.TTS_MODEL}, voice={global_settings.TTS_VOICE}, "
        f"api_key_configured={bool(dashscope.api_key)}"
    )
        # 初始化 TTS 回调函数
        self.callback = None
        # 初始化 TTS 生成器
        self.synthesizer = SpeechSynthesizer(
            model=global_settings.TTS_MODEL,
            voice=global_settings.TTS_VOICE,
            format=AudioFormat.PCM_16000HZ_MONO_16BIT,
            callback=self.callback
        )

    class __tts_callback(ResultCallback):

        def __init__(self, on_open=None, on_complete=None, on_error=None, on_close=None, on_data=None):
            self.on_open = on_open or (lambda: logger.info("tts server-WS is open."))
            self.on_complete = on_complete or (lambda: logger.info("Speech synthesis task completed successfully."))
            self.on_error = on_error or (lambda message: logger.info(f"Speech synthesis task failed, {message}"))
            self.on_close = on_close or (lambda: logger.info("tts server-WS is closed."))
            self.on_data = on_data or (lambda data: logger.info(f"Audio result length: {len(data)}"))

        # 实现 ResultCallback 必需的方法
        #接收语音数据
        def on_open(self):
            self.on_open()

        def on_complete(self):
            self.on_complete()

        def on_error(self, message: str):
            self.on_error(message)

        def on_close(self):
            self.on_close()

        def on_data(self, data: bytes) -> None:
            self.on_data(data)

    def tts_stream_set(self, on_open=None, on_complete=None, on_error=None, on_close=None, on_data=None):
        '''设置TTS回调函数, 提前打开ws连接'''
        logger.info(
        f"TTS streaming config: "
        f"ws_url={dashscope.base_websocket_api_url}, "
        f"model={global_settings.TTS_MODEL}, voice={global_settings.TTS_VOICE}, "
        f"api_key_configured={bool(dashscope.api_key)}"
    )
        #右边的on_open是从text_handler中传过来的参数
        #on_data在这里被赋值为我们定义的函数
        self.callback = self.__tts_callback(on_open=on_open, on_complete=on_complete,
                                      on_error=on_error, on_close=on_close, on_data=on_data)
        self.synthesizer=SpeechSynthesizer(
            model=global_settings.TTS_MODEL,
            voice=global_settings.TTS_VOICE,
            format=AudioFormat.PCM_16000HZ_MONO_16BIT,
            callback=self.callback
        )
        # try:
        #     # self.synthesizer.streaming_call('') # 先提前打开ws连接
        #     self.synthesizer._SpeechSynthesizer__connect(5)
        #     logger.info("TTS WebSocket pre-connected successfully")
        #     time.sleep(0.1)
        return True
        # except Exception as e:
        #     logger.error(f"TTS WebSocket pre-connect failed: {e}")
        #     return False

    def tts_stream_close(self):
        self.synthesizer.streaming_complete()
        logger.info(f"Request ID: {self.synthesizer.get_last_request_id()}")

    def tts_stream_speech_synthesis(self, text_chunk):
        '''流式语音合成

        :param: text_chunk: 文本片
        :return: 合成是否成功'''

        if not isinstance(text_chunk, str):
            logger.error("TTS 输入必须是文本，已忽略无效数据")
            return False

        if text_chunk:
            try:
                self.synthesizer.streaming_call(text_chunk)# 阿里云SDk内部调用发送
            except Exception as e:
                logger.error(f"TTS 合成失败 [model={global_settings.TTS_MODEL}, voice={global_settings.TTS_VOICE}]: {e}")
                return False

