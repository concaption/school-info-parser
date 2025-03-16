"""
path: src/utils.py
author: concaption
description: Utility functions for processing and merging school information.
"""

import logging
from typing import List, Dict, Any
from difflib import SequenceMatcher
import pandas as pd
import os

logger = logging.getLogger(__name__)

def similar(a: str, b: str) -> float:
    """Calculate similarity ratio between two strings."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_similar_location(locations: List[Dict], city: str, country: str, threshold: float = 0.8) -> int:
    """Find index of location with similar city and country."""
    for i, loc in enumerate(locations):
        if similar(loc["city"], city) >= threshold and similar(loc["country"], country) >= threshold:
            return i
    return -1

def find_similar_course(courses: List[Dict], course_name: str, threshold: float = 0.8) -> int:
    """Find index of course with similar name."""
    for i, course in enumerate(courses):
        if similar(course["name"], course_name) >= threshold:
            return i
    return -1

def merge_all_results(raw_results: List[Dict]) -> Dict:
    """
    Merge all raw results into a consolidated school information dictionary.
    
    Args:
        raw_results: List of parsed school data from individual PDF pages
        
    Returns:
        Dict containing merged school information
    """
    logger.info("Merging all results")
    
    if not raw_results:
        logger.warning("No results to merge")
        return {}
    
    # Initialize with the first school entry
    merged_result = {
        "name": raw_results[0].get("name", "Unknown School"),
        "locations": []
    }
    
    # Process all raw results
    for result in raw_results:
        if not result or "locations" not in result:
            logger.warning(f"Skipping invalid result: {result}")
            continue
            
        school_name = result.get("name")
        if school_name and not merged_result.get("name"):
            merged_result["name"] = school_name
            
        # Process locations
        for location in result.get("locations", []):
            city = location.get("city")
            country = location.get("country")
            
            if not city or not country:
                logger.warning(f"Skipping location without city or country: {location}")
                continue
                
            # Check if similar location already exists
            loc_idx = find_similar_location(merged_result["locations"], city, country)
            
            if loc_idx == -1:
                # Add new location with all its fields
                # Ensure all fields are present and non-None
                if "courses" not in location or location["courses"] is None:
                    location["courses"] = []
                if "accommodation_fees" not in location or location["accommodation_fees"] is None:
                    location["accommodation_fees"] = []
                if "suplement_fees" not in location or location["suplement_fees"] is None:
                    location["suplement_fees"] = []
                if "additional_fees" not in location or location["additional_fees"] is None:
                    location["additional_fees"] = []
                    
                merged_result["locations"].append(location)
            else:
                # Merge courses from this location
                existing_location = merged_result["locations"][loc_idx]
                
                # Ensure all required fields exist in the existing location
                if "courses" not in existing_location or existing_location["courses"] is None:
                    existing_location["courses"] = []
                if "accommodation_fees" not in existing_location or existing_location["accommodation_fees"] is None:
                    existing_location["accommodation_fees"] = []
                if "suplement_fees" not in existing_location or existing_location["suplement_fees"] is None:
                    existing_location["suplement_fees"] = []
                if "additional_fees" not in existing_location or existing_location["additional_fees"] is None:
                    existing_location["additional_fees"] = []
                
                # Process courses for this location
                for course in location.get("courses", []):
                    course_name = course.get("name")
                    if not course_name:
                        logger.warning(f"Skipping course without name: {course}")
                        continue
                        
                    # Check if similar course already exists
                    course_idx = find_similar_course(existing_location["courses"], course_name)
                    
                    if course_idx == -1:
                        # Add new course
                        existing_location["courses"].append(course)
                    else:
                        # Courses already exist, could implement more detailed merging if needed
                        # For now, we'll keep the first occurrence of each course
                        pass
                
                # Merge accommodation fees
                if location.get("accommodation_fees"):
                    # Add unique accommodation options
                    existing_accommodations = {acc["name"] for acc in existing_location["accommodation_fees"]}
                    for acc in location["accommodation_fees"]:
                        if acc["name"] not in existing_accommodations:
                            existing_location["accommodation_fees"].append(acc)
                            existing_accommodations.add(acc["name"])
                
                # Merge supplement fees
                if location.get("suplement_fees"):
                    # Add unique supplement options
                    existing_supplements = {sup["type"] for sup in existing_location["suplement_fees"]}
                    for sup in location["suplement_fees"]:
                        if sup["type"] not in existing_supplements:
                            existing_location["suplement_fees"].append(sup)
                            existing_supplements.add(sup["type"])
                
                # Merge additional fees
                if location.get("additional_fees"):
                    # Add unique additional fees
                    existing_fees = {fee["fee_type"] for fee in existing_location["additional_fees"]}
                    for fee in location["additional_fees"]:
                        if fee["fee_type"] not in existing_fees:
                            existing_location["additional_fees"].append(fee)
                            existing_fees.add(fee["fee_type"])
    
    logger.info(f"Finished merging results: {len(merged_result['locations'])} locations")
    return merged_result

def melt_results(merged_results: Dict) -> List[Dict]:
    """
    Transform merged results into a melted format where each row represents a fee
    with associated school and course metadata.
    
    Args:
        merged_results: Dictionary containing merged school information
        
    Returns:
        List of dictionaries, each representing a row in the melted format
    """
    logger.info("Melting results into row-based format")
    
    melted_rows = []
    
    if not merged_results or "name" not in merged_results:
        logger.warning("No valid results to melt")
        return []
    
    school_name = merged_results.get("name", "Unknown School")
    terms = merged_results.get("terms", {})
    
    # Convert terms dictionary to a paragraph if present
    terms_paragraph = ""
    if terms:
        terms_paragraph = "\n\n".join([f"{key}: {value}" for key, value in terms.items()])
    
    # Process each location
    for location in merged_results.get("locations", []):
        location_city = location.get("city", "")
        location_country = location.get("country", "")
        location_address = location.get("address", "")
        
        # Process courses for this location
        for course in location.get("courses", []):
            # Extract course metadata
            course_name = course.get("name", "")
            course_type = course.get("course_type", "")
            course_min_age = course.get("min_age", "")
            course_max_age = course.get("max_age", "")
            course_age_range = course.get("age_range_display", "")
            course_lessons_per_week = course.get("lessons_per_week", "")
            course_intensity = course.get("course_intensity", "")
            course_description = course.get("description", "")
            course_requirements = course.get("requirements", "")
            
            # Common metadata for all fees related to this course
            base_metadata = {
                "school_name": school_name,
                "location_city": location_city,
                "location_country": location_country,
                "location_address": location_address,
                "course_name": course_name,
                "course_type": course_type,
                "course_min_age": course_min_age,
                "course_max_age": course_max_age,
                "course_age_range": course_age_range,
                "course_lessons_per_week": course_lessons_per_week,
                "course_intensity": course_intensity,
                "course_description": course_description,
                "course_requirements": course_requirements,
                "terms": terms_paragraph
            }
            
            # Process weekly course fees
            weekly_course_fees = course.get("weekly_course_fees", [])
            if weekly_course_fees:
                for fee in weekly_course_fees:
                    fee_row = base_metadata.copy()
                    fee_row.update({
                        "fee_type": "weekly_course_fee",
                        "duration": fee.get("duration", ""),
                        "price_per_week": fee.get("price_per_week", ""),
                        "currency": fee.get("currency", ""),
                        "description": fee.get("description", ""),
                        "name": "",
                        "type": ""
                    })
                    melted_rows.append(fee_row)
            else:
                # If no weekly_course_fees, still add an entry for the course with empty fee details
                fee_row = base_metadata.copy()
                fee_row.update({
                    "fee_type": "weekly_course_fee",
                    "duration": "",
                    "price_per_week": "",
                    "currency": "",
                    "description": "",
                    "name": "",
                    "type": ""
                })
                melted_rows.append(fee_row)
            
            # Process course additional fees - ensure additional_fees is a list
            additional_fees = course.get("additional_fees")
            if additional_fees is None:
                additional_fees = []
            elif not isinstance(additional_fees, list):
                logger.warning(f"additional_fees is not a list: {additional_fees}")
                additional_fees = []
            
            for fee in additional_fees:
                fee_row = base_metadata.copy()
                fee_row.update({
                    "fee_type": fee.get("fee_type", "course_additional_fee"),
                    "duration": "",
                    "price_per_week": fee.get("price_per_week", ""),
                    "currency": fee.get("currency", ""),
                    "description": fee.get("description", ""),
                    "name": "",
                    "type": ""
                })
                melted_rows.append(fee_row)
        
        # Process accommodation fees
        for acc in location.get("accommodation_fees", []):
            # Create a base row for accommodation
            acc_base = {
                "school_name": school_name,
                "location_city": location_city,
                "location_country": location_country,
                "location_address": location_address,
                "course_name": "",
                "course_type": "",
                "course_min_age": "",
                "course_max_age": "",
                "course_age_range": "",
                "course_lessons_per_week": "",
                "course_intensity": "",
                "course_description": "",
                "course_requirements": "",
                "terms": terms_paragraph,
                "fee_type": "accommodation_fee",
                "duration": "",
                "price_per_week": acc.get("price_per_week", ""),
                "currency": acc.get("currency", ""),
                "description": acc.get("name", ""),
                "name": "",
                "type": acc.get("type", "")
            }
            melted_rows.append(acc_base)
            
            # Process food supplements for this accommodation
            for food in acc.get("food_suplements", []):
                food_row = {
                    "school_name": school_name,
                    "location_city": location_city,
                    "location_country": location_country,
                    "location_address": location_address,
                    "course_name": "",
                    "course_type": "",
                    "course_min_age": "",
                    "course_max_age": "",
                    "course_age_range": "",
                    "course_lessons_per_week": "",
                    "course_intensity": "",
                    "course_description": "",
                    "course_requirements": "",
                    "terms": terms_paragraph,
                    "fee_type": "food_supplement_fee",
                    "duration": "",
                    "price_per_week": food.get("price_per_week", ""),
                    "currency": food.get("currency", ""),
                    "description": "",
                    "name": food.get("name", ""),
                    "type": food.get("meal_type", "")
                }
                melted_rows.append(food_row)
        
        # Process supplement fees
        for supp in location.get("suplement_fees", []):
            supp_row = {
                "school_name": school_name,
                "location_city": location_city,
                "location_country": location_country,
                "location_address": location_address,
                "course_name": "",
                "course_type": "",
                "course_min_age": "",
                "course_max_age": "",
                "course_age_range": "",
                "course_lessons_per_week": "",
                "course_intensity": "",
                "course_description": "",
                "course_requirements": "",
                "terms": terms_paragraph,
                "fee_type": supp.get("type", "supplement_fee"),  # Use the type field as the fee_type
                "duration": "",
                "price_per_week": supp.get("price_per_week", ""),
                "currency": supp.get("currency", ""),
                "description": "",
                "name": "",
                "type": ""
            }
            melted_rows.append(supp_row)
        
        # Process location additional fees
        for fee in location.get("additional_fees", []):
            fee_row = {
                "school_name": school_name,
                "location_city": location_city,
                "location_country": location_country,
                "location_address": location_address,
                "course_name": "",
                "course_type": "",
                "course_min_age": "",
                "course_max_age": "",
                "course_age_range": "",
                "course_lessons_per_week": "",
                "course_intensity": "",
                "course_description": "",
                "course_requirements": "",
                "terms": terms_paragraph,
                "fee_type": fee.get("fee_type", "location_additional_fee"),  # Use the fee_type field value
                "duration": "",
                "price_per_week": fee.get("price_per_week", ""),
                "currency": fee.get("currency", ""),
                "description": fee.get("description", ""),  # Include description
                "name": "",
                "type": ""
            }
            melted_rows.append(fee_row)
    
    logger.info(f"Melted results into {len(melted_rows)} rows")
    return melted_rows

def export_to_excel(melted_results: List[Dict], output_path: str) -> str:
    """
    Convert melted results to an Excel file.
    
    Args:
        melted_results: List of dictionaries containing the melted data
        output_path: Directory path where the Excel file should be saved
        
    Returns:
        Path to the created Excel file
    """
    logger.info("Exporting melted results to Excel")
    
    if not melted_results:
        logger.warning("No data to export to Excel")
        return ""
    
    try:
        # Create DataFrame from melted results
        df = pd.DataFrame(melted_results)
        
        # Ensure output directory exists
        os.makedirs(output_path, exist_ok=True)
        
        # Generate filename with timestamp to avoid overwriting
        timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        excel_file = os.path.join(output_path, f"school_info_{timestamp}.xlsx")
        
        # Create a writer to format the Excel file
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='School Info', index=False)
            
            # Auto-adjust column widths
            worksheet = writer.sheets['School Info']
            for i, col in enumerate(df.columns):
                max_width = max(
                    df[col].astype(str).map(len).max(),  # Width of data
                    len(col)  # Width of column header
                ) + 2  # Add a little extra space
                
                # Limit max width to avoid very wide columns
                max_width = min(max_width, 50)
                
                # Excel column widths are measured in characters
                worksheet.column_dimensions[chr(65 + i)].width = max_width
        
        logger.info(f"Excel file created successfully: {excel_file}")
        return excel_file
        
    except Exception as e:
        logger.error(f"Error exporting to Excel: {str(e)}")
        return ""
