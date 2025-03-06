"""
path: src/schema.py
author: concaption
description: This script contains the Pydantic models used for data validation and serialization.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional


class Price(BaseModel):
    duration: str = Field(..., description="Duration of the course")
    description: Optional[str] = Field(None, description="Description of the duration")
    price: float = Field(..., description="Price of the course")
    currency: str = Field(..., description="Currency of the price in ISO 4217 format (e.g., 'EUR', 'USD')")


class Fee(BaseModel):
    fee_type: str = Field(..., description="Type of the fee (e.g. registration, material, exam, insurance, miscellaneous etc.) in snake_case format")
    description: Optional[str] = Field(None, description="Description of the fee")
    price: float = Field(..., description="Price of the fee")
    currency: str = Field(..., description="Currency of the price in ISO 4217 format (e.g., 'EUR', 'USD')")


class Course(BaseModel):
    name: str = Field(..., description="Name of the course")
    course_type: str = Field(..., description="Type of course (Adult/Teenagers). Use 'Adult' for courses that are suitable for both adults and teenagers.")
    min_age: int = Field(..., description="Minimum age requirement for the course")
    max_age: Optional[int] = Field(None, description="Maximum age limit for the course (None if no upper limit)")
    age_range_display: str = Field(None, description="Formatted age range string for display (e.g., '16+', '12-17')")
    lessons_per_week: int = Field(..., description="Number of lessons per week")
    course_intensity: str = Field(..., description="Simple orignal course name with number of lessons per week (e.g., 'General English - 20'). No need for additional categorization like Standard or Intensive.")
    description: Optional[str] = Field(..., description="Course description")
    prices: List[Price] = Field(..., description="List of prices for the course")
    requirements: Optional[str] = Field(None, description="Course requirements")
    additional_fees: Optional[List[Fee]] = Field(default_factory=list, description="Additional fees")

class FoodSupplement(BaseModel):
    name: str = Field(..., description="Name of the food supplement")
    description: Optional[str] = Field(None, description="Description of the food supplement")
    price_per_week: float = Field(..., description="Weekly price of the food supplement")
    currency: str = Field(..., description="Currency of the price in ISO 4217 format (e.g., 'EUR', 'USD')")
    meals_per_week: int = Field(..., description="Number of meals per week")
    meal_type: str = Field(..., description="Type of meal (e.g. gluten_free, vegetarian, vegan, halal, kosher, lactose_free etc.) in snake_case format")

class Accommodation(BaseModel):
    name: str = Field(..., description="Name of the accommodation")
    description: str = Field(..., description="Accommodation description")
    type: str = Field(..., description="Type of accommodation (e.g., host_family, residence, apartment, hotel, homestay etc.) in snake_case format")
    price_per_week: float = Field(..., description="Weekly price of accommodation")
    currency: str = Field(..., description="Currency of the price in ISO 4217 format (e.g., 'EUR', 'USD')")
    food_suplements: Optional[List[FoodSupplement]] = Field(default_factory=list, description="List of food supplements")

class Supplement(BaseModel):
    name: str = Field(..., description="Name of the supplement")
    description: Optional[str] = Field(None, description="Description of the supplement")
    type: str = Field(..., description="Type of supplement (e.g., airport_transfer, insurance, visa_support, activities etc.) in snake_case format")
    price_per_week: float = Field(..., description="Weekly price of the supplement")
    currency: str = Field(..., description="Currency of the price in ISO 4217 format (e.g., 'EUR', 'USD')")


class Location(BaseModel):
    city: str = Field(..., description="City where the school is located in English")
    country: str = Field(...,description="Country where the school is located in ISO 3166-1 alpha-2 format. UK should be represented as 'GB'")
    address: str = Field(..., description="Address of the school")
    courses: List[Course] = Field(..., description="List of available courses")
    accommodations: List[Accommodation] = Field(..., description="List of accommodations")
    suplements: Optional[List[Supplement]] = Field(default_factory=list, description="List of supplements")
    additional_fees: Optional[List[Fee]] = Field(default_factory=list, description="Additional fees")


class School(BaseModel):
    name: str = Field(..., description="Name of the school")
    locations: List[Location] = Field(..., description="List of locations where the school operates")
    terms: Optional[Dict[str, str]] = Field(default_factory=dict, description="Terms and conditions")
    repeat: Optional[bool] = Field(description="If there are more courses available but can not fit in one response, set this flag to true")