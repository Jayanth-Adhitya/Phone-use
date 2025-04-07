import os
import logging
import time
from adb_controller import ADBController
from omniparser_sim import call_omniparser_v2
from llm_handler import get_llm_action # Keep this import
from action_executor import execute_action, summarize_action # Import summarize_action
import config

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("agent_log.log", mode='w'), # Overwrite log each run
        logging.StreamHandler()
    ])
logger = logging.getLogger(__name__)

def main():
    logger.info("--- Mobile Automation Agent Starting ---")

    # --- Initial Setup ---
    if not config.GOOGLE_API_KEY:
        logger.critical("GOOGLE_API_KEY is not set. Please set it in .env or environment variables.")
        return

    os.makedirs(config.SCREENSHOT_DIR, exist_ok=True)
    screenshot_path = os.path.join(config.SCREENSHOT_DIR, config.SCREENSHOT_FILENAME)
    # Keep track of the path to the *last* annotated screenshot
    last_annotated_screenshot_path = None

    try:
        adb = ADBController(host=config.ADB_HOST, port=config.ADB_PORT)
        screen_dims = adb.get_screen_dimensions()
        if not screen_dims:
            logger.critical("Could not get screen dimensions. Exiting.")
            return
    except Exception as e:
        logger.critical(f"Failed to initialize ADB connection: {e}. Exiting.")
        return

    # --- Get Task ---
    task = input("Please enter the task for the agent: ")
    if not task:
        logger.warning("No task entered. Exiting.")
        return
    logger.info(f"Received Task: {task}")

    # --- Initialize State ---
    action_history = []
    last_action_summary = None # For basic loop detection

    # --- Automation Loop ---
    for step in range(config.MAX_STEPS):
        current_step = step + 1
        logger.info(f"--- Step {current_step} / {config.MAX_STEPS} ---")

        # 1. Take Screenshot
        logger.info("Taking screenshot...")
        if not adb.take_screenshot(screenshot_path):
            logger.error("Failed to take screenshot. Stopping agent.")
            break # Stop if screenshot fails, as we have no state

        # 2. Analyze Screenshot (Omniparser)
        logger.info("Analyzing screenshot with Omniparser...")
        omni_elements, annotated_img_path = call_omniparser_v2(screenshot_path)
        if omni_elements is None:
             logger.warning("Omniparser analysis failed or returned no elements. LLM will proceed without element details.")
             # Continue, maybe LLM decides to wait or scroll
        if annotated_img_path:
             logger.info(f"Using annotated screenshot: {annotated_img_path}")
             last_annotated_screenshot_path = annotated_img_path # Store path for LLM
        else:
             logger.warning("No annotated screenshot available from Omniparser.")
             last_annotated_screenshot_path = None # Ensure it's None if not available


        # 3. Get Action from LLM (passing history and annotated path)
        logger.info("Getting next action from LLM...")
        llm_action, llm_reasoning = get_llm_action(
            task,
            omni_elements,
            action_history, # Pass the history
            screenshot_path, # Pass original screenshot path
            last_annotated_screenshot_path # Pass annotated path
        )

        if llm_action is None:
            logger.error("Failed to get valid action/reasoning from LLM. Stopping agent.")
            break # Stop if LLM fails to respond meaningfully

        # --- Basic Loop Detection ---
        current_action_summary = summarize_action(llm_action, omni_elements)
        if current_action_summary == last_action_summary:
             logger.warning(f"Potential loop detected: LLM suggested the same action summary twice in a row: '{current_action_summary}'. Agent will proceed, but monitor closely.")
             # Consider forcing a different action (e.g., SCROLL) or stopping if this happens too often.
        last_action_summary = current_action_summary # Update for next iteration

        # 4. Execute Action
        logger.info(f"Executing action: {llm_action}")
        should_continue = execute_action(llm_action, adb, screen_dims, omni_elements)

        # 5. Update History (only if action was attempted)
        history_entry = {
            "step": current_step,
            "summary": current_action_summary, # Use the summarized action
            "reasoning": llm_reasoning,
            "action_data": llm_action # Store full action data for potential future use
        }
        action_history.append(history_entry)
        # Keep history length bounded
        action_history = action_history[-config.ACTION_HISTORY_LENGTH:]

        if not should_continue:
            logger.info("Action executor signaled to stop (DONE action or critical error during execution).")
            break

        # Prevent hammering the device/API too quickly
        # time.sleep(0.5) # Small delay between steps (optional)

    else: # Loop finished without break (max steps reached)
         logger.warning(f"Agent reached maximum steps ({config.MAX_STEPS}). Stopping.")

    logger.info("--- Mobile Automation Agent Finished ---")

if __name__ == "__main__":
    main()