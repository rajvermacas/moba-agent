# UI Integration Prompt: Session Management Feature

## Overview
We have implemented a new session management system for the chat API that allows users to create, manage, and clear chat sessions. This replaces the previous hardcoded "default" thread_id with dynamic session management. You need to integrate this into the UI with a "New Chat" or "Clear Chat" functionality.

## API Endpoints

### 1. Create New Session
**Endpoint:** `POST /sessions/new`  
**Method:** POST  
**Headers:** None required  
**Request Body:** None  
**Response Schema:**
```json
{
  "success": boolean,
  "thread_id": string,  // e.g., "session_1_29257d0a"
  "message": string      // e.g., "New session created successfully"
}
```
**Status Codes:**
- 200: Success
- 500: Server error

**Example Request:**
```javascript
const response = await fetch('http://localhost:8001/sessions/new', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  }
});
const data = await response.json();
const newThreadId = data.thread_id;
```

### 2. Chat with Session
**Endpoint:** `POST /chat/completions`  
**Method:** POST  
**Headers:** 
- `Content-Type: application/json`
- `X-Thread-Id: <thread_id>` (Optional - if not provided, creates new session automatically)

**Request Body Schema:**
```json
{
  "messages": [
    {
      "role": "user" | "assistant" | "system",
      "content": string
    }
  ],
  "model": string  // Optional, defaults to configured model
}
```

**Response Schema:**
```json
{
  "id": string,
  "object": "chat.completion",
  "created": number,
  "model": string,
  "choices": [
    {
      "index": number,
      "message": {
        "role": "assistant",
        "content": string,
        "name": null
      },
      "finish_reason": string
    }
  ],
  "usage": null
}
```

**Example Request:**
```javascript
const response = await fetch('http://localhost:8001/chat/completions', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Thread-Id': currentThreadId  // Use stored thread_id
  },
  body: JSON.stringify({
    messages: [
      { role: 'user', content: userMessage }
    ]
  })
});
```

### 3. Clear/Delete Session
**Endpoint:** `DELETE /sessions/{thread_id}`  
**Method:** DELETE  
**URL Parameters:** 
- `thread_id`: The session ID to clear

**Response Schema (Success):**
```json
{
  "success": boolean,
  "message": string,
  "thread_id": string,
  "cleared_components": string[]  // ["resource_injection", "active_session"]
}
```

**Status Codes:**
- 200: Success - Session cleared
- 404: Session not found
- 500: Server error

**Example Request:**
```javascript
const response = await fetch(`http://localhost:8001/sessions/${currentThreadId}`, {
  method: 'DELETE'
});

if (response.status === 404) {
  console.log('Session already cleared or does not exist');
} else if (response.status === 200) {
  const data = await response.json();
  console.log('Session cleared:', data.message);
}
```

### 4. Get Active Sessions (Optional)
**Endpoint:** `GET /sessions`  
**Method:** GET  
**Response Schema:**
```json
{
  "success": boolean,
  "active_sessions": string[],  // Array of thread_ids
  "session_count": number
}
```

## UI Implementation Requirements

### 1. Session State Management
The UI should maintain the current `thread_id` in the application state:

```javascript
// State management example
const [currentThreadId, setCurrentThreadId] = useState(null);
const [conversationHistory, setConversationHistory] = useState([]);
```

### 2. New Chat / Clear Chat Button
Implement a button that allows users to start a new conversation:

```javascript
const handleNewChat = async () => {
  try {
    // Option 1: Clear current session and create new one
    if (currentThreadId) {
      await fetch(`http://localhost:8001/sessions/${currentThreadId}`, {
        method: 'DELETE'
      });
    }
    
    // Create new session
    const response = await fetch('http://localhost:8001/sessions/new', {
      method: 'POST'
    });
    
    const data = await response.json();
    if (data.success) {
      setCurrentThreadId(data.thread_id);
      setConversationHistory([]); // Clear UI conversation history
      // Show success message to user
      showNotification('New chat session started');
    }
  } catch (error) {
    console.error('Failed to create new session:', error);
    showError('Failed to start new chat');
  }
};
```

### 3. Session Persistence
Consider storing the `thread_id` in localStorage for session persistence across page refreshes:

```javascript
// Save thread_id when created
localStorage.setItem('chatThreadId', threadId);

// Restore on app load
const savedThreadId = localStorage.getItem('chatThreadId');
if (savedThreadId) {
  setCurrentThreadId(savedThreadId);
}

// Clear on new chat
localStorage.removeItem('chatThreadId');
```

### 4. Error Handling
Handle various error scenarios:

```javascript
const sendMessage = async (message) => {
  try {
    const response = await fetch('http://localhost:8001/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(currentThreadId && { 'X-Thread-Id': currentThreadId })
      },
      body: JSON.stringify({
        messages: [{ role: 'user', content: message }]
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    
    // If no thread_id was set, the server auto-created one
    // You might want to extract and store it from response headers if provided
    
    return data.choices[0].message.content;
  } catch (error) {
    console.error('Failed to send message:', error);
    // Handle error appropriately
  }
};
```

## UI/UX Recommendations

### 1. Visual Indicators
- Show current session status (active/new)
- Display a clear "New Chat" or "Clear Conversation" button
- Consider showing a confirmation dialog before clearing the current session

### 2. Button Placement Options
- **Header/Toolbar**: Place a "New Chat" button in the main toolbar
- **Sidebar**: If you have a conversation list, add a "+" or "New Chat" button
- **Chat Input Area**: Add a clear/reset button near the message input

### 3. Confirmation Dialog
```javascript
const confirmNewChat = () => {
  if (conversationHistory.length > 0) {
    return confirm('Starting a new chat will clear the current conversation. Continue?');
  }
  return true;
};

const handleNewChatClick = async () => {
  if (confirmNewChat()) {
    await handleNewChat();
  }
};
```

### 4. Loading States
Show appropriate loading states during session operations:

```javascript
const [isCreatingSession, setIsCreatingSession] = useState(false);

const handleNewChat = async () => {
  setIsCreatingSession(true);
  try {
    // ... session creation logic
  } finally {
    setIsCreatingSession(false);
  }
};

// In UI
<button 
  onClick={handleNewChatClick} 
  disabled={isCreatingSession}
>
  {isCreatingSession ? 'Creating...' : 'New Chat'}
</button>
```

## Migration Notes

### From Old Implementation
If your UI was previously working with the hardcoded "default" thread_id:
1. No breaking changes for existing chat functionality
2. The API is backward compatible - omitting `X-Thread-Id` header auto-creates sessions
3. Consider adding the new session management features gradually

### Testing Checklist
- [ ] New chat button creates a new session
- [ ] Messages are sent with the correct thread_id
- [ ] Conversation history is maintained within a session
- [ ] Clear/delete functionality works properly
- [ ] UI state is cleared when starting new chat
- [ ] Error states are handled gracefully
- [ ] Session persists across page refreshes (if implemented)
- [ ] Loading states appear during async operations
- [ ] Confirmation dialog appears before clearing active conversation

## Example Complete Implementation

```javascript
import React, { useState, useEffect } from 'react';

const ChatComponent = () => {
  const [threadId, setThreadId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  // Initialize session on mount
  useEffect(() => {
    const initSession = async () => {
      const savedThreadId = localStorage.getItem('chatThreadId');
      if (!savedThreadId) {
        await createNewSession();
      } else {
        setThreadId(savedThreadId);
      }
    };
    initSession();
  }, []);

  const createNewSession = async () => {
    try {
      const response = await fetch('http://localhost:8001/sessions/new', {
        method: 'POST'
      });
      const data = await response.json();
      if (data.success) {
        setThreadId(data.thread_id);
        localStorage.setItem('chatThreadId', data.thread_id);
        return data.thread_id;
      }
    } catch (error) {
      console.error('Failed to create session:', error);
    }
  };

  const clearChat = async () => {
    if (!confirm('Start a new conversation? Current chat will be cleared.')) {
      return;
    }

    setIsLoading(true);
    try {
      // Clear current session
      if (threadId) {
        await fetch(`http://localhost:8001/sessions/${threadId}`, {
          method: 'DELETE'
        });
      }
      
      // Create new session
      await createNewSession();
      
      // Clear UI state
      setMessages([]);
      
    } finally {
      setIsLoading(false);
    }
  };

  const sendMessage = async (content) => {
    try {
      const response = await fetch('http://localhost:8001/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(threadId && { 'X-Thread-Id': threadId })
        },
        body: JSON.stringify({
          messages: [{ role: 'user', content }]
        })
      });

      const data = await response.json();
      return data.choices[0].message.content;
    } catch (error) {
      console.error('Failed to send message:', error);
      throw error;
    }
  };

  return (
    <div>
      <button onClick={clearChat} disabled={isLoading}>
        {isLoading ? 'Creating new chat...' : 'New Chat'}
      </button>
      {/* Rest of your chat UI */}
    </div>
  );
};
```

## API Base URL Configuration
Make sure to configure the API base URL appropriately for your environment:
- Development: `http://localhost:8001`
- Production: Configure based on your deployment

## Questions to Consider
1. Do you want to show a list of previous sessions?
2. Should sessions expire after a certain time?
3. Do you want to implement session naming/labeling?
4. Should the UI auto-save conversation history locally?

## Support
For any questions about the API implementation, refer to the backend documentation or contact the backend team. The session management system is designed to be simple and straightforward to integrate while providing flexibility for future enhancements.