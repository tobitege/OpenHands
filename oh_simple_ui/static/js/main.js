document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = getCookie('oh_theme') || 'dark';
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatContainer = document.getElementById('chat-container');
    const modelDropdown = document.getElementById('model-dropdown');
    const startBtn = document.getElementById('start-button');
    const restartBtn = document.getElementById('restart-button');
    const confirmYesBtn = document.getElementById('confirm-yes');
    const confirmNoBtn = document.getElementById('confirm-no');
    const backendStatus = document.getElementById('backend-status');
    const loadingIndicator = document.getElementById('loading-indicator');
    const cancelButton = document.getElementById('cancel-button');
    const sendButton = document.getElementById('send-button');
    const clearButton = document.getElementById('clear-button');
    const confirmDialog = document.getElementById('confirm-dialog');
    const imageUploadButton = document.getElementById('image-upload-button');

    function updateBackendStatus(isRunning) {
        if (isRunning) {
            backendStatus.classList.remove('bg-red-500');
            backendStatus.classList.add('bg-green-500');
            backendStatus.title = 'Backend is running';
        } else {
            backendStatus.classList.remove('bg-green-500');
            backendStatus.classList.add('bg-red-500');
            backendStatus.title = 'Backend is not running';
        }
        console.debug('updateBackendStatus done', isRunning);
    }

    async function checkAndUpdateBackendStatus() {
        try {
            const response = await fetch('/backend_status');
            const data = await response.json();
            updateBackendStatus(data.is_running);
        } catch (error) {
            console.error('Error fetching backend status:', error);
            updateBackendStatus(false);
        }
    }

    function showLoadingIndicator() {
        backendStatus.style.display = 'none';
        loadingIndicator.style.display = 'inline-block';
        userInput.disabled = true;
        clearButton.disabled = true;
        cancelButton.disabled = true;
        sendButton.disabled = true;
    }

    function hideLoadingIndicator() {
        loadingIndicator.style.display = 'none';
        backendStatus.style.display = 'block';
        userInput.disabled = false;
        clearButton.disabled = false;
        cancelButton.disabled = false;
        sendButton.disabled = false;
    }

    // Initial status check
    checkAndUpdateBackendStatus();

    // Fetch and populate model dropdown
    fetch('/models')
        .then(response => response.json())
        .then(data => {
            modelDropdown.innerHTML = ''; // Clear existing options
            data.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                if (model === data.default_model) {
                    option.selected = true;
                }
                modelDropdown.appendChild(option);
            });

            // Load selected model from cookie
            const selectedModel = getCookie('oh_selected_model');
            if (selectedModel) {
                console.debug('Loading selected model from cookie:', selectedModel);
                modelDropdown.value = selectedModel;
                // Trigger change event to update backend
                modelDropdown.dispatchEvent(new Event('change'));
            }
        })
        .catch(error => console.error('Error fetching models:', error));

    const websocket = new WebSocket(`ws://${window.location.host}/ws`);

    websocket.onmessage = (event) => {
        const messageData = JSON.parse(event.data);
        const { role, content } = messageData;
        if (role != 'user') {
            addMessage(role, content);
        }
    };

    websocket.onclose = () => {
        console.warn('WebSocket connection closed');
    };

    websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
        addStatusMessage('WebSocket error occurred');
    };

    modelDropdown.addEventListener('change', async () => {
        const selectedModel = modelDropdown.value;
        console.debug('Model changed to:', selectedModel);

        // Save selected model to cookie
        setCookie('oh_selected_model', selectedModel, 30); // Expires in 30 days

        try {
            const response = await fetch('/switch_model/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ model: selectedModel }),
            });
            const data = await response.json();
            if (data.success) {
                addStatusMessage(`Model switched to ${selectedModel}`);
            } else {
                addStatusMessage(`Failed to switch model to ${selectedModel}`);
            }
        } catch (error) {
            console.error('Error switching model:', error);
            addStatusMessage('Error occurred while switching model');
        }
    });

    clearButton.addEventListener('click', async () => {
        try {
            const response = await fetch('/clear/', { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                chatContainer.innerHTML = '';
                addStatusMessage('Chat history cleared.');
            } else {
                addStatusMessage('Failed to clear chat history on server.');
            }
        } catch (error) {
            console.error('Error clearing chat history:', error);
            addStatusMessage('Error occurred while clearing chat history.');
        }
    });

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = userInput.value.trim();
        if (message) {
            addMessage('user', message);
            userInput.value = '';
            try {
                const response = await fetch('/chat/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ message }),
                });
                const data = await response.json();
                addMessage('assistant', data.response);
            } catch (error) {
                console.error('Error:', error);
                addMessage('assistant', 'Sorry, an error occurred. Please try again.');
            }
        }
    });

    imageUploadButton.addEventListener('click', () => {
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = 'image/*';
        fileInput.style.display = 'none';

        fileInput.addEventListener('change', () => {
            const file = fileInput.files[0];
            if (file) {
                // Handle the image file upload here
                console.log('Selected file:', file);
                // You can display a preview or send the file to the server
            }
        });

        // Trigger the file input click
        fileInput.click();
    });

    const themeSelector = document.getElementById('theme-selector');
    themeSelector.addEventListener('change', () => {
        const selectedTheme = themeSelector.value.toLowerCase();
        document.documentElement.setAttribute('data-theme', selectedTheme);
        setCookie('oh_theme', selectedTheme, 30);
    });

    if (savedTheme) {
        themeSelector.value = savedTheme;
        document.documentElement.setAttribute('data-theme', savedTheme);
    }

    startBtn.addEventListener('click', async () => {
        startBtn.disabled = true;
        showLoadingIndicator();

        try {
            const response = await fetch('/start_backend/', { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                addStatusMessage('Backend started successfully');
                startBtn.style.display = 'none';
                restartBtn.style.display = 'inline-block';
            } else {
                addStatusMessage('Failed to start backend');
                startBtn.disabled = false;
            }
        } catch (error) {
            console.error('Error starting backend:', error);
            addStatusMessage('Error occurred while starting backend');
            startBtn.disabled = false;
        } finally {
            hideLoadingIndicator();
            await checkAndUpdateBackendStatus();
        }
    });

    restartBtn.addEventListener('click', () => {
        confirmDialog.classList.add('modal-open');
    });

    confirmYesBtn.addEventListener('click', async () => {
        confirmDialog.classList.remove('modal-open');
        restartBtn.disabled = true;
        restartBtn.textContent = 'Restarting...';
        restartBtn.style.opacity = '0.5';

        try {
            const response = await fetch('/restart_backend/', { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                addStatusMessage('Backend restarted successfully');
            } else {
                addStatusMessage('Failed to restart backend');
            }
        } catch (error) {
            console.error('Error restarting backend:', error);
            addStatusMessage('Error occurred while restarting backend');
        } finally {
            restartBtn.disabled = false;
            restartBtn.textContent = 'Restart Backend';
            restartBtn.style.opacity = '1';
            await checkAndUpdateBackendStatus();
        }
    });

    confirmNoBtn.addEventListener('click', () => {
        confirmDialog.classList.remove('modal-open');
        addStatusMessage('Restart cancelled.');
    });

    function addMessage(sender, content) {
        let textContent = Array.isArray(content) ? content[1] : content;
        if (!textContent || textContent.length === 0) {
            return;
        }
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat ${sender === 'user' ? 'chat-end' : 'chat-start'} w-full`;

        const headerDiv = document.createElement('div');
        headerDiv.className = 'chat-header text-xs';
        headerDiv.innerHTML = `
            ${sender === 'user' ? 'User' : 'Assistant'}
            <time class="text-xs opacity-50 ml-1">${new Date().toLocaleTimeString()}</time>
        `;

        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = `chat-bubble ${
            sender === 'user' ? 'chat-bubble-primary' : 'chat-bubble-secondary'
        }`;

        const lines = textContent.split('\n');
        let currentSection = [];
        let inCodeBlock = false;

        for (const line of lines) {
            if (line.includes('❯ Command:') || line.includes('❯ Code:') || line.startsWith('IPython ❯')) {
                if (currentSection.length > 0) {
                    appendSection(bubbleDiv, currentSection, inCodeBlock);
                    currentSection = [];
                }
                inCodeBlock = true;
                currentSection.push(line);
            } else {
                currentSection.push(line);
            }
        }

        if (currentSection.length > 0) {
            appendSection(bubbleDiv, currentSection, inCodeBlock);
        }

        messageDiv.appendChild(headerDiv);
        messageDiv.appendChild(bubbleDiv);

        chatContainer.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function appendSection(bubbleDiv, section, isCode) {
        if (isCode) {
            const firstLine = document.createElement('p');
            firstLine.textContent = section[0];
            bubbleDiv.appendChild(firstLine);

            if (section.length > 1) {
                const mockupCode = document.createElement('div');
                mockupCode.className = 'mockup-code';

                section.slice(1).forEach((line, index) => {
                    const pre = document.createElement('pre');
                    pre.setAttribute('data-prefix', index + 1);
                    const code = document.createElement('code');
                    code.textContent = line;
                    pre.appendChild(code);
                    mockupCode.appendChild(pre);
                });

                bubbleDiv.appendChild(mockupCode);
            }
        } else {
            const p = document.createElement('p');
            p.textContent = section.join('\n');
            bubbleDiv.appendChild(p);
        }
    }

    function addStatusMessage(message) {
        const statusLog = document.getElementById('status-log');
        const timestamp = new Date().toLocaleTimeString(navigator.language, {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        const formattedMessage = `[${timestamp}] ${message}`;

        if (statusLog.value) {
            statusLog.value += '\n' + formattedMessage;
        } else {
            statusLog.value = formattedMessage;
        }

        statusLog.scrollTop = statusLog.scrollHeight;
    }

    // Helper function to set a cookie
    function setCookie(name, value, days) {
        let expires = "";
        if (days) {
            const date = new Date();
            date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
            expires = "; expires=" + date.toUTCString();
        }
        document.cookie = name + "=" + (value || "")  + expires + "; path=/; SameSite=Strict";
    }

    // Helper function to get a cookie
    function getCookie(name) {
        const nameEQ = name + "=";
        const ca = document.cookie.split(';');
        for(let i = 0; i < ca.length; i++) {
            let c = ca[i];
            while (c.charAt(0) == ' ') c = c.substring(1, c.length);
            if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length, c.length);
        }
        return null;
    }
});
