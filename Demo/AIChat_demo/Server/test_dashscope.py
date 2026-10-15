import dashscope

dashscope.api_key ="sk-ws-H.EEIYEPH.7Z6x.MEYCIQDXb71BjZ"

response = dashscope.Generation.call(
    model="qwen-turbo",
    messages=[
        {"role": "user", "content": "你好，请回复测试成功"}
    ],
    result_format="message"
)

print("status_code =", response.status_code)
print(response)