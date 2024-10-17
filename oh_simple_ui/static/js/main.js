document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = getCookie('oh_theme') || 'dark';
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatContainer = document.getElementById('chat-container');
    const scrollableContainer = chatContainer.parentElement;
    const modelDropdown = document.getElementById('model-dropdown');
    const startBtn = document.getElementById('start-button');
    const restartBtn = document.getElementById('restart-button');
    const confirmYesBtn = document.getElementById('confirm-yes');
    const confirmNoBtn = document.getElementById('confirm-no');
    const backendStatus = document.getElementById('backend-status');
    const loadingIndicator = document.getElementById('loading-indicator');
    const themeSelector = document.getElementById('theme-selector');
    const cancelButton = document.getElementById('cancel-button');
    const sendButton = document.getElementById('send-button');
    const clearButton = document.getElementById('clear-button');
    const confirmDialog = document.getElementById('confirm-dialog');
    const copyAllButton = document.getElementById('copy-all-button');
    const imageUploadButton = document.getElementById('image-upload-button');

    const websocket = new WebSocket(`ws://${window.location.host}/ws`);

    const MAX_IMAGES = 4;
    const ALLOWED_IMAGE_TYPES = ['image/gif', 'image/jpeg', 'image/png'];

    let backendRunning = null;
    let backendLoading = false;
    let uploadedImages = [];

    function updateBackendStatus() {
        if (backendRunning) {
            backendStatus.classList.remove('bg-red-500');
            backendStatus.classList.add('bg-green-500');
            backendStatus.title = 'Backend is running';
        } else {
            backendStatus.classList.remove('bg-green-500');
            backendStatus.classList.add('bg-red-500');
            backendStatus.title = 'Backend is not running';
        }
        startBtn.style.display = backendRunning ? 'none' : 'inline-block';
        restartBtn.style.display = backendRunning ? 'inline-block' : 'none';
        setLoadingIndicator(backendLoading);
    }

    function setLoadingIndicator(isEnabled) {
        backendLoading = isEnabled;
        loadingIndicator.style.display = isEnabled ? 'inline-block' : 'none';
        backendStatus.style.display = isEnabled ? 'none' : 'inline-block';
        chatInput.disabled = isEnabled;
        clearButton.disabled = isEnabled;
        cancelButton.disabled = isEnabled;
        sendButton.disabled = isEnabled;
    }

    function checkAndUpdateBackendStatus() {
        fetch('/backend_status')
            .then(response => response.json())
            .then(data => {
                const newStatus = data.is_running;
                console.debug('checkAndUpdateBackendStatus', newStatus);
                // if (newStatus !== backendRunning) {
                backendRunning = newStatus;
                updateBackendStatus();
                // }
            })
            .catch(error => console.error('Error:', error));
    }

    const startPeriodicCheck = () => {
        const checkInterval = 30 * 1000; // 30 seconds

        const periodicCheck = () => {
            const loadingIndicator = document.querySelector(".loading-indicator");
            if (!loadingIndicator || !loadingIndicator.classList.contains("visible")) {
                checkAndUpdateBackendStatus();
            }
        };

        setInterval(periodicCheck, checkInterval);
    };

    copyAllButton.addEventListener('click', () => {
        const messages = chatContainer.querySelectorAll('.chat-bubble .markdown-body');
        let allContent = '';
        messages.forEach((message, index) => {
            if (index > 0) {
                allContent += '\n\n--------------------------------------------------\n\n';
            }
            allContent += message.innerText;
        });

        navigator.clipboard.writeText(allContent).then(() => {
            copyAllButton.title = 'Copied!';
            setTimeout(() => {
                copyAllButton.title = 'Copy all messages';
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy all messages: ', err);
        });
    });

    function updateCopyAllButtonState() {
        const messages = chatContainer.querySelectorAll('.chat-bubble');
        copyAllButton.disabled = messages.length === 0;
    }

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

    // Initialize status display and start status checks
    checkAndUpdateBackendStatus();
    startPeriodicCheck();
    // fetchInitialChatHistory();

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
                updateCopyAllButtonState();
                addStatusMessage('Chat history cleared.');
                uploadedImages = [];
                updateImagePreview();
            } else {
                addStatusMessage('Failed to clear chat history on server.');
            }
        } catch (error) {
            console.error('Error clearing chat history:', error);
            addStatusMessage('Error occurred while clearing chat history.');
        }
    });

    async function handleChatSubmit() {
        const messageContent = chatInput.value.trim();
        if (!messageContent || !backendRunning) {
            return;
        }
        const message = {
            content: messageContent,
            images_urls: uploadedImages,
            timestamp: new Date().toISOString()
        };
        addMessage('user', message);
        chatInput.value = '';
        setLoadingIndicator(true);
        try {
            const response = await fetch('/chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(message),
            });
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            if (data.response) {
                addMessage('assistant', data.response);
            }
        } catch (error) {
            console.error('Error:', error);
            addMessage('assistant', {
                content: 'Sorry, an error occurred. Please try again.',
                images_urls: [],
                timestamp: new Date().toISOString()
            });
        } finally {
            setLoadingIndicator(false);
            uploadedImages = [];
            updateImagePreview();
            chatInput.focus();
        }
    }

    chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        handleChatSubmit();
    });

    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (backendRunning) {
                handleChatSubmit();
            }
        }
    });

    sendButton.addEventListener('click', (e) => {
        e.preventDefault();
        if (backendRunning) {
            handleChatSubmit();
        }
    });

    imageUploadButton.addEventListener('click', () => {
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = 'image/gif,image/jpeg,image/png';
        fileInput.multiple = true;
        fileInput.style.display = 'none';

        fileInput.addEventListener('change', async () => {
            const files = Array.from(fileInput.files);
            for (const file of files) {
                if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
                    addStatusMessage(`File type ${file.type} not allowed. Skipping.`);
                    continue;
                }

                if (uploadedImages.length >= MAX_IMAGES) {
                    addStatusMessage(`Maximum of ${MAX_IMAGES} images reached. Some images were not added.`);
                    break;
                }

                try {
                    // const base64Image = await readFileAsBase64(file);
                    const base64Image = await readFileAsDataURL(file);
                    uploadedImages.push(base64Image);
                } catch (error) {
                    console.error('Error reading image:', error);
                    addStatusMessage('Error reading image');
                }
            }
            updateImagePreview();
        });
        fileInput.click();
    });

    function readFileAsDataURL(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }

    function updateImagePreview() {
        const previewContainer = document.getElementById('image-preview-container');
        previewContainer.innerHTML = '';

        uploadedImages.forEach((base64Image, index) => {
            const imgElement = document.createElement('img');
            imgElement.src = base64Image.startsWith('data:')? base64Image : `data:image/png;base64,${base64Image}`;
            imgElement.alt = `Uploaded image ${index + 1}`;
            imgElement.className = 'preview-image';

            const removeButton = document.createElement('button');
            removeButton.textContent = '×';
            removeButton.className = 'remove-image-button';
            removeButton.onclick = () => removeUploadedImage(index);

            const imageContainer = document.createElement('div');
            imageContainer.className = 'image-preview-item';
            imageContainer.appendChild(imgElement);
            imageContainer.appendChild(removeButton);

            previewContainer.appendChild(imageContainer);
        });

        // Update image upload button state
        imageUploadButton.disabled = uploadedImages.length >= MAX_IMAGES;
        imageUploadButton.title = uploadedImages.length >= MAX_IMAGES ?
            `Maximum of ${MAX_IMAGES} images reached` : 'Upload image';
    }

    function removeUploadedImage(index) {
        uploadedImages.splice(index, 1);
        updateImagePreview();
    }

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
        setLoadingIndicator(true);

        try {
            const response = await fetch('/start_backend/', { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                addStatusMessage('Backend started successfully');
            } else {
                addStatusMessage('Failed to start backend');
            }
        } catch (error) {
            console.error('Error starting backend:', error);
            addStatusMessage('Error occurred while starting backend');
        } finally {
            await checkAndUpdateBackendStatus();
            setLoadingIndicator(false);
            startBtn.disabled = false;
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
        setLoadingIndicator(true);

        try {
            const response = await fetch('/restart_backend/', { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                addStatusMessage('Backend restarted successfully');
                uploadedImages = [];
                updateImagePreview();
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
            setLoadingIndicator(false);
        }
    });

    confirmNoBtn.addEventListener('click', () => {
        confirmDialog.classList.remove('modal-open');
        addStatusMessage('Restart cancelled.');
    });

    function addMessage(sender, message) {
        // Ensure message is an object
        if (typeof message === 'string') {
            message = { content: message };
        }

        // Ensure message has required properties
        message = {
            content: message.content || '',
            images_urls: message.images_urls || [],
            timestamp: message.timestamp || new Date().toISOString()
        };

        if (!message.content && message.images_urls.length === 0) {
            console.error('Invalid message:', message);
            return;
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = `chat ${sender === 'user' ? 'chat-end' : 'chat-start'} w-full`;

        const headerDiv = document.createElement('div');
        headerDiv.className = 'chat-header text-xs flex items-center';
        headerDiv.innerHTML = `
            <span>${sender === 'user' ? 'User' : 'Assistant'}</span>
            <time class="text-xs opacity-50 ml-1">${new Date(message.timestamp).toLocaleTimeString()}</time>
            <button class="ml-4 copy-button" title="Copy to clipboard">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                </svg>
            </button>
        `;

        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = `chat-bubble ${
            sender === 'user' ? 'chat-bubble-primary' : 'chat-bubble-secondary'
        }`;

        const markdownBody = document.createElement('div');
        markdownBody.className = 'markdown-body';
        markdownBody.innerHTML = formatContent(message.content);

        bubbleDiv.appendChild(markdownBody);

        if (message.images_urls && message.images_urls.length > 0) {
            const imageContainer = document.createElement('div');
            imageContainer.className = 'flex flex-wrap gap-2 mt-2';
            message.images_urls.forEach((base64Image, index) => {
                const imgWrapper = document.createElement('div');
                imgWrapper.className = 'relative';

                const img = document.createElement('img');
                img.src = base64Image.startsWith('data:')? base64Image : `data:image/png;base64,${base64Image}`;
                img.alt = `upload preview ${index}`;
                img.className = 'object-cover rounded bg-white';
                img.style = 'width: 200px;';

                const deleteButton = document.createElement('button');
                deleteButton.className = 'absolute top-1 right-1 bg-red-500 text-white rounded-full w-6 h-6 flex items-center justify-center';
                deleteButton.innerHTML = '×';
                deleteButton.onclick = (e) => {
                    e.stopPropagation();
                    deleteImage(message.id, index, base64Image);
                };

                imgWrapper.appendChild(img);
                imgWrapper.appendChild(deleteButton);
                imageContainer.appendChild(imgWrapper);
            });
            bubbleDiv.appendChild(imageContainer);
        }

        messageDiv.appendChild(headerDiv);
        messageDiv.appendChild(bubbleDiv);

        chatContainer.appendChild(messageDiv);
        Prism.highlightAll();
        setTimeout(() => {
            scrollableContainer.scrollTop = scrollableContainer.scrollHeight;
        }, 50);

        updateCopyAllButtonState();

        // Add click event listener to the copy button
        const copyButton = headerDiv.querySelector('.copy-button');
        copyButton.addEventListener('click', () => {
            const content = markdownBody.innerText;
            navigator.clipboard.writeText(content).then(() => {
                // Optionally, you can provide some visual feedback here
                copyButton.title = 'Copied!';
                setTimeout(() => {
                    copyButton.title = 'Copy to clipboard';
                }, 2000);
            }).catch(err => {
                console.error('Failed to copy text: ', err);
            });
        });
    }

    async function deleteImage(messageId, index) {
        console.log(`Deleting image at index ${index} for message ${messageId}`);

        try {
            const response = await fetch('/delete_image/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message_id: messageId, image_index: index }),
            });
            const result = await response.json();
            if (result.success) {
                // Remove the image from the UI
                const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
                if (messageElement) {
                    const imageElements = messageElement.querySelectorAll('.flex.flex-wrap.gap-2.mt-2 > div');
                    if (imageElements[index]) {
                        imageElements[index].remove();
                    }
                }
            } else {
                console.error('Failed to delete image');
                addStatusMessage('Failed to delete image');
            }
        } catch (error) {
            console.error('Error deleting image:', error);
            addStatusMessage(`Error deleting image: ${error.message}`);
        }
    }

    function formatContent(content) {
        const lines = content.split('\n');
        let formattedContent = '';
        let inCodeBlock = false;
        let codeLanguage = '';

        for (const line of lines) {
            if (line.startsWith('```')) {
                if (inCodeBlock) {
                    formattedContent += '</code></pre>';
                    inCodeBlock = false;
                } else {
                    codeLanguage = line.slice(3).trim();
                    formattedContent += `<pre><code class="language-${codeLanguage}">`;
                    inCodeBlock = true;
                }
            } else if (line.startsWith('Bash ❯') || line.startsWith('❯ Command:')) {
                formattedContent += `<pre><code class="language-bash">${escapeHtml(line)}\n`;
            } else if (line.startsWith('IPython ❯') || line.startsWith('❯ Code:')) {
                formattedContent += `<pre><code class="language-python">${escapeHtml(line)}\n`;
            } else if (inCodeBlock) {
                formattedContent += escapeHtml(line) + '\n';
            } else {
                formattedContent += parseMarkdown(line) + '\n';
            }
        }

        if (inCodeBlock) {
            formattedContent += '</code></pre>';
        }

        return formattedContent;
    }

    function escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function parseMarkdown(text) {
        let inList = false;
        let listType = null;
        let listContent = '';

        // Process the text line by line
        const lines = text.split('\n');
        const processedLines = lines.map((line, index) => {
            // Basic inline formatting
            line = line
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.*?)\*/g, '<em>$1</em>')
                .replace(/`(.*?)`/g, '<code>$1</code>')
                .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2">$1</a>');

            // Headers
            if (line.startsWith('# ')) {
                return `<h1>${line.slice(2)}</h1>`;
            } else if (line.startsWith('## ')) {
                return `<h2>${line.slice(3)}</h2>`;
            } else if (line.startsWith('### ')) {
                return `<h3>${line.slice(4)}</h3>`;
            }

            // Lists
            if (line.match(/^\d+\. /) || line.startsWith('- ')) {
                const newListType = line.match(/^\d+\. /) ? 'ol' : 'ul';
                const listItemContent = line.replace(/^\d+\. |-\s*/, '');

                if (!inList) {
                    inList = true;
                    listType = newListType;
                    listContent = `<${listType}><li>${listItemContent}</li>`;
                } else if (listType !== newListType) {
                    const completedList = `${listContent}</${listType}>`;
                    listType = newListType;
                    listContent = `<${listType}><li>${listItemContent}</li>`;
                    return completedList;
                } else {
                    listContent += `<li>${listItemContent}</li>`;
                }

                if (index === lines.length - 1) {
                    return `${listContent}</${listType}>`;
                }
                return null;
            } else if (inList) {
                const completedList = `${listContent}</${listType}>`;
                inList = false;
                listContent = '';
                return completedList + (line.trim() ? `\n${line}` : '');
            }

            return line;
        });

        // Filter out null values and join the lines
        return processedLines.filter(line => line !== null).join('\n');
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

    async function fetchInitialChatHistory() {
        // TODO: not working yet!
        try {
            const response = await fetch('/initial_chat_history');
            const data = await response.json();
            if (data.history && data.history.length > 0) {
                data.history.forEach(item => {
                    appendMessage(item.role, item.message.content);
                });
            }
        } catch (error) {
            console.error('Error fetching initial chat history:', error);
        }
    }

    function appendMessage(role, content) {
        const chatBox = document.getElementById('chat-box');
        const messageDiv = document.createElement('div');
        messageDiv.className = role === 'assistant' ? 'assistant-message' : 'user-message';
        messageDiv.textContent = content;
        chatBox.appendChild(messageDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

});
