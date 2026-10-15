import os
from openai import OpenAI

client = OpenAI(
    api_key="sk-ws-H.EEPXIPM.3o94.MEUCIQDLzoxNHFKJyeq03ad70ygMQXviKJdAI8evswRZRmCCMgIgedefMwZJxpo7QsdMSqHaaKC0Go2Csio_mMXGl9c6hwQ",
    base_url="https://ws-6ns27tvfzwkmq8zg.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
)

completion = client.chat.completions.create(
    model="qwen-turbo",
    messages=[{"role": "user", "content": "你好,你是谁"}]
)
print(completion.choices[0].message.content)