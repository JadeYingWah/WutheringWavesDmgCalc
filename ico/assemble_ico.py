"""Merge single-size Wico*.ico files into one multi-resolution icon.ico."""
import struct

HERE = r"c:\Users\yutia\Python\WutheringWavesDmgCalc\ico"
SIZES = [256, 128, 64, 48, 32, 24, 16]

entries = []   # list of (width, height, image_data_bytes)
for sz in SIZES:
    path = f"{HERE}\\Wico{sz}.ico"
    with open(path, "rb") as f:
        data = f.read()

    # Parse ICO header
    count = struct.unpack_from("<H", data, 4)[0]
    # Parse first (only) directory entry
    w = struct.unpack_from("<B", data, 6)[0]
    w = w if w != 0 else 256
    h = struct.unpack_from("<B", data, 7)[0]
    h = h if h != 0 else 256
    img_size = struct.unpack_from("<I", data, 14)[0]
    img_offset = struct.unpack_from("<I", data, 18)[0]

    img_data = data[img_offset : img_offset + img_size]
    entries.append((w, h, img_data))
    print(f"  {sz}x{sz}: {w}x{h}  data={img_size} bytes  offset_in_source={img_offset}")

# ── Assemble multi-resolution ICO ──
total_count = len(entries)
header = struct.pack("<HHH", 0, 1, total_count)

dir_bytes = b""
data_bytes = b""
offset = 6 + total_count * 16

for w, h, img_data in entries:
    ew = w if w < 256 else 0
    eh = h if h < 256 else 0
    dir_bytes += struct.pack(
        "<BBBBHHII", ew, eh, 0, 0, 1, 32, len(img_data), offset,
    )
    data_bytes += img_data
    offset += len(img_data)

out = header + dir_bytes + data_bytes
out_path = HERE + r"\icon.ico"
with open(out_path, "wb") as f:
    f.write(out)

print(f"\nDone: {out_path}  ({len(out)} bytes, {total_count} sizes)")
