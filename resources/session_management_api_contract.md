# Session Management API Contract

## Overview
The chat API now supports dynamic session management. Previously, all conversations used a hardcoded "default" thread_id. The new system allows creating, managing, and clearing individual chat sessions.

## Business Requirements Implemented
- Users can start new chat conversations (clear current session)
- Each session maintains its own conversation history
- Sessions are isolated from each other
- Conversation context persists within a session
- Sessions can be explicitly cleared/deleted

## API Endpoints

### 1. Create New Session
**Purpose:** Creates a new chat session with a unique identifier

**Endpoint:** `POST /sessions/new`  
**Method:** `POST`  
**Request Body:** None required  
**Response (200 OK):**
```json
{
  "success": true,
  "thread_id": "session_1_29257d0a",
  "message": "New session created successfully"
}
```
**Error Response (500):**
```json
{
  "detail": "Error creating new session: <error_message>"
}
```

### 2. Send Chat Message
**Purpose:** Send a message within a specific session or auto-create a new session

**Endpoint:** `POST /chat/completions`  
**Method:** `POST`  
**Headers:** 
- `Content-Type: application/json` (required)
- `X-Thread-Id: <thread_id>` (optional - if omitted, auto-creates new session)

**Request Body:**
```json
{
  "messages": [
    {
      "role": "user",
      "content": "Your message here"
    }
  ],
  "model": "gemini-2.5-flash"  // optional
}
```

**Response (200 OK):**
```json
{
  "id": "chatcmpl-<uuid>",
  "object": "chat.completion",
  "created": 1756030552,
  "model": "gemini-2.5-flash",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Assistant's response",
        "name": null
      },
      "finish_reason": "stop",
      "query_result": null
    }
  ],
  "usage": null
}
```

### 3. Clear Session
**Purpose:** Clears a specific chat session and its conversation history

**Endpoint:** `DELETE /sessions/{thread_id}`  
**Method:** `DELETE`  
**Path Parameters:** 
- `thread_id`: The session identifier to clear

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Session cleared successfully",
  "thread_id": "session_1_29257d0a",
  "cleared_components": ["resource_injection", "active_session"]
}
```

**Response (404 Not Found):**
```json
{
  "detail": "Session with thread_id 'session_xyz' not found"
}
```

### 4. List Active Sessions
**Purpose:** Retrieves list of all currently active sessions

**Endpoint:** `GET /sessions`  
**Method:** `GET`  
**Response (200 OK):**
```json
{
  "success": true,
  "active_sessions": ["session_1_29257d0a", "session_2_abc123"],
  "session_count": 2
}
```

## Session Management Behavior

### Session Lifecycle
1. **Creation**: Sessions are created via `/sessions/new` or automatically when sending a message without `X-Thread-Id`
2. **Usage**: Include `X-Thread-Id` header in chat requests to use a specific session
3. **Persistence**: Sessions maintain conversation history until explicitly cleared
4. **Deletion**: Sessions are removed via DELETE endpoint

### Session Identifiers
- Format: `session_{counter}_{random_hex}`
- Example: `session_1_29257d0a`
- Unique per session
- Must be included in `X-Thread-Id` header for subsequent messages

### Memory Management
- Each session maintains independent conversation history
- Clearing a session removes its conversation context
- Sessions are isolated - no data sharing between sessions

## Integration Notes

### For "New Chat" / "Clear Chat" Functionality
1. Call `DELETE /sessions/{current_thread_id}` to clear current session (optional)
2. Call `POST /sessions/new` to create fresh session
3. Use returned `thread_id` for subsequent chat messages
4. Update UI state to reflect new session

### Backward Compatibility
- Omitting `X-Thread-Id` header auto-creates a new session
- Existing integrations continue to work without modification
- Each request without header gets its own session

### Error Handling Considerations
- 404 on DELETE is safe to ignore (session already cleared)
- 500 errors should trigger retry logic or user notification
- Always check `success` field in responses

## Functional Requirements for UI Integration

The UI should support the following user actions:
1. **Start New Conversation**: Clear current session and begin fresh
2. **Continue Conversation**: Maintain context within same session
3. **Handle Session State**: Track current session ID
4. **Clear Confirmation**: Optionally confirm before clearing active conversation

## Testing Scenarios

Backend guarantees the following behaviors:
1. New sessions have unique identifiers
2. Messages within same session maintain context
3. Different sessions are completely isolated
4. Clearing non-existent session returns 404
5. Auto-session creation works when header is omitted

## Additional Information

- **Server Base URL**: `http://localhost:8001` (development)
- **Content Type**: All requests use `application/json`
- **Authentication**: Not required (current implementation)
- **Rate Limiting**: Not implemented
- **Session Expiry**: Sessions persist until explicitly cleared

## Contact
For backend API questions or issues, refer to the backend team. The API is designed for simplicity and flexibility to support various UI implementations.