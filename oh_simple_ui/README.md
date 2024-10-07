# OpenHands Simple UI App

This is the Simple UI interface for the OpenHands project, a custom made, more leightweight
FastAPI app to interact with the OpenHands backend.

## Installation and Setup

Before you begin, ensure that this folder is placed within the OpenHands root repository.

To set up the OpenHands SimpleUI App, follow these steps:

1. Navigate to the `oh_simple_ui` directory:

   ```sh
   cd path/to/OpenHands/oh_simple_ui
   ```

2. Run the setup script to install dependencies and build the CSS:

   ```sh
   npm run setup
   ```

This will install all necessary dependencies and build the initial CSS file.

## Available Scripts

In the project directory, you can run:

### `npm run setup`

Installs all dependencies and builds the initial CSS file. This is a combination of `npm install` and `npm run build:css`.

### `npm run build:css`

Builds the CSS file using Tailwind CSS, processing the input file `./static/css/styles.css` and outputting to `./static/css/output.css`.

### `npm run watch:css`

Starts Tailwind CSS in watch mode, automatically rebuilding the CSS file whenever changes are made to the input file or Tailwind configuration.

### `npm test`

Currently set up as a placeholder. It will echo an error message and exit with a non-zero status.

## Overview

The `app.py` file is the main entry point for the OpenHands SimpleUI application. It sets up and runs a UI interface for interacting with an AI agent.

Features for the OpenHands SimpleUI app:

1. Chat Interface:
   - Chat conversation between user and assistant with in-line code rendering
   - Clear chat history button
   - Image upload support coming soon

1. Model Selection:
   - Dropdown menu to select different AI models based on config.toml file
   - Ability to switch between models dynamically, even with running backend
   - Persistence of selected model between sessions using cookies

1. Backend Management:
   - Start/Restart backend functionality (includes docker container)
   - Visual indicator of backend status (running/not running)
   - Confirmation dialog for restarting the backend

1. Themes:
   - Theme selector with multiple options (light, dark, and various other themes)
   - Theme persistence between sessions using cookies

1. Status Logging:
   - Display of status messages in a dedicated log area
   - Timestamped entries for various actions and events

1. Responsive Design:
   - Layout adapts to different screen sizes
   - Sidebar for options and main content area for chat

1. Loading Indicators:
   - Visual feedback for loading states (e.g., when starting/restarting the backend)

1. Error Handling:
    - Display of error messages in the chat and status log
    - Graceful handling of WebSocket connection issues

1. Accessibility:
    - ARIA labels for buttons to improve screen reader compatibility

## Future Features

1. Image Upload:
   - Button to trigger image file selection
   - Note: The image upload functionality is not implemented yet and may cause errors!

1. Cancel Functionality:
    - The Cancel button for the Chat options will be implemented soon

## Used technologies

1. DaisyUI
1. JavaScript
1. HTML
1. WebSockets

Based on OpenHands:

1. FastAPI
1. uvicorn
1. Tailwind CSS
1. Docker
