import logging
import copy
from typing import Optional

def setup_logging():
   """Configure and return a logger instance"""
   logger = logging.getLogger('merger')
   logger.setLevel(logging.INFO)
   
   console = logging.StreamHandler()
   console.setLevel(logging.INFO)
   
   file_handler = logging.FileHandler('merger.log')
   file_handler.setLevel(logging.INFO)
   
   formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
   console.setFormatter(formatter)
   file_handler.setFormatter(formatter)
   
   logger.addHandler(console)
   logger.addHandler(file_handler)
   
   return logger

logger = setup_logging()

def merge_accommodation_details(existing: dict, new: dict):
   """Merge details of two accommodation dictionaries"""
   logger.debug(f"Merging accommodation details for type: {existing.get('type')}")
   
   for field in ['price_per_week', 'description']:
       if new.get(field):
           logger.debug(f"Updating {field}")
           existing[field] = new[field]
   
   existing_supp = existing.get('supplements') or {}
   new_supp = new.get('supplements') or {}
   existing_supp.update(new_supp)
   existing['supplements'] = existing_supp

def merge_location_details(existing: dict, new: dict):
   """Merge details of two location dictionaries"""
   logger.debug(f"Merging location details for {existing.get('city')}")
   
   if not existing.get('address') and new.get('address'):
       logger.debug("Adding missing address")
       existing['address'] = new['address']
   
   existing['courses'] = merge_courses(existing.get('courses', []), new.get('courses', []))
   existing['accommodations'] = merge_accommodations(
       existing.get('accommodations', []), 
       new.get('accommodations', [])
   )
   
   existing_fees = existing.get('additional_fees') or {}
   new_fees = new.get('additional_fees') or {}
   existing_fees.update(new_fees)
   existing['additional_fees'] = existing_fees

def merge_schools(school1: dict, school2: dict) -> dict:
   """Merge two school dictionaries into one"""
   logger.info("Merging schools")
   if not school1:
       logger.debug("First school empty, returning copy of second school")
       return copy.deepcopy(school2)
   
   merged = copy.deepcopy(school1)
   
   merged_terms = merged.get('terms') or {}
   merged_terms.update(school2.get('terms') or {})
   merged['terms'] = merged_terms

   merged['locations'] = merge_locations(merged.get('locations', []), school2.get('locations', []))
   return merged

def merge_locations(locations1: list, locations2: list) -> list:
   """Merge two lists of locations"""
   logger.info(f"Merging {len(locations1)} locations with {len(locations2)} locations")
   merged = copy.deepcopy(locations1)
   
   for loc2 in locations2:
       logger.debug(f"Processing location: {loc2['city']}, {loc2['country']}")
       existing = find_location(merged, loc2['city'], loc2['country'])
       if not existing:
           logger.debug(f"New location found: {loc2['city']}")
           merged.append(copy.deepcopy(loc2))
           continue
       merge_location_details(existing, loc2)
   
   return merged

def find_location(locations: list, city: str, country: str) -> Optional[dict]:
   """Find a location in a list by city and country"""
   logger.debug(f"Finding location: {city}, {country}")
   return next(
       (l for l in locations if l['city'] == city and l['country'] == country),
       None
   )

def merge_courses(courses1: list, courses2: list) -> list:
   """Merge two lists of courses"""
   logger.info(f"Merging {len(courses1)} courses with {len(courses2)} courses")
   merged = copy.deepcopy(courses1)
   
   for course2 in courses2:
       logger.debug(f"Processing course: {course2['name']}")
       existing = find_course(merged, course2['name'])
       if not existing:
           logger.debug(f"New course found: {course2['name']}")
           merged.append(copy.deepcopy(course2))
           continue
       merge_course_details(existing, course2)
   
   return merged

def find_course(courses: list, name: str) -> Optional[dict]:
   """Find a course in a list by name"""
   logger.debug(f"Finding course: {name}")
   return next((c for c in courses if c['name'] == name), None)

def merge_course_details(existing: dict, new: dict):
   """Merge details of two course dictionaries"""
   logger.debug(f"Merging course details for: {existing.get('name')}")
   
   for field in ['lessons_per_week', 'description', 'requirements']:
       if new.get(field):
           logger.debug(f"Updating {field}")
           existing[field] = new[field]
   
   existing['prices'] = merge_prices(existing.get('prices', []), new.get('prices', []))

def merge_prices(prices1: list, prices2: list) -> list:
   """Merge two lists of prices"""
   logger.debug("Merging price lists")
   merged = {p['duration']: copy.deepcopy(p) for p in prices1}
   for price in prices2:
       merged[price['duration']] = copy.deepcopy(price)
   return list(merged.values())

def merge_accommodations(acc1: list, acc2: list) -> list:
   """Merge two lists of accommodations"""
   logger.info(f"Merging {len(acc1)} accommodations with {len(acc2)} accommodations")
   merged = copy.deepcopy(acc1)
   
   for acc in acc2:
       logger.debug(f"Processing accommodation type: {acc['type']}")
       existing = find_accommodation(merged, acc['type'])
       if not existing:
           logger.debug(f"New accommodation type found: {acc['type']}")
           merged.append(copy.deepcopy(acc))
           continue
       merge_accommodation_details(existing, acc)
   
   return merged

def find_accommodation(accommodations: list, acc_type: str) -> Optional[dict]:
   """Find an accommodation in a list by type"""
   logger.debug(f"Finding accommodation type: {acc_type}")
   return next((a for a in accommodations if a['type'] == acc_type), None)

def merge_all_results(results: list) -> dict:
   """Merge all results from multiple pages into a single school dictionary"""
   logger.info(f"Starting merge of {len(results)} results")
   if not results:
       logger.warning("No results to merge")
       return {}
   
   merged = {}
   for i, result in enumerate(results):
       logger.debug(f"Merging result {i+1}/{len(results)}")
       merged = merge_schools(merged, result)
   
   logger.info("Merge completed successfully")
   return merged