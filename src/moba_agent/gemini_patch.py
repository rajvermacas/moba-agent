"""
Patch for langchain-google-genai finish_reason enum issue.
This module provides a workaround for the AttributeError that occurs when
Google's API returns unrecognized enum values (like 12) for finish_reason.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def apply_gemini_patch():
    """
    Apply a monkey patch to handle unrecognized finish_reason enum values
    in langchain_google_genai responses.
    """
    try:
        # Import the module we need to patch
        import langchain_google_genai.chat_models as chat_models
        
        # Store the original function
        original_response_to_result = chat_models._response_to_result
        
        def patched_response_to_result(response: Any) -> Dict[str, Any]:
            """
            Patched version of _response_to_result that handles enum errors gracefully.
            """
            try:
                # Try the original function first
                return original_response_to_result(response)
            except AttributeError as e:
                if "finish_reason" in str(e) and "'int' object has no attribute 'name'" in str(e):
                    # Log the issue
                    logger.warning(f"Encountered unrecognized finish_reason enum value. Applying workaround.")
                    
                    # Create a modified response handler
                    result = {
                        "generations": []
                    }
                    
                    for candidate in response.candidates:
                        generation_info = {}
                        
                        # Handle finish_reason safely
                        if hasattr(candidate, 'finish_reason'):
                            try:
                                # Try to get the name attribute
                                if hasattr(candidate.finish_reason, 'name'):
                                    generation_info["finish_reason"] = candidate.finish_reason.name
                                else:
                                    # If it's an int, convert to string
                                    generation_info["finish_reason"] = str(candidate.finish_reason)
                                    logger.debug(f"Converted integer finish_reason to string: {candidate.finish_reason}")
                            except Exception as inner_e:
                                # Fallback to string representation
                                generation_info["finish_reason"] = "UNKNOWN"
                                logger.debug(f"Failed to process finish_reason: {inner_e}")
                        
                        # Handle safety ratings
                        if hasattr(candidate, 'safety_ratings'):
                            generation_info["safety_ratings"] = [
                                {
                                    "category": rating.category.name if hasattr(rating.category, 'name') else str(rating.category),
                                    "probability": rating.probability.name if hasattr(rating.probability, 'name') else str(rating.probability),
                                    "blocked": rating.blocked if hasattr(rating, 'blocked') else False
                                }
                                for rating in candidate.safety_ratings
                            ]
                        
                        # Get the content and tool calls
                        content = ""
                        tool_calls = []
                        
                        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                            for part in candidate.content.parts:
                                if hasattr(part, 'text'):
                                    content += part.text
                                elif hasattr(part, 'function_call'):
                                    # Extract tool call information
                                    func_call = part.function_call
                                    tool_call = {
                                        "name": func_call.name,
                                        "args": dict(func_call.args) if hasattr(func_call, 'args') else {},
                                        "id": f"call_{func_call.name}_{id(func_call)}"
                                    }
                                    tool_calls.append(tool_call)
                        
                        from langchain_core.messages import AIMessage
                        from langchain_core.outputs import ChatGeneration
                        
                        # Create AIMessage with tool calls if present
                        ai_message = AIMessage(content=content)
                        if tool_calls:
                            ai_message.tool_calls = tool_calls
                        
                        result["generations"].append(
                            ChatGeneration(
                                message=ai_message,
                                generation_info=generation_info
                            )
                        )
                    
                    from langchain_core.outputs import ChatResult
                    return ChatResult(**result)
                else:
                    # Re-raise if it's a different AttributeError
                    raise
        
        # Apply the patch
        chat_models._response_to_result = patched_response_to_result
        logger.info("Successfully applied Gemini finish_reason patch")
        return True
        
    except ImportError as e:
        logger.error(f"Failed to import langchain_google_genai: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to apply Gemini patch: {e}")
        return False