import asyncio

import gradio as gr

from ohgradio.oh_engine import OpenHandsEngine
from openhands.core.logger import openhands_logger as logger


class OHInterface:
    def __init__(self):
        self.chatbot_state = [('assistant', 'Welcome to OpenHands!')]
        self.chatbot = None
        self.engine = OpenHandsEngine()  # Instantiate OpenHandsEngine
        self.engine.chat_delegate = self.add_chat_message  # Set the chat delegate
        self.interface = None
        self.model = None
        self.create_interface()

    def create_interface(self):
        if self.interface:
            self.interface.close()
        self.interface = self._create_interface()

    def _create_interface(self):
        models, default_model = self.engine.get_model_names()
        models_available = models is not None and len(models) > 0

        async def _start_backend_wrapper():
            if not models_available:
                self.chatbot_state.append(
                    ('system', 'No models available. Cannot start backend.')
                )
                return (
                    gr.update(visible=True),
                    gr.update(visible=False),
                    gr.update(),
                    gr.update(value=self.chatbot_state),
                )
            if self.engine.is_running:
                return (
                    gr.update(visible=False),
                    gr.update(visible=True),
                    gr.update(),
                    gr.update(),
                )
            await self._start_backend()
            return (
                gr.update(visible=not self.engine.is_running),
                gr.update(visible=self.engine.is_running),
                '',
                gr.update(value=self.chatbot_state),
                gr.update(visible=False),
            )

        async def _handle_confirmation(confirmed):
            if confirmed:
                return await _restart_backend()
            else:
                self.chatbot_state.append(('system', 'Restart cancelled.'))
                return (
                    gr.update(visible=False),
                    gr.update(visible=True),
                    '',
                    gr.update(value=self.chatbot_state),
                    gr.update(visible=False),
                )

        async def _confirm_restart():
            return gr.update(visible=True)

        async def _restart_backend():
            await self.engine.run(restart=True, llm_override=self.model)
            return (
                gr.update(visible=not self.engine.is_running),
                gr.update(visible=self.engine.is_running),
                '',
                gr.update(value=self.chatbot_state),
                gr.update(visible=False),
            )

        async def _chat_interface(message, history):
            history = history or []
            if not self.engine.is_running:
                self.chatbot_state.append(('system', 'Backend not started!'))
                return '', history, gr.update(value='')
            if self.engine.is_running:
                await asyncio.wait_for(
                    self.engine.handle_user_input(message), timeout=30.0
                )
            return '', history, gr.update(value='')

        async def update_chatbot():
            while True:
                await asyncio.sleep(0.5)
                if self.chatbot and self.chatbot_state:
                    yield self.preprocess_messages(self.chatbot_state)

        custom_colors = {
            'primary': '#0084ff',  # Bright blue from the send button
            'primary_hover': '#0073e6',  # Slightly darker blue for hover states
            'primary_dark': '#1a90ff',  # Brighter blue for dark mode
            'primary_hover_dark': '#40a9ff',  # Lighter blue for dark mode hover
            'neutral_50': '#f8f9fa',
            'neutral_100': '#f1f3f5',
            'neutral_200': '#e9ecef',
            'neutral_300': '#dee2e6',
            'neutral_400': '#ced4da',
            'neutral_500': '#adb5bd',
            'neutral_600': '#6c757d',
            'neutral_700': '#495057',
            'neutral_800': '#343a40',
            'neutral_900': '#212529',
            'neutral_950': '#1a1e21',
        }
        custom_theme = gr.themes.Default(
            primary_hue=gr.themes.colors.neutral,
            secondary_hue=gr.themes.colors.neutral,
            neutral_hue=gr.themes.colors.neutral,
            font_mono=[gr.themes.GoogleFont('Inconsolata'), 'Montserrat', 'sans-serif'],
            font=[gr.themes.GoogleFont('Roboto Mono'), 'Consolas', 'ui-monospace'],
            spacing_size=gr.themes.sizes.spacing_sm,
            radius_size=gr.themes.sizes.radius_sm,
        )
        custom_theme.set(
            block_info_text_size='text_xs',
            # Light mode
            background_fill_primary='white',
            background_fill_secondary=custom_colors['neutral_100'],
            body_text_color=custom_colors['neutral_900'],
            body_text_color_subdued=custom_colors['neutral_700'],
            body_text_size='text_xs',
            border_color_primary=custom_colors['neutral_300'],
            button_primary_background_fill=custom_colors['primary'],
            button_primary_background_fill_hover=custom_colors['primary_hover'],
            button_primary_text_color='white',
            button_secondary_background_fill=custom_colors['neutral_100'],
            button_secondary_background_fill_hover=custom_colors['neutral_200'],
            button_secondary_text_color=custom_colors['neutral_800'],
            button_border_width='2px',
            input_background_fill=custom_colors['neutral_100'],
            input_border_width='2px',
            input_border_color=custom_colors['neutral_300'],
            # Dark mode
            background_fill_primary_dark=custom_colors['neutral_900'],
            background_fill_secondary_dark=custom_colors['neutral_800'],
            body_text_color_dark=custom_colors['neutral_100'],
            body_text_color_subdued_dark=custom_colors['neutral_400'],
            border_color_primary_dark=custom_colors['neutral_700'],
            button_primary_background_fill_dark=custom_colors['primary_dark'],
            button_primary_background_fill_hover_dark=custom_colors[
                'primary_hover_dark'
            ],
            button_primary_text_color_dark='white',
            button_secondary_background_fill_dark=custom_colors['neutral_700'],
            button_secondary_background_fill_hover_dark=custom_colors['neutral_600'],
            button_secondary_text_color_dark=custom_colors['neutral_200'],
            input_background_fill_dark=custom_colors['neutral_800'],
            input_border_color_dark=custom_colors['neutral_600'],
            # Common properties
            layout_gap='*spacing_md',
            input_padding='*spacing_md',
            input_radius='*radius_sm',
            block_background_fill='*background_fill_primary',
            block_border_width='1px',
            block_border_color='*border_color_primary',
            block_padding='*spacing_sm',
            block_radius='*radius_md',
            block_shadow='*shadow_drop_sm',
            checkbox_background_color='*background_fill_primary',
            checkbox_border_color='*border_color_primary',
            checkbox_background_color_selected='*button_primary_background_fill',
            checkbox_border_color_selected='*button_primary_background_fill',
            checkbox_border_radius='*radius_sm',
            checkbox_label_background_fill='*button_primary_background_fill',
            checkbox_label_background_fill_hover='*button_primary_background_fill_hover',
            checkbox_label_text_color='*button_primary_text_color',
            slider_color='*button_primary_background_fill',
            table_border_color='*border_color_primary',
            table_even_background_fill='*background_fill_primary',
            table_odd_background_fill='*background_fill_secondary',
            table_radius='*radius_sm',
        )
        # this sets the padding between the chatbot messages to a normal value
        custom_css = """
.message-row.panel {
    padding-top: 6px !important;
    padding-bottom: 6px !important;
    line-height: 1.1 !important;
}
        """
        with gr.Blocks(theme=custom_theme, fill_height=True) as _interface:
            with gr.Row():
                gr.Markdown('# OpenHands: Code Less, Make More.')
            with gr.Row():
                with gr.Column(scale=1, elem_classes='sidebar'):
                    gr.Markdown('Options')
                    with gr.Group():
                        model_dropdown = gr.Dropdown(
                            label='Model',
                            choices=models if models_available else None,
                            value=default_model if models_available else None,
                            visible=models_available,
                            elem_id='model_dropdown',
                        )
                        if not models_available:
                            gr.Markdown(
                                'No models available. Please check your config.toml file.'
                            )
                        start_btn = gr.Button(
                            'Start Backend',
                            elem_id='start_button',
                            interactive=models_available,
                        )
                        restart_btn = gr.Button(
                            'Restart Backend',
                            elem_id='restart_button',
                            visible=False,
                            interactive=models_available,
                        )
                    with gr.Group():
                        toggle_dark = gr.Button(value='Toggle Dark')

                with gr.Column(scale=20):
                    chatbot = gr.Chatbot(
                        [],
                        label='Chat History',
                        elem_id='chatbot',
                        bubble_full_width=False,
                        show_copy_button=False,
                        # layout='panel',
                        height='65vh',
                    )

                    with gr.Row(visible=False) as confirm_dialog:
                        with gr.Group():
                            gr.Markdown('Are you sure you want to restart the backend?')
                            confirm_yes = gr.Button('Yes')
                            confirm_no = gr.Button('No')

                    with gr.Row():
                        with gr.Group():
                            msg = gr.Textbox(
                                label='Your prompt',
                                placeholder='',
                                show_copy_button=False,
                            )
                            send_btn = gr.Button('Send', variant='primary')

                    with gr.Row():
                        clear_btn = gr.Button('Clear', elem_id='clear_button')
                        cancel_btn = gr.Button('Cancel', elem_id='cancel_button')

                    self.chatbot = chatbot

            model_dropdown.change(
                fn=self.update_model,
                inputs=[model_dropdown],
                outputs=[],
                js="""
                (value) => {
                    document.cookie = 'oh_gradio_selected_model=' + encodeURIComponent(value) + '; path=/; SameSite=None; Secure';
                    return value;
                }
                """,
            )

            msg.submit(
                self._submit_wrapper, msg, [msg, chatbot], queue=False, show_api=False
            )

            send_btn.click(
                self._submit_wrapper, msg, [msg, chatbot], queue=False, show_api=False
            )

            toggle_dark.click(
                None,
                js="""() => { document.body.classList.toggle('dark'); }""",
            )

            clear_btn.click(
                self._clear_chatbot_wrapper,
                inputs=[],
                outputs=[chatbot, msg],
                queue=False,
            )

            cancel_btn.click(
                self._cancel_operation_wrapper, inputs=[], outputs=[msg, chatbot]
            )

            start_btn.click(
                _start_backend_wrapper,
                inputs=[],
                outputs=[start_btn, restart_btn, msg, chatbot],
                queue=False,
                js="""
                () => {
                    const btn = document.getElementById('start_button');
                    btn.disabled = true;
                    btn.textContent = 'Starting...';
                    btn.style.opacity = '0.5';
                    return [];
                }
                """,
            ).then(
                None,
                None,
                None,
                js="""
                () => {
                    const btn = document.getElementById('start_button');
                    btn.disabled = false;
                    btn.textContent = 'Start Backend';
                    btn.style.opacity = '1';
                }
                """,
            )

            restart_btn.click(
                _confirm_restart,
                inputs=[],
                outputs=[confirm_dialog],
                queue=False,
            )

            confirm_yes.click(
                _handle_confirmation,
                inputs=[gr.Checkbox(value=True, visible=False)],
                outputs=[start_btn, restart_btn, msg, chatbot, confirm_dialog],
            )

            confirm_no.click(
                _handle_confirmation,
                inputs=[gr.Checkbox(value=False, visible=False)],
                outputs=[start_btn, restart_btn, msg, chatbot, confirm_dialog],
            )

            _interface.load(
                update_chatbot,
                inputs=None,
                outputs=chatbot,
                show_api=False,
                js=f"""
                () => {{
                    document.querySelector('footer').style.display = 'none';
                    const style = document.createElement('style');
                    style.textContent = `{custom_css}`;
                    document.head.appendChild(style);

                    // Read the cookie and set the model_dropdown value
                    var selectedModel = document.cookie
                        .split('; ')
                        .find(row => row.startsWith('oh_gradio_selected_model='))
                        ?.split('=')[1];
                    if (selectedModel) {{
                        console.log('cookie selectedModel', selectedModel);
                        selectedModel = decodeURIComponent(selectedModel);
                        console.log('decoded selectedModel', selectedModel);
                        var modelDropdown = document.getElementById('model_dropdown');
                        if (modelDropdown) {{
                            console.log('modelDropdown', modelDropdown);
                            var selectElem = modelDropdown.querySelector('input[role="listbox"]');
                            if (selectElem) {{
                                console.log('selectElem', selectElem);
                                selectElem.value = selectedModel;
                                // Trigger change event to update backend
                                selectElem.dispatchEvent(new Event('change'));
                            }}
                        }}
                    }}
                }}
                """,
            )

        return _interface

    async def add_chat_message(self, assistant_message):
        self.chatbot_state.append(assistant_message)
        # await self._submit_wrapper(assistant_message)
        return gr.update(value=self.preprocess_messages(self.chatbot_state))

    async def _submit_wrapper(self, message):
        if not self.engine.is_running or not self.chatbot:
            gr.Warning(
                visible=True,
                duration=3000,
                message='Backend not started. Please start the backend first.',
            )
            self.chatbot_state.append(('user', message))
        elif 'assistant' not in message:
            try:
                await asyncio.wait_for(
                    self.engine.handle_user_input(message), timeout=30.0
                )
            except asyncio.TimeoutError:
                self.chatbot_state.append(
                    ('system', 'Operation timed out. Please try again.')
                )
            except Exception as e:
                self.chatbot_state.append(('system', f'An error occurred: {str(e)}'))

        return (
            '',
            gr.update(value=self.preprocess_messages(self.chatbot_state)),
        )

    async def _clear_chatbot_wrapper(self):
        self.chatbot_state = []
        return gr.update(value=self.preprocess_messages(self.chatbot_state)), ''

    def _cancel_operation_wrapper(self):
        if self.engine:
            result = self.engine.cancel_operation()  # Call engine method directly
            self.chatbot_state.append(('assistant', result))
        else:
            self.chatbot_state.append(('assistant', 'Backend not started!'))
        return '', gr.update(value=self.chatbot_state)

    def preprocess_messages(self, messages):
        processed_messages = []
        previous_role = None
        for role, content in messages:
            if role == previous_role:
                processed_messages.append((None, content))
            else:
                processed_messages.append((role, content))
            previous_role = role
        return processed_messages

    def update_model(self, model):
        if not model:
            logger.error('No model provided to update_model')
            return
        self.model = model
        self.engine.switch_running_model(self.model)

    async def _start_backend(self):
        self.chatbot_state.append(
            ('assistant', f'Starting backend with model {self.model}, please wait...')
        )

        try:
            await self.engine.run(llm_override=self.model)
            self.chatbot_state.append(
                (
                    'assistant',
                    f'Backend started successfully with model `{self.model}`!',
                )
            )
        except Exception as e:
            logger.error(f'Failed to start backend: {e}')
            self.chatbot_state.append(('assistant', 'Failed to start backend!'))

    def launch(self):
        if not self.interface:
            self.create_interface()
        self.interface.launch(
            server_port=7860,
            prevent_thread_lock=True,
            share=False,
        )
