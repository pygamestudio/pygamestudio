"""A small QR code encoder: byte mode, error correction level M.

The editor ships no QR library and adding one just for the "try it on your
phone" button would force every user to reinstall, so the encoder lives here.
It covers what a preview link needs: byte mode (UTF-8), versions 1-10 (up to
213 bytes - far more than an ``http://host:port/index.html`` address) and
error correction level M (about 15%), which scanners read reliably.

The public entry points return data, never widgets:

* :func:`encode` -> the module matrix (``True`` is a dark module);
* :func:`to_qimage` -> the same matrix as a ``QImage`` with a quiet zone.

The implementation follows ISO/IEC 18004 (bit stream, Reed-Solomon inside
GF(256), the eight data masks and the format / version information).
"""

#: Error correction codewords per block and the block layout, level M.
#: ``{version: (ec_per_block, [(blocks, data_codewords), ...])}``
_EC_BLOCKS = {
    1: (10, [(1, 16)]),
    2: (16, [(1, 28)]),
    3: (26, [(1, 44)]),
    4: (18, [(2, 32)]),
    5: (24, [(2, 43)]),
    6: (16, [(4, 27)]),
    7: (18, [(4, 31)]),
    8: (22, [(2, 38), (2, 39)]),
    9: (22, [(3, 36), (2, 37)]),
    10: (26, [(4, 43), (1, 44)]),
}

#: Centre coordinates of the alignment patterns per version.
_ALIGNMENT = {
    1: (),
    2: (6, 18),
    3: (6, 22),
    4: (6, 26),
    5: (6, 30),
    6: (6, 34),
    7: (6, 22, 38),
    8: (6, 24, 42),
    9: (6, 26, 46),
    10: (6, 28, 50),
}

#: Modules a version needs (17 + 4 * version).
MAX_VERSION = max(_EC_BLOCKS)


class QrError(ValueError):
    """The text does not fit the supported QR sizes."""


def capacity(version):
    """How many payload bytes fit a version (level M, byte mode)."""
    ec_per_block, blocks = _EC_BLOCKS[version]
    data_codewords = sum(count * words for count, words in blocks)
    header_bits = 4 + (8 if version < 10 else 16)
    return (data_codewords * 8 - header_bits) // 8


# --------------------------------------------------------------- arithmetic
def _gf_tables():
    """Exponent / logarithm tables of GF(256) with the QR primitive 0x11D."""
    exponent = [0] * 512
    logarithm = [0] * 256
    value = 1
    for power in range(255):
        exponent[power] = value
        logarithm[value] = power
        value <<= 1
        if value & 0x100:
            value ^= 0x11D
    for power in range(255, 512):
        exponent[power] = exponent[power - 255]
    return exponent, logarithm


_EXPONENT, _LOGARITHM = _gf_tables()


def _gf_multiply(a, b):
    if a == 0 or b == 0:
        return 0
    return _EXPONENT[_LOGARITHM[a] + _LOGARITHM[b]]


def _rs_generator(degree):
    """The generator polynomial of ``degree`` error correction codewords."""
    polynomial = [1]
    for index in range(degree):
        term = [1, _EXPONENT[index]]
        result = [0] * (len(polynomial) + 1)
        for position, coefficient in enumerate(polynomial):
            for shift, factor in enumerate(term):
                result[position + shift] ^= _gf_multiply(coefficient, factor)
        polynomial = result
    return polynomial


def _rs_ecc(data, count):
    """``count`` Reed-Solomon codewords of one block."""
    generator = _rs_generator(count)
    remainder = [0] * count
    for byte in data:
        factor = byte ^ remainder[0]
        remainder = remainder[1:] + [0]
        for index in range(count):
            remainder[index] ^= _gf_multiply(generator[index + 1], factor)
    return remainder


# ------------------------------------------------------------------ payload
def _pick_version(length):
    for version in range(1, MAX_VERSION + 1):
        if length <= capacity(version):
            return version
    raise QrError('The text is too long for a QR code ({} bytes)'.format(length))


def _bit_stream(payload, version):
    """Mode indicator, character count, payload, terminator and padding."""
    count_bits = 8 if version < 10 else 16
    bits = [0, 1, 0, 0]                     # byte mode
    bits.extend((len(payload) >> shift) & 1 for shift in range(count_bits - 1, -1, -1))
    for byte in payload:
        bits.extend((byte >> shift) & 1 for shift in range(7, -1, -1))
    total = sum(count * words for count, words in _EC_BLOCKS[version][1]) * 8
    bits.extend([0] * min(4, total - len(bits)))
    while len(bits) % 8:
        bits.append(0)
    codewords = [int(''.join(str(bit) for bit in bits[start:start + 8]), 2)
                 for start in range(0, len(bits), 8)]
    pads = (0xEC, 0x11)
    index = 0
    while len(codewords) * 8 < total:
        codewords.append(pads[index % 2])
        index += 1
    return codewords


def _interleave(codewords, version):
    """Split into blocks, add their EC codewords and interleave everything."""
    ec_per_block, layout = _EC_BLOCKS[version]
    blocks = []
    position = 0
    for count, words in layout:
        for _ in range(count):
            blocks.append(codewords[position:position + words])
            position += words
    eccs = [_rs_ecc(block, ec_per_block) for block in blocks]
    result = []
    for index in range(max(len(block) for block in blocks)):
        for block in blocks:
            if index < len(block):
                result.append(block[index])
    for index in range(ec_per_block):
        for ecc in eccs:
            result.append(ecc[index])
    return result


# ------------------------------------------------------------------- matrix
def _new_matrix(version):
    size = 17 + 4 * version
    return ([[False] * size for _ in range(size)],
            [[False] * size for _ in range(size)])


def _set(matrix, functions, row, column, dark=True):
    matrix[row][column] = dark
    functions[row][column] = True


def _draw_finder(matrix, functions, row, column):
    for offset_row in range(-1, 8):
        for offset_column in range(-1, 8):
            target_row = row + offset_row
            target_column = column + offset_column
            if not (0 <= target_row < len(matrix) and 0 <= target_column < len(matrix)):
                continue
            inside = (0 <= offset_row <= 6 and 0 <= offset_column <= 6 and
                      (offset_row in (0, 6) or offset_column in (0, 6) or
                       (2 <= offset_row <= 4 and 2 <= offset_column <= 4)))
            _set(matrix, functions, target_row, target_column, inside)


def _draw_alignment(matrix, functions, version):
    centres = _ALIGNMENT[version]
    size = len(matrix)
    for row in centres:
        for column in centres:
            # The three corners are taken by the finder patterns.
            if (row, column) in ((6, 6), (6, size - 7), (size - 7, 6)):
                continue
            for offset_row in range(-2, 3):
                for offset_column in range(-2, 3):
                    inside = max(abs(offset_row), abs(offset_column)) != 1
                    _set(matrix, functions, row + offset_row, column + offset_column, inside)


def _draw_function_patterns(version):
    """Finder / timing / alignment / reserved areas of a version."""
    matrix, functions = _new_matrix(version)
    size = len(matrix)
    _draw_finder(matrix, functions, 0, 0)
    _draw_finder(matrix, functions, 0, size - 7)
    _draw_finder(matrix, functions, size - 7, 0)
    for index in range(8, size - 8):
        dark = index % 2 == 0
        _set(matrix, functions, 6, index, dark)
        _set(matrix, functions, index, 6, dark)
    _draw_alignment(matrix, functions, version)
    # The dark module right above the bottom-left format area.
    _set(matrix, functions, size - 8, 8, True)
    # Format information areas (written later, reserved here).
    for index in range(9):
        if not functions[8][index]:
            _set(matrix, functions, 8, index, False)
        if not functions[index][8]:
            _set(matrix, functions, index, 8, False)
    for index in range(8):
        _set(matrix, functions, 8, size - 1 - index, False)
        _set(matrix, functions, size - 1 - index, 8, False)
    if version >= 7:
        bits = _version_bits(version)
        for index in range(18):
            dark = bool((bits >> index) & 1)
            row = index // 3
            column = size - 11 + index % 3
            _set(matrix, functions, row, column, dark)
            _set(matrix, functions, column, row, dark)
    return matrix, functions


def _version_bits(version):
    """The 18-bit version information (v7 and up)."""
    value = version << 12
    remainder = value
    for shift in range(17, 11, -1):
        if (remainder >> shift) & 1:
            remainder ^= 0x1F25 << (shift - 12)
    return value | remainder


def _format_bits(mask):
    """The 15-bit format information of level M (``00``) and ``mask``."""
    value = (0b00 << 3) | mask
    remainder = value << 10
    for shift in range(14, 9, -1):
        if (remainder >> shift) & 1:
            remainder ^= 0x537 << (shift - 10)
    return ((value << 10) | remainder) ^ 0x5412


def _place_data(matrix, functions, codewords):
    """Walk the data area in the QR zigzag and write the bit stream."""
    size = len(matrix)
    bits = []
    for codeword in codewords:
        bits.extend((codeword >> shift) & 1 for shift in range(7, -1, -1))
    index = 0
    column = size - 1
    upward = True
    while column > 0:
        if column == 6:            # the vertical timing column
            column -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for row in rows:
            for offset in (0, 1):
                target = column - offset
                if functions[row][target]:
                    continue
                matrix[row][target] = bool(bits[index]) if index < len(bits) else False
                index += 1
        upward = not upward
        column -= 2


def _mask_bit(mask, row, column):
    if mask == 0:
        return (row + column) % 2 == 0
    if mask == 1:
        return row % 2 == 0
    if mask == 2:
        return column % 3 == 0
    if mask == 3:
        return (row + column) % 3 == 0
    if mask == 4:
        return (row // 2 + column // 3) % 2 == 0
    if mask == 5:
        return (row * column) % 2 + (row * column) % 3 == 0
    if mask == 6:
        return ((row * column) % 2 + (row * column) % 3) % 2 == 0
    return ((row + column) % 2 + (row * column) % 3) % 2 == 0


def _apply_mask(matrix, functions, mask):
    size = len(matrix)
    for row in range(size):
        for column in range(size):
            if not functions[row][column] and _mask_bit(mask, row, column):
                matrix[row][column] = not matrix[row][column]


def _penalty(matrix):
    """The four penalty rules of the spec (used to pick the best mask)."""
    size = len(matrix)
    score = 0
    # Rule 1: runs of five or more modules of the same colour.
    for line in list(matrix) + [list(column) for column in zip(*matrix)]:
        run = 1
        for index in range(1, size):
            if line[index] == line[index - 1]:
                run += 1
            else:
                if run >= 5:
                    score += 3 + (run - 5)
                run = 1
        if run >= 5:
            score += 3 + (run - 5)
    # Rule 2: 2x2 blocks of one colour.
    for row in range(size - 1):
        for column in range(size - 1):
            block = (matrix[row][column], matrix[row][column + 1],
                     matrix[row + 1][column], matrix[row + 1][column + 1])
            if len(set(block)) == 1:
                score += 3
    # Rule 3: finder-like patterns.
    patterns = ([True, False, True, True, True, False, True, False, False, False, False],
                [False, False, False, False, True, False, True, True, True, False, True])
    for line in list(matrix) + [list(column) for column in zip(*matrix)]:
        for index in range(size - 10):
            window = line[index:index + 11]
            if window in patterns:
                score += 40
    # Rule 4: deviation from a 50% dark ratio.
    dark = sum(1 for row in matrix for module in row if module)
    ratio = dark * 100 // (size * size)
    score += 10 * (abs(ratio - 50) // 5)
    return score


def _write_format(matrix, functions, mask):
    """Write both copies of the 15-bit format information (level M, ``mask``)."""
    size = len(matrix)
    bits = _format_bits(mask)

    def dark(index):
        return bool((bits >> index) & 1)

    # Copy around the top-left finder: six modules up its right side, then the
    # one beside it, the corner and the six along the top of the bottom-left
    # format strip (bit 0 nearest the finder).
    for index in range(6):
        _set(matrix, functions, index, 8, dark(index))
    _set(matrix, functions, 7, 8, dark(6))
    _set(matrix, functions, 8, 8, dark(7))
    _set(matrix, functions, 8, 7, dark(8))
    for index in range(9, 15):
        _set(matrix, functions, 8, 14 - index, dark(index))

    # Copy split between the other two finders.
    for index in range(8):
        _set(matrix, functions, 8, size - 1 - index, dark(index))
    for index in range(8, 15):
        _set(matrix, functions, size - 15 + index, 8, dark(index))

    # The dark module right above the bottom-left format area.
    _set(matrix, functions, size - 8, 8, True)


def encode(text):
    """The QR module matrix of ``text`` (``True`` = dark module).

    Level M, byte mode; the smallest version that fits is used and the mask
    with the lowest penalty is picked, so the result stays easy to scan.
    """
    payload = str(text).encode('utf-8')
    version = _pick_version(len(payload))
    codewords = _interleave(_bit_stream(payload, version), version)

    base, functions = _draw_function_patterns(version)
    _place_data(base, functions, codewords)

    best = None
    for mask in range(8):
        candidate = [row[:] for row in base]
        candidate_functions = [row[:] for row in functions]
        _apply_mask(candidate, candidate_functions, mask)
        _write_format(candidate, candidate_functions, mask)
        score = _penalty(candidate)
        if best is None or score < best[0]:
            best = (score, candidate)
    return best[1]


def to_qimage(text, scale=6, border=6):
    """Render ``text`` as a QR code picture (lazy Qt import, GUI side only).

    ``scale`` is the pixel size of one module and ``border`` the quiet zone
    (4 modules is what the spec asks for), so the result is
    ``(modules + 2 * border) * scale`` pixels wide.
    """
    from PySide6.QtGui import QColor, QImage, QPainter

    matrix = encode(text)
    modules = len(matrix)
    total = (modules + border * 2) * scale
    image = QImage(total, total, QImage.Format.Format_RGB32)
    painter = QPainter(image)
    painter.fillRect(0, 0, total, total, QColor('#ffffff'))
    dark = QColor('#000000')
    for row in range(modules):
        for column in range(modules):
            if matrix[row][column]:
                painter.fillRect((column + border) * scale, (row + border) * scale,
                                 scale, scale, dark)
    painter.end()
    return image
