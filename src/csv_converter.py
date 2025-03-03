"""
path: src/csv_converter.py
author: concaption
description: Utilities to convert parsed school data to CSV format
"""

import json
import pandas as pd
from typing import Dict, List, Any, Optional
import logging
from pathlib import Path
import io
import traceback

from .logger import setup_logging

# Initialize logger
logger = setup_logging()


def format_supplements(supplements: Dict[str, Any]) -> str:
    """Format supplements dictionary into a readable string"""
    try:
        if not supplements:
            return ""
        return "; ".join(f"{k}: {v}" for k, v in supplements.items())
    except Exception as e:
        logger.error(f"Error formatting supplements: {str(e)}")
        logger.debug(f"Problematic supplements: {supplements}")
        return "ERROR_FORMATTING"


def format_additional_fees(fees: Dict[str, Any]) -> str:
    """Format additional fees dictionary into a readable string"""
    try:
        if not isinstance(fees, dict):
            if isinstance(fees, list):
                return "; ".join(f"{fee.get('name', 'Unknown')}: {fee.get('price', 'N/A')} {fee.get('currency', '')}" 
                                for fee in fees if isinstance(fee, dict))
            return ""
        return "; ".join(f"{k}: {v}" for k, v in fees.items())
    except Exception as e:
        logger.error(f"Error formatting additional fees: {str(e)}")
        logger.debug(f"Problematic fees: {fees}")
        return "ERROR_FORMATTING"


def format_terms(terms: Dict[str, Any]) -> str:
    """Format terms dictionary into a readable string"""
    try:
        if not terms:
            return ""
        return "; ".join(f"{k}: {v}" for k, v in terms.items())
    except Exception as e:
        logger.error(f"Error formatting terms: {str(e)}")
        logger.debug(f"Problematic terms: {terms}")
        return "ERROR_FORMATTING"


def format_accommodations(accommodations: List[Dict[str, Any]]) -> str:
    """Format accommodations list into a readable string"""
    try:
        if not accommodations:
            return ""
        
        acc_details = []
        for i, acc in enumerate(accommodations):
            try:
                if not isinstance(acc, dict):
                    logger.warning(f"Skipping non-dict accommodation at index {i}: {type(acc)}")
                    continue
                
                details = f"Type: {acc.get('type', 'N/A')}"
                
                if acc.get('price_per_week'):
                    details += f", Price/week: {acc['price_per_week']}"
                
                if acc.get('currency'):
                    details += f" {acc['currency']}"
                
                if acc.get('description'):
                    # Truncate very long descriptions
                    desc = acc['description']
                    if len(desc) > 200:
                        desc = desc[:197] + "..."
                    details += f", Description: {desc}"
                
                if acc.get('supplements'):
                    try:
                        supplements = format_supplements(acc['supplements'])
                        if supplements:
                            details += f", Supplements: {supplements}"
                    except Exception as se:
                        logger.error(f"Error formatting supplements for accommodation {i}: {str(se)}")
                
                acc_details.append(details)
            except Exception as ae:
                logger.error(f"Error processing accommodation {i}: {str(ae)}")
                logger.debug(f"Problematic accommodation: {acc}")
        
        return " | ".join(acc_details)
    except Exception as e:
        logger.error(f"Error formatting accommodations: {str(e)}")
        logger.debug(f"Problematic accommodations list: {accommodations}")
        return "ERROR_FORMATTING"


def extract_total_fee(course: Dict[str, Any], currency_map: Dict[str, str]) -> Optional[float]:
    """Extract and calculate total fee if available"""
    try:
        # If total_fee is directly available, use it
        if course.get('total_fee') is not None:
            try:
                return float(course['total_fee'])
            except (ValueError, TypeError) as e:
                logger.error(f"Could not convert total_fee to float: {course['total_fee']}, error: {str(e)}")
        
        # Try to calculate from the first price in the list
        prices = course.get('prices', [])
        if prices and isinstance(prices, list) and len(prices) > 0:
            price = prices[0]
            if price.get('total_price') is not None:
                try:
                    return float(price['total_price'])
                except (ValueError, TypeError) as e:
                    logger.error(f"Could not convert total_price to float: {price['total_price']}, error: {str(e)}")
            
            # Try to extract from price string
            if price.get('price'):
                try:
                    price_str = str(price['price'])
                    # Remove currency symbols and convert to float
                    for symbol, _ in currency_map.items():
                        price_str = price_str.replace(symbol, '')
                    price_str = price_str.replace(',', '').strip()
                    return float(price_str)
                except (ValueError, TypeError) as e:
                    logger.error(f"Could not extract price from string: {price['price']}, error: {str(e)}")
        
        return None
    except Exception as e:
        logger.error(f"Error extracting total fee: {str(e)}")
        return None


def flatten_school_data(merged_results: Dict) -> List[Dict]:
    """
    Flattens JSON school data into a list of dictionaries, each representing a row in the final CSV.
    Handles merged results structure with accommodations, terms, and additional fees.
    """
    all_rows = []
    
    try:
        if not merged_results:
            logger.warning("Empty merged results provided")
            return all_rows
        
        # Make sure we're getting the right structure - handle both direct and nested formats
        actual_merged_results = merged_results
        if "merged_results" in merged_results:
            # If we're passed the outer structure with merged_results inside
            logger.debug("Found nested merged_results structure, extracting inner data")
            actual_merged_results = merged_results["merged_results"]
        
        logger.info(f"Starting to flatten school data for: {actual_merged_results.get('name', 'Unnamed School')}")
        
        school_name = actual_merged_results.get('name', '')
        if not school_name:
            # Try harder to find the school name
            logger.warning("School name not found in the primary location, looking deeper")
            if isinstance(actual_merged_results.get('locations', []), list) and len(actual_merged_results.get('locations', [])) > 0:
                first_location = actual_merged_results['locations'][0]
                if 'school_name' in first_location:
                    school_name = first_location['school_name']
                    logger.info(f"Found school name in first location: {school_name}")
                elif 'school_name' in actual_merged_results:
                    school_name = actual_merged_results['school_name']
                    logger.info(f"Found school name in school_name field: {school_name}")
            
        if not school_name:
            logger.warning("Could not find a valid school name in the data")
        
        school_terms = actual_merged_results.get('terms', {})
        
        # Currency mapping for standardization
        currency_map = {
            '€': 'EUR',
            '$': 'USD',
            '£': 'GBP'
        }
        
        # Track processing stats
        location_count = 0
        course_count = 0
        price_count = 0
        row_count = 0
        
        for location_idx, location in enumerate(actual_merged_results.get('locations', [])):
            try:
                location_count += 1
                city = location.get('city', '')
                country = location.get('country', '')
                address = location.get('address', '')
                logger.debug(f"Processing location {location_idx+1}: {city}, {country}")
                
                accommodations = location.get('accommodations', [])
                additional_fees = location.get('additional_fees', {})
                
                # Format complex fields
                try:
                    formatted_accommodations = format_accommodations(accommodations)
                    logger.debug(f"Formatted {len(accommodations)} accommodations")
                except Exception as e:
                    logger.error(f"Error formatting accommodations for {city}: {str(e)}")
                    formatted_accommodations = "ERROR_FORMATTING_ACCOMMODATIONS"
                
                try:
                    formatted_fees = format_additional_fees(additional_fees)
                    logger.debug(f"Formatted additional fees")
                except Exception as e:
                    logger.error(f"Error formatting additional fees for {city}: {str(e)}")
                    formatted_fees = "ERROR_FORMATTING_FEES"
                
                try:
                    formatted_terms = format_terms(school_terms)
                    logger.debug(f"Formatted terms")
                except Exception as e:
                    logger.error(f"Error formatting terms: {str(e)}")
                    formatted_terms = "ERROR_FORMATTING_TERMS"
                
                for course_idx, course in enumerate(location.get('courses', [])):
                    try:
                        course_count += 1
                        course_name = course.get('name', '')
                        logger.debug(f"Processing course {course_idx+1}: {course_name}")
                        
                        lessons_per_week = course.get('lessons_per_week', '')
                        description = course.get('description', '')
                        requirements = course.get('requirements', '')
                        course_type = course.get('course_type', '')
                        age_range = course.get('age_range_display', '') or f"{course.get('min_age', '')}-{course.get('max_age', '')}" or course.get('age_range', '')
                        
                        try:
                            total_fee = extract_total_fee(course, currency_map)
                            logger.debug(f"Extracted total fee: {total_fee}")
                        except Exception as e:
                            logger.error(f"Error extracting total fee for course {course_name}: {str(e)}")
                            total_fee = None
                        
                        prices = course.get('prices', [])
                        if prices and isinstance(prices, list):
                            for price_idx, price in enumerate(prices):
                                try:
                                    if not isinstance(price, dict):
                                        logger.warning(f"Skipping non-dict price at index {price_idx} for course {course_name}")
                                        continue
                                    
                                    price_count += 1
                                    logger.debug(f"Processing price {price_idx+1} for course {course_name}: {price.get('duration', 'Unknown')} - {price.get('price', 'Unknown')}")
                                        
                                    currency = price.get('currency', '')
                                    if not currency and isinstance(price.get('price'), str):
                                        price_str = price.get('price', '')
                                        for symbol, curr in currency_map.items():
                                            if symbol in price_str:
                                                currency = curr
                                                break
                                    
                                    # Calculate or extract total price for this price option
                                    price_total = None
                                    if price.get('total_price') is not None:
                                        price_total = price['total_price']
                                    else:
                                        try:
                                            price_str = str(price.get('price', ''))
                                            for symbol, _ in currency_map.items():
                                                price_str = price_str.replace(symbol, '')
                                            price_str = price_str.replace(',', '').strip()
                                            price_total = float(price_str)
                                        except (ValueError, TypeError) as e:
                                            logger.debug(f"Could not extract numerical value from price: {price.get('price', '')}")
                                                
                                    row = {
                                        'School Name': school_name,
                                        'City': city,
                                        'Country': country,
                                        'Address': address,
                                        'Course Name': course_name,
                                        'Course Type': course_type,
                                        'Age Range': age_range,
                                        'Lessons Per Week': lessons_per_week,
                                        'Description': description,
                                        'Requirements': requirements,
                                        'Duration': price.get('duration', ''),
                                        'Price': price.get('price', ''),
                                        'Price Value': price_total,
                                        'Currency': currency,
                                        'Total Fee': total_fee,
                                        'Accommodations': formatted_accommodations,
                                        'Additional Fees': formatted_fees,
                                        'Terms': formatted_terms
                                    }
                                    all_rows.append(row)
                                    row_count += 1
                                except Exception as price_e:
                                    logger.error(f"Error processing price {price_idx} for course {course_name}: {str(price_e)}")
                                    logger.debug(f"Price data: {price}")
                                    logger.debug(traceback.format_exc())
                        else:
                            # If no prices, create a single row
                            row = {
                                'School Name': school_name,
                                'City': city,
                                'Country': country,
                                'Address': address,
                                'Course Name': course_name,
                                'Course Type': course_type,
                                'Age Range': age_range,
                                'Lessons Per Week': lessons_per_week,
                                'Description': description,
                                'Requirements': requirements,
                                'Duration': '',
                                'Price': '',
                                'Price Value': None,
                                'Currency': '',
                                'Total Fee': total_fee,
                                'Accommodations': formatted_accommodations,
                                'Additional Fees': formatted_fees,
                                'Terms': formatted_terms
                            }
                            all_rows.append(row)
                            row_count += 1
                    except Exception as course_e:
                        logger.error(f"Error processing course {course_idx} in {city}: {str(course_e)}")
                        logger.debug(f"Course data: {course}")
                        logger.debug(traceback.format_exc())
            except Exception as loc_e:
                logger.error(f"Error processing location {location_idx}: {str(loc_e)}")
                logger.debug(f"Location data: {location}")
                logger.debug(traceback.format_exc())
        
        logger.info(f"Flattening complete. Processed {location_count} locations, {course_count} courses, {price_count} prices, created {row_count} rows.")
        return all_rows
    except Exception as e:
        logger.error(f"Error in flatten_school_data: {str(e)}")
        logger.debug(traceback.format_exc())
        return all_rows


def json_to_dataframe(merged_results: Dict) -> pd.DataFrame:
    """Convert JSON merged results to a DataFrame"""
    try:
        logger.info("Starting JSON to DataFrame conversion")
        
        # Add additional debugging about the input structure
        if isinstance(merged_results, dict):
            logger.debug(f"Input is a dictionary with keys: {list(merged_results.keys())}")
            if "name" in merged_results:
                logger.info(f"School name found in input: {merged_results['name']}")
            elif "merged_results" in merged_results and isinstance(merged_results["merged_results"], dict):
                if "name" in merged_results["merged_results"]:
                    logger.info(f"School name found in nested structure: {merged_results['merged_results']['name']}")
        else:
            logger.warning(f"Input is not a dictionary, type: {type(merged_results)}")
        
        flattened_data = flatten_school_data(merged_results)
        
        if not flattened_data:
            logger.warning("No data was extracted from the merged results")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(flattened_data)
        
        # Clean column names
        df.columns = df.columns.str.replace('[^a-zA-Z0-9]', '_').str.lower()
        
        logger.info(f"Successfully created DataFrame with {len(df)} rows and {len(df.columns)} columns")
        logger.debug(f"DataFrame columns: {list(df.columns)}")
        logger.debug(f"First row: {df.iloc[0].to_dict() if len(df) > 0 else 'No data'}")
        
        return df
    except Exception as e:
        logger.error(f"Error in json_to_dataframe: {str(e)}")
        logger.debug(traceback.format_exc())
        return pd.DataFrame()


def json_to_csv(merged_results: Dict, output_path: Optional[str] = None) -> Optional[str]:
    """
    Convert JSON merged results to CSV
    
    Args:
        merged_results: Dictionary containing merged school information
        output_path: Optional path to save CSV file
        
    Returns:
        Path to saved CSV file if output_path is provided, else None
    """
    try:
        logger.info(f"Converting JSON to CSV, output path: {output_path}")
        
        if not isinstance(merged_results, dict):
            if isinstance(merged_results, str):
                logger.info("Input is a string, attempting to parse as JSON")
                try:
                    with open(merged_results, 'r') as f:
                        merged_results = json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load JSON from file: {str(e)}")
                    return None
            else:
                logger.error(f"Invalid input type: {type(merged_results)}, expected dict")
                return None
        
        df = json_to_dataframe(merged_results)
        
        if df.empty:
            logger.error("DataFrame is empty, cannot create CSV")
            return None
        
        # If output path is provided, save to file
        if output_path:
            logger.info(f"Saving CSV to {output_path}")
            output_dir = Path(output_path).parent
            if not output_dir.exists():
                logger.info(f"Creating directory: {output_dir}")
                output_dir.mkdir(parents=True, exist_ok=True)
            
            df.to_csv(output_path, index=False, encoding='utf-8')
            logger.info(f"CSV file created successfully: {output_path}")
            
            # Verify file was created
            if Path(output_path).exists():
                logger.info(f"File verification successful, size: {Path(output_path).stat().st_size} bytes")
            else:
                logger.error("File verification failed, file does not exist after writing")
            
            return output_path
        
        # Otherwise, return the DataFrame
        logger.info("No output path provided, returning DataFrame")
        return df
        
    except Exception as e:
        logger.error(f"Error creating CSV: {str(e)}")
        logger.debug(traceback.format_exc())
        return None


def dataframe_to_csv_string(df: pd.DataFrame) -> str:
    """Convert DataFrame to CSV string"""
    try:
        if df.empty:
            logger.warning("Empty DataFrame, returning empty string")
            return ""
        
        logger.info(f"Converting DataFrame with {len(df)} rows to CSV string")
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_string = csv_buffer.getvalue()
        logger.info(f"CSV string created, length: {len(csv_string)} characters")
        return csv_string
    except Exception as e:
        logger.error(f"Error converting DataFrame to CSV string: {str(e)}")
        logger.debug(traceback.format_exc())
        return ""
