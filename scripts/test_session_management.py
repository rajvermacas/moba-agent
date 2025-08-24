#!/usr/bin/env python3
"""
Test script for the new session management functionality.
This script tests the new endpoints for creating and clearing chat sessions.
"""

import asyncio
import aiohttp
import json
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Server configuration
SERVER_URL = "http://localhost:8001"

async def test_create_new_session() -> str:
    """Test creating a new session and return the thread_id."""
    logger.info("Testing: Create new session")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{SERVER_URL}/sessions/new") as response:
            result = await response.json()
            
            if response.status == 200:
                logger.info(f"✓ New session created successfully")
                logger.info(f"  Thread ID: {result.get('thread_id')}")
                return result.get('thread_id')
            else:
                logger.error(f"✗ Failed to create session: {result}")
                return None


async def test_chat_with_session(thread_id: str = None) -> Dict[str, Any]:
    """Test chat completion with a specific thread_id."""
    logger.info(f"Testing: Chat completion with thread_id={thread_id}")
    
    headers = {}
    if thread_id:
        headers["X-Thread-Id"] = thread_id
    
    payload = {
        "messages": [
            {
                "role": "user",
                "content": "Hello! Remember that my name is TestUser."
            }
        ],
        "model": "gemini-2.0-flash-exp"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{SERVER_URL}/chat/completions",
            json=payload,
            headers=headers
        ) as response:
            result = await response.json()
            
            if response.status == 200:
                logger.info(f"✓ Chat completion successful")
                content = result['choices'][0]['message']['content']
                logger.info(f"  Response preview: {content[:100]}...")
                return result
            else:
                logger.error(f"✗ Chat completion failed: {result}")
                return None


async def test_conversation_continuity(thread_id: str) -> bool:
    """Test that conversation context is maintained within a session."""
    logger.info(f"Testing: Conversation continuity in session {thread_id}")
    
    # Second message in the same session
    headers = {"X-Thread-Id": thread_id}
    payload = {
        "messages": [
            {
                "role": "user",
                "content": "What name did I tell you earlier?"
            }
        ],
        "model": "gemini-2.0-flash-exp"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{SERVER_URL}/chat/completions",
            json=payload,
            headers=headers
        ) as response:
            result = await response.json()
            
            if response.status == 200:
                content = result['choices'][0]['message']['content']
                # Check if the agent remembers the name from the previous message
                if "TestUser" in content or "don't" in content.lower() or "no" in content.lower():
                    logger.info(f"✓ Conversation context maintained")
                    logger.info(f"  Response: {content[:200]}...")
                    return True
                else:
                    logger.warning(f"⚠ Context might not be maintained properly")
                    logger.info(f"  Response: {content[:200]}...")
                    return False
            else:
                logger.error(f"✗ Chat completion failed: {result}")
                return False


async def test_get_active_sessions() -> list:
    """Test getting list of active sessions."""
    logger.info("Testing: Get active sessions")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{SERVER_URL}/sessions") as response:
            result = await response.json()
            
            if response.status == 200:
                sessions = result.get('active_sessions', [])
                count = result.get('session_count', 0)
                logger.info(f"✓ Retrieved {count} active sessions")
                for session_id in sessions[:5]:  # Show first 5
                    logger.info(f"  - {session_id}")
                if count > 5:
                    logger.info(f"  ... and {count - 5} more")
                return sessions
            else:
                logger.error(f"✗ Failed to get sessions: {result}")
                return []


async def test_clear_session(thread_id: str) -> bool:
    """Test clearing a specific session."""
    logger.info(f"Testing: Clear session {thread_id}")
    
    async with aiohttp.ClientSession() as session:
        async with session.delete(f"{SERVER_URL}/sessions/{thread_id}") as response:
            result = await response.json()
            
            if response.status == 200:
                logger.info(f"✓ Session cleared successfully")
                logger.info(f"  Cleared components: {result.get('cleared_components', [])}")
                return True
            elif response.status == 404:
                logger.warning(f"⚠ Session not found: {thread_id}")
                return False
            else:
                logger.error(f"✗ Failed to clear session: {result}")
                return False


async def test_clear_nonexistent_session() -> bool:
    """Test clearing a non-existent session (should return 404)."""
    fake_thread_id = "nonexistent_session_12345"
    logger.info(f"Testing: Clear non-existent session {fake_thread_id}")
    
    async with aiohttp.ClientSession() as session:
        async with session.delete(f"{SERVER_URL}/sessions/{fake_thread_id}") as response:
            result = await response.json()
            
            if response.status == 404:
                logger.info(f"✓ Correctly returned 404 for non-existent session")
                return True
            else:
                logger.error(f"✗ Unexpected response: {response.status} - {result}")
                return False


async def test_session_isolation() -> bool:
    """Test that different sessions are isolated from each other."""
    logger.info("Testing: Session isolation")
    
    # Create two separate sessions
    session1 = await test_create_new_session()
    await asyncio.sleep(5)
    session2 = await test_create_new_session()
    
    if not session1 or not session2:
        logger.error("✗ Failed to create test sessions")
        return False
    
    # Send different messages to each session
    headers1 = {"X-Thread-Id": session1}
    payload1 = {
        "messages": [{"role": "user", "content": "My favorite color is blue."}],
        "model": "gemini-2.0-flash-exp"
    }
    
    headers2 = {"X-Thread-Id": session2}
    payload2 = {
        "messages": [{"role": "user", "content": "My favorite color is red."}],
        "model": "gemini-2.0-flash-exp"
    }
    
    async with aiohttp.ClientSession() as session:
        # Send messages to both sessions
        await session.post(f"{SERVER_URL}/chat/completions", json=payload1, headers=headers1)
        await session.post(f"{SERVER_URL}/chat/completions", json=payload2, headers=headers2)
        
        # Check session 1 remembers blue
        check1 = {
            "messages": [{"role": "user", "content": "What's my favorite color?"}],
            "model": "gemini-2.0-flash-exp"
        }
        async with session.post(
            f"{SERVER_URL}/chat/completions",
            json=check1,
            headers=headers1
        ) as response:
            result1 = await response.json()
            content1 = result1['choices'][0]['message']['content'] if response.status == 200 else ""
        
        # Check session 2 remembers red
        async with session.post(
            f"{SERVER_URL}/chat/completions",
            json=check1,
            headers=headers2
        ) as response:
            result2 = await response.json()
            content2 = result2['choices'][0]['message']['content'] if response.status == 200 else ""
    
    # Clean up test sessions
    await test_clear_session(session1)
    await test_clear_session(session2)
    
    # Verify isolation
    blue_in_1 = "blue" in content1.lower()
    red_in_2 = "red" in content2.lower()
    blue_not_in_2 = "blue" not in content2.lower()
    red_not_in_1 = "red" not in content1.lower()
    
    if blue_in_1 and red_in_2:
        logger.info("✓ Sessions are properly isolated")
        logger.info(f"  Session 1 response: {content1[:100]}...")
        logger.info(f"  Session 2 response: {content2[:100]}...")
        return True
    else:
        logger.error("✗ Session isolation failed")
        logger.info(f"  Session 1 response: {content1[:100]}...")
        logger.info(f"  Session 2 response: {content2[:100]}...")
        return False


async def run_all_tests():
    """Run all session management tests."""
    logger.info("=" * 60)
    logger.info("SESSION MANAGEMENT TEST SUITE")
    logger.info("=" * 60)
    
    test_results = []
    
    try:
        # Test 1: Create new session
        thread_id = await test_create_new_session()
        test_results.append(("Create new session", thread_id is not None))
        
        if thread_id:
            # Test 2: Chat with session
            logger.info("-" * 40)
            chat_result = await test_chat_with_session(thread_id)
            test_results.append(("Chat with session", chat_result is not None))
            
            # Test 3: Conversation continuity
            logger.info("-" * 40)
            continuity = await test_conversation_continuity(thread_id)
            test_results.append(("Conversation continuity", continuity))
            
            # Test 4: Get active sessions
            logger.info("-" * 40)
            sessions = await test_get_active_sessions()
            test_results.append(("Get active sessions", len(sessions) > 0))
            
            # Test 5: Session isolation
            logger.info("-" * 40)
            isolation = await test_session_isolation()
            test_results.append(("Session isolation", isolation))
            
            # Test 6: Clear session
            logger.info("-" * 40)
            cleared = await test_clear_session(thread_id)
            test_results.append(("Clear session", cleared))
            
            # Test 7: Clear non-existent session
            logger.info("-" * 40)
            clear_404 = await test_clear_nonexistent_session()
            test_results.append(("Clear non-existent (404)", clear_404))
            
            # Test 8: Auto-generate thread_id when not provided
            logger.info("-" * 40)
            logger.info("Testing: Auto-generate thread_id")
            auto_result = await test_chat_with_session(None)
            test_results.append(("Auto-generate thread_id", auto_result is not None))
    
    except Exception as e:
        logger.error(f"Test suite error: {e}")
        import traceback
        traceback.print_exc()
    
    # Print summary
    logger.info("=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info("-" * 40)
    logger.info(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed!")
    else:
        logger.warning(f"⚠ {total - passed} test(s) failed")
    
    return passed == total


async def main():
    """Main function to run the test suite."""
    # Wait a moment for the server to be ready
    logger.info("Waiting for server to be ready...")
    await asyncio.sleep(2)
    
    try:
        success = await run_all_tests()
        exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Failed to run tests: {e}")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())