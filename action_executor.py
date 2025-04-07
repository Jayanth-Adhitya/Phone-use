import logging
import time
import config

logger = logging.getLogger(__name__)

def summarize_action(action_data, omni_elements):
    """Creates a concise summary string for an action, useful for history."""
    action_type = action_data.get("action")
    summary = f"Action: {action_type}"
    try:
        if action_type == "TAP":
            idx = action_data.get("element_index")
            target_element = next((e for e in (omni_elements or []) if e.get('index') == idx), None)
            content = f"'{str(target_element.get('content', 'N/A'))[:20].strip()}'" if target_element else "'Element not found'"
            summary += f" (Index: {idx}, Content: {content})"
        elif action_type == "INPUT_TEXT":
            text = action_data.get("text", "")
            idx = action_data.get("element_index")
            summary += f" (Text: '{text[:20]}...', Index: {idx if idx is not None else 'N/A'})"
        elif action_type == "SWIPE":
            summary += f" (From: ({action_data.get('start_x')},{action_data.get('start_y')}) To: ({action_data.get('end_x')},{action_data.get('end_y')}))"
        elif action_type == "WAIT":
             summary += f" ({action_data.get('duration_seconds')}s)"
        # SCROLL_UP, SCROLL_DOWN, DONE have simple summaries already
    except Exception as e:
         logger.warning(f"Error summarizing action {action_data}: {e}")
         summary = str(action_data) # Fallback to raw string if summarization fails
    return summary


def execute_action(action_data, adb_controller, screen_dimensions, omni_elements):
    """
    Executes the action suggested by the LLM using the ADB controller.
    (Function body remains largely the same as before - no major changes needed here
     except maybe adding slightly more detailed logging if desired)

    Returns:
        bool: True if the action indicates the process should continue, False if DONE or critical error.
    """
    action_type = action_data.get("action")
    if not action_type:
        logger.error("Invalid action data: 'action' key missing.")
        return False # Stop if action is invalid

    # --- Check for element existence BEFORE execution for TAP/INPUT_TEXT ---
    element_index = action_data.get("element_index")
    if action_type in ["TAP", "INPUT_TEXT"] and element_index is not None:
         target_element = next((e for e in (omni_elements or []) if e.get('index') == element_index), None)
         if not target_element:
              logger.error(f"{action_type} failed: Element with index {element_index} not found in current screen analysis.")
              # Decide whether to stop or continue. Let's continue but log the error.
              # The LLM should ideally notice the element isn't there in the next step.
              return True # Continue, allow LLM to re-evaluate

    width, height = screen_dimensions
    success = False

    try:
        if action_type == "TAP":
            # Element check already done above
            idx = action_data.get("element_index") # Already checked it exists
            target_element = next((e for e in (omni_elements or []) if e.get('index') == idx), None) # Find it again
            # We proceed even if element is None here because we checked above,
            # but defensive coding is good. If it's None now something is wrong.
            if not target_element:
                 logger.error(f"INTERNAL ERROR: Element {idx} disappeared between check and execution.")
                 return True # Continue but log

            bbox = target_element.get('bbox')
            if not bbox or len(bbox) != 4:
                logger.error(f"TAP failed: Bounding box missing or invalid for element {idx}.")
                return True # Continue

            center_x_rel = (bbox[0] + bbox[2]) / 2
            center_y_rel = (bbox[1] + bbox[3]) / 2
            tap_x = int(center_x_rel * width)
            tap_y = int(center_y_rel * height)

            logger.info(f"Executing TAP on element {idx} ('{str(target_element.get('content', 'N/A'))[:20].strip()}' at ({tap_x}, {tap_y})")
            success = adb_controller.tap(tap_x, tap_y)

        elif action_type == "INPUT_TEXT":
            text_to_input = action_data.get("text")
            # Element check (for tapping) already done above
            idx = action_data.get("element_index")

            if text_to_input is None:
                 logger.error("INPUT_TEXT action requires 'text'.")
                 return True # Continue

            if idx is not None:
                # Tap the element first to ensure focus
                logger.info(f"INPUT_TEXT: Tapping element {idx} first.")
                # Re-find element for tap coords
                target_element = next((e for e in (omni_elements or []) if e.get('index') == idx), None)
                if not target_element:
                     logger.error(f"INPUT_TEXT failed: Element {idx} not found for pre-tap.")
                     return True # Continue
                bbox = target_element.get('bbox')
                if not bbox or len(bbox) != 4:
                     logger.error(f"INPUT_TEXT failed: BBox missing for pre-tap element {idx}.")
                     return True # Continue

                center_x_rel = (bbox[0] + bbox[2]) / 2
                center_y_rel = (bbox[1] + bbox[3]) / 2
                tap_x = int(center_x_rel * width)
                tap_y = int(center_y_rel * height)
                tap_success = adb_controller.tap(tap_x, tap_y)
                if not tap_success:
                     logger.error("INPUT_TEXT failed: Could not tap target element first.")
                     return True # Continue
                time.sleep(0.5) # Short pause after tap before typing

            logger.info(f"Executing INPUT_TEXT: '{text_to_input}'")
            success = adb_controller.input_text(text_to_input)


        elif action_type == "SCROLL_DOWN":
            start_x = width // 2
            start_y = int(height * 0.8)
            end_y = int(height * 0.2)
            logger.info("Executing SCROLL_DOWN (Swipe Up)")
            success = adb_controller.swipe(start_x, start_y, start_x, end_y, duration_ms=400)

        elif action_type == "SCROLL_UP":
            start_x = width // 2
            start_y = int(height * 0.2)
            end_y = int(height * 0.8)
            logger.info("Executing SCROLL_UP (Swipe Down)")
            success = adb_controller.swipe(start_x, start_y, start_x, end_y, duration_ms=400)

        elif action_type == "SWIPE":
            sx_rel = action_data.get("start_x")
            sy_rel = action_data.get("start_y")
            ex_rel = action_data.get("end_x")
            ey_rel = action_data.get("end_y")
            duration = action_data.get("duration", 300)

            if None in [sx_rel, sy_rel, ex_rel, ey_rel]:
                logger.error("SWIPE action requires 'start_x', 'start_y', 'end_x', 'end_y'.")
                return True # Continue

            sx = int(sx_rel * width)
            sy = int(sy_rel * height)
            ex = int(ex_rel * width)
            ey = int(ey_rel * height)
            logger.info(f"Executing custom SWIPE from ({sx}, {sy}) to ({ex}, {ey})")
            success = adb_controller.swipe(sx, sy, ex, ey, duration_ms=duration)

        elif action_type == "WAIT":
            duration = action_data.get("duration_seconds", config.DEFAULT_WAIT_TIME)
            logger.info(f"Executing WAIT for {duration} seconds")
            adb_controller.wait(duration)
            success = True

        elif action_type == "DONE":
            logger.info("Executing DONE: Task marked as completed by LLM.")
            return False # Signal to stop the main loop

        else:
            logger.warning(f"Unknown action type received: '{action_type}'")
            return True # Continue

        # Optional: Add a default wait after most actions
        if success and action_type not in ["WAIT", "DONE"]:
             # Check if screen changed significantly? Hard to do reliably.
             # Default wait is often helpful regardless.
             adb_controller.wait(config.DEFAULT_WAIT_TIME)

        if not success:
             logger.error(f"Execution failed for action: {action_data}")
             # Still continue, let LLM see the state after failure in the next step
             return True

        return True # Continue to next step

    except Exception as e:
        logger.error(f"Unhandled exception during action execution {action_data}: {e}", exc_info=True)
        return True # Attempt to continue