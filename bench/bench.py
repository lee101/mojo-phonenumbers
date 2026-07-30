"""Benchmarks against python-phonenumbers on identical inputs."""

from __future__ import annotations

import os
import platform
import sys
import time


sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"
    ),
)

import mojo_phonenumbers as mojo  # noqa: E402
import phonenumbers as upstream  # noqa: E402


def best_time(function, repetitions=3):
    best = float("inf")
    result = None
    for _ in range(repetitions):
        start = time.perf_counter()
        result = function()
        best = min(best, time.perf_counter() - start)
    return best, result


def machine_name():
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as cpuinfo:
            for line in cpuinfo:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


def main():
    parse_inputs = (
        ("+1 650-253-0000", None),
        ("020 7031 3000", "GB"),
        ("01 42 68 53 00", "FR"),
        ("+91 98765 43210", None),
        ("1-800-FLOWERS", "US"),
    ) * 20_000
    mojo_numbers = [mojo.parse(raw, region) for raw, region in parse_inputs[:5]]
    upstream_numbers = [
        upstream.parse(raw, region) for raw, region in parse_inputs[:5]
    ]
    formatted_text = "+1 (650) 253-0000, " * 250_000

    benchmarks = []
    ours, ours_result = best_time(
        lambda: [mojo.parse(raw, region) for raw, region in parse_inputs]
    )
    theirs, their_result = best_time(
        lambda: [upstream.parse(raw, region) for raw, region in parse_inputs]
    )
    assert [
        (number.country_code, number.national_number) for number in ours_result
    ] == [(number.country_code, number.national_number) for number in their_result]
    benchmarks.append(("parse 100,000 mixed inputs", ours, theirs))

    ours, ours_result = best_time(
        lambda: [
            mojo.is_valid_number(mojo_numbers[index % 5])
            for index in range(500_000)
        ]
    )
    theirs, their_result = best_time(
        lambda: [
            upstream.is_valid_number(upstream_numbers[index % 5])
            for index in range(500_000)
        ]
    )
    assert ours_result == their_result
    benchmarks.append(("validate 500,000 numbers", ours, theirs))

    ours, ours_result = best_time(
        lambda: [
            mojo.format_number(
                mojo_numbers[index % 5], mojo.PhoneNumberFormat.INTERNATIONAL
            )
            for index in range(250_000)
        ]
    )
    theirs, their_result = best_time(
        lambda: [
            upstream.format_number(
                upstream_numbers[index % 5],
                upstream.PhoneNumberFormat.INTERNATIONAL,
            )
            for index in range(250_000)
        ]
    )
    assert ours_result == their_result
    benchmarks.append(("format 250,000 numbers", ours, theirs))

    ours, ours_result = best_time(
        lambda: mojo.normalize_digits_only(formatted_text)
    )
    theirs, their_result = best_time(
        lambda: upstream.normalize_digits_only(formatted_text)
    )
    assert ours_result == their_result
    benchmarks.append(("normalize 5.25M characters", ours, theirs))

    print(f"Machine: {machine_name()} ({platform.system()} {platform.machine()})")
    print()
    print("| workload | mojo-phonenumbers | phonenumbers | relative |")
    print("| --- | ---: | ---: | ---: |")
    for name, mojo_seconds, upstream_seconds in benchmarks:
        relative = upstream_seconds / mojo_seconds
        print(
            f"| {name} | {mojo_seconds * 1e3:.2f} ms | "
            f"{upstream_seconds * 1e3:.2f} ms | {relative:.2f}x |"
        )


if __name__ == "__main__":
    main()
