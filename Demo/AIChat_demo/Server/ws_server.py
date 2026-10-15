import asyncio
import websockets
import json
import queue
from handle.text_handler import TextHandler
from handle.audio_handler import AudioHandler
from handle.auth_handler import AuthHandler
from service_manager import ServiceManager

import sys
sys.path.append("..")
from tools.logger import logger

class WebSocketServer:
    def __init__(self, host="0.0.0.0", port=8000, access_token="123456", device_id="00:11:22:33:44:55", protocol_version=2, service_manager: ServiceManager = None):
        self.host = host
        self.port = port

        # 初始化vad asr chat intent tts等服务
        self.service_manager = service_manager
        # 初始化文本和音频处理器对象
        self.text_handler = TextHandler(self.service_manager)
        self.audio_handler = AudioHandler(self.service_manager)
        # 初始化鉴权处理器
        self.auth_handler = AuthHandler(access_token, device_id, protocol_version)

    async def process_send_queue(self, websocket):#定义一个协程，协程的本质是函数
        """
        异步任务：从发送队列中取出数据并发送
        它作为异步任务，与接收消息等任务共用一个事件循环线程。
        """
        while True:
            try:
                # 检查队列是否为空 ws_send_queue为发送队列
                if not self.service_manager.ws_send_queue.empty():
                    # 队列不为空时获取数据
                    # 更短、无延迟、无空转、无竞态
                    data = self.service_manager.ws_send_queue.get_nowait()  # 非阻塞获取数据
                    # 通过 WebSocket 发送数据
                    await websocket.send(data)
                    # logger.info(f"发送数据到客户端: {len(data)} bytes")
                else:
                    # 如果队列为空，稍作等待
                    await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"发送队列处理错误: {e}")

    # 库创建的连接对象叫 conn
    # await server.handle_client(conn, "/")
    # async def 定义的是协程函数。   
    #收到消息第一时间在这里处理
    async def handle_client(self, websocket, path):#允许使用async异步操作
        """
        处理客户端连接，
        服务端项目代码中，最先拿到音频消息的
        异步回调函数
        websocket是库传过来的
        """
        # connected
        logger.info("Client connected")
        process_task = None
        try:
            # 启动发送队列处理任务
            # 因为服务端一边接收客户端音频，一边还需要把识别结果、回答音频等发回客户端，所以要启动一个专门处理发送的任务。
            # 准确地说，这行启动的是发送队列的处理任务：  
            process_task = asyncio.create_task(self.process_send_queue(websocket))

            # 获取连接时的请求头 客户端打包的头
            headers = websocket.request_headers
            logger.info("========== Client Headers ==========")
            for k, v in headers.items():
                logger.info(f"{k}: {v}")
            logger.info("===================================")
            # 执行鉴权
            if not self.auth_handler.authenticate(headers):
                # 这里用 await 执行它，并等待这次发送操作完成。如果发送过程中需要等待，事件循环可以去执行其他任务。
                await websocket.send(json.dumps({"type": "auth", "message": "Authentication failed"}))
                #发送给关闭原因raseon
                #websockets 库里的 close() 定义成 async def
                #必须带有await方可执行
                await websocket.close(reason="Authentication failed")
                logger.error("Authentication failed for client")
                return

            # 鉴权通过后，向客户端发送成功响应
            response = {
                "type": "auth",
                "message": "Client authenticated",
            }
            await websocket.send(json.dumps(response))

            # 开始接收和处理客户端消息
            #这个是官方文档用于接收消息的代码
            #：连接保持期间，它一直运行在这个接收循环中，反复等待和处理消息。
            #websocket是异步迭代对象不可直接用for
            async for message in websocket:
                if isinstance(message, bytes):
                    # 处理音频消息
                    await self.audio_handler.handle_audio_message(message)
                else:
                    # 处理 JSON 文本消息 客户端发来的状态信息
                    text = json.loads(message)
                    await self.text_handler.handle_text_message(text)
    #两段本质都是退出前的收尾，只是触发的时机不同：
    # except：因为连接断开而退出时走这里
    # finally：不管怎么退出都走这里
        except websockets.exceptions.ConnectionClosed as e:
            if process_task:
                process_task.cancel()
            logger.warning(f"Connection closed: {e}")
            self.service_manager.reset_services()
        finally:
            if process_task:
                process_task.cancel()
            logger.info("Client disconnected")
            self.service_manager.reset_services()

    async def start_server(self):
        """
        启动 WebSocket 服务器
        """
        #handle_client在这里用到的
        #这里把 self.handle_client 登记为连接处理函数。之后：
        # 1. 客户端连接进来，库为它创建一个连接对象。
        # 2. 库用这个对象完成 WebSocket 握手。
        # serve(ws_handler, host=None, port=None, ...)
        # 注意传入的是 self.handle_client，没有加 ()，实际是对象，表示把函数交给库，供库稍后调用。
        # main中的server就是self

        async with websockets.serve(self.handle_client, self.host, self.port):#完成tcp的握手，返回一个服务器对象
            logger.info(f"WebSocket server started on {self.host}:{self.port}")
            #挂起
            await asyncio.Future()  # 保持服务器运行
            # await asyncio.Future() 是一个永远不完成的 Future，
            # 让这个协程永远卡在这里，从而让 async with 块不退出、服务器一直运行
        # async with 管理它的启动和关闭
    # websocket 对象可以参考官方源码
   