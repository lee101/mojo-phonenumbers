"""ASCII phone-number kernels exposed through a stable C ABI."""

from std.sys.info import simd_width_of

comptime BPtr = UnsafePointer[UInt8, AnyOrigin[mut=True]]
comptime IPtr = UnsafePointer[Int64, AnyOrigin[mut=True]]


def alpha_digit(c: UInt8) -> UInt8:
    if (c >= UInt8(65) and c <= UInt8(67)) or (c >= UInt8(97) and c <= UInt8(99)):
        return UInt8(50)
    if (c >= UInt8(68) and c <= UInt8(70)) or (c >= UInt8(100) and c <= UInt8(102)):
        return UInt8(51)
    if (c >= UInt8(71) and c <= UInt8(73)) or (c >= UInt8(103) and c <= UInt8(105)):
        return UInt8(52)
    if (c >= UInt8(74) and c <= UInt8(76)) or (c >= UInt8(106) and c <= UInt8(108)):
        return UInt8(53)
    if (c >= UInt8(77) and c <= UInt8(79)) or (c >= UInt8(109) and c <= UInt8(111)):
        return UInt8(54)
    if (c >= UInt8(80) and c <= UInt8(83)) or (c >= UInt8(112) and c <= UInt8(115)):
        return UInt8(55)
    if (c >= UInt8(84) and c <= UInt8(86)) or (c >= UInt8(116) and c <= UInt8(118)):
        return UInt8(56)
    if (c >= UInt8(87) and c <= UInt8(90)) or (c >= UInt8(119) and c <= UInt8(122)):
        return UInt8(57)
    return UInt8(0)


@export("mpn_normalize")
def mpn_normalize(
    src_addr: Int, n: Int, dst_addr: Int, capacity: Int, map_alpha: Int
) abi("C") -> Int:
    if n < 0 or capacity < 0 or capacity < n:
        return -1
    if n == 0:
        return 0
    if src_addr == 0 or dst_addr == 0:
        return -1
    var src = BPtr(unsafe_from_address=src_addr)
    var dst = BPtr(unsafe_from_address=dst_addr)
    var written = 0
    if map_alpha == 0 and capacity >= n:
        comptime W = simd_width_of[DType.uint8]()
        var i = 0
        while i + W <= n:
            var chars = src.load[width=W](i)
            var digits = chars.ge(UInt8(48)) & chars.le(UInt8(57))
            if digits.reduce_and():
                dst.store(written, chars)
                written += W
            elif digits.reduce_or():
                for lane in range(W):
                    if digits[lane]:
                        dst[written] = chars[lane]
                        written += 1
            i += W
        while i < n:
            var c = src[i]
            if c >= UInt8(48) and c <= UInt8(57):
                dst[written] = c
                written += 1
            i += 1
        return written
    for i in range(n):
        var c = src[i]
        var digit = UInt8(0)
        if c >= UInt8(48) and c <= UInt8(57):
            digit = c
        elif map_alpha != 0:
            digit = alpha_digit(c)
        if digit != UInt8(0):
            if written >= capacity:
                return -1
            dst[written] = digit
            written += 1
    return written


@export("mpn_possible_length")
def mpn_possible_length(
    actual: Int,
    possible_addr: Int,
    possible_count: Int,
    local_addr: Int,
    local_count: Int,
) abi("C") -> Int:
    if possible_count < 0 or local_count < 0:
        return -1
    if local_count > 0:
        if local_addr == 0:
            return -1
        var local = IPtr(unsafe_from_address=local_addr)
        for i in range(local_count):
            if Int(local[i]) == actual:
                return 4
    if possible_count == 0:
        return 5
    if possible_addr == 0:
        return -1
    var possible = IPtr(unsafe_from_address=possible_addr)
    var minimum = Int(possible[0])
    if actual < minimum:
        return 2
    var maximum = Int(possible[possible_count - 1])
    if actual > maximum:
        return 3
    for i in range(possible_count):
        if Int(possible[i]) == actual:
            return 0
    return 5


@export("mpn_count_possible_lengths")
def mpn_count_possible_lengths(
    lengths_addr: Int, count: Int, allowed_addr: Int, allowed_count: Int
) abi("C") -> Int:
    if count < 0 or allowed_count < 0:
        return -1
    if count == 0 or allowed_count == 0:
        return 0
    if lengths_addr == 0 or allowed_addr == 0:
        return -1
    var lengths = IPtr(unsafe_from_address=lengths_addr)
    var allowed = IPtr(unsafe_from_address=allowed_addr)
    var total = 0
    for i in range(count):
        for j in range(allowed_count):
            if lengths[i] == allowed[j]:
                total += 1
                break
    return total
