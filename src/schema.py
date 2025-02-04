
"""
path: src/schema.py
author: concaption
description: This script contains the Pydantic models used for data validation and serialization.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional

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
