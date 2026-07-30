"""Behavioral parity with python-phonenumbers 9.0 metadata."""

import pytest

import mojo_phonenumbers as mojo
import phonenumbers as upstream
from mojo_phonenumbers._metadata import NON_GEO, REGIONS


VALID_VECTORS = (
    ("+1 650-253-0000", None, "US", upstream.PhoneNumberType.FIXED_LINE_OR_MOBILE),
    ("(650) 253-0000", "US", "US", upstream.PhoneNumberType.FIXED_LINE_OR_MOBILE),
    ("+44 20 7031 3000", None, "GB", upstream.PhoneNumberType.FIXED_LINE),
    ("020 7031 3000", "GB", "GB", upstream.PhoneNumberType.FIXED_LINE),
    ("+33 1 42 68 53 00", None, "FR", upstream.PhoneNumberType.FIXED_LINE),
    ("01 42 68 53 00", "FR", "FR", upstream.PhoneNumberType.FIXED_LINE),
    ("+39 02 36618 300", None, "IT", upstream.PhoneNumberType.FIXED_LINE),
    ("+91 98765 43210", None, "IN", upstream.PhoneNumberType.MOBILE),
    ("+81 90-1234-5678", None, "JP", upstream.PhoneNumberType.MOBILE),
    ("+55 11 96123-4567", None, "BR", upstream.PhoneNumberType.MOBILE),
    ("1-800-FLOWERS", "US", "US", upstream.PhoneNumberType.TOLL_FREE),
)


@pytest.mark.parametrize("raw,region,expected_region,expected_type", VALID_VECTORS)
def test_published_and_common_vectors(raw, region, expected_region, expected_type):
    ours = mojo.parse(raw, region)
    theirs = upstream.parse(raw, region)
    assert ours.country_code == theirs.country_code
    assert mojo.national_significant_number(ours) == upstream.national_significant_number(
        theirs
    )
    assert mojo.region_code_for_number(ours) == expected_region
    assert mojo.number_type(ours) == expected_type
    assert mojo.is_possible_number(ours) == upstream.is_possible_number(theirs)
    assert mojo.is_valid_number(ours) == upstream.is_valid_number(theirs)


def test_all_upstream_examples_parse_validate_and_classify():
    compared = 0
    for region in sorted(upstream.SUPPORTED_REGIONS):
        for number_kind in range(11):
            theirs = upstream.example_number_for_type(region, number_kind)
            if theirs is None:
                continue
            raw = upstream.format_number(theirs, upstream.PhoneNumberFormat.E164)
            ours = mojo.parse(raw)
            assert ours.country_code == theirs.country_code, (region, number_kind)
            assert mojo.national_significant_number(
                ours
            ) == upstream.national_significant_number(theirs), (region, number_kind)
            assert mojo.is_possible_number_with_reason(
                ours
            ) == upstream.is_possible_number_with_reason(theirs), (region, number_kind)
            assert mojo.is_valid_number(ours) == upstream.is_valid_number(theirs), (
                region,
                number_kind,
            )
            assert mojo.number_type(ours) == upstream.number_type(theirs), (
                region,
                number_kind,
            )
            assert mojo.region_code_for_number(ours) == upstream.region_code_for_number(
                theirs
            ), (region, number_kind)
            compared += 1
    assert compared == 1_377


def test_all_regions_national_international_and_rfc3966_parse():
    compared = 0
    for region in sorted(upstream.SUPPORTED_REGIONS):
        theirs = upstream.example_number(region)
        if theirs is None:
            continue
        for number_format in (
            upstream.PhoneNumberFormat.NATIONAL,
            upstream.PhoneNumberFormat.INTERNATIONAL,
            upstream.PhoneNumberFormat.RFC3966,
        ):
            raw = upstream.format_number(theirs, number_format)
            expected = upstream.parse(raw, region)
            ours = mojo.parse(raw, region)
            assert ours.country_code == expected.country_code, (region, raw)
            assert mojo.national_significant_number(
                ours
            ) == upstream.national_significant_number(expected), (region, raw)
            compared += 1
    assert compared == 735


def test_all_region_primary_examples_format_identically():
    compared = 0
    for region in sorted(upstream.SUPPORTED_REGIONS):
        theirs = upstream.example_number(region)
        if theirs is None:
            continue
        ours = mojo.parse(
            upstream.format_number(theirs, upstream.PhoneNumberFormat.E164)
        )
        for number_format in range(4):
            assert mojo.format_number(ours, number_format) == upstream.format_number(
                theirs, number_format
            ), (region, number_format)
            compared += 1
    assert compared == 980


def test_metadata_contains_every_upstream_region_and_non_geographical_code():
    upstream_non_geo = {
        code
        for code, regions in upstream.phonenumberutil.COUNTRY_CODE_TO_REGION_CODE.items()
        if regions == ("001",)
    }
    assert set(REGIONS) == upstream.SUPPORTED_REGIONS
    assert set(NON_GEO) == upstream_non_geo


@pytest.mark.parametrize(
    "raw,region",
    (
        ("Tel: +1 (650) 253-0000 ext. 123", None),
        ("＋１ ６５０ ２５３ ００００", None),
        ("٠٠٤٤ ٢٠ ٧٠٣١ ٣٠٠٠", "GB"),
        ("011 44 20 7031 3000", "US"),
    ),
)
def test_lenient_unicode_extension_and_idd_parsing(raw, region):
    ours = mojo.parse(raw, region, keep_raw_input=True)
    theirs = upstream.parse(raw, region, keep_raw_input=True)
    assert ours.country_code == theirs.country_code
    assert mojo.national_significant_number(ours) == upstream.national_significant_number(
        theirs
    )
    assert ours.extension == theirs.extension
    assert ours.raw_input == theirs.raw_input
    assert ours.country_code_source == theirs.country_code_source


@pytest.mark.parametrize(
    "value",
    (
        "+1 (650) 253-0000",
        "１２３-٤٥٦",
        "no digits",
        "",
    ),
)
def test_normalize_digits_only(value):
    assert mojo.normalize_digits_only(value) == upstream.normalize_digits_only(value)


def test_normalize_digits_only_simd_blocks_and_scalar_tails():
    unit = "+12 (345)-abc 6789"
    for size in range(81):
        value = (unit * 6)[:size]
        assert mojo.normalize_digits_only(value) == upstream.normalize_digits_only(
            value
        )


@pytest.mark.parametrize(
    "raw,region",
    (
        (None, None),
        ("not a number", "US"),
        ("+9991234", None),
        ("12", None),
        ("123456789012345678901", "US"),
    ),
)
def test_parse_error_types(raw, region):
    with pytest.raises(upstream.NumberParseException) as reference:
        upstream.parse(raw, region)
    with pytest.raises(mojo.NumberParseException) as ours:
        mojo.parse(raw, region)
    assert ours.value.error_type == reference.value.error_type


def test_existing_phone_number_object_is_populated():
    target = mojo.PhoneNumber(country_code=44, national_number=1)
    returned = mojo.parse("+1 650 253 0000", numobj=target)
    assert returned is target
    assert target.country_code == 1
    assert target.national_number == 6502530000


def test_cached_parse_returns_independent_objects():
    first = mojo.parse("+1 650-253-0000")
    first.national_number = 1
    second = mojo.parse("+1 650-253-0000")
    assert second is not first
    assert second.national_number == 6502530000


def test_cached_format_tracks_object_mutation():
    number = mojo.parse("+1 650-253-0000")
    assert mojo.format_number(number, mojo.PhoneNumberFormat.E164) == "+16502530000"
    number.national_number = 6502530001
    assert mojo.format_number(number, mojo.PhoneNumberFormat.E164) == "+16502530001"


def test_region_specific_validation():
    number = mojo.parse("+1 416 555 0123")
    reference = upstream.parse("+1 416 555 0123")
    for region in ("CA", "US", "GB", None):
        assert mojo.is_valid_number_for_region(
            number, region
        ) == upstream.is_valid_number_for_region(reference, region)


def test_country_region_helpers():
    for region in ("US", "GB", "FR", "IT", "IN", "JP", "BR", "ZZ", None):
        assert mojo.country_code_for_region(
            region
        ) == upstream.country_code_for_region(region)
    for code in (1, 7, 33, 39, 44, 81, 800, 999):
        assert mojo.region_code_for_country_code(
            code
        ) == upstream.region_code_for_country_code(code)


def test_invalid_and_possible_numbers():
    for raw in ("+1 650253000", "+44 20 7031 300", "+33 1 42 68 53"):
        ours = mojo.parse(raw)
        theirs = upstream.parse(raw)
        assert mojo.is_possible_number_with_reason(
            ours
        ) == upstream.is_possible_number_with_reason(theirs)
        assert mojo.is_valid_number(ours) == upstream.is_valid_number(theirs)
