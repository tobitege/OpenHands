import asyncio

from fastapi import WebSocket

from openhands.core.logger import openhands_logger as logger

from .oh_engine import OpenHandsEngine


class OHInterface:
    def __init__(self):
        self.chatbot_state = [('assistant', 'Welcome to OpenHands!')]
        self.engine = OpenHandsEngine()
        self.engine.chat_delegate = self.add_chat_message
        self.model = None
        self.model_names, self.default_model = self.get_model_names()
        self.active_websockets = set()

    async def is_backend_running(self):
        if self.engine:
            is_running = await self.engine.check_if_running()
            return is_running
        return False

    async def start_backend(self):
        logger.debug('start_backend called')
        if not self.engine.is_running:
            logger.debug('Starting backend')
            await self.engine.run(restart=False, llm_override=self.model)
        return self.engine.is_running

    async def restart_backend(self):
        await self.engine.run(restart=True, llm_override=self.model)
        return self.engine.is_running

    async def handle_user_input(self, message):
        if not self.engine.is_running:
            return 'Backend not started!'
        try:
            response = await self.engine.handle_user_input(message)
            return response
        except asyncio.TimeoutError:
            return 'Request timed out. Please try again.'

    def add_chat_message(self, role, content):
        self.chatbot_state.append((role, content))
        asyncio.create_task(self.broadcast_message(role, content))

    def clear_chat_state(self):
        self.chatbot_state = [('assistant', 'Chat cleared. How can I help you?')]
        self.engine.clear_chat_state()

    def switch_model(self, model_name):
        if not self.engine.is_running:
            return False
        success = self.engine.switch_running_model(model_name)
        if success:
            self.model = model_name
        return success

    def get_available_models(self):
        return self.model_names, self.default_model

    def get_model_names(self):
        return self.engine.get_model_names()

    def cancel_operation(self):
        return self.engine.cancel_operation()

    def get_chat_history(self):
        return self.chatbot_state

    async def broadcast_message(self, role, content):
        message = {'role': role, 'content': content}
        for websocket in self.active_websockets:
            await websocket.send_json(message)

    async def register_websocket(self, websocket: WebSocket):
        self.active_websockets.add(websocket)

    async def unregister_websocket(self, websocket: WebSocket):
        self.active_websockets.remove(websocket)
