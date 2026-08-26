# mojo-phonenumbers

Phone number parsing and validation with the repetitive character work compiled
in [Mojo](https://www.modular.com/mojo).

This is a standalone port of the parse/validate slice of the Python
[`phonenumbers`](https://pypi.org/project/phonenumbers/) API. It bundles a
generated snapshot of the upstream 9.0.35 numbering metadata, so upstream is a
parity-test dependency rather than a runtime dependency.

## Covered API

The package exposes this tested subset of upstream names and behavior:

- `parse`, including international, national, IDD, RFC3966, vanity, extension,
  Unicode digit, `keep_raw_input`, and `numobj` inputs
- `PhoneNumber`, `NumberParseException`, `CountryCodeSource`
- `is_possible_number`, `is_possible_number_with_reason`, `ValidationResult`
- `is_valid_number`, `is_valid_number_for_region`
- `number_type`, `PhoneNumberType`
- `region_code_for_number`, `region_code_for_country_code`,
  `country_code_for_region`
- `format_number`, `PhoneNumberFormat`, `national_significant_number`
- `normalize_digits_only`

The metadata snapshot contains all 245 upstream regions and all 9
non-geographical calling codes. The test suite compares all 1,377 available
typed upstream examples for parse, possibility, validity, type, and region. It
also tests all 245 primary regional examples across 735 formatted parse cases
and 980 format cases.

This is not the complete `phonenumbers` distribution. It does not include
short-number rules, geocoding, carrier or timezone data, as-you-type formatting,
number matching, out-of-country dialing, or the full set of metadata query
helpers. Import it under the conventional name when porting covered code:

```python
import mojo_phonenumbers as phonenumbers
```

## Install and use

```bash
pixi install
pixi run build
```

The following example runs from the repository:

```bash
pixi run python - <<'PY'
import mojo_phonenumbers as phonenumbers

number = phonenumbers.parse("020 7031 3000", "GB")
print(phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164))
print(phonenumbers.is_possible_number(number))
print(phonenumbers.is_valid_number(number))
print(phonenumbers.region_code_for_number(number))
PY
```

It prints:

```text
+442070313000
True
True
GB
```

Run the checks with:

```bash
pixi run test
pixi run bench
```

## Benchmarks

Measured with `pixi run bench` on an Intel Xeon E5-2697 v4 at 2.30 GHz,
Linux x86-64. Times are the best of three runs; each comparison uses identical
inputs and asserts identical output before reporting. The workloads repeatedly
cycle five representative numbers; the bounded parse, validation, and formatting
caches are warm after benchmark setup.

| workload | mojo-phonenumbers | phonenumbers 9.0.35 | relative |
| --- | ---: | ---: | ---: |
| parse 100,000 mixed inputs | 148.56 ms | 2855.04 ms | 19.22x |
| validate 500,000 numbers | 228.60 ms | 6716.02 ms | 29.38x |
| format 250,000 numbers | 117.47 ms | 2091.93 ms | 17.81x |
| normalize 5.25M characters | 10.34 ms | 1056.18 ms | 102.16x |

These are end-to-end Python API timings, including ctypes overhead. The largest
gains come from bounded reuse of parsed and formatted results and the SIMD
character scan. Python holds the input and output buffers alive for each
synchronous FFI call, and tiny immutable metadata arrays are reused rather than
allocated for every call.

Profiling found no kernel at parity with or slower than upstream: every measured
workload is more than 17x faster. No additional optimization was applied to
these already-ahead paths.

There is no GPU path. These workloads are byte filtering, short regex matching,
and small metadata lookups; transfer and launch overhead are a poor fit. They
also stay serial because individual phone-number calls are small and
normalization preserves input order.

## How it works

`src/phonenumbers.mojo` is one compilation unit. `build/build.sh` emits
`dist/libmojo-phonenumbers.so`, and `python/mojo_phonenumbers/_lib.py` loads its
C ABI with ctypes. ASCII strings cross the boundary as contiguous byte buffers
with explicit lengths. The wrapper validates integer widths, array dtypes,
contiguity, kernel errors, and result lengths. Mojo writes normalized ASCII
digits into caller-owned memory, so there is no allocator or ownership transfer
across the ABI.

Possible-number checks are metadata-driven length classification in Mojo.
Exact validity and type classification use the bundled region patterns from
`python/mojo_phonenumbers/_metadata.py`; Python applies those patterns because
the scalar regex work is already highly optimized and moving a complete regex
engine across the ABI would add cost. Region resolution, national-prefix
transforms, and formatting rules use the same snapshot.

`tools/generate_metadata.py` refreshes the snapshot from the installed upstream
package. Upstream remains installed in the Pixi environment solely so tests can
perform live behavioral parity checks.

MIT. The generated numbering-plan metadata is derived from
python-phonenumbers/libphonenumber; see `NOTICE`.
