# OpenHands Gradio App

This is the Gradio interface for the OpenHands project.

## Overview

The `app.py` file is the main entry point for the OpenHands Gradio application. It sets up and runs a Gradio interface for interacting with an AI agent. Here's a breakdown of its key components and functionality:

1. **Imports and Setup:**
   - Imports necessary modules, including Gradio, asyncio, and OpenHands components.
   - Sets up logging and initializes global variables for the chat state.

2. **Helper Functions:**
   - `display_command_output`: Formats command output for display.
   - `display_event`: Converts various event types into human-readable strings.
   - `get_parser`: Sets up command-line argument parsing.

3. **Main Function:**
   - Initializes the configuration, agent, event stream, and runtime.
   - Sets up the AgentController to manage the agent's operations.

4. **Event Handling:**
   - `prompt_for_next_task`: Handles user input and adds it to the event stream.
   - `on_event`: Processes events and updates the chat interface.

5. **User Input Handling:**
   - `handle_user_input`: Manages the flow of conversation, including waiting for agent responses and handling cancellations.

6. **Gradio Interface:**
   - Sets up the Gradio interface using `oh_interface` (defined elsewhere).
   - Launches the Gradio interface asynchronously.

7. **Main Event Loop:**
   - Runs the main application loop, handling cancellation and shutdown gracefully.

8. **Error Handling and Shutdown:**
   - Includes try-except blocks to handle interruptions and errors.
   - Ensures proper shutdown of the Gradio interface and other components.

This file orchestrates the entire application, connecting the AI agent, the event system, and the user interface through Gradio. It provides a robust framework for interactive AI conversations with error handling and asynchronous operation.
