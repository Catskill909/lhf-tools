#!/usr/bin/env python3
"""Crop a full-page screenshot down to the dialogue in the middle of it.

Pure stdlib — PNG is just zlib plus a header, so no Pillow and nothing to
install. Decode, find the modal, crop, re-encode.

Finding the modal is easy in this app because every dialogue is drawn with a
4px solid --spot red top border. That one run of red gives the left edge, the
right edge and the top in a single pass. The bottom is then the last row where
the modal's own paper colour is still showing at that x — the backdrop behind
it is the page dimmed to ~45%, which is measurably darker.

    python3 cropshot.py IN.png OUT.png [--pad 32] [--check]

--check prints what it found and writes nothing.
"""
import struct, sys, zlib

SPOT = {"dark": (0xD8, 0x50, 0x3A), "light": (0xB8, 0x33, 0x1D)}


def read_png(path):
    d = open(path, "rb").read()
    assert d[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    pos, idat, hdr = 8, [], None
    while pos < len(d):
        ln = struct.unpack(">I", d[pos:pos + 4])[0]
        typ = d[pos + 4:pos + 8]
        body = d[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            hdr = struct.unpack(">IIBBBBB", body)
        elif typ == b"IDAT":
            idat.append(body)
        elif typ == b"IEND":
            break
        pos += 12 + ln
    w, h, depth, color, comp, filt, inter = hdr
    assert depth == 8, f"only 8-bit supported (got {depth})"
    assert inter == 0, "interlaced PNGs not supported"
    nch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    raw = zlib.decompress(b"".join(idat))

    # Undo the per-scanline filters. Rows are stored as [filter byte][pixels].
    stride = w * nch
    out = bytearray(h * stride)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]; p += 1
        line = bytearray(raw[p:p + stride]); p += stride
        if f == 1:
            for i in range(nch, stride):
                line[i] = (line[i] + line[i - nch]) & 0xFF
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif f == 3:
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif f == 4:
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                b = prev[i]
                c = prev[i - nch] if i >= nch else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return w, h, nch, out


def write_png(path, w, h, nch, px):
    color = {1: 0, 2: 4, 3: 2, 4: 6}[nch]
    stride = w * nch
    # Filter 0 (None) on every row: zlib does the work, and the size penalty on
    # a screenshot is small. Keeps this readable.
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += px[y * stride:(y + 1) * stride]

    def chunk(typ, body):
        return (struct.pack(">I", len(body)) + typ + body
                + struct.pack(">I", zlib.crc32(typ + body) & 0xFFFFFFFF))

    open(path, "wb").write(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, color, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b""))


def find_modal(w, h, nch, px, tol=26):
    at = lambda x, y: tuple(px[(y * w + x) * nch:(y * w + x) * nch + 3])
    near = lambda p, q: all(abs(a - b) <= tol for a, b in zip(p, q))

    # The longest horizontal run of spot red anywhere in the image is the
    # dialogue's top border. Nothing else in this UI is a wide solid bar of it.
    best = None
    for y in range(h):
        for spot in SPOT.values():
            run = x0 = None
            for x in range(w):
                if near(at(x, y), spot):
                    if run is None:
                        run, x0 = 1, x
                    else:
                        run += 1
                elif run is not None:
                    if best is None or run > best[0]:
                        best = (run, x0, x - 1, y)
                    run = None
            if run is not None and (best is None or run > best[0]):
                best = (run, x0, w - 1, y)
    if not best or best[0] < w // 6:
        return None
    _, x0, x1, ytop = best

    # The bottom is where the modal's left edge stops being an edge.
    #
    # Matching the paper colour absolutely does not work: the backdrop is the
    # same page dimmed to ~45%, which lands about 11 levels per channel below
    # --paper — inside any tolerance loose enough to survive JPEG-ish noise and
    # subpixel text. So compare *across* the boundary instead. Just inside the
    # modal is paper; just outside is that same paper dimmed. While the
    # dialogue is present those two differ; past its bottom edge they are the
    # same pixel of backdrop and the difference collapses.
    inx = min(x0 + 8, w - 1)
    outx = max(0, x0 - 10)
    delta = lambda y: sum(abs(a - b) for a, b in zip(at(inx, y), at(outx, y)))
    ybot, run = ytop, 0
    for y in range(ytop + 6, h):
        if delta(y) > 12:
            ybot, run = y, 0
        else:
            run += 1
            if run > 20:         # twenty rows with no edge — we are past it
                break
    return x0, ytop, x1, ybot


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    pad = 32
    if "--pad" in sys.argv:
        pad = int(sys.argv[sys.argv.index("--pad") + 1])
    check = "--check" in sys.argv
    src = args[0]
    w, h, nch, px = read_png(src)
    box = find_modal(w, h, nch, px)
    if not box:
        print(f"  {src}: no dialogue found — left alone")
        return
    x0, y0, x1, y1 = box
    x0 = max(0, x0 - pad); y0 = max(0, y0 - pad)
    x1 = min(w - 1, x1 + pad); y1 = min(h - 1, y1 + pad)
    nw, nh = x1 - x0 + 1, y1 - y0 + 1
    print(f"  {src}: {w}x{h} -> {nw}x{nh}   (modal at {box}, pad {pad})")
    if check:
        return
    stride = w * nch
    out = bytearray()
    for y in range(y0, y1 + 1):
        out += px[y * stride + x0 * nch: y * stride + (x1 + 1) * nch]
    write_png(args[1], nw, nh, nch, out)


main()
