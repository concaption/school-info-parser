"""
path: src/utils.py
author: concaption
description: This script contains utility functions for merging dictionaries.
"""

import copy
from typing import Optional
from .logger import setup_logging

logger = setup_logging()


def merge_accommodation_details(existing: dict, new: dict):
    """Merge details of two accommodation dictionaries"""
    try:
        logger.debug(f"Merging accommodation details for type: {existing.get('type')}")

        for field in ["price_per_week", "description"]:
            if new.get(field):
                logger.debug(f"Updating {field}")
                existing[field] = new[field]

        existing_supp = existing.get("supplements") or {}
        new_supp = new.get("supplements") or {}
        existing_supp.update(new_supp)
        existing["supplements"] = existing_supp
    except Exception as e:
        logger.error(f"Error in merge_accommodation_details for type {existing.get('type', 'unknown')}: {str(e)}")
        raise


def merge_location_details(existing: dict, new: dict):
    """Merge details of two location dictionaries"""
    try:
        logger.debug(f"Merging location details for {existing.get('city')}")

        if not existing.get("address") and new.get("address"):
            logger.debug("Adding missing address")
            existing["address"] = new["address"]

        # Ensure courses and accommodations are lists before merging
        if existing.get("courses") is None:
            existing["courses"] = []
        if new.get("courses") is None:
            new["courses"] = []
            
        try:
            existing["courses"] = merge_courses(existing["courses"], new["courses"])
        except Exception as e:
            logger.error(f"Error merging courses for location {existing.get('city')}: {str(e)}")
            raise
        
        # Ensure accommodations are lists
        if existing.get("accommodations") is None:
            existing["accommodations"] = []
        if new.get("accommodations") is None:
            new["accommodations"] = []
            
        try:
            existing["accommodations"] = merge_accommodations(existing["accommodations"], new["accommodations"])
        except Exception as e:
            logger.error(f"Error merging accommodations for location {existing.get('city')}: {str(e)}")
            raise

        # Handle the additional fees as a list
        existing_fees = existing.get("additional_fees") or []
        new_fees = new.get("additional_fees") or []
        
        if isinstance(existing_fees, dict):
            # Convert old dictionary format to new list format
            existing_fees = [{"name": k.lower().replace(" ", "_"), "price": v.replace("€", "").strip(), "currency": "EUR"} 
                             for k, v in existing_fees.items()]
            existing["additional_fees"] = existing_fees
        
        if isinstance(new_fees, dict):
            # Convert new dictionary format to new list format
            new_fees = [{"name": k.lower().replace(" ", "_"), "price": v.replace("€", "").strip(), "currency": "EUR"} 
                        for k, v in new_fees.items()]

        # Merge fees by name
        fee_dict = {fee["name"]: fee for fee in existing_fees}
        for new_fee in new_fees:
            fee_dict[new_fee["name"]] = new_fee
        
        existing["additional_fees"] = list(fee_dict.values())
    except Exception as e:
        logger.error(f"Error in merge_location_details for {existing.get('city', 'unknown')}: {str(e)}")
        raise


def merge_schools(school1: dict, school2: dict) -> dict:
    """Merge two school dictionaries into one"""
    logger.info("Merging schools")
    try:
        if not school1:
            logger.debug("First school empty, returning copy of second school")
            return copy.deepcopy(school2)

        merged = copy.deepcopy(school1)

        merged_terms = merged.get("terms") or {}
        merged_terms.update(school2.get("terms") or {})
        merged["terms"] = merged_terms

        # Ensure locations are lists
        if merged.get("locations") is None:
            merged["locations"] = []
        if school2.get("locations") is None:
            school2["locations"] = []
            
        try:
            merged["locations"] = merge_locations(merged["locations"], school2["locations"])
        except Exception as e:
            logger.error(f"Error merging locations for school: {str(e)}")
            raise
            
        return merged
    except Exception as e:
        logger.error(f"Error in merge_schools: {str(e)}")
        raise


def merge_locations(locations1: list, locations2: list) -> list:
    """Merge two lists of locations"""
    logger.info(f"Merging {len(locations1)} locations with {len(locations2)} locations")
    try:
        merged = copy.deepcopy(locations1)

        for loc2 in locations2:
            try:
                city = loc2.get('city', 'unknown')
                country = loc2.get('country', 'unknown')
                logger.debug(f"Processing location: {city}, {country}")
                
                existing = find_location(merged, city, country)
                if not existing:
                    logger.debug(f"New location found: {city}")
                    merged.append(copy.deepcopy(loc2))
                    continue
                merge_location_details(existing, loc2)
            except Exception as e:
                logger.error(f"Error processing location {loc2.get('city', 'unknown')}: {str(e)}")
                raise

        return merged
    except Exception as e:
        logger.error(f"Error in merge_locations: {str(e)}")
        raise


def find_location(locations: list, city: str, country: str) -> Optional[dict]:
    """Find a location in a list by city and country"""
    logger.debug(f"Finding location: {city}, {country}")
    return next(
        (l for l in locations if l["city"] == city and l["country"] == country), None
    )


def merge_courses(courses1: list, courses2: list) -> list:
    """Merge two lists of courses"""
    logger.info(f"Merging {len(courses1)} courses with {len(courses2)} courses")
    try:
        merged = copy.deepcopy(courses1)

        for course2 in courses2:
            try:
                name = course2.get('name', 'unknown')
                logger.debug(f"Processing course: {name}")
                existing = find_course(merged, name)
                if not existing:
                    logger.debug(f"New course found: {name}")
                    merged.append(copy.deepcopy(course2))
                    continue
                merge_course_details(existing, course2)
            except Exception as e:
                logger.error(f"Error processing course {course2.get('name', 'unknown')}: {str(e)}")
                raise

        return merged
    except Exception as e:
        logger.error(f"Error in merge_courses: {str(e)}")
        raise


def find_course(courses: list, name: str) -> Optional[dict]:
    """Find a course in a list by name"""
    logger.debug(f"Finding course: {name}")
    return next((c for c in courses if c["name"] == name), None)


def merge_course_details(existing: dict, new: dict):
    """Merge details of two course dictionaries"""
    try:
        logger.debug(f"Merging course details for: {existing.get('name')}")

        for field in ["lessons_per_week", "description", "requirements", "course_type", "age_range", "total_fee"]:
            if new.get(field):
                logger.debug(f"Updating {field}")
                existing[field] = new[field]

        # Ensure prices are lists
        if existing.get("prices") is None:
            existing["prices"] = []
        if new.get("prices") is None:
            new["prices"] = []
            
        try:
            existing["prices"] = merge_prices(existing["prices"], new["prices"])
        except Exception as e:
            logger.error(f"Error merging prices for course {existing.get('name', 'unknown')}: {str(e)}")
            raise
        
        # Calculate total_price if not present
        for price in existing["prices"]:
            if price.get("total_price") is None and price.get("price"):
                try:
                    # Extract numeric value and convert to float
                    price_str = price["price"].replace("€", "").replace(",", "").strip()
                    price_value = float(price_str)
                    price["total_price"] = price_value
                except (ValueError, TypeError):
                    pass
        
        # Calculate total_fee if not present but prices are available
        if existing.get("total_fee") is None and existing.get("prices") and existing["prices"]:
            try:
                # Use the first price's total_price as a base estimate
                if existing["prices"][0].get("total_price"):
                    existing["total_fee"] = existing["prices"][0]["total_price"]
                    
                    # Add registration fee if available in the location
                    if isinstance(existing.get("additional_fees"), list):
                        for fee in existing.get("additional_fees", []):
                            if fee.get("name") == "registration_fee" and fee.get("price"):
                                try:
                                    fee_value = float(fee["price"].replace("€", "").replace(",", "").strip())
                                    existing["total_fee"] += fee_value
                                except (ValueError, TypeError):
                                    pass
            except (IndexError, ValueError, TypeError):
                pass
    except Exception as e:
        logger.error(f"Error in merge_course_details for course {existing.get('name', 'unknown')}: {str(e)}")
        raise


def merge_prices(prices1: list, prices2: list) -> list:
    """Merge two lists of prices"""
    try:
        logger.debug("Merging price lists")
        if not prices1 and not prices2:
            return []
            
        merged = {}
        for p in prices1:
            if "duration" in p:
                merged[p["duration"]] = copy.deepcopy(p)
                
        for price in prices2:
            try:
                if "duration" in price:
                    merged[price["duration"]] = copy.deepcopy(price)
            except KeyError as e:
                logger.error(f"Missing required key in price: {e}. Price object: {price}")
                continue  # Skip this price but continue with others
            except Exception as e:
                logger.error(f"Error merging individual price {price}: {str(e)}")
                continue  # Skip this price but continue with others
                
        return list(merged.values())
    except Exception as e:
        logger.error(f"Error in merge_prices: {str(e)}")
        raise


def merge_accommodations(acc1: list, acc2: list) -> list:
    """Merge two lists of accommodations"""
    logger.info(f"Merging {len(acc1)} accommodations with {len(acc2)} accommodations")
    try:
        merged = copy.deepcopy(acc1)

        for acc in acc2:
            try:
                acc_type = acc.get('type', 'unknown')
                logger.debug(f"Processing accommodation type: {acc_type}")
                existing = find_accommodation(merged, acc_type)
                if not existing:
                    logger.debug(f"New accommodation type found: {acc_type}")
                    merged.append(copy.deepcopy(acc))
                    continue
                merge_accommodation_details(existing, acc)
            except Exception as e:
                logger.error(f"Error processing accommodation {acc.get('type', 'unknown')}: {str(e)}")
                raise

        return merged
    except Exception as e:
        logger.error(f"Error in merge_accommodations: {str(e)}")
        raise


def find_accommodation(accommodations: list, acc_type: str) -> Optional[dict]:
    """Find an accommodation in a list by type"""
    logger.debug(f"Finding accommodation type: {acc_type}")
    return next((a for a in accommodations if a["type"] == acc_type), None)


def merge_all_results(results: list) -> dict:
    """Merge all results from multiple pages into a single school dictionary"""
    logger.info(f"Starting merge of {len(results)} results")
    if not results:
        logger.warning("No results to merge")
        return {}

    merged = {}
    for i, result in enumerate(results):
        if result is None:
            logger.warning(f"Skipping None result at index {i}")
            continue
        
        logger.debug(f"Merging result {i+1}/{len(results)}")
        try:
            merged = merge_schools(merged, result)
        except Exception as e:
            logger.error(f"Error merging result {i+1}: {str(e)}")
            if isinstance(result, dict):
                logger.debug(f"Problematic result structure: dictionary with keys: {list(result.keys())}")
                # Try to extract and merge usable parts instead of skipping completely
                try:
                    if "name" in result and merged.get("name") is None:
                        merged["name"] = result["name"]
                    if "terms" in result and result["terms"]:
                        merged_terms = merged.get("terms") or {}
                        merged_terms.update(result.get("terms") or {})
                        merged["terms"] = merged_terms
                except Exception:
                    pass
            else:
                logger.debug(f"Problematic result is not a dict: {type(result)}")
            # Continue with next result rather than failing completely
            continue

    logger.info("Merge completed successfully")
    return merged
