import numpy as np
from service_manager import ServiceManager
import json
from tools.logger import logger
from config.settings import global_settings


class AudioHandler:
    def __init__(self, service_manager: ServiceManager):
        self.service_manager = service_manager
        #本轮音频是否继续处理，就是一句话分为若干个音频块继续传过来
        #false就是持续处理音频块
        #本轮音频是否已经结束处理”，可以把它理解成接收音频的开关：
        # 主要就是防止同一轮音频重复触发识别和对话处理。
        # 第一次检测到说完后，把 is_vad 设为 True，后续到来的音频就跳过处理。等下一轮开始，再设回 False
    #    这里可以设置为面试遇到的问题
        self.service_manager.is_vad = False # 防止VAD发生后还语音加入

    # VAD 每次检测 200ms，ASR 最后识别的是累计的整句话。
    #加async的原因是被await调用
    async def handle_audio_message(self, msg):
        """
        处理音频消息
        :param msg: 收到的按照格式打包的 包含 PCM 音频的数据
        :return: 响应消息
        """
        # 解码音频数据
        bin_protocol = self.service_manager.audio_processor.unpack_bin_frame(msg)
        if bin_protocol:
            protocol_version, type, payload = bin_protocol
            if type == 0 and protocol_version == global_settings.protocol_version and self.service_manager.is_vad == False:
                # 处理音频数据
                pcm_data = self.service_manager.audio_processor.decode_audio(payload)
                audio_data_np_array = np.frombuffer(pcm_data, dtype=np.int16)  # 按两个字节为一个采样点分组

                # 使用 VAD 检测语音活动
                vad_result = self.service_manager.vad_service.process_audio_frame(audio_data_np_array)
                # 正常处理，未检测到语音结束或无语音活动
                # 这一步是把当前这块 PCM 音频追加到 ASR 的缓冲区，先积累音频，等用户说完再识别成文字。
                if vad_result == 0: # 继续接收音频数据，攒够5个块200ms的数据才处理
                    # 存入音频到 ASR 服务的缓冲区
                    # 本轮接收音频期间，只要 VAD 返回 0，当前这块音频就会追加到 ASR 缓冲区。
                    self.service_manager.asr_service.asr_add_audio_buffer(pcm_data)
                # 检测到语音结束
                elif vad_result == 1:#本轮对话结束，开始识别
                    #说完了，ASR会对整个的音频进行处理
                    self.service_manager.is_vad = True
                    #asr_res实际一整段文字
                    asr_res = self.service_manager.asr_service.asr_generate_text()
                    # asr识别到，然后开一个任务进行对话  云端对话
                    #把任务丢进线程池异步执行
                    self.service_manager.task_manager.submit_task(self.service_manager.chat_start_task, asr_res)
                    #聊天任务已提交到后台，下面继续发送 ASR 识别结果
                    # 发送asr识别结果
                    res =  {
                            "type": "asr",
                            "text": asr_res
                    }
                    logger.info(f"asr result: {asr_res}")
                    # send asr result to client
                    self.service_manager.ws_send_queue.put(json.dumps(res))
                # 无语音活动
                elif vad_result == 2:#没人说话
                    self.service_manager.is_vad = True
                    res = {
                    "type": "vad",
                    "state": "no_speech"
                    }
                    logger.warning("vad result: no_speech")
                    self.service_manager.ws_send_queue.put(json.dumps(res))
                # 缓冲区已满
                elif vad_result == 3:#说满15秒了
                    self.service_manager.is_vad = True
                    asr_res = self.service_manager.asr_service.asr_generate_text()
                    # asr识别到，然后开一个任务进行对话
                    self.service_manager.task_manager.submit_task(self.service_manager.chat_start_task, asr_res)
                    # 发送asr识别结果
                    res =  {
                            "type": "asr",
                            "text": asr_res
                    }
                    logger.warning(f"vad result: buffer_full, asr result: {asr_res}")
                    # send asr result to client
                    self.service_manager.ws_send_queue.put(json.dumps(res))


