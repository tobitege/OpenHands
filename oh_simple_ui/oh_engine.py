import asyncio
import re
import uuid
from asyncio import AbstractEventLoop
from typing import Callable, Type

import openhands.agenthub  # noqa F401 (we import this to get the agents registered)
from openhands.controller.agent import Agent
from openhands.controller.agent_controller import AgentController
from openhands.core.config import AppConfig, LLMConfig, load_app_config
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
    NullObservation,
)
from openhands.llm.llm import LLM
from openhands.runtime import get_runtime_cls
from openhands.runtime.runtime import Runtime
from openhands.storage import get_file_store


class OpenHandsEngine:
    def __init__(self, sid: str | None = None, config: AppConfig | None = None):
        """Initialize the OpenHandsEngine.
        config.toml is source of truth for switching models!

        Args:
            sid (str | None): Session ID. If None, a unique ID will be generated.
            config (AppConfig | None): Application configuration. If None, default config will be loaded.

        Attributes:
            sid (str): Unique session identifier.
            _agent (Agent | None): The agent instance.
            _agent_task (asyncio.Task | None): Internal task for running the agent.
            _controller (AgentController | None): Controller for managing the agent.
            _event_stream (EventStream | None): Stream for handling events.
            _loop (AbstractEventLoop): The event loop for asynchronous operations.

            is_running (bool): Flag indicating if the engine is running.
            chat_delegate (Callable[[tuple[str, str]], None] | None): Function to handle chat messages.
            cancel_event (asyncio.Event | None): Event for cancelling operations.
            config (AppConfig): Appl. configuration, if None, default will be used.
            llm_name (str | None): Name of the toml `llm` section as in [llm.name].
            model (str | None): Name of the actual model, e.g. 'gpt-4o' or 'claude-3.5-sonnet'.
        """
        self.sid = sid or f'oh_backend_{uuid.uuid4().hex[:8]}'
        self._agent: Agent | None = None
        self._agent_task: asyncio.Task | None = None
        self._controller: AgentController | None = None
        self._event_stream: EventStream | None = None
        self._loop: AbstractEventLoop = asyncio.get_event_loop()

        self.is_running: bool = False
        self.chat_delegate: Callable[[tuple[str, str]], None] | None = None
        self.cancel_event: asyncio.Event | None = None
        self.llm_name: str | None = None
        self.model: str | None = None
        self.config = config or load_app_config()
        self._is_initializing: bool = False

    def switch_running_model(self, new_llm_name: str) -> bool:
        """Switch the currently running model to a new one.

        This method attempts to change the language model (LLM) used by the agent
        to the one specified by `new_llm_name`. It performs several checks and validations
        before making the switch.

        Args:
            new_llm_name (str): The name of the new LLM to switch to.

        Returns:
            bool: True if the switch was successful, False otherwise.

        Raises:
            Exception: If there's an error while switching to the new model.

        Note:
            - This method requires an active agent (_agent) to be running.
            - It will not switch if the new model name is the same as the current one.
            - The method logs various debug and error messages during the process.
        """
        if not self._agent:
            logger.warning('No agent running, cannot switch model.')
            return False

        if not new_llm_name:
            logger.warning('No new LLM name provided.')
            return False

        if new_llm_name == self.llm_name:
            logger.info(f"LLM '{new_llm_name}' is already active.")
            return True

        new_llm_config = self.get_llm_config(new_llm_name)
        if new_llm_config and hasattr(new_llm_config, 'model'):
            try:
                self._agent.llm = LLM(config=new_llm_config)
                self.llm_name = new_llm_name
                self.model = new_llm_config.model
                logger.debug('>>> --------------------------------------------------')
                logger.debug(f'>>> Backend model switched to: `{self.model}`')
                logger.debug('>>> --------------------------------------------------')
                return True
            except Exception as e:
                logger.error(
                    f"'>>> Error switching to model '{new_llm_name}': {str(e)}"
                )
                return False
        else:
            logger.debug(
                f'>>> Backend model not switched, check config for `{new_llm_name}`'
            )
            return False

    async def run(self, restart: bool = False, llm_override: str | None = None):
        """Start or restart the OpenHands engine.

        This method initializes and starts the OpenHands engine. It sets up the agent,
        event stream, and runtime, and begins the agent loop.

        Args:
            restart (bool): If True, the engine will be restarted by closing the existing instance.
            llm_override (str | None): Optional new LLM name to switch to instead of the default.

        Note:
            - If `restart` is True, the existing engine instance will be closed first.
            - If `llm_override` is provided, the engine will switch to the new LLM.
        """
        if self._is_initializing:
            logger.debug(
                'Engine initialization already in progress, ignoring `run` call.'
            )
            return

        if self.is_running:
            if restart:
                await self.close()
            elif not llm_override:
                self._is_initializing = False
                logger.debug('Engine already running, ignoring `run` call.')
                return

        self._is_initializing = True
        self.is_running = False
        try:
            agent_cls: Type[Agent] = Agent.get_cls(self.config.default_agent)
            agent_config = self.config.get_agent_config(self.config.default_agent)
            llm_config = self.config.get_llm_config_from_agent(
                self.config.default_agent
            )

            if llm_override:
                model_llm_config = self.get_llm_config(llm_override)
                if model_llm_config:
                    self.llm_name = llm_override
                    self.model = model_llm_config.model
                    llm_config = model_llm_config
                    logger.debug(f'>>> Backend using model `{llm_override}`')
                else:
                    logger.warning(
                        f'>>> Model `{llm_override}` not found, using default model'
                    )

            self._agent = agent_cls(
                llm=LLM(config=llm_config),
                config=agent_config,
            )

            file_store = get_file_store(
                self.config.file_store, self.config.file_store_path
            )
            self._event_stream = EventStream(self.sid, file_store)

            runtime_cls = get_runtime_cls(self.config.runtime)
            self.runtime: Runtime = runtime_cls(
                config=self.config,
                event_stream=self._event_stream,
                sid=self.sid,
                plugins=agent_cls.sandbox_plugins,
                # TODO: add status message callback
                # status_message_callback = self.add_status_message,
            )

            self._controller = AgentController(
                agent=self._agent,
                max_iterations=self.config.max_iterations,
                max_budget_per_task=self.config.max_budget_per_task,
                agent_to_llm_config=self.config.get_agent_to_llm_config_map(),
                event_stream=self._event_stream,
                sid=self.sid,
                confirmation_mode=False,
                headless_mode=False,
            )

            self._event_stream.subscribe(EventStreamSubscriber.MAIN, self.on_event)

            logger.info('OpenHands started!')

            self._agent_task = self._loop.create_task(self._run_agent_loop())

            self.is_running = True

        except Exception as e:
            logger.error(f'Error starting OpenHands: {e}')
            self.is_running = False
        finally:
            self._is_initializing = False

    async def _run_agent_loop(self):
        while self.is_running:
            try:
                await self._controller._step()
            except asyncio.CancelledError:
                logger.debug('AgentController task was cancelled, closing...')
                break
            except Exception as e:
                logger.error(f'Error in agent loop: {e}')
                break
            await asyncio.sleep(0.1)  # Short sleep to prevent CPU hogging

    async def check_if_running(self):
        return self.is_running

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

        elif isinstance(event, IPythonRunCellObservation) and event.content:
            msg = 'IPython ❯\n' + self.display_command_output(event.content)

        elif isinstance(event, IPythonRunCellObservation) and event.code:
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
                    msg = ''  # f'👤 {event.content}'
                else:
                    msg = f'🤖 {event.content}'
            else:
                msg = self.display_command_output(f'🤖 {event.content}')

        return msg if msg is not None else ''

    async def on_event(self, event: Event):
        logger.debug(f'>>> Event: {event}')
        if not self._event_stream or isinstance(event, NullObservation):
            return

        output = await self.display_event(event)
        if output:
            logger.debug(f'>>> Output: {output}')
            chat_message = (
                'assistant' if event.source != EventSource.USER else 'user',
                output,
            )
            if self.chat_delegate:
                self.chat_delegate('assistant', chat_message)
                logger.debug('>>> Message sent to UI')
            else:
                logger.error('>>> No message delegate assigned!')

        if isinstance(event, AgentStateChangedObservation):
            if event.agent_state == AgentState.ERROR:
                if self.chat_delegate:
                    self.chat_delegate(
                        ('assistant', 'An error occurred. Please try again.')
                    )
            elif event.agent_state in [
                AgentState.AWAITING_USER_INPUT,
                AgentState.FINISHED,
                AgentState.ERROR,
            ]:
                await self._check_for_next_task('')

    async def _check_for_next_task(self, message: str):
        if not message or not self._event_stream:
            return
        if message == 'exit':
            self._event_stream.add_event(
                ChangeAgentStateAction(AgentState.STOPPED), EventSource.USER
            )
            return
        action = MessageAction(content=message)
        self._event_stream.add_event(action, EventSource.USER)
        logger.debug(f'Added MessageAction to event stream:\n{action}')

    async def handle_user_input(self, message: str):
        if not self._event_stream or not self._controller:
            return
        await self._check_for_next_task(message)
        if self._controller.state.agent_state != AgentState.RUNNING:
            await self._controller.set_agent_state_to(AgentState.RUNNING)

    def cancel_operation(self):
        if self._event_stream:
            self._event_stream.add_event(
                ChangeAgentStateAction(AgentState.STOPPED), EventSource.USER
            )
            return 'Operation cancelled.'
        return 'Backend not started!'

    def clear_chat_state(self):
        if self._event_stream:
            self._event_stream.clear()
            return 'Chat history cleared.'

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

        if hasattr(self, '_controller') and isinstance(
            self._controller, AgentController
        ):
            await self._controller.close()
        if hasattr(self, 'runtime') and isinstance(self.runtime, Runtime):
            self.runtime.close()

        logger.info('OpenHandsEngine closed successfully')

    def get_model_names(self):
        models = []
        default_model = None

        if not self.config.llms:
            logger.error('Error: no model specifications found in config.toml!')
            return None, None

        if 'llm' in self.config.llms and self.config.llms['llm'].model is not None:
            default_model = '(Default)'

        for key in self.config.llms:
            if key != 'llm':  # Exclude the default 'llm' key
                models.append(key)
                models.sort()

        if default_model:
            models = [default_model] + models

        return models, default_model

    def get_llm_config(self, model) -> LLMConfig | None:
        if not model:
            logger.error('>>> No model specified, using default')
            return None

        llm_config = self.config.get_llm_config(f'{model}')
        if llm_config:
            return llm_config

        logger.error(f'>>> Model `{model}` not found')
        return None
