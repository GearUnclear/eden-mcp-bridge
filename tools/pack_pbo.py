"""
pack_pbo.py — Minimal PBO packer for Arma 3 addons.
Usage: python pack_pbo.py <source_dir> <output_file>
"""
import os
import sys
import struct
import hashlib

def pack_pbo(source_dir, output_file):
    source_dir = os.path.abspath(source_dir)

    # Collect files (skip $PBOPREFIX$ — it's metadata, not a data file)
    files = []
    for root, dirs, filenames in os.walk(source_dir):
        dirs.sort()
        for fname in sorted(filenames):
            if fname == "$PBOPREFIX$":
                continue
            abs_path = os.path.join(root, fname)
            rel_path = os.path.relpath(abs_path, source_dir).replace(os.sep, "\\")
            files.append((rel_path, abs_path))

    # Read prefix from $PBOPREFIX$ if present
    prefix_file = os.path.join(source_dir, "$PBOPREFIX$")
    prefix = ""
    if os.path.exists(prefix_file):
        with open(prefix_file, "rb") as f:
            prefix = f.read().decode("utf-8").strip().replace("/", "\\")

    data_chunks = []
    header_parts = []

    # --- Version entry (first entry in header) ---
    # filename=\0, method=0x56657273, sizes=0
    version_entry = b"\x00"                    # empty filename
    version_entry += struct.pack("<I", 0x56657273)  # "Vers" method
    version_entry += struct.pack("<I", 0)       # originalSize
    version_entry += struct.pack("<I", 0)       # reserved
    version_entry += struct.pack("<I", 0)       # timestamp
    version_entry += struct.pack("<I", 0)       # dataSize
    # Properties: prefix=value\0
    if prefix:
        version_entry += b"prefix\x00" + prefix.encode("utf-8") + b"\x00"
    version_entry += b"\x00"                    # end of properties

    header_parts.append(version_entry)

    # --- File entries ---
    for rel_path, abs_path in files:
        size = os.path.getsize(abs_path)
        entry = rel_path.encode("utf-8") + b"\x00"
        entry += struct.pack("<I", 0)    # method: uncompressed
        entry += struct.pack("<I", size) # originalSize
        entry += struct.pack("<I", 0)    # reserved
        entry += struct.pack("<I", 0)    # timestamp
        entry += struct.pack("<I", size) # dataSize
        header_parts.append(entry)

        with open(abs_path, "rb") as f:
            data_chunks.append(f.read())

    # --- End-of-header entry ---
    end_entry = b"\x00" + struct.pack("<5I", 0, 0, 0, 0, 0)
    header_parts.append(end_entry)

    # --- Assemble and hash ---
    body = b"".join(header_parts) + b"".join(data_chunks)
    sha1 = hashlib.sha1(body).digest()

    with open(output_file, "wb") as f:
        f.write(body)
        f.write(b"\x00")   # hash marker
        f.write(sha1)

    print(f"Packed {len(files)} files -> {output_file} ({os.path.getsize(output_file)} bytes)")
    if prefix:
        print(f"Prefix: {prefix}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python pack_pbo.py <source_dir> <output_file>")
        sys.exit(1)
    pack_pbo(sys.argv[1], sys.argv[2])
