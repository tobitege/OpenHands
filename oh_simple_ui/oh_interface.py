import asyncio
import json
from dataclasses import asdict

from fastapi import WebSocket

from openhands.core.logger import openhands_logger as logger
from openhands.events.action import MessageAction

from .oh_engine import OpenHandsEngine


class OHInterface:
    def __init__(self):
        self.engine = OpenHandsEngine()
        self.engine.chat_delegate = self.add_chat_message
        self.model = None
        self.model_names, self.default_model = self.get_model_names()
        self.active_websockets = set()
        self.load_chat_history()

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

    async def handle_user_input(self, message: MessageAction):
        if not self.engine.is_running:
            return 'Backend not started!'
        try:
            response = await self.engine.handle_user_input(message)
            return response
        except asyncio.TimeoutError:
            return 'Request timed out. Please try again.'

    def add_chat_message(self, role: str, message: MessageAction):
        self.chatbot_state.append((role, message))
        asyncio.create_task(self.broadcast_message(role, message))

    async def delete_image(self, message_id: str, image_index: int) -> bool:
        for role, message in self.chatbot_state:
            if message.id == message_id:
                if 0 <= image_index < len(message.image_urls):
                    del message.image_urls[image_index]
                    await self.broadcast_message(role, message)
                    return True
                else:
                    logger.error(
                        f'Invalid image index {image_index} for message {message_id}'
                    )
                    return False

        logger.error(f'Message with id {message_id} not found')
        return False

    def get_chat_history(self):
        return self.chatbot_state

    def clear_chat_state(self):
        self.chatbot_state = []
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

    async def broadcast_message(self, role: str, message: MessageAction):
        message_dict = asdict(message)
        message_dict['role'] = role
        for websocket in self.active_websockets:
            await websocket.send_json(message_dict)

    async def register_websocket(self, websocket: WebSocket):
        self.active_websockets.add(websocket)

    async def unregister_websocket(self, websocket: WebSocket):
        self.active_websockets.remove(websocket)

    def serialize_chat_history(self):
        return json.dumps(
            [(role, message.dict()) for role, message in self.chatbot_state]
        )

    def deserialize_chat_history(self, serialized_data):
        data = json.loads(serialized_data)
        self.chatbot_state = [
            (role, MessageAction(**message)) for role, message in data
        ]

    def save_chat_history(self, filename='chat_history.json'):
        with open(filename, 'w') as f:
            f.write(self.serialize_chat_history())

    def load_chat_history(self, filename='chat_history.json'):
        # TODO: this format doesn't work yet, need to delegate to backend's EventStream?
        # try:
        #     with open(filename, 'r') as f:
        #         serialized_data = f.read()
        #     self.deserialize_chat_history(serialized_data)
        # except FileNotFoundError:
        #     logger.warning(
        #         f'Chat history file {filename} not found. Starting with empty history.'
        #     )
        #     self.chatbot_state = []
        self.chatbot_state = []
