import asyncio
import logging
import os
import signal

import uvicorn
from fastapi import FastAPI, Request, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.websockets import WebSocketDisconnect

from openhands.core.logger import openhands_logger as logger

from .oh_interface import OHInterface

app = FastAPI()

current_dir = os.path.dirname(os.path.abspath(__file__))
app.mount(
    '/static', StaticFiles(directory=os.path.join(current_dir, 'static'), name='static')
)
templates = Jinja2Templates(directory=os.path.join(current_dir, 'templates'))

cancel_event = asyncio.Event()
logging.basicConfig(level=logging.DEBUG)

oh_interface = OHInterface()


@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await oh_interface.register_websocket(websocket)
    try:
        while True:
            # Keep the connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        await oh_interface.unregister_websocket(websocket)
        logger.info('WebSocket disconnected')


@app.get('/')
async def read_root(request: Request):
    return templates.TemplateResponse('index.html', {'request': request})


@app.on_event('startup')
async def startup_event():
    # await oh_interface.start_backend()
    pass


@app.get('/backend_status')
async def get_backend_status():
    if not oh_interface:
        return {'is_running': False}
    is_running = await oh_interface.is_backend_running()
    return {'is_running': is_running}


@app.post('/start_backend/')
async def start_backend():
    success = await oh_interface.start_backend()
    return {'success': success}


@app.post('/restart_backend/')
async def restart_backend():
    success = await oh_interface.restart_backend()
    return {'success': success}


@app.post('/chat/')
async def chat(request: Request):
    data = await request.json()
    message = data.get('message')
    response = await oh_interface.handle_user_input(message)
    return {'response': response}


@app.get('/chat_history/')
async def get_chat_history():
    return {'history': oh_interface.get_chat_history()}


@app.post('/switch_model/')
async def switch_model(request: Request):
    data = await request.json()
    model_name = data.get('model')
    success = oh_interface.switch_model(model_name)
    return {'success': success}


@app.post('/clear/')
async def clear_chat():
    oh_interface.clear_chat_state()
    return {'success': True}


@app.post('/cancel/')
async def cancel_operation():
    result = oh_interface.cancel_operation()
    return {'message': result}


@app.get('/models/')
async def get_models():
    models, default_model = oh_interface.get_model_names()
    return {'models': models, 'default_model': default_model}


@app.get('/available_models/')
async def get_available_models():
    models, default_model = oh_interface.get_available_models()
    return {'models': models, 'default_model': default_model}


@app.on_event('shutdown')
async def shutdown_event():
    logger.info('Shutting down API server.')
    if oh_interface.engine is not None:
        await oh_interface.engine.close()


if __name__ == '__main__':

    async def shutdown(signal, loop):
        logger.info(f'Received exit signal {signal.name}...')
        await app.shutdown()
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        loop.stop()

    def handle_exception(loop, context):
        msg = context.get('exception', context['message'])
        logger.error(f'Caught exception: {msg}')
        asyncio.create_task(shutdown(signal.SIGTERM, loop))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(s, lambda s=s: asyncio.create_task(shutdown(s, loop)))

    loop.set_exception_handler(handle_exception)

    config = uvicorn.Config(app, host='0.0.0.0', port=8000, loop=loop)
    server = uvicorn.Server(config)

    try:
        loop.run_until_complete(server.serve())
    except KeyboardInterrupt:
        logger.info('Caught keyboard interrupt. Shutting down.')
    finally:
        loop.run_until_complete(shutdown(signal.SIGINT, loop))
        loop.close()
        logger.info('Shutdown complete.')
