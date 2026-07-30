"""Safety and type-contract tests for the Mojo C boundary."""

import ctypes

import numpy as np
import pytest

from mojo_phonenumbers import _lib


def test_empty_buffers_do_not_require_non_null_pointers():
    assert _lib.normalize_ascii("", False) == ""
    assert _lib.possible_length(7, ()) == 5
    assert _lib.count_possible_lengths(np.array([], dtype=np.int64), ()) == 0


def test_kernel_rejects_invalid_pointer_and_length_combinations():
    kernel = _lib.lib()
    byte = ctypes.create_string_buffer(b"1")
    assert kernel.mpn_normalize(None, 1, ctypes.addressof(byte), 1, 0) == -1
    assert kernel.mpn_normalize(ctypes.addressof(byte), -1, None, 0, 0) == -1
    assert kernel.mpn_possible_length(1, None, 1, None, 0) == -1
    assert kernel.mpn_possible_length(1, None, 0, None, 1) == -1
    assert kernel.mpn_count_possible_lengths(None, 1, None, 1) == -1


@pytest.mark.parametrize(
    "values",
    (
        np.array([7.0], dtype=np.float64),
        np.array([True], dtype=np.bool_),
        np.array([1 << 63], dtype=np.uint64),
    ),
)
def test_length_arrays_reject_narrowing(values):
    expected = OverflowError if values.dtype == np.uint64 else TypeError
    with pytest.raises(expected):
        _lib.possible_length(7, values)


def test_scalar_length_rejects_ctypes_wraparound():
    with pytest.raises(OverflowError):
        _lib.possible_length(1 << 63, (7,))
    with pytest.raises(TypeError):
        _lib.possible_length(7.5, (7,))


def test_noncontiguous_integer_arrays_are_copied_safely():
    values = np.arange(20, dtype=np.int32)[::2]
    assert not values.flags.c_contiguous
    assert _lib.possible_length(8, values) == 0
    assert _lib.count_possible_lengths(values, (4, 8, 12)) == 3
