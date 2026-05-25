"""Generate simple placeholder PNG icons for the extension."""
import struct, zlib, math

def make_png(size: int, path: str):
    """Generate a minimal shopping-cart PNG icon."""
    img = []
    bg = (13, 15, 20)
    accent = (240, 165, 0)
    cx, cy, r = size // 2, size // 2, int(size * 0.42)

    for y in range(size):
        row = []
        for x in range(size):
            dx, dy = x - cx, y - cy
            dist = math.sqrt(dx * dx + dy * dy)
            # Rounded rect background
            margin = size * 0.08
            in_rect = (margin <= x <= size - margin and margin <= y <= size - margin)
            corner_r = size * 0.22
            # Approximate rounded corners
            corners = [
                (margin + corner_r, margin + corner_r),
                (size - margin - corner_r, margin + corner_r),
                (margin + corner_r, size - margin - corner_r),
                (size - margin - corner_r, size - margin - corner_r),
            ]
            in_corner = False
            for (cx2, cy2) in corners:
                cdx, cdy = x - cx2, y - cy2
                if cdx * cdx + cdy * cdy > corner_r * corner_r:
                    # Only matters if we're in the corner box
                    if (abs(x - cx2) > corner_r and abs(y - cy2) > corner_r):
                        in_corner = True

            if in_rect and not in_corner:
                # Draw a simple cart shape
                # Cart body: rectangle in lower half
                body_x1, body_x2 = int(size * 0.2), int(size * 0.82)
                body_y1, body_y2 = int(size * 0.38), int(size * 0.65)
                # Cart handle
                handle_x1, handle_x2 = int(size * 0.15), int(size * 0.42)
                handle_y1, handle_y2 = int(size * 0.22), int(size * 0.42)
                # Wheels
                w_r = max(2, int(size * 0.07))
                w1 = (int(size * 0.33), int(size * 0.73))
                w2 = (int(size * 0.67), int(size * 0.73))

                in_body = body_x1 <= x <= body_x2 and body_y1 <= y <= body_y2
                in_handle = (handle_x1 <= x <= handle_x2 and handle_y1 <= y <= handle_y2 and
                             (x == handle_x1 or y == handle_y1 or
                              (x >= handle_x2 - 2 and y >= handle_y2 - 2)))
                in_w1 = (x - w1[0]) ** 2 + (y - w1[1]) ** 2 <= w_r ** 2
                in_w2 = (x - w2[0]) ** 2 + (y - w2[1]) ** 2 <= w_r ** 2

                if in_body or in_w1 or in_w2:
                    row.extend(accent)
                elif in_handle:
                    row.extend(accent)
                else:
                    row.extend(bg)
            else:
                row.extend((0, 0, 0))  # transparent (will be treated as black)

        img.append(bytes([0] + row))

    def adler32(data):
        s1, s2 = 1, 0
        for b in data: s1 = (s1 + b) % 65521; s2 = (s2 + s1) % 65521
        return (s2 << 16) | s1

    raw = b"".join(img)
    compressed = zlib.compress(raw, 9)

    def chunk(name, data):
        c = name + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )
    with open(path, "wb") as f:
        f.write(png)
    print(f"  Created {path} ({size}×{size})")

import os
os.makedirs("extension/icons", exist_ok=True)
for sz in [16, 48, 128]:
    make_png(sz, f"extension/icons/icon{sz}.png")
print("Icons generated!")
