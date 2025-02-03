#!/usr/bin/env python

import os
import base64
import json
import fitz  # PyMuPDF
from openai import OpenAI
from dataclasses import dataclass, field
from typing import List, Dict
from dotenv import load_dotenv
import io
from PIL import Image
import logging
from logging.handlers import RotatingFileHandler
import sys
import traceback


# Set up logging
def setup_logging():
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)

    # Configure logging
    logger = logging.getLogger("PDFParser")
    logger.setLevel(logging.DEBUG)

    # File handler with rotation
    file_handler = RotatingFileHandler(
        "logs/pdf_parser.log", maxBytes=1024 * 1024, backupCount=5  # 1MB
    )
    file_handler.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # Create formatters and add it to the handlers
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_formatter = logging.Formatter("%(levelname)s: %(message)s")

    file_handler.setFormatter(file_formatter)
    console_handler.setFormatter(console_formatter)

    # Add the handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Initialize logger
logger = setup_logging()

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("OpenAI API key not found in environment variables")
    raise ValueError("OpenAI API key not found")


# Data Structure Classes
@dataclass
class Price:
    duration: str
    price: str
    currency: str


@dataclass
class Course:
    name: str
    lessons_per_week: int
    description: str
    prices: List[Price]
    requirements: str = ""


@dataclass
class Accommodation:
    type: str
    price_per_week: str
    description: str
    supplements: Dict[str, str] = field(default_factory=dict)


@dataclass
class Location:
    city: str
    country: str
    address: str
    courses: List[Course]
    accommodations: List[Accommodation]
    additional_fees: Dict[str, str] = field(default_factory=dict)


@dataclass
class School:
    name: str
    locations: List[Location]
    terms: Dict[str, str] = field(default_factory=dict)


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

Format the response as valid JSON with this structure:
{
    "school_name": "Centre of English Studies",
    "locations": [
        {
            "city": "Dublin",
            "country": "Ireland",
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
}"""

    def parse_page(self, pixmap):
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
            response = self.client.chat.completions.create(
                model="gpt-4o-2024-11-20",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.system_prompt},
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
                response_format={"type": "json_object"},
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
                
                try:
                    page_data = self.parser.parse_page(pix)
                    self.results.append(page_data)
                    logger.info(f"Successfully processed page {page_num + 1}")
                except Exception as e:
                    logger.error(f"Error processing page {page_num + 1}: {str(e)}")
            
            pdf_document.close()
            logger.info("PDF processing completed")
            # return self.merge_results()
            return self.results
            
        except Exception as e:
            logger.error(f"Error in process_pdf: {str(e)}")
            raise
    
    
    def safe_get_list(self, data: dict, key: str) -> list:
        """Safely get a list from a dictionary, handling None input."""
        if data is None:
            return []
        value = data.get(key, [])
        return value if isinstance(value, list) else []
        
    def safe_get_dict(self, data: dict, key: str) -> dict:
        """Safely get a dictionary from a dictionary, returning empty dict if None or not a dict."""
        if not isinstance(data, dict):
            logger.warning(f"Input is not a dictionary: {type(data)}")
            return {}
        value = data.get(key, {})
        if value is None:
            logger.warning(f"Found None value for key '{key}'")
            return {}
        if not isinstance(value, dict):
            logger.warning(f"Value for key '{key}' is not a dict: {type(value)}")
            return {}
        return value

    def merge_locations(self, locations: List[dict]) -> List[dict]:
        """
        Merge locations that refer to the same city, combining their courses and other details.
        """
        if not locations:
            logger.warning("No locations found to merge")
            return []
          # First pass: Filter out invalid entries
        valid_locations = []
        for loc in locations:
            if not isinstance(loc, dict):
                logger.warning(f"Skipping invalid location entry: {loc}")
                continue
            if not loc.get('city') or not loc.get('country'):
                logger.warning(f"Skipping location missing city/country: {loc}")
                continue
            valid_locations.append(loc)

        # Group locations by city and country
        location_map = {}
        for location in valid_locations:
            city = location.get('city')
            country = location.get('country')
            key = (city.lower().strip(), country.lower().strip())
            location_map.setdefault(key, []).append(location)

        merged_locations = []
        for (city, country), city_locations in location_map.items():
            merged_location = {
                'city': city,
                'country': country,
                'address': None,
                'courses': [],
                'accommodations': [],
                'additional_fees': {}
            }
            
            # Get first non-null address if available
            # Get first non-null address if available
            addresses = [loc.get('address') for loc in city_locations if loc.get('address')]
            if addresses:
                merged_location['address'] = addresses[0]
            
            # Track seen course names to avoid duplicates
            seen_courses = {}
            for location in city_locations:
                for course in self.safe_get_list(location, 'courses'):
                    if not isinstance(course, dict):
                        logger.warning(f"Skipping invalid course entry: {course}")
                        continue
                    
                    name = course.get('name')
                    if not name:
                        logger.warning(f"Skipping course without name: {course}")
                        continue
                    
                    course_key = (name, course.get('lessons_per_week'))
                    
                    if course_key not in seen_courses:
                        # New course - ensure all required fields exist
                        seen_courses[course_key] = {
                            'name': name,
                            'lessons_per_week': course.get('lessons_per_week'),
                            'description': course.get('description', ''),
                            'prices': self.safe_get_list(course, 'prices'),
                            'requirements': course.get('requirements', '')
                        }
                    else:
                        # Existing course - merge prices if they exist
                        existing_course = seen_courses[course_key]
                        course_prices = self.safe_get_list(course, 'prices')
                        if course_prices:
                            if not existing_course['prices']:
                                existing_course['prices'] = course_prices
                            else:
                                # Merge prices based on duration
                                price_map = {p.get('duration'): p for p in existing_course['prices'] if p.get('duration')}
                                for price in course_prices:
                                    if price.get('duration') and price.get('duration') not in price_map:
                                        existing_course['prices'].append(price)
                        
                        # Take the most detailed description
                        if len(course.get('description', '')) > len(existing_course.get('description', '')):
                            existing_course['description'] = course.get('description', '')
            
            merged_location['courses'] = list(seen_courses.values())
            
            # Merge accommodations
            seen_accommodations = {}
            for location in city_locations:
                for accommodation in self.safe_get_list(location, 'accommodations'):
                    if not isinstance(accommodation, dict):
                        logger.warning(f"Skipping invalid accommodation entry: {accommodation}")
                        continue
                    
                    acc_type = accommodation.get('type')
                    if not acc_type:
                        logger.warning(f"Skipping accommodation without type: {accommodation}")
                        continue
                    
                    if acc_type not in seen_accommodations:
                        seen_accommodations[acc_type] = {
                            'type': acc_type,
                            'price_per_week': accommodation.get('price_per_week'),
                            'description': accommodation.get('description', ''),
                            'supplements': accommodation.get('supplements', {})
                        }
                    else:
                        # Merge supplements if they exist
                        existing_acc = seen_accommodations[acc_type]
                        supplements = accommodation.get('supplements', {})
                        if supplements:
                            if not existing_acc['supplements']:
                                existing_acc['supplements'] = supplements
                            else:
                                existing_acc['supplements'].update(supplements)
                        
                        # Take non-null values from the new accommodation if they exist
                        if accommodation.get('price_per_week') and not existing_acc.get('price_per_week'):
                            existing_acc['price_per_week'] = accommodation['price_per_week']
                        
                        if len(accommodation.get('description', '')) > len(existing_acc.get('description', '')):
                            existing_acc['description'] = accommodation['description']
            
            merged_location['accommodations'] = list(seen_accommodations.values())
            
            # Merge additional fees
            for location in city_locations:
                additional_fees = location.get('additional_fees', {})
                if isinstance(additional_fees, dict):
                    merged_location.get('additional_fees').update(additional_fees)
            
            merged_locations.append(merged_location)
        
                   
            # Track seen course names to avoid duplicates
            seen_courses = {}
            for location in city_locations:
                for course in location.get('courses', []):
                    if not isinstance(course, dict):
                        logger.warning(f"Skipping invalid course entry: {course}")
                        continue
                        
                    name = course.get('name')
                    if not name:
                        logger.warning(f"Skipping course without name: {course}")
                        continue
                        
                    course_key = (name, course.get('lessons_per_week'))
                    
                    if course_key not in seen_courses:
                        # New course - ensure all required fields exist
                        seen_courses[course_key] = {
                            'name': name,
                            'lessons_per_week': course.get('lessons_per_week'),
                            'description': course.get('description', ''),
                            'prices': course.get('prices', []),
                            'requirements': course.get('requirements', '')
                        }
                    else:
                        # Existing course - merge prices if they exist
                        existing_course = seen_courses[course_key]
                        if course.get('prices'):
                            if not existing_course.get('prices'):
                                existing_course['prices'] = course['prices']
                            else:
                                # Merge prices based on duration
                                price_map = {p.get('duration'): p for p in existing_course['prices'] if p.get('duration')}
                                for price in course['prices']:
                                    if price.get('duration') and price.get('duration') not in price_map:
                                        existing_course['prices'].append(price)
                        
                        # Take the most detailed description
                        if len(course.get('description', '')) > len(existing_course.get('description', '')):
                            existing_course['description'] = course.get('description', '')
            
            merged_location['courses'] = list(seen_courses.values())
            
            # Merge accommodations
            seen_accommodations = {}
            for location in city_locations:
                accommodation_list = location.get('accommodations', [])
                if not isinstance(accommodation_list, list):
                    logger.warning(f"Invalid accommodations list: {accommodation_list}")
                    continue
                for accommodation in location.get('accommodations', []):
                    if not isinstance(accommodation, dict):
                        logger.warning(f"Skipping invalid accommodation entry: {accommodation}")
                        continue
                        
                    acc_type = accommodation.get('type')
                    if not acc_type:
                        logger.warning(f"Skipping accommodation without type: {accommodation}")
                        continue
                        
                    if acc_type not in seen_accommodations:
                        seen_accommodations[acc_type] = {
                            'type': acc_type,
                            'price_per_week': accommodation.get('price_per_week'),
                            'description': accommodation.get('description', ''),
                            'supplements': accommodation.get('supplements', {})
                        }
                    else:
                        # Merge supplements if they exist
                        existing_acc = seen_accommodations[acc_type]
                        if accommodation.get('supplements'):
                            if not existing_acc.get('supplements'):
                                existing_acc['supplements'] = accommodation['supplements']
                            else:
                                existing_acc['supplements'].update(accommodation['supplements'])
                                
                        # Take non-null values from the new accommodation if they exist
                        if accommodation.get('price_per_week') and not existing_acc.get('price_per_week'):
                            existing_acc['price_per_week'] = accommodation['price_per_week']
                            
                        if len(accommodation.get('description', '')) > len(existing_acc.get('description', '')):
                            existing_acc['description'] = accommodation['description']
            
            merged_location['accommodations'] = list(seen_accommodations.values())
            
            # Merge additional fees
            for location in city_locations:
                additional_fees = self.safe_get_dict(location, 'additional_fees')
                merged_location['additional_fees'].update(additional_fees)
            
            merged_locations.append(merged_location)
        
        logger.info(f"Merged {len(merged_locations)} locations")
        return merged_locations

    def merge_results(self):
        logger.info("Merging results from all pages")
        try:
            merged = {
                "school_name": "",
                "locations": [],
                "terms": {}
            }
            
            # Get first non-empty school name
            for page in self.results:
                if page and page.get("school_name"):
                    merged["school_name"] = page["school_name"]
                    break
            
            # Collect all locations
            all_locations = []
            for page in self.results:
                if page and isinstance(page, dict):
                    locations = page.get("locations", [])
                    if locations is None:
                        logger.warning(f"Found None for locations in page: {page}")
                        continue
                    if not isinstance(locations, list):
                        logger.warning(f"Locations is not a list: {type(locations)}")
                        continue
                    all_locations.extend(locations)
                else:
                    logger.warning(f"Invalid page data: {page}")
            
            logger.info(f"Collected {len(all_locations)} locations for merging")
            
            # Merge locations
            if not all_locations:
                logger.warning("No locations found to merge")
                return merged
                
            merged["locations"] = self.merge_locations(all_locations)
            
            # Merge terms
            for page in self.results:
                if page and isinstance(page, dict):
                    terms = page.get("terms", {})
                    if isinstance(terms, dict):
                        merged["terms"].update(terms)
            
            logger.info("Successfully merged results")
            return merged
            
        except Exception as e:
            logger.error(f"Error in merge_results: {str(e)}")
            raise

# Usage Example
if __name__ == "__main__":
    try:
        logger.info("Starting PDF processing")
        processor = PDFProcessor(api_key=OPENAI_API_KEY)
        result = processor.process_pdf("data/input_files/2025_CES_Adult_Price_List_as_at_8th_August.pdf")
        
        output_file = "output.json"
        logger.info(f"Writing results to {output_file}")
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)
        
        logger.info("Processing complete. Results saved to output.json")
        
    except Exception as e:
        logger.error(f"Main process failed: {str(e)}")
        raise