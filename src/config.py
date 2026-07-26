import json
import os
import re
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

IATA_PATTERN = re.compile(r"^[A-Z]{3}$")


class CityStayRange(BaseModel):
    min: int = Field(..., ge=1)
    max: int = Field(..., ge=1)

    @model_validator(mode="after")
    def validate_range(self) -> "CityStayRange":
        if self.max < self.min:
            raise ValueError(f"max stay ({self.max}) cannot be less than min stay ({self.min})")
        return self


class TripSettings(BaseModel):
    home_city: str = Field(..., description="Home city IATA code (e.g. GVA)")
    destinations: List[str] = Field(..., description="List of 3 to 6 destination city IATA codes")
    start_date: str = Field(..., description="Departure date YYYY-MM-DD")
    stay_days_per_city: Optional[int] = Field(3, ge=1, description="Default stay days per city if min/max not specified")
    min_stay_days_per_city: Optional[int] = Field(2, ge=1, description="Minimum stay days per city")
    max_stay_days_per_city: Optional[int] = Field(4, ge=1, description="Maximum stay days per city")
    city_stay_overrides: Dict[str, CityStayRange] = Field(default_factory=dict, description="Custom per-city stay day constraints")
    preferred_departure_window: Optional[str] = Field("daytime", description="Preferred flight departure window: 'morning', 'afternoon', 'daytime'")
    max_departure_hour: Optional[int] = Field(19, ge=1, le=23, description="Latest allowed departure hour (e.g. 19 for 7:00 PM)")

    @field_validator("home_city")
    @classmethod
    def validate_home_city(cls, v: str) -> str:
        v_upper = v.strip().upper()
        if not IATA_PATTERN.match(v_upper):
            raise ValueError(f"Invalid home_city IATA code: '{v}'. Must be 3 uppercase letters.")
        return v_upper

    @field_validator("destinations")
    @classmethod
    def validate_destinations(cls, v: List[str]) -> List[str]:
        if not (3 <= len(v) <= 6):
            raise ValueError(f"Destinations count must be between 3 and 6. Got {len(v)}.")
        cleaned = []
        for city in v:
            city_upper = city.strip().upper()
            if not IATA_PATTERN.match(city_upper):
                raise ValueError(f"Invalid destination IATA code: '{city}'. Must be 3 uppercase letters.")
            cleaned.append(city_upper)
        return cleaned

    def get_stay_days_for_city(self, city_code: str) -> int:
        """Returns target stay days for a given city based on overrides or min/max/default settings."""
        code = city_code.upper()
        if code in self.city_stay_overrides:
            override = self.city_stay_overrides[code]
            return (override.min + override.max) // 2
        if self.min_stay_days_per_city is not None and self.max_stay_days_per_city is not None:
            return (self.min_stay_days_per_city + self.max_stay_days_per_city) // 2
        return self.stay_days_per_city or 3

    def get_stay_range_for_city(self, city_code: str) -> tuple[int, int]:
        """Returns (min_stay, max_stay) tuple for a given city code."""
        code = city_code.upper()
        if code in self.city_stay_overrides:
            override = self.city_stay_overrides[code]
            return (override.min, override.max)
        min_d = self.min_stay_days_per_city if self.min_stay_days_per_city is not None else (self.stay_days_per_city or 3)
        max_d = self.max_stay_days_per_city if self.max_stay_days_per_city is not None else (self.stay_days_per_city or 3)
        return (min_d, max_d)


class CostWeights(BaseModel):
    weight_time: float = Field(0.5, ge=0.0, le=1.0)
    weight_price: float = Field(0.3, ge=0.0, le=1.0)
    weight_geo_deviation: float = Field(0.2, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_sum(self) -> "CostWeights":
        total = self.weight_time + self.weight_price + self.weight_geo_deviation
        if abs(total - 1.0) > 1e-4:
            raise ValueError(f"Cost weights must sum to 1.0. Current sum: {total:.4f}")
        return self


class CacheSettings(BaseModel):
    cache_ttl_hours: int = Field(24, ge=0)
    cache_file: str = Field("cache/flight_cache.json")


class AppConfig(BaseModel):
    trip_settings: TripSettings
    cost_weights: CostWeights
    cache_settings: CacheSettings


def load_config(config_path: str = "config.json") -> AppConfig:
    """Loads configuration from JSON file."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return AppConfig(**data)
