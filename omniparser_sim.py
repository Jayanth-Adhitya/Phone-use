import logging
import re
import ast
import config
from gradio_client import Client, handle_file
# Removed the problematic import: from gradio_client.utils import BadStatusCodeError

logger = logging.getLogger(__name__)

# Keep this function to parse the string output from the real API
def parse_omniparser_output_string(output_string):
    """Parses the structured string output from Omniparser into a list of dicts."""
    elements = []
    pattern = re.compile(r"icon\s+(\d+):\s+({.*?})$", re.MULTILINE)
    if not output_string: # Handle empty string case
        logger.warning("Received empty string from Omniparser.")
        return []
    matches = pattern.findall(output_string.strip())

    for index_str, dict_str in matches:
        try:
            index = int(index_str)
            element_data = ast.literal_eval(dict_str)
            element_data['index'] = index
            elements.append(element_data)
        except (ValueError, SyntaxError) as e:
            logger.warning(f"Could not parse line: icon {index_str}: {dict_str}. Error: {e}")
            continue
    elements.sort(key=lambda x: x['index'])
    return elements


def call_omniparser_v2(image_path):
    """
    Calls the locally running Omniparser v2 service via Gradio Client.

    Args:
        image_path (str): Path to the input screenshot.

    Returns:
        tuple: (parsed_elements, annotated_image_path)
               parsed_elements (list): List of dictionaries, each representing a UI element.
               annotated_image_path (str): Path to the annotated image returned by the service.
               Returns (None, None) if the call fails or parsing fails.
    """
    if config.USE_OMNIPARSER_SIMULATION:
        # --- Simulation Path (kept for fallback/testing if needed) ---
        logger.info("--- Using SIMULATED Omniparser v2 ---")
        try:
            parsed_elements = parse_omniparser_output_string(config.SIMULATED_OMNIPARSER_OUTPUT)
            if not parsed_elements:
                logger.error("Failed to parse simulated Omniparser output.")
                return None, None
            logger.warning("Simulation active: No real annotated image generated.")
            return parsed_elements, None
        except Exception as e:
            logger.error(f"Error during Omniparser simulation: {e}", exc_info=True)
            return None, None
    else:
        # --- Real API Call Path ---
        logger.info(f"--- Calling REAL Omniparser service at {config.OMNIPARSER_URL} ---")
        try:
            client = Client(config.OMNIPARSER_URL)
            logger.debug(f"Sending image {image_path} to Omniparser /process API")
            result = client.predict(
                image_input=handle_file(image_path),
                box_threshold=config.OMNIPARSER_BOX_THRESHOLD,
                iou_threshold=config.OMNIPARSER_IOU_THRESHOLD,
                use_paddleocr=config.OMNIPARSER_USE_PADDLEOCR,
                imgsz=config.OMNIPARSER_IMGSZ,
                api_name="/process"
            )
            logger.debug("Received result from Omniparser.")

            # --- Process the result tuple ---
            if not isinstance(result, tuple) or len(result) != 2:
                logger.error(f"Unexpected result format from Omniparser API: {type(result)}")
                return None, None

            # Extract annotated image path
            annotated_image_dict = result[0]
            if not isinstance(annotated_image_dict, dict) or 'path' not in annotated_image_dict:
                 logger.warning(f"Could not find 'path' in annotated image result: {annotated_image_dict}. Proceeding without annotated image.")
                 annotated_image_path = None
            else:
                 annotated_image_path = annotated_image_dict['path']
                 logger.info(f"Omniparser returned annotated image path: {annotated_image_path}")

            # Extract and parse the elements string
            parsed_elements_string = result[1]
            if not isinstance(parsed_elements_string, str):
                 logger.error(f"Expected string for parsed elements, got {type(parsed_elements_string)}")
                 return None, annotated_image_path # Return image path even if text parsing fails

            parsed_elements = parse_omniparser_output_string(parsed_elements_string)

            if parsed_elements is None:
                 logger.error("Failed to parse the string output from Omniparser API.")
                 return None, annotated_image_path
            elif not parsed_elements:
                 logger.warning("Omniparser returned elements string, but parsing resulted in an empty list.")

            logger.info(f"Successfully parsed {len(parsed_elements)} elements from Omniparser.")
            return parsed_elements, annotated_image_path

        except FileNotFoundError:
            logger.error(f"Input image file not found: {image_path}")
            return None, None
        # Catch generic Exception during API call and log it
        except Exception as e:
            logger.error(f"Error during Omniparser API call or processing: {e}", exc_info=True)
            # You can add more specific checks here if needed based on observed errors
            # For example: if "connection error" in str(e).lower(): ...
            return None, None