import asyncio
import re
import traceback
import uuid
from asyncio import AbstractEventLoop
from typing import Callable, Type

import agenthub  # noqa F401 (we import this to get the agents registered)
from openhands.controller import AgentController
from openhands.controller.agent import Agent
from openhands.core.config import AppConfig, load_app_config
from openhands.core.logger import openhands_logger as logger
from openhands.core.schema import AgentState
from openhands.events import EventSource, EventStream, EventStreamSubscriber
from openhands.events.action import (
    Action,
    AgentDelegateAction,
    AgentFinishAction,
    BrowseInteractiveAction,
    ChangeAgentStateAction,
    CmdRunAction,
    IPythonRunCellAction,
    MessageAction,
)
from openhands.events.event import Event
from openhands.events.observation import (
    AgentStateChangedObservation,
    CmdOutputObservation,
    IPythonRunCellObservation,
)
from openhands.llm.llm import LLM
from openhands.runtime import get_runtime_cls
from openhands.runtime.runtime import Runtime
from openhands.storage import get_file_store


class OpenHandsEngine:
    def __init__(self, sid: str | None = None, config: AppConfig | None = None):
        self.sid = sid or f'oh_backend_{uuid.uuid4().hex[:8]}'
        self._agent_task: asyncio.Task | None = None
        self.is_running: bool = False
        self.controller: AgentController | None = None
        self.chat_delegate: Callable[[tuple[str, str]], None] | None = None
        self.cancel_event: asyncio.Event | None = None
        self.event_stream: EventStream | None = None
        self.config = config or load_app_config()
        self.loop: AbstractEventLoop = asyncio.get_event_loop()

    async def run(self, restart: bool = False):
        if self.is_running:
            if not restart:
                return
            await self.close()

        self.is_running = True

        agent_cls: Type[Agent] = Agent.get_cls(self.config.default_agent)
        agent_config = self.config.get_agent_config(self.config.default_agent)
        llm_config = self.config.get_llm_config_from_agent(self.config.default_agent)
        self.agent = agent_cls(
            llm=LLM(config=llm_config),
            config=agent_config,
        )

        file_store = get_file_store(self.config.file_store, self.config.file_store_path)
        self.event_stream = EventStream(self.sid, file_store)

        runtime_cls = get_runtime_cls(self.config.runtime)
        self.runtime: Runtime = runtime_cls(
            config=self.config,
            event_stream=self.event_stream,
            sid=self.sid,
            plugins=agent_cls.sandbox_plugins,
        )

        self.controller = AgentController(
            agent=self.agent,
            max_iterations=self.config.max_iterations,
            max_budget_per_task=self.config.max_budget_per_task,
            agent_to_llm_config=self.config.get_agent_to_llm_config_map(),
            event_stream=self.event_stream,
            sid=self.sid,
            confirmation_mode=False,
            headless_mode=False,
        )

        self.event_stream.subscribe(EventStreamSubscriber.MAIN, self.on_event)

        logger.info('OpenHands started!')

        self._agent_task = self.loop.create_task(self._run_agent_loop())

    async def _run_agent_loop(self):
        while self.is_running:
            try:
                await self.controller._step()
            except asyncio.CancelledError:
                logger.info('AgentController task was cancelled, closing...')
                break
            except Exception as e:
                logger.error(f'Error in agent loop: {e}')
                traceback.print_exc()
                break
            await asyncio.sleep(0.1)  # Short sleep to prevent CPU hogging

    def _remove_terminal_codes(self, text: str) -> str:
        """Remove terminal special codes from the given text."""
        # This regex pattern matches ANSI escape codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def display_command_output(self, output: str):
        output = self._remove_terminal_codes(output)
        lines = output.splitlines()
        formatted_output = []
        for line in lines:
            if (
                line.startswith('[Jupyter ')
                or line.startswith('[Python Interpreter')
                or line.startswith('openhands@')
            ):
                continue
            formatted_output.append(line)
        return ('\n'.join(formatted_output)).strip()

    async def display_event(self, event: Event):
        # TODO: `what if event.source is `system`?
        msg = None
        if isinstance(event, CmdRunAction) or isinstance(event, IPythonRunCellAction):
            if hasattr(event, 'thought'):
                msg = f'🤖 {event.thought}'
            if hasattr(event, 'command'):
                msg += (
                    ('\n' if msg else '')
                    + '❯ Command:\n'
                    + self.display_command_output(event.command)
                )
            elif hasattr(event, 'code'):
                msg += (
                    ('\n' if msg else '')
                    + '❯ Code:\n'
                    + self.display_command_output(event.code)
                )

        elif isinstance(event, CmdOutputObservation) and hasattr(event, 'content'):
            msg = 'Bash ❯\n' + self.display_command_output(event.content)

        elif isinstance(event, IPythonRunCellObservation) and hasattr(event, 'code'):
            msg = 'IPython ❯\n' + self.display_command_output(event.code)

        elif isinstance(event, AgentDelegateAction):
            msg = f'🤖 Delegating to {event.agent}: {event.inputs.get("task", "")}'

        elif isinstance(event, BrowseInteractiveAction):
            msg = f'🌐 {event.browser_actions}'

        elif isinstance(event, AgentFinishAction):
            msg = f'🏁 Agent finished: {event.thought}'

        elif isinstance(event, Action) and hasattr(event, 'thought'):
            msg = f'🤖 {event.thought}'

        elif hasattr(event, 'content') and event.content.strip():
            if isinstance(event, MessageAction):
                if event.source == EventSource.USER:
                    msg = f'👤 {event.content}'
                else:
                    msg = f'🤖 {event.content}'
            else:
                msg = self.display_command_output(f'🤖 {event.content}')

        return msg if msg is not None else ''

    async def on_event(self, event: Event):
        logger.debug(f'>>> Event: {event}')
        if not self.event_stream:
            return

        output = await self.display_event(event)
        logger.debug(f'>>> Output: {output}')
        if output:
            chat_message = (
                'assistant' if event.source != EventSource.USER else 'user',
                output,
            )
            if self.chat_delegate:
                await self.chat_delegate(chat_message)
                logger.debug('>>> sent message to UI')
            else:
                logger.error('>>> No message delegate assigned!')

        if isinstance(event, AgentStateChangedObservation):
            if event.agent_state == AgentState.ERROR:
                if self.chat_delegate:
                    await self.chat_delegate(
                        ('assistant', 'An error occurred. Please try again.')
                    )
            elif event.agent_state in [
                AgentState.AWAITING_USER_INPUT,
                AgentState.FINISHED,
                AgentState.ERROR,
            ]:
                await self._check_for_next_task('')

    async def _check_for_next_task(self, message: str):
        if not message or not self.event_stream:
            return
        if message == 'exit':
            self.event_stream.add_event(
                ChangeAgentStateAction(AgentState.STOPPED), EventSource.USER
            )
            return
        action = MessageAction(content=message)
        self.event_stream.add_event(action, EventSource.USER)
        logger.debug(f'Added MessageAction to event stream:\n{action}')

    async def handle_user_input(self, message: str):
        if not self.event_stream or not self.controller:
            return
        await self._check_for_next_task(message)
        # Ensure the agent is in the RUNNING state
        if self.controller.state.agent_state != AgentState.RUNNING:
            await self.controller.set_agent_state_to(AgentState.RUNNING)

    def cancel_operation(self):
        if self.event_stream:
            self.event_stream.add_event(
                ChangeAgentStateAction(AgentState.STOPPED), EventSource.USER
            )
            return 'Operation cancelled.'
        return 'Backend not started!'

    async def close(self):
        """Clean up resources and close the sandbox container."""
        self.is_running = False
        if self._agent_task:
            self._agent_task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(self._agent_task), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning('Timeout while waiting for agent task to cancel')
            except asyncio.CancelledError:
                logger.info('Agent task was cancelled successfully')
            except Exception as e:
                logger.error(f'Error while cancelling agent task: {e}')
            finally:
                self._agent_task = None

        if hasattr(self, 'controller') and isinstance(self.controller, AgentController):
            await self.controller.close()
        if hasattr(self, 'runtime') and isinstance(self.runtime, Runtime):
            self.runtime.close()

        logger.info('OpenHandsEngine closed successfully')
