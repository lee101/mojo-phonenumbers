"""ctypes bindings for the Mojo kernels."""

from __future__ import annotations

import ctypes
from functools import lru_cache
import operator
import os
import subprocess

import numpy as np


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE = os.path.join(ROOT, "src", "phonenumbers.mojo")
LIBRARY = os.environ.get("MOJO_PHONENUMBERS_LIB") or os.path.join(
    ROOT, "dist", "libmojo-phonenumbers.so"
)
I64 = ctypes.c_int64
P = ctypes.c_void_p
_I64_MIN = -(1 << 63)
_I64_MAX = (1 << 63) - 1
_library = None


def build(force=False):
    if (
        not force
        and os.path.exists(LIBRARY)
        and os.path.getmtime(LIBRARY) >= os.path.getmtime(SOURCE)
    ):
        return LIBRARY
    proc = subprocess.run(
        ["bash", os.path.join(ROOT, "build", "build.sh")],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode or not os.path.exists(LIBRARY):
        raise RuntimeError((proc.stderr or proc.stdout).strip())
    return LIBRARY


def lib():
    global _library
    if _library is None:
        _library = ctypes.CDLL(build())
        _library.mpn_normalize.argtypes = [P, I64, P, I64, I64]
        _library.mpn_normalize.restype = I64
        _library.mpn_possible_length.argtypes = [I64, P, I64, P, I64]
        _library.mpn_possible_length.restype = I64
        _library.mpn_count_possible_lengths.argtypes = [P, I64, P, I64]
        _library.mpn_count_possible_lengths.restype = I64
    return _library


def normalize_ascii(value: str, map_alpha: bool) -> str:
    raw = value.encode("ascii")
    source = ctypes.create_string_buffer(raw)
    destination = ctypes.create_string_buffer(max(1, len(raw)))
    count = lib().mpn_normalize(
        ctypes.addressof(source),
        len(raw),
        ctypes.addressof(destination),
        len(raw),
        map_alpha,
    )
    if count < 0 or count > len(raw):
        raise RuntimeError(f"mpn_normalize failed with result {count}")
    return destination[:count].decode("ascii")


@lru_cache(maxsize=None)
def _cached_int64(values: tuple) -> np.ndarray:
    array = _coerce_int64(values)
    array.flags.writeable = False
    return array


def _coerce_int64(values) -> np.ndarray:
    array = np.asarray(values)
    if array.size == 0:
        return np.empty(0, dtype=np.int64)
    if array.dtype.kind not in "iu":
        raise TypeError("length arrays must contain integers")
    if array.size and (
        int(array.min()) < _I64_MIN or int(array.max()) > _I64_MAX
    ):
        raise OverflowError("length value does not fit in int64")
    if array.dtype == np.int64 and array.flags.c_contiguous:
        return array
    return np.ascontiguousarray(array, dtype=np.int64)


def _int64_array(values) -> np.ndarray:
    if isinstance(values, tuple):
        return _cached_int64(values)
    return _coerce_int64(values)


def _checked_i64(value, name) -> int:
    try:
        value = operator.index(value)
    except TypeError:
        raise TypeError(f"{name} must be an integer") from None
    if value < _I64_MIN or value > _I64_MAX:
        raise OverflowError(f"{name} does not fit in int64")
    return value


def _checked_result(result, operation) -> int:
    result = int(result)
    if result < 0:
        raise RuntimeError(f"{operation} failed with result {result}")
    return result


def possible_length(actual: int, possible, local=()) -> int:
    actual = _checked_i64(actual, "actual length")
    possible_array = _int64_array(possible)
    local_array = _int64_array(local)
    return _checked_result(
        lib().mpn_possible_length(
            actual,
            possible_array.ctypes.data if possible_array.size else None,
            possible_array.size,
            local_array.ctypes.data if local_array.size else None,
            local_array.size,
        ),
        "mpn_possible_length",
    )


def count_possible_lengths(lengths: np.ndarray, allowed) -> int:
    lengths = _int64_array(lengths)
    allowed = _int64_array(allowed)
    return _checked_result(
        lib().mpn_count_possible_lengths(
            lengths.ctypes.data if lengths.size else None,
            lengths.size,
            allowed.ctypes.data if allowed.size else None,
            allowed.size,
        ),
        "mpn_count_possible_lengths",
    )
