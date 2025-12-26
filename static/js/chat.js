// static/js/chat.js
document.addEventListener('DOMContentLoaded', function() {
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const chatMessages = document.getElementById('chat-messages');
    const typingIndicator = document.getElementById('typing-indicator');
    
    // Focus on input when page loads
    messageInput.focus();
    
    // Send message on button click
    sendButton.addEventListener('click', sendMessage);
    
    // Send message on Enter key press
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Auto-resize input and enable/disable send button
    messageInput.addEventListener('input', function() {
        const message = this.value.trim();
        sendButton.disabled = message === '';
        
        if (message === '') {
            sendButton.style.opacity = '0.6';
        } else {
            sendButton.style.opacity = '1';
        }
    });
    
    async function sendMessage() {
        const message = messageInput.value.trim();
        if (!message) return;
        
        // Disable input and button
        messageInput.disabled = true;
        sendButton.disabled = true;
        
        // Add user message to chat
        addMessage(message, 'user');
        
        // Clear input
        messageInput.value = '';
        
        // Show typing indicator
        showTypingIndicator();
        
        try {
            // Send message to backend
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message })
            });
            
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            
            const data = await response.json();
            
            // Hide typing indicator
            hideTypingIndicator();
            
            // Add bot response to chat
            addMessage(data.response, 'bot');
            
        } catch (error) {
            console.error('Error:', error);
            hideTypingIndicator();
            addMessage('Sorry, I encountered an error. Please try again later.', 'bot');
        } finally {
            // Re-enable input and button
            messageInput.disabled = false;
            sendButton.disabled = false;
            messageInput.focus();
            sendButton.style.opacity = '0.6';
        }
    }
    
    function addMessage(content, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;
        
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'message-avatar';
        
        if (sender === 'user') {
            avatarDiv.innerHTML = '<i class="fas fa-user"></i>';
        } else {
            avatarDiv.innerHTML = '<i class="fas fa-robot"></i>';
        }
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        // Convert markdown-like formatting to HTML
        let formattedContent = content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>');
        
        // Convert bullet points to HTML lists
        if (formattedContent.includes('•') || formattedContent.includes('-')) {
            const lines = formattedContent.split('<br>');
            let inList = false;
            let htmlLines = [];
            
            lines.forEach(line => {
                const trimmedLine = line.trim();
                if (trimmedLine.startsWith('•') || trimmedLine.startsWith('-')) {
                    if (!inList) {
                        htmlLines.push('<ul>');
                        inList = true;
                    }
                    const listContent = trimmedLine.substring(1).trim();
                    htmlLines.push(`<li>${listContent}</li>`);
                } else {
                    if (inList) {
                        htmlLines.push('</ul>');
                        inList = false;
                    }
                    if (trimmedLine) {
                        htmlLines.push(`<p>${trimmedLine}</p>`);
                    }
                }
            });
            
            if (inList) {
                htmlLines.push('</ul>');
            }
            
            formattedContent = htmlLines.join('');
        } else {
            // Wrap in paragraphs if no lists
            const paragraphs = formattedContent.split('<br><br>');
            formattedContent = paragraphs.map(p => p.trim() ? `<p>${p}</p>` : '').join('');
        }
        
        contentDiv.innerHTML = formattedContent;
        
        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        
        chatMessages.appendChild(messageDiv);
        
        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        // Add animation
        messageDiv.style.opacity = '0';
        messageDiv.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            messageDiv.style.transition = 'all 0.3s ease';
            messageDiv.style.opacity = '1';
            messageDiv.style.transform = 'translateY(0)';
        }, 50);
    }
    
    function showTypingIndicator() {
        typingIndicator.style.display = 'flex';
    }
    
    function hideTypingIndicator() {
        typingIndicator.style.display = 'none';
    }
    
    // Scroll to bottom on page load
    setTimeout(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }, 100);
    
    // Sample quick questions for demonstration
    const quickQuestions = [
        "How many sick days do I have?",
        "When does my passport expire?",
        "What's my salary information?",
        "Show me all my leave balances",
        "How many vacation days are left?"
    ];
    
    // Add quick question buttons (optional)
    function addQuickQuestions() {
        const quickQuestionsDiv = document.createElement('div');
        quickQuestionsDiv.className = 'quick-questions';
        quickQuestionsDiv.innerHTML = '<p><strong>Quick Questions:</strong></p>';
        
        const buttonsContainer = document.createElement('div');
        buttonsContainer.className = 'quick-question-buttons';
        
        quickQuestions.forEach(question => {
            const button = document.createElement('button');
            button.className = 'btn btn-outline-primary btn-sm me-2 mb-2';
            button.textContent = question;
            button.addEventListener('click', () => {
                messageInput.value = question;
                sendMessage();
            });
            buttonsContainer.appendChild(button);
        });
        
        quickQuestionsDiv.appendChild(buttonsContainer);
        
        // Add to initial bot message
        const initialMessage = chatMessages.querySelector('.bot-message .message-content');
        if (initialMessage) {
            initialMessage.appendChild(quickQuestionsDiv);
        }
    }
    
    // Add quick questions after a short delay
    setTimeout(addQuickQuestions, 1000);
    
    // Handle window resize for mobile
    function handleResize() {
        if (window.innerWidth <= 768) {
            chatMessages.style.height = `${window.innerHeight - 200}px`;
        } else {
            chatMessages.style.height = 'auto';
        }
    }
    
    window.addEventListener('resize', handleResize);
    handleResize();
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Focus input on any letter key (when not already focused)
        if (e.key.match(/^[a-zA-Z]$/) && document.activeElement !== messageInput) {
            messageInput.focus();
        }
        
        // Clear chat with Ctrl+L
        if (e.ctrlKey && e.key === 'l') {
            e.preventDefault();
            clearChat();
        }
    });
    
    function clearChat() {
        // Remove all messages except the initial bot message
        const messages = chatMessages.querySelectorAll('.message:not(:first-child)');
        messages.forEach(message => message.remove());
    }
});