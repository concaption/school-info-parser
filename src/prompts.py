"""
path: src/prompts.py
author: concaption
description: This script contains the system prompt used by the PDFParser class to request information from the OpenAI API.
"""

system_prompt = """Please analyze this image and extract the language school information. Focus on identifying:
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
