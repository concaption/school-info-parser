"""
path: src/prompts.py
author: concaption
description: This script contains the system prompt used by the PDFParser class to request information from the OpenAI API.
"""

system_prompt = """Please analyze this image and extract the language school information. Focus on identifying:
- School name
- Location details
- Course information including:
  * Course type (Adult/Teenagers)
  * Age range requirements
  * Total fee (when available)
  * Number of lessons
  * Pricing
- Accommodation options
- Any terms or conditions

if there are more than one location, please provide information for all locations.
if there are more than one course, please provide information for all courses.
sometimes the information can also be in the file name or header/footer of the document, please include that as well.
make sure to include all the courses available, including the prices and any additional fees.
do not make any assumptions, only provide the information that is available in the document. skip any information that is not available.

For additional fees, use snake_case for the fee names and include the currency in ISO 4217 format.
For course prices, calculate and include the total_price in numeric format when possible.
Use standardized currency codes (EUR, USD, GBP, etc.) for all price fields.

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
                    "course_type": "Adult",
                    "age_range": "16+",
                    "total_fee": 455.0,
                    "lessons_per_week": 20,
                    "description": "Morning classes Mon-Fri",
                    "prices": [
                        {"duration": "2-4 weeks", "price": "€355", "currency": "EUR", "total_price": 355.0}
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
            "additional_fees": [
                {"name": "registration_fee", "price": "85", "currency": "EUR"},
                {"name": "course_materials", "price": "45", "currency": "EUR"}
            ]
        }
    ],
    "terms": {
        "cancellation": "14 days notice required"
    }
}

"""
