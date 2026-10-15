"""云端失败处理回归测试；不访问网络，也不加载 ASR/VAD 模型。"""

import importlib.util
import json
from pathlib import Path
import queue
import sys
import types
import unittest
from unittest.mock import Mock, patch

SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))

from models.llm_model import LLMModel
from models.tts_model import TTSModel
from services.intent_service import IntentService
from tools.registry import FunctionRegistry


def load_service_manager():
    # 这里只测试文字分发，不需要本地语音模型和 Opus 依赖。
    stubs = {}
    for module_name, class_name in [
        ("services.vad_service", "VADService"),
        ("services.asr_service", "ASRService"),
        ("tools.audio_processor", "AudioProcessor"),
    ]:
        module = types.ModuleType(module_name)
        setattr(module, class_name, Mock())
        stubs[module_name] = module
    spec = importlib.util.spec_from_file_location(
        "cloud_failure_service_manager", SERVER_ROOT / "service_manager.py"
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module.ServiceManager


ServiceManager = load_service_manager()


class CloudFailureTests(unittest.TestCase):
    def make_manager(self, chunks):
        manager = ServiceManager.__new__(ServiceManager)
        manager.intent_service = Mock()
        manager.intent_service.detect_intent.return_value = [
            {"function_call": {"name": "continue_chat"}}
        ]
        manager.chat_service = Mock()
        manager.chat_service.generate_chat_response.return_value = iter(chunks)
        manager.tts_service = Mock()
        manager.ws_send_queue = queue.Queue()
        return manager

    def test_api_failure_is_not_returned_as_an_answer(self):
        model = LLMModel()
        with patch.object(model, "_get_client", side_effect=RuntimeError("model_not_found")):
            self.assertIsNone(model.get_LLM_response("你是谁？"))
            self.assertEqual(list(model.get_LLM_response_stream("你是谁？")), [-1])
        self.assertFalse(any(m["role"] == "assistant" for m in model.messages))

    def test_intent_api_failure_skips_json_parsing(self):
        service = IntentService(FunctionRegistry())
        with patch.object(service.intent_llm_model, "get_LLM_response", return_value=None), \
                patch("services.intent_service.json.loads") as parse:
            self.assertEqual(service.detect_intent("你好"), [
                {"function_call": {"name": "continue_chat"}}
            ])
        parse.assert_not_called()

    def test_failed_stream_does_not_start_tts(self):
        manager = self.make_manager([-1])
        self.assertEqual(manager.chat_start_task("你好"), -1)
        manager.tts_service.tts_speech_stream.assert_not_called()
        manager.tts_service.tts_close.assert_not_called()
        self.assertEqual(json.loads(manager.ws_send_queue.get_nowait())["type"], "error")

    def test_partial_stream_failure_closes_tts_and_notifies_client(self):
        manager = self.make_manager(["你好", -1])
        # 即使清理已经开始的语音合成失败，也应通知客户端。
        manager.tts_service.tts_close.side_effect = RuntimeError("connection closed")
        self.assertEqual(manager.chat_start_task("你好"), -1)
        manager.tts_service.tts_speech_stream.assert_called_once_with("你好")
        manager.tts_service.tts_close.assert_called_once()
        self.assertEqual(json.loads(manager.ws_send_queue.get_nowait())["type"], "error")

    def test_successful_stream_reaches_tts(self):
        manager = self.make_manager(["你好", "！"])
        manager.chat_start_task("你好")
        self.assertEqual(
            [call.args[0] for call in manager.tts_service.tts_speech_stream.call_args_list],
            ["你好", "！"],
        )
        manager.tts_service.tts_close.assert_called_once()
        self.assertTrue(manager.ws_send_queue.empty())

    def test_tts_rejects_non_text_before_sdk_call(self):
        model = TTSModel.__new__(TTSModel)
        model.synthesizer = Mock()
        self.assertFalse(model.tts_stream_speech_synthesis(-1))
        model.synthesizer.streaming_call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
