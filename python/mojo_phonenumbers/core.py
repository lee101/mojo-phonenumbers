"""Upstream-compatible phone number objects, parsing, validation, and formatting."""

from __future__ import annotations

from functools import lru_cache
import re
import unicodedata

from . import _lib
from ._metadata import COUNTRY_CODE_TO_REGION, NON_GEO, REGIONS


class PhoneNumberFormat:
    E164 = 0
    INTERNATIONAL = 1
    NATIONAL = 2
    RFC3966 = 3


class PhoneNumberType:
    FIXED_LINE = 0
    MOBILE = 1
    FIXED_LINE_OR_MOBILE = 2
    TOLL_FREE = 3
    PREMIUM_RATE = 4
    SHARED_COST = 5
    VOIP = 6
    PERSONAL_NUMBER = 7
    PAGER = 8
    UAN = 9
    VOICEMAIL = 10
    UNKNOWN = 99


class ValidationResult:
    IS_POSSIBLE = 0
    INVALID_COUNTRY_CODE = 1
    TOO_SHORT = 2
    TOO_LONG = 3
    IS_POSSIBLE_LOCAL_ONLY = 4
    INVALID_LENGTH = 5


class CountryCodeSource:
    UNSPECIFIED = 0
    FROM_NUMBER_WITH_PLUS_SIGN = 1
    FROM_NUMBER_WITH_IDD = 5
    FROM_NUMBER_WITHOUT_PLUS_SIGN = 10
    FROM_DEFAULT_COUNTRY = 20


class NumberParseException(Exception):
    INVALID_COUNTRY_CODE = 0
    NOT_A_NUMBER = 1
    TOO_SHORT_AFTER_IDD = 2
    TOO_SHORT_NSN = 3
    TOO_LONG = 4

    def __init__(self, error_type, msg):
        super().__init__(msg)
        self.error_type = error_type
        self._msg = msg

    def __str__(self):
        return f"({self.error_type}) {self._msg}"


class PhoneNumber:
    def __init__(
        self,
        country_code=None,
        national_number=None,
        extension=None,
        italian_leading_zero=None,
        number_of_leading_zeros=None,
        raw_input=None,
        country_code_source=CountryCodeSource.UNSPECIFIED,
        preferred_domestic_carrier_code=None,
    ):
        self.country_code = None if country_code is None else int(country_code)
        self.national_number = (
            None if national_number is None else int(national_number)
        )
        self.extension = None if extension is None else str(extension)
        self.italian_leading_zero = (
            None if italian_leading_zero is None else bool(italian_leading_zero)
        )
        self.number_of_leading_zeros = (
            None if number_of_leading_zeros is None else int(number_of_leading_zeros)
        )
        self.raw_input = None if raw_input is None else str(raw_input)
        self.country_code_source = (
            CountryCodeSource.UNSPECIFIED
            if country_code_source is None
            else country_code_source
        )
        self.preferred_domestic_carrier_code = (
            None
            if preferred_domestic_carrier_code is None
            else str(preferred_domestic_carrier_code)
        )

    def clear(self):
        self.__init__()

    def merge_from(self, other):
        for field in (
            "country_code",
            "national_number",
            "extension",
            "italian_leading_zero",
            "number_of_leading_zeros",
            "raw_input",
            "preferred_domestic_carrier_code",
        ):
            value = getattr(other, field)
            if value is not None:
                setattr(self, field, value)
        if other.country_code_source != CountryCodeSource.UNSPECIFIED:
            self.country_code_source = other.country_code_source

    def __eq__(self, other):
        return isinstance(other, PhoneNumber) and (
            self.country_code,
            self.national_number,
            self.extension,
            bool(self.italian_leading_zero),
            self.number_of_leading_zeros,
            self.raw_input,
            self.country_code_source,
            self.preferred_domestic_carrier_code,
        ) == (
            other.country_code,
            other.national_number,
            other.extension,
            bool(other.italian_leading_zero),
            other.number_of_leading_zeros,
            other.raw_input,
            other.country_code_source,
            other.preferred_domestic_carrier_code,
        )

    def __repr__(self):
        return (
            f"PhoneNumber(country_code={self.country_code}, "
            f"national_number={self.national_number}, extension={self.extension!r}, "
            f"italian_leading_zero={self.italian_leading_zero}, "
            f"number_of_leading_zeros={self.number_of_leading_zeros}, "
            f"country_code_source={self.country_code_source}, "
            "preferred_domestic_carrier_code="
            f"{self.preferred_domestic_carrier_code!r})"
        )

    def __str__(self):
        text = (
            f"Country Code: {self.country_code} National Number: "
            f"{self.national_number}"
        )
        if self.italian_leading_zero is not None:
            text += f" Leading Zero(s): {self.italian_leading_zero}"
        if self.number_of_leading_zeros is not None:
            text += f" Number of leading zeros: {self.number_of_leading_zeros}"
        if self.extension is not None:
            text += f" Extension: {self.extension}"
        return text


_TYPE_DESCRIPTION = {
    PhoneNumberType.PREMIUM_RATE: "premium_rate",
    PhoneNumberType.TOLL_FREE: "toll_free",
    PhoneNumberType.SHARED_COST: "shared_cost",
    PhoneNumberType.VOIP: "voip",
    PhoneNumberType.PERSONAL_NUMBER: "personal_number",
    PhoneNumberType.PAGER: "pager",
    PhoneNumberType.UAN: "uan",
    PhoneNumberType.VOICEMAIL: "voicemail",
    PhoneNumberType.FIXED_LINE: "fixed_line",
    PhoneNumberType.MOBILE: "mobile",
}
_TYPE_ORDER = (
    PhoneNumberType.PREMIUM_RATE,
    PhoneNumberType.TOLL_FREE,
    PhoneNumberType.SHARED_COST,
    PhoneNumberType.VOIP,
    PhoneNumberType.PERSONAL_NUMBER,
    PhoneNumberType.PAGER,
    PhoneNumberType.UAN,
    PhoneNumberType.VOICEMAIL,
)
_EXTENSION = re.compile(
    r"(?:;ext=|ext(?:ension|n)?\.?|x|#)\s*[:.]?\s*(\d{1,20})\s*$", re.I
)
_PHONE_CONTEXT = re.compile(r";phone-context=([^;]+)", re.I)
_CANDIDATE_START = re.compile(r"[+＋\d(（]")
_PLUS_PREFIX = re.compile(r"^\s*[+＋]")
_RFC3966_LEADING = re.compile(r"^[^\d]+")
_RFC3966_SEPARATOR = re.compile(r"[^\d]+")


@lru_cache(maxsize=None)
def _compiled(pattern):
    return re.compile(pattern)


def _ascii_normalize(number, map_alpha=False):
    try:
        return _lib.normalize_ascii(number, map_alpha)
    except UnicodeEncodeError:
        pieces = []
        for char in number:
            try:
                pieces.append(str(unicodedata.decimal(char)))
            except (TypeError, ValueError):
                if char.isascii():
                    pieces.append(char)
        return _lib.normalize_ascii("".join(pieces), map_alpha)


def normalize_digits_only(number, keep_non_digits=False):
    if number is None:
        return ""
    if keep_non_digits:
        result = []
        for char in str(number):
            try:
                result.append(str(unicodedata.decimal(char)))
            except (TypeError, ValueError):
                result.append(char)
        return "".join(result)
    return _ascii_normalize(str(number), False)


def _normalize_for_parse(number):
    alpha_count = sum(char.isalpha() and char.isascii() for char in number)
    return _ascii_normalize(number, alpha_count >= 3)


def _metadata_for_region(region):
    if region == "001":
        return None
    return REGIONS.get(region)


def _metadata_for_code_region(country_code, region=None):
    if region == "001":
        return NON_GEO.get(country_code)
    if region:
        return REGIONS.get(region)
    regions = COUNTRY_CODE_TO_REGION.get(country_code)
    if not regions:
        return None
    if regions[0] == "001":
        return NON_GEO.get(country_code)
    return REGIONS[regions[0]]


def _matches(number, description):
    return bool(
        description
        and description[0]
        and _compiled(description[0]).fullmatch(number)
    )


def _general_matches(number, metadata):
    return _matches(number, metadata["descriptions"]["general_desc"])


def _strip_national_prefix(number, metadata):
    pattern = metadata["national_prefix_for_parsing"]
    if not pattern:
        return "", number, False
    compiled = _compiled(pattern)
    match = compiled.match(number)
    if not match:
        return "", number, False
    original_valid = _general_matches(number, metadata)
    transform = metadata["national_prefix_transform_rule"]
    if transform and match.groups() and match.groups()[-1] is not None:
        transformed = compiled.sub(transform, number, count=1)
    else:
        transformed = number[match.end() :]
    if original_valid and not _general_matches(transformed, metadata):
        return "", number, False
    carrier = match.group(1) if match.groups() else ""
    return carrier or "", transformed, True


def _extract_candidate(number):
    phone_context = _PHONE_CONTEXT.search(number)
    if phone_context:
        context = phone_context.group(1)
        start = 4 if number.lower().startswith("tel:") else 0
        local = number[start : phone_context.start()]
        number = (context if context.startswith("+") else "") + local
    else:
        if number.lower().startswith("tel:"):
            number = number[4:]
        start = _CANDIDATE_START.search(number)
        number = number[start.start() :] if start else ""
    number = number.split(";isub=", 1)[0]
    number = number.rstrip()
    while number and not (number[-1].isalnum() or number[-1] == "#"):
        number = number[:-1]
    return number


def _extract_country_code(digits):
    for size in (1, 2, 3):
        if len(digits) >= size:
            code = int(digits[:size])
            if code in COUNTRY_CODE_TO_REGION:
                return code, digits[size:]
    return 0, digits


def parse(
    number,
    region=None,
    keep_raw_input=False,
    numobj=None,
    _check_region=True,
    _use_cache=True,
):
    if (
        _use_cache
        and numobj is None
        and not keep_raw_input
        and _check_region
        and number is not None
        and (region is None or isinstance(region, str))
    ):
        values = _parse_cached(str(number), region)
        return PhoneNumber(
            country_code=values[0],
            national_number=values[1],
            extension=values[2],
            italian_leading_zero=values[3],
            number_of_leading_zeros=values[4],
        )
    if numobj is None:
        numobj = PhoneNumber()
    else:
        numobj.clear()
    if number is None:
        raise NumberParseException(
            NumberParseException.NOT_A_NUMBER, "The phone number supplied was None."
        )
    number = str(number)
    if len(number) > 250:
        raise NumberParseException(
            NumberParseException.TOO_LONG,
            "The string supplied was too long to parse.",
        )
    candidate = _extract_candidate(number)
    extension_match = _EXTENSION.search(candidate)
    if extension_match:
        numobj.extension = normalize_digits_only(extension_match.group(1))
        candidate = candidate[: extension_match.start()]
    digits = _normalize_for_parse(candidate)
    if len(digits) < 2:
        raise NumberParseException(
            NumberParseException.NOT_A_NUMBER,
            "The string supplied did not seem to be a phone number.",
        )
    normalized_region = region.upper() if region is not None else None
    metadata = _metadata_for_region(normalized_region) if normalized_region else None
    has_plus = bool(_PLUS_PREFIX.match(candidate))
    source = CountryCodeSource.FROM_DEFAULT_COUNTRY
    international_digits = digits
    if not has_plus and metadata:
        idd = metadata["international_prefix"]
        idd_match = _compiled(idd).match(digits) if idd else None
        if idd_match:
            international_digits = digits[idd_match.end() :]
            source = CountryCodeSource.FROM_NUMBER_WITH_IDD
        else:
            international_digits = ""
    elif has_plus:
        source = CountryCodeSource.FROM_NUMBER_WITH_PLUS_SIGN
    elif _check_region and metadata is None:
        raise NumberParseException(
            NumberParseException.INVALID_COUNTRY_CODE,
            "Missing or invalid default region.",
        )

    if has_plus or international_digits:
        if len(international_digits) <= 2:
            raise NumberParseException(
                NumberParseException.TOO_SHORT_AFTER_IDD,
                "Phone number had an IDD, but was too short.",
            )
        country_code, national = _extract_country_code(international_digits)
        if not country_code:
            raise NumberParseException(
                NumberParseException.INVALID_COUNTRY_CODE,
                "Country calling code supplied was not recognised.",
            )
        regions = COUNTRY_CODE_TO_REGION[country_code]
        metadata = _metadata_for_code_region(country_code, regions[0])
    else:
        country_code = metadata["country_code"]
        national = digits
        code_text = str(country_code)
        if national.startswith(code_text):
            potential = national[len(code_text) :]
            _, stripped_potential, _ = _strip_national_prefix(potential, metadata)
            if (
                not _general_matches(national, metadata)
                and _general_matches(stripped_potential, metadata)
            ) or is_too_long(national, metadata):
                national = stripped_potential
                source = CountryCodeSource.FROM_NUMBER_WITHOUT_PLUS_SIGN

    carrier, potential, stripped = _strip_national_prefix(national, metadata)
    if stripped:
        desc = metadata["descriptions"]["general_desc"]
        reason = _lib.possible_length(len(potential), desc[1], desc[2])
        if reason not in (
            ValidationResult.TOO_SHORT,
            ValidationResult.IS_POSSIBLE_LOCAL_ONLY,
            ValidationResult.INVALID_LENGTH,
        ):
            national = potential
            if keep_raw_input and carrier:
                numobj.preferred_domestic_carrier_code = carrier
    if len(national) < 2:
        raise NumberParseException(
            NumberParseException.TOO_SHORT_NSN,
            "The string supplied is too short to be a phone number.",
        )
    if len(national) > 17:
        raise NumberParseException(
            NumberParseException.TOO_LONG,
            "The string supplied is too long to be a phone number.",
        )
    leading_zeros = len(national) - len(national.lstrip("0"))
    numobj.country_code = country_code
    numobj.national_number = int(national)
    if leading_zeros:
        numobj.italian_leading_zero = True
        if leading_zeros > 1:
            numobj.number_of_leading_zeros = leading_zeros
    if keep_raw_input:
        numobj.raw_input = number
        numobj.country_code_source = source
    return numobj


@lru_cache(maxsize=4096)
def _parse_cached(number, region):
    parsed = parse(number, region, _use_cache=False)
    return (
        parsed.country_code,
        parsed.national_number,
        parsed.extension,
        parsed.italian_leading_zero,
        parsed.number_of_leading_zeros,
    )


def is_too_long(number, metadata):
    lengths = metadata["descriptions"]["general_desc"][1]
    return bool(lengths and len(number) > lengths[-1])


def national_significant_number(numobj):
    zeros = ""
    if numobj.italian_leading_zero:
        zeros = "0" * (numobj.number_of_leading_zeros or 1)
    return zeros + str(numobj.national_number)


def region_code_for_country_code(country_code):
    regions = COUNTRY_CODE_TO_REGION.get(country_code)
    return regions[0] if regions else "ZZ"


def country_code_for_region(region_code):
    metadata = REGIONS.get(region_code.upper()) if region_code else None
    return metadata["country_code"] if metadata else 0


def region_code_for_number(numobj):
    regions = COUNTRY_CODE_TO_REGION.get(numobj.country_code)
    if not regions:
        return None
    if len(regions) == 1:
        return regions[0]
    national = national_significant_number(numobj)
    for region in regions:
        metadata = _metadata_for_code_region(numobj.country_code, region)
        leading = metadata["leading_digits"]
        if leading and _compiled(leading).match(national):
            return region
        if not leading and _number_type(national, metadata) != PhoneNumberType.UNKNOWN:
            return region
    return None


def _number_type(national, metadata):
    descriptions = metadata["descriptions"]
    if not _matches(national, descriptions["general_desc"]):
        return PhoneNumberType.UNKNOWN
    for number_kind in _TYPE_ORDER:
        if _matches(national, descriptions[_TYPE_DESCRIPTION[number_kind]]):
            return number_kind
    fixed = _matches(national, descriptions["fixed_line"])
    mobile = _matches(national, descriptions["mobile"])
    if fixed:
        if metadata["same_mobile_and_fixed_line_pattern"] or mobile:
            return PhoneNumberType.FIXED_LINE_OR_MOBILE
        return PhoneNumberType.FIXED_LINE
    if mobile and not metadata["same_mobile_and_fixed_line_pattern"]:
        return PhoneNumberType.MOBILE
    return PhoneNumberType.UNKNOWN


@lru_cache(maxsize=4096)
def _number_type_for_values(country_code, national):
    regions = COUNTRY_CODE_TO_REGION.get(country_code)
    if not regions:
        return PhoneNumberType.UNKNOWN
    if len(regions) == 1:
        metadata = _metadata_for_code_region(country_code, regions[0])
        return _number_type(national, metadata)
    for region in regions:
        metadata = _metadata_for_code_region(country_code, region)
        leading = metadata["leading_digits"]
        if leading:
            if _compiled(leading).match(national):
                return _number_type(national, metadata)
            continue
        result = _number_type(national, metadata)
        if result != PhoneNumberType.UNKNOWN:
            return result
    return PhoneNumberType.UNKNOWN


def number_type(numobj):
    return _number_type_for_values(
        numobj.country_code, national_significant_number(numobj)
    )


def is_valid_number(numobj):
    return number_type(numobj) != PhoneNumberType.UNKNOWN


def is_valid_number_for_region(numobj, region_code):
    if region_code is None:
        return False
    region = region_code.upper()
    metadata = _metadata_for_code_region(numobj.country_code, region)
    if metadata is None:
        return False
    if region != "001" and metadata["country_code"] != numobj.country_code:
        return False
    return (
        _number_type(national_significant_number(numobj), metadata)
        != PhoneNumberType.UNKNOWN
    )


def is_possible_number_with_reason(numobj):
    metadata = _metadata_for_code_region(numobj.country_code)
    if metadata is None:
        return ValidationResult.INVALID_COUNTRY_CODE
    description = metadata["descriptions"]["general_desc"]
    return _lib.possible_length(
        len(national_significant_number(numobj)), description[1], description[2]
    )


def is_possible_number(numobj):
    return is_possible_number_with_reason(numobj) in (
        ValidationResult.IS_POSSIBLE,
        ValidationResult.IS_POSSIBLE_LOCAL_ONLY,
    )


def _format_national(national, metadata, number_format):
    formats = (
        metadata["number_formats"]
        if number_format == PhoneNumberFormat.NATIONAL
        or not metadata["intl_number_formats"]
        else metadata["intl_number_formats"]
    )
    for pattern, replacement, leading, prefix_rule, _, _ in formats:
        if leading and not _compiled(leading[-1]).match(national):
            continue
        compiled = _compiled(pattern)
        if not compiled.fullmatch(national):
            continue
        if number_format == PhoneNumberFormat.NATIONAL and prefix_rule:
            replacement = replacement.replace(r"\1", prefix_rule, 1)
        formatted = compiled.sub(replacement, national)
        if number_format == PhoneNumberFormat.RFC3966:
            formatted = _RFC3966_LEADING.sub("", formatted)
            formatted = _RFC3966_SEPARATOR.sub("-", formatted)
        return formatted
    return national


@lru_cache(maxsize=4096)
def _format_national_cached(national, country_code, number_format):
    metadata = _metadata_for_code_region(country_code)
    if metadata is None:
        return national
    return _format_national(national, metadata, number_format)


@lru_cache(maxsize=4096)
def _format_number_for_values(country_code, national, extension_value, num_format):
    if num_format == PhoneNumberFormat.E164:
        return f"+{country_code}{national}"
    metadata = _metadata_for_code_region(country_code)
    if metadata is None:
        return national
    formatted = _format_national_cached(national, country_code, num_format)
    extension = ""
    if extension_value:
        if num_format == PhoneNumberFormat.RFC3966:
            extension = f";ext={extension_value}"
        else:
            prefix = metadata["preferred_extn_prefix"] or " ext. "
            extension = prefix + extension_value
    if num_format == PhoneNumberFormat.NATIONAL:
        return formatted + extension
    if num_format == PhoneNumberFormat.RFC3966:
        return f"tel:+{country_code}-{formatted}{extension}"
    return f"+{country_code} {formatted}{extension}"


def format_number(numobj, num_format):
    return _format_number_for_values(
        numobj.country_code,
        national_significant_number(numobj),
        numobj.extension,
        num_format,
    )
