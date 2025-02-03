import copy


def merge_accommodation_details(existing: dict, new: dict):
    """Merge details of two accommodation dictionaries"""
    # Update scalar fields
    for field in ['price_per_week', 'description']:
        if new.get(field):
            existing[field] = new[field]
    
    # Handle None values for supplements
    existing_supp = existing.get('supplements') or {}
    new_supp = new.get('supplements') or {}
    existing_supp.update(new_supp)
    existing['supplements'] = existing_supp

def merge_location_details(existing: dict, new: dict):
    """Merge details of two location dictionaries"""
    # Update address if missing
    if not existing.get('address') and new.get('address'):
        existing['address'] = new['address']
    
    # Merge courses
    existing['courses'] = merge_courses(existing.get('courses', []), new.get('courses', []))
    
    # Merge accommodations
    existing['accommodations'] = merge_accommodations(
        existing.get('accommodations', []),
        new.get('accommodations', [])
    )
    
    # Merge additional fees (handle None values)
    existing_fees = existing.get('additional_fees') or {}
    new_fees = new.get('additional_fees') or {}
    existing_fees.update(new_fees)
    existing['additional_fees'] = existing_fees

def merge_schools(school1: dict, school2: dict) -> dict:
    """Merge two school dictionaries into one"""
    if not school1:
        return copy.deepcopy(school2)
    
    merged = copy.deepcopy(school1)
    
    # Merge terms (handle None values)
    merged_terms = merged.get('terms') or {}
    merged_terms.update(school2.get('terms') or {})
    merged['terms'] = merged_terms

    # Merge locations
    merged['locations'] = merge_locations(merged.get('locations', []), school2.get('locations', []))
    
    return merged


def merge_locations(locations1: list, locations2: list) -> list:
    """Merge two lists of locations"""
    merged = copy.deepcopy(locations1)
    
    for loc2 in locations2:
        existing = find_location(merged, loc2['city'], loc2['country'])
        if not existing:
            merged.append(copy.deepcopy(loc2))
            continue
        
        # Merge location details
        merge_location_details(existing, loc2)
    
    return merged

def find_location(locations: list, city: str, country: str) -> Optional[dict]:
    """Find a location in a list by city and country"""
    return next(
        (l for l in locations if l['city'] == city and l['country'] == country),
        None
    )


def merge_courses(courses1: list, courses2: list) -> list:
    """Merge two lists of courses"""
    merged = copy.deepcopy(courses1)
    
    for course2 in courses2:
        existing = find_course(merged, course2['name'])
        if not existing:
            merged.append(copy.deepcopy(course2))
            continue
        
        # Update course details
        merge_course_details(existing, course2)
    
    return merged

def find_course(courses: list, name: str) -> Optional[dict]:
    """Find a course in a list by name"""
    return next((c for c in courses if c['name'] == name), None)

def merge_course_details(existing: dict, new: dict):
    """Merge details of two course dictionaries"""
    # Update scalar fields
    for field in ['lessons_per_week', 'description', 'requirements']:
        if new.get(field):
            existing[field] = new[field]
    
    # Merge prices
    existing['prices'] = merge_prices(existing.get('prices', []), new.get('prices', []))

def merge_prices(prices1: list, prices2: list) -> list:
    """Merge two lists of prices"""
    merged = {p['duration']: copy.deepcopy(p) for p in prices1}
    for price in prices2:
        merged[price['duration']] = copy.deepcopy(price)
    return list(merged.values())

def merge_accommodations(acc1: list, acc2: list) -> list:
    """Merge two lists of accommodations"""
    merged = copy.deepcopy(acc1)
    
    for acc in acc2:
        existing = find_accommodation(merged, acc['type'])
        if not existing:
            merged.append(copy.deepcopy(acc))
            continue
        
        # Update accommodation details
        merge_accommodation_details(existing, acc)
    
    return merged

def find_accommodation(accommodations: list, acc_type: str) -> Optional[dict]:
    """Find an accommodation in a list by type"""
    return next((a for a in accommodations if a['type'] == acc_type), None)

def merge_all_results(results: list) -> dict:
    """Merge all results from multiple pages into a single school dictionary"""
    if not results:
        return {}
    
    merged = {}
    for result in results:
        merged = merge_schools(merged, result)
