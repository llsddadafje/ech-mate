import dashscope
from openai import OpenAI
from typing import Optional
from config.settings import global_settings
from tools.logger import logger

#LLMModel 是项目中调用云端大语言模型的 Python 类，负责管理对话历史、发送请求和获取回复。
# 你的百炼 Workspace 专属 OpenAI Compatible 地址
OPENAI_BASE_URL = (
    "https://ws-6ns27tvfzwkmq8zg.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
)


class LLMModel:
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or global_settings.CHAT_MODEL

        # 对话初始历史记录
        self.messages = [
            {
                "role": "system",
                "content": "你是一个桌面机器人, 名为Echo, 快速地回复我."
            }
        ]

    def _get_client(self):
        """
        使用当前 dashscope.api_key 创建 OpenAI Compatible 客户端。

        注意：
        DeskBot 连接 Server 后会更新 dashscope.api_key，
        因此这里不能在 __init__ 中固定保存旧 key。
        """
        if not dashscope.api_key:
            raise RuntimeError("DashScope API Key 未设置")

        return OpenAI(
            api_key=dashscope.api_key,
            base_url=OPENAI_BASE_URL,
            timeout=global_settings.API_TIMEOUT
        )

    def set_model_sys_content(self, content: str):
        """
        设置模型的系统描述内容
        """
        self.messages[0]["content"] = content

    def add_message(self, role: str, content: str):
        """
        添加对话历史记录
        self.messages.append({
            "role": "user",
            "content": "你好"
        })
        """
        self.messages.append({
            "role": role,
            "content": content
        })

    def clear_messages(self):
        """
        清空对话历史记录
        """
        self.messages = [
            {
                "role": "system",
                "content": (
                    "你是一个桌面机器人, 名为Echo, "
                    "全程请快速地回复我. "
                    "同时你还有函数执行的功能, "
                    "可以根据函数来回复我."
                )
            }
        ]

    def get_LLM_response(self, question: str) -> Optional[str]:
        """
        非流式生成回答

        :param question: 用户问题
        :return: 完整回答；API 调用失败时返回 None
        """
        if question:
            self.add_message("user", question)

        try:
            client = self._get_client()

            #创建客户端进行云端连接  opai式调用
            response = client.chat.completions.create(
                model=self.model_name,
                messages=self.messages,
                extra_body={"enable_thinking": False}
            )

            content = response.choices[0].message.content

            if content is None:
                content = ""

            self.add_message("assistant", content)

            logger.info(f"LLM 非流式回复成功: {content}")

            return content

        except Exception as e:
            logger.error(f"非流式生成异常 [model={self.model_name}, base_url={OPENAI_BASE_URL}]: {e}")
            return None

#返回的是一个个片段
    def get_LLM_response_stream(self, question):
        """
        流式生成回答。

        注意：
        此处是 yield 生成器，需要在外部循环中调用。
        """

            # stream：
            # {
            #     "id": "chatcmpl-123",
            #     "object": "chat.completion.chunk",
            #     "created": 1677652288,
            #     "model": "gpt-5.2",
            #     "choices": [
            #         {
            #             "index": 0,
            #             "delta": {
            #                 "role": "assistant",
            #                 "content": "Hello"
            #             },
            #             "finish_reason": None #回答
            #         }
            #     ]
            # }通常每个 chunk 都会重复带上这些顶层字段
# [
#     {"role": "system", "content": "你是一个桌面机器人..."},
#     {"role": "user", "content": "你是谁？"},
#     {"role": "assistant", "content": "我是Echo。"}  # <--- 新增的字典
# ]
        if question:
            self.add_message("user", question)

        try:
            client = self._get_client()

            stream = client.chat.completions.create(#发消息并且接收消息
                model=self.model_name,
                messages=self.messages,
                stream=True,
                extra_body={"enable_thinking": False}
            )

            full_text = ""
# 准确地说，含有 yield 的函数，不再是一个普通的函数（Function），而是一个“生成器函数（Generator Function）”。
# 当你调用它时，它不会执行函数体，而是直接返回一个“生成器对象（Generator Object）
#stream对象比较特殊，云端明确发来了 [DONE] 信号，底层库主动抛出 StopIteration
# 外层 for 再调用 next(answers) 时，生成器已经没有内容可返回，就会产生 StopIteration。
# for 会自动处理这个信号，退出循环。
# 准确地说：stream 是一个迭代器（Iterator）对象。
# 虽然它严格来说不是由你写 yield 创建出来的“生成器（Generator）”，但它的行为模式和生成器一模一样。
            for chunk in stream:#迭代对象是空的就会跳出循环这是对于普通对象

                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta.content
                # "delta": {
                #     "role": "assistant",
                #     "content": "Hello"
                # }
                if delta:
                    full_text += delta
                    yield delta

            # 完整回复加入历史记录 yield结束
            if full_text:
                self.add_message("assistant", full_text)

            logger.info(f"LLM 流式回复完成: {full_text}")

        except Exception as e:
            logger.error(f"流式生成异常 [model={self.model_name}, base_url={OPENAI_BASE_URL}]: {e}")
            yield -1

#多个choices
# "choices": [
#     {
#         "delta": {
#             "content": "Hello"
#         }
#     }
# ]
# {
#     "choices": [
#         {
#             "delta": {
#                 "content": "!"
#             },
#             "finish_reason": null
#         }
#     ]
# }
# {
#     "choices": [
#         {
#             "delta": {},
#             "finish_reason": "stop"
#         }
#     ]
# }
