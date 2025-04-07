import google.generativeai as genai
import config
import logging
import json
from PIL import Image
import os # Import os for checking image existence

logger = logging.getLogger(__name__)

if not config.GOOGLE_API_KEY:
    logger.warning("GOOGLE_API_KEY not found in config/environment. LLM calls will fail.")
else:
    genai.configure(api_key=config.GOOGLE_API_KEY)

def format_prompt(task_description, omni_elements, action_history):
    """Formats the prompt for the LLM, including action history."""

    # Describe the screen elements clearly
    screen_description = "Current screen elements:\n"
    if not omni_elements:
         screen_description += "(No elements detected or Omniparser failed)\n"
    else:
        for elem in omni_elements:
            screen_description += (
                f"- Element {elem['index']} "
                f"({elem.get('type', 'unknown')}): "
                f"Content='{str(elem.get('content', 'N/A'))[:50].strip()}...' " # Ensure content is string, limit length
                f"BBox={elem.get('bbox', 'N/A')} "
                f"Interactive={elem.get('interactivity', False)}\n"
            )

    # Describe recent history
    history_description = "Recent Action History (Oldest to Newest):\n"
    if not action_history:
        history_description += "(No actions taken yet)\n"
    else:
        # Take only the last N actions as defined in config
        relevant_history = action_history[-config.ACTION_HISTORY_LENGTH:]
        for i, entry in enumerate(relevant_history):
             history_description += f"{i+1}. Action: {entry['summary']}\n   Reasoning: {entry['reasoning']}\n"


    prompt = f"""
You are an expert mobile automation agent. Your goal is to perform the following task on an Android device:
TASK: "{task_description}"

Based on the current screen elements AND the recent action history provided below, decide the *single best next action* to progress towards the task. Consider the history to avoid loops and redundant actions.

{history_description}
{screen_description}

Available Actions:
1. TAP: Tap an interactive element. Requires 'element_index'.
2. INPUT_TEXT: Type text. Requires 'text'. Optionally specify 'element_index' to tap first (e.g., for text fields). If no index is specified, it assumes the field is already focused.
3. SCROLL_DOWN: Scroll the screen down (equivalent to a swipe up). Useful if needed element is likely below.
4. SCROLL_UP: Scroll the screen up (equivalent to a swipe down). Useful if needed element is likely above.
5. SWIPE: Perform a custom swipe. Requires normalized start/end coordinates 'start_x', 'start_y', 'end_x', 'end_y' (0.0 to 1.0) and 'duration' (milliseconds). Use sparingly.
6. WAIT: Wait for a short period (e.g., for content to load). Requires 'duration_seconds'.
7. DONE: Use this action ONLY when the TASK is fully completed according to the initial request.

Constraints:
- Choose only ONE action.
- Provide a brief 'reasoning' explaining *why* you chose this action based on the task, current screen, and history.
- Prioritize interactive elements (interactivity=True) for TAPs.
- Ensure the chosen element is relevant to the task.
- If you need to type text, first TAP the input field (if not focused), then use INPUT_TEXT. This might take two steps.
- If the screen seems unchanged after an action, consider scrolling or waiting. If stuck, consider if the task is achievable or if you should use DONE (if impossible).

Output Format:
Return ONLY a valid JSON object containing the 'action' object and a 'reasoning' string. Do not include any other text, explanations, or markdown formatting.

Example:
{{
  "action": {{ "action": "TAP", "element_index": 15 }},
  "reasoning": "Tapping element 15 'Settings icon' to navigate to the settings page as requested by the task."
}}
{{
  "action": {{ "action": "INPUT_TEXT", "element_index": 24, "text": "search query" }},
  "reasoning": "Tapped search bar (element 24) in previous step, now inputting the required search query."
}}
{{
  "action": {{ "action": "SCROLL_DOWN" }},
  "reasoning": "The target element 'Submit button' is not visible on the current screen, scrolling down to find it."
}}
{{
  "action": {{ "action": "DONE" }},
  "reasoning": "The confirmation message 'Email Sent' is visible, indicating the task is complete."
}}

Choose the next action and provide your reasoning:
"""
    return prompt

def get_llm_action(task_description, omni_elements, action_history, screenshot_path, annotated_screenshot_path=None):
    """
    Gets the next action recommendation from the Gemini LLM, considering history.

    Args:
        task_description (str): The user's high-level task.
        omni_elements (list): Parsed elements from Omniparser.
        action_history (list): List of recent action summaries and reasonings.
        screenshot_path (str): Path to the original screenshot image.
        annotated_screenshot_path (str, optional): Path to the annotated screenshot. Defaults to None.


    Returns:
        tuple: (action_json, reasoning_str) or (None, None) if failed.
               action_json (dict): The parsed JSON action object (e.g., {"action": "TAP", "element_index": 10}).
               reasoning_str (str): The reasoning provided by the LLM.
    """
    if not config.GOOGLE_API_KEY:
        logger.error("Cannot call LLM: GOOGLE_API_KEY not configured.")
        return None, None
    # Allow calling LLM even if omni_elements is empty, it might decide to scroll/wait/give up.
    # if not omni_elements:
    #     logger.error("Cannot call LLM: No Omniparser elements provided.")
    #     return None, None

    prompt = format_prompt(task_description, omni_elements, action_history)
    logger.info("--- Sending Request to LLM ---")
    logger.debug(f"LLM Prompt (excluding images):\n{prompt[:1000]}...") # Log truncated prompt

    try:
        # Prepare image inputs
        model_inputs = [prompt]
        valid_images_sent = []
        if os.path.exists(screenshot_path):
             img_orig = Image.open(screenshot_path)
             model_inputs.append(img_orig)
             valid_images_sent.append("original screenshot")
        else:
             logger.warning(f"Original screenshot not found at: {screenshot_path}")

        # Add annotated image if path exists and is valid
        if annotated_screenshot_path and os.path.exists(annotated_screenshot_path):
             try:
                 img_annotated = Image.open(annotated_screenshot_path)
                 model_inputs.append(img_annotated)
                 valid_images_sent.append("annotated screenshot")
             except Exception as img_err:
                 logger.warning(f"Could not open or process annotated screenshot {annotated_screenshot_path}: {img_err}")
        elif annotated_screenshot_path:
             logger.warning(f"Annotated screenshot path provided but not found: {annotated_screenshot_path}")

        if not valid_images_sent:
             logger.error("No valid images could be found or opened to send to the LLM.")
             return None, None

        logger.info(f"Sending {len(valid_images_sent)} image(s) to LLM: {', '.join(valid_images_sent)}")

        model = genai.GenerativeModel(config.GEMINI_MODEL_NAME)
        response = model.generate_content(model_inputs)

        # Attempt to extract and parse the JSON response
        raw_response_text = response.text.strip()
        logger.debug(f"LLM Raw Response:\n{raw_response_text}")

        # Clean potential markdown code block fences
        if raw_response_text.startswith("```json"):
            raw_response_text = raw_response_text[7:]
        if raw_response_text.endswith("```"):
            raw_response_text = raw_response_text[:-3]
        raw_response_text = raw_response_text.strip()

        full_response_json = json.loads(raw_response_text)

        # Extract action and reasoning
        action_json = full_response_json.get("action")
        reasoning_str = full_response_json.get("reasoning", "[No reasoning provided]") # Provide default

        if not isinstance(action_json, dict) or not action_json.get("action"):
            logger.error(f"LLM response missing valid 'action' object within the JSON. Response: {full_response_json}")
            return None, None

        logger.info(f"LLM suggested action: {action_json}")
        logger.info(f"LLM reasoning: {reasoning_str}")
        return action_json, reasoning_str

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response from LLM: {e}\nRaw response: {raw_response_text}")
        return None, None
    except Exception as e:
        # Catch more specific errors from google.generativeai if needed, e.g., permission denied, quota exceeded
        logger.error(f"Error interacting with Gemini API: {e}", exc_info=True)
        return None, None