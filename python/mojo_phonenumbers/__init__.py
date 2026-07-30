"""Phone number parsing and validation accelerated by Mojo."""

from ._metadata import UPSTREAM_VERSION
from .core import (
    CountryCodeSource,
    NumberParseException,
    PhoneNumber,
    PhoneNumberFormat,
    PhoneNumberType,
    ValidationResult,
    country_code_for_region,
    format_number,
    is_possible_number,
    is_possible_number_with_reason,
    is_valid_number,
    is_valid_number_for_region,
    national_significant_number,
    normalize_digits_only,
    number_type,
    parse,
    region_code_for_country_code,
    region_code_for_number,
)

__version__ = "0.1.0"

__all__ = [
    "CountryCodeSource",
    "NumberParseException",
    "PhoneNumber",
    "PhoneNumberFormat",
    "PhoneNumberType",
    "ValidationResult",
    "country_code_for_region",
    "format_number",
    "is_possible_number",
    "is_possible_number_with_reason",
    "is_valid_number",
    "is_valid_number_for_region",
    "national_significant_number",
    "normalize_digits_only",
    "number_type",
    "parse",
    "region_code_for_country_code",
    "region_code_for_number",
]
