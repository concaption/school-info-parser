#!/usr/bin/env python

import os
import base64
import json
import time
import fitz  # PyMuPDF
from openai import OpenAI
from dotenv import load_dotenv
import io
from PIL import Image
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import logging
from logging.handlers import RotatingFileHandler
import sys
import traceback
from logger import setup_logging

# Initialize logger
logger = setup_logging()

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("OpenAI API key not found in environment variables")
    raise ValueError("OpenAI API key not found")


class Price(BaseModel):
    duration: str = Field(..., description="Duration of the course")
    price: str = Field(..., description="Price of the course")
    currency: str = Field(..., description="Currency of the price")

class Course(BaseModel):
    name: str = Field(..., description="Name of the course")
    lessons_per_week: int = Field(..., description="Number of lessons per week")
    description: str = Field(..., description="Course description")
    prices: List[Price] = Field(..., description="List of prices for the course")
    requirements: Optional[str] = Field(None, description="Course requirements")

class Accommodation(BaseModel):
    type: str = Field(..., description="Type of accommodation")
    price_per_week: str = Field(..., description="Weekly price of accommodation")
    description: str = Field(..., description="Accommodation description")
    supplements: Optional[Dict[str, str]] = Field(default_factory=dict, description="Additional supplements")

class Location(BaseModel):
    city: str = Field(..., description="City where the school is located in English")
    country: str = Field(..., description="Country where the school is located in ISO 3166-1 alpha-2 format")
    address: str = Field(..., description="Address of the school")
    courses: List[Course] = Field(..., description="List of available courses")
    accommodations: List[Accommodation] = Field(..., description="List of accommodations")
    additional_fees: Optional[Dict[str, str]] = Field(default_factory=dict, description="Additional fees")

class School(BaseModel):
    name: str = Field(..., description="Name of the school")
    locations: List[Location] = Field(..., description="List of locations where the school operates")
    terms: Optional[Dict[str, str]] = Field(default_factory=dict, description="Terms and conditions")
    repeat: Optional[bool] = Field(description="If there are more courses available but can not fit in one response, set this flag to true")

class PDFParser:
    def __init__(self, api_key):
        logger.info("Initializing PDFParser")

        self.client = OpenAI(api_key=api_key)
        self.system_prompt = """Please analyze this image and extract the language school information. Focus on identifying:
- School name
- Location details
- Course information
- Pricing
- Accommodation options
- Any terms or conditions

if there are more than one location, please provide information for all locations.
if there are more than one course, please provide information for all courses.
make sure to include all the courses available, including the prices and any additional fees.

if there are more courses available but can not fit in one response, please set the repeat flag to true and provide the remaining courses in the next response.

Format the response as valid JSON with this structure:
{
    "school_name": "Centre of English Studies",
    "locations": [
        {
            "city": "Dublin",
            "country": "IE",
            "address": "...",
            "courses": [
                {
                    "name": "Standard General English",
                    "lessons_per_week": 20,
                    "description": "Morning classes Mon-Fri",
                    "prices": [
                        {"duration": "2-4 weeks", "price": "€355", "currency": "EUR"}
                    ]
                }
            ],
            "accommodations": [
                {
                    "type": "Homestay",
                    "price_per_week": "€280",
                    "description": "Single room, half board",
                    "supplements": {
                        "Summer": "€35/week"
                    }
                }
            ],
            "additional_fees": {
                "registration": "€85"
            }
        }
    ],
    "terms": {
        "cancellation": "14 days notice required"
    }
}

"""

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
        self.results = []
    
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
                        self.results.append(page_data)
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
            # return self.merge_results()

            return self.results
            
        except Exception as e:
            logger.error(f"Error in process_pdf: {str(e)}")
            raise

# Usage Example
if __name__ == "__main__":
    try:
        logger.info("Starting PDF processing")
        processor = PDFProcessor(api_key=OPENAI_API_KEY)
        file_path = "data/input_files/2025_CES_Adult_Price_List_as_at_8th_August.pdf"
        result = processor.process_pdf(file_path)
        
        output_file =  f"data/output_files/{os.path.basename(file_path).replace('.pdf', '_output.json')}"
        output_data = {}
        output_data["parsed_results"] = result
        logger.info(f"Writing results to {output_file}")
        with open(output_file, "w") as f:
            json.dump(output_data, f, indent=2)
        
        logger.info("Processing complete. Results saved to output.json")
        
    except Exception as e:
        logger.error(f"Main process failed: {str(e)}")
        raise