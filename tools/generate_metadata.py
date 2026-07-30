"""Generate the standalone metadata snapshot from upstream phonenumbers."""

from __future__ import annotations

import pprint
from pathlib import Path

import phonenumbers
from phonenumbers import COUNTRY_CODE_TO_REGION_CODE
from phonenumbers.phonemetadata import PhoneMetadata


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "python" / "mojo_phonenumbers" / "_metadata.py"
DESCRIPTION_NAMES = (
    "general_desc",
    "premium_rate",
    "toll_free",
    "shared_cost",
    "voip",
    "personal_number",
    "pager",
    "uan",
    "voicemail",
    "fixed_line",
    "mobile",
)


def description(desc):
    if desc is None:
        return None
    return (
        desc.national_number_pattern or "",
        tuple(desc.possible_length),
        tuple(desc.possible_length_local_only),
    )


def number_format(fmt):
    return (
        fmt.pattern,
        fmt.format,
        tuple(fmt.leading_digits_pattern),
        fmt.national_prefix_formatting_rule or "",
        fmt.domestic_carrier_code_formatting_rule or "",
        bool(fmt.national_prefix_optional_when_formatting),
    )


def region_metadata(region):
    metadata = PhoneMetadata.metadata_for_region(region)
    return {
        "country_code": metadata.country_code,
        "international_prefix": metadata.international_prefix,
        "national_prefix": metadata.national_prefix or "",
        "national_prefix_for_parsing": metadata.national_prefix_for_parsing or "",
        "national_prefix_transform_rule": metadata.national_prefix_transform_rule or "",
        "leading_digits": metadata.leading_digits or "",
        "preferred_extn_prefix": metadata.preferred_extn_prefix or "",
        "same_mobile_and_fixed_line_pattern": bool(
            metadata.same_mobile_and_fixed_line_pattern
        ),
        "descriptions": {
            name: description(getattr(metadata, name)) for name in DESCRIPTION_NAMES
        },
        "number_formats": tuple(number_format(fmt) for fmt in metadata.number_format),
        "intl_number_formats": tuple(
            number_format(fmt) for fmt in metadata.intl_number_format
        ),
    }


def non_geo_metadata(country_code):
    metadata = PhoneMetadata.metadata_for_nongeo_region(country_code)
    if metadata is None:
        return None
    data = {
        "country_code": metadata.country_code,
        "international_prefix": metadata.international_prefix,
        "national_prefix": "",
        "national_prefix_for_parsing": "",
        "national_prefix_transform_rule": "",
        "leading_digits": "",
        "preferred_extn_prefix": metadata.preferred_extn_prefix or "",
        "same_mobile_and_fixed_line_pattern": bool(
            metadata.same_mobile_and_fixed_line_pattern
        ),
        "descriptions": {
            name: description(getattr(metadata, name)) for name in DESCRIPTION_NAMES
        },
        "number_formats": tuple(number_format(fmt) for fmt in metadata.number_format),
        "intl_number_formats": tuple(
            number_format(fmt) for fmt in metadata.intl_number_format
        ),
    }
    return data


def main():
    regions = {
        region: region_metadata(region)
        for region in sorted(phonenumbers.SUPPORTED_REGIONS)
    }
    non_geo = {
        code: data
        for code in sorted(phonenumbers.COUNTRY_CODES_FOR_NON_GEO_REGIONS)
        if (data := non_geo_metadata(code)) is not None
    }
    country_map = {
        code: tuple(regions)
        for code, regions in sorted(COUNTRY_CODE_TO_REGION_CODE.items())
    }
    payload = (
        '"""Generated metadata derived from python-phonenumbers '
        f'{phonenumbers.__version__}. Do not edit by hand."""\n\n'
        f"UPSTREAM_VERSION = {phonenumbers.__version__!r}\n\n"
        f"COUNTRY_CODE_TO_REGION = {pprint.pformat(country_map, width=100)}\n\n"
        f"REGIONS = {pprint.pformat(regions, width=120, sort_dicts=True)}\n\n"
        f"NON_GEO = {pprint.pformat(non_geo, width=120, sort_dicts=True)}\n"
    )
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(payload, encoding="utf-8")
    print(f"wrote {DEST} ({DEST.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
