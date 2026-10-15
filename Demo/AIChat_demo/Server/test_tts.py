import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer, AudioFormat

dashscope.api_key = "sk-ws-H.EEPXIPM.3o94.MEUCIQDLzoxNHFKJyeq03ad70ygMQXviKJdAI8evswRZRmCCMgIgedefMwZJxpo7QsdMSqHaaKC0Go2Csio_mMXGl9c6hwQapi"

dashscope.base_websocket_api_url = (
    "wss://ws-6ns27tvfzwkmq8zg.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference"
)

print("WS =", dashscope.base_websocket_api_url)
print("key len =", len(dashscope.api_key))

synthesizer = SpeechSynthesizer(
    model="cosyvoice-v1",
    voice="longxiaochun",
    format=AudioFormat.PCM_16000HZ_MONO_16BIT,
)

try:
    audio = synthesizer.call("你好，这是语音合成测试。")
    print("TTS success")
    print("audio bytes =", len(audio) if audio else 0)
except Exception as e:
    print("TTS failed:", repr(e))