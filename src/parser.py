"""
path: src/parser.py
author: concaption
description: This script contains the PDFParser and PDFProcessor classes that are used to extract information from PDF files using the OpenAI API.
"""

import os
import base64
import json
import time
import fitz  # PyMuPDF
from openai import OpenAI
from dotenv import load_dotenv
import io
from PIL import Image

from .schema import School
from .prompts import system_prompt
from .logger import setup_logging
from .utils import merge_schools

# Initialize logger
logger = setup_logging()

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("OpenAI API key not found in environment variables")
    raise ValueError("OpenAI API key not found")


class PDFParser:
    def __init__(self, api_key):
        logger.info("Initializing PDFParser")

        self.client = OpenAI(api_key=api_key)
        self.system_prompt = system_prompt

    def parse_page(self, pixmap, previous_output=[]):
        try:
            logger.debug("Converting PyMuPDF pixmap to PIL Image")
            img = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)

            logger.debug("Converting PIL Image to JPEG bytes")
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format="JPEG")
            img_byte_arr = img_byte_arr.getvalue()

            logger.debug("Encoding image to base64")
            base64_image = base64.b64encode(img_byte_arr).decode("utf-8")

            logger.info("Sending request to OpenAI API")
            prompt = self.system_prompt
            if previous_output is not None and len(previous_output) > 0:
                prompt += "\nPlease provide the remaining courses that were not included in the previous response. \n Previous response was: \n " + json.dumps(previous_output, indent=2)
            logger.debug(f"Prompt:\n {prompt}")

            # save the image to disk for debugging
            # generate a unique filename based on the current timestamp
            image_filename = f"logs/image_{int(time.time())}.jpg"
            with open(image_filename, "wb") as f:
                f.write(img_byte_arr)
            logger.debug(f"Saved image to {image_filename}")

            response = self.client.beta.chat.completions.parse(
                model="gpt-4o-2024-11-20",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
                max_completion_tokens=16383,
                response_format=School,
            )

            logger.debug("Received response from OpenAI API")

            # Log the raw response content for debugging
            logger.debug(
                f"Raw API response content: {response.choices[0].message.content}"
            )

            try:
                parsed_response = json.loads(response.choices[0].message.content)
                logger.info("Successfully parsed JSON response")
                return parsed_response
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Response content: {response.choices[0].message.content}")
                raise

        except Exception as e:
            logger.error(f"Error in parse_page: {str(e)}")
            raise


class PDFProcessor:
    def __init__(self, api_key):
        logger.info("Initializing PDFProcessor")
        self.parser = PDFParser(api_key)
        self.raw_results = []
        self.all_results = {}
        self.merged_results = {}
    
    def process_pdf(self, pdf_path):
        logger.info(f"Processing PDF: {pdf_path}")
        try:
            if not os.path.exists(pdf_path):
                logger.error(f"PDF file not found: {pdf_path}")
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
            pdf_document = fitz.open(pdf_path)
            logger.info(f"Opened PDF with {pdf_document.page_count} pages")
            
            for page_num in range(pdf_document.page_count):
                logger.info(f"Processing page {page_num + 1}/{pdf_document.page_count}")
                page = pdf_document[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                retry_count = 0
                max_retries = 3  # Set a maximum number of retries to prevent infinite loops
                previous_outputs = []
                
                while True:
                    try:
                        page_data = self.parser.parse_page(pix, previous_output=previous_outputs)
                        self.raw_results.append(page_data)
                        previous_outputs.append(page_data)
                        if page_data.get("repeat") and retry_count < max_retries:
                            logger.info("Repeat flag set. Processing the the page again")
                            retry_count += 1
                            logger.info(f"Repeat flag set. Processing page {page_num + 1} again (attempt {retry_count + 1})")
                            continue
                        else:
                            logger.info(f"Successfully processed page {page_num + 1}")
                            break
                    except Exception as e:
                        logger.error(f"Error processing page {page_num + 1}: {str(e)}")
                        logger.error("Retrying page processing")
                        retry_count += 1
                        if retry_count >= max_retries:
                            logger.error(f"Max retries reached for page {page_num + 1}. Skipping page")
                            break
            
            pdf_document.close()
            logger.info("PDF processing completed")
            self.all_results["raw_results"] = self.raw_results
            try:
                self.merged_results = merge_schools(self.raw_results)
                self.all_results["merged_results"] = self.merged_results
            except Exception as e:
                logger.error(f"Error merging schools: {str(e)}")
            return self.all_results
            
        except Exception as e:
            logger.error(f"Error in process_pdf: {str(e)}")
            raise