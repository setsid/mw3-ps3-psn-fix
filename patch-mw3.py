#!/usr/bin/env python3
"""Patch the MW3 PS3 multiplayer binary so a failed Demonware profile lookup
stops being fatal.

BLES01428 TU 1.24. Operates on a decrypted or RAM reconstructed ELF, not on the
encrypted default_mp.self.
"""

import argparse
import hashlib
import shutil
import struct
import sys

VADDR = 0x00340D20

# bl 0x43f010 / cmpwi r27,2 / ori r28,r3,0 / bne 0x340dc0
# The site is located by signature rather than by offset so the tool still works
# on a rebased or differently reconstructed image.
SIG_STOCK = bytes.fromhex("480FE2F9 2C1B0002 607C0000 408200 9C".replace(" ", ""))
SIG_PATCHED = bytes.fromhex("480FE2F9 2C1B0002 3B800000 408200 9C".replace(" ", ""))

INSN_OFFSET = 8
STOCK = bytes.fromhex("607C0000")
PATCHED = bytes.fromhex("3B800000")


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_segments(data):
    """Return (offset, vaddr, filesz) for each PT_LOAD, or None if not an ELF64 BE."""
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 2:
        return None
    phoff = struct.unpack_from(">Q", data, 0x20)[0]
    phentsize, phnum = struct.unpack_from(">HH", data, 0x36)
    out = []
    for i in range(phnum):
        b = phoff + i * phentsize
        p_type = struct.unpack_from(">I", data, b)[0]
        if p_type != 1:
            continue
        off, vaddr = struct.unpack_from(">QQ", data, b + 0x08)
        filesz = struct.unpack_from(">Q", data, b + 0x20)[0]
        if filesz:
            out.append((off, vaddr, filesz))
    return out


def vaddr_to_offset(segments, vaddr):
    for off, va, filesz in segments:
        if va <= vaddr < va + filesz:
            return off + (vaddr - va)
    return None


def find_site(data):
    """Return (offset, state) where state is 'stock' or 'patched'."""
    for sig, state in ((SIG_STOCK, "stock"), (SIG_PATCHED, "patched")):
        hits = []
        start = 0
        while True:
            i = data.find(sig, start)
            if i < 0:
                break
            hits.append(i)
            start = i + 1
        if len(hits) > 1:
            sys.exit("signature matched %d times, refusing to guess" % len(hits))
        if hits:
            return hits[0] + INSN_OFFSET, state
    return None, None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("binary", help="decrypted or RAM reconstructed MW3 MP ELF")
    ap.add_argument("-o", "--output", help="write here instead of editing in place")
    ap.add_argument("--restore", action="store_true", help="put the stock instruction back")
    ap.add_argument("--check", action="store_true", help="report state and exit")
    args = ap.parse_args()

    data = bytearray(open(args.binary, "rb").read())
    print("input   %s" % args.binary)
    print("size    %d bytes" % len(data))
    print("sha1    %s" % sha1(args.binary))

    off, state = find_site(data)
    if off is None:
        sys.exit("patch site not found: this does not look like BLES01428 TU 1.24 MP")

    segments = load_segments(data)
    if segments:
        expected = vaddr_to_offset(segments, VADDR)
        if expected is None:
            print("warning: vaddr %08X not covered by any PT_LOAD" % VADDR)
        elif expected != off:
            print("warning: signature at %08X, program headers put %08X at %08X"
                  % (off, VADDR, expected))
        else:
            print("vaddr   %08X" % VADDR)
    else:
        print("note    not an ELF64 BE image, using signature match only")

    print("offset  %08X" % off)
    print("state   %s" % state)

    if args.check:
        return

    want = "stock" if args.restore else "patched"
    if state == want:
        print("nothing to do, already %s" % want)
        return

    data[off:off + 4] = STOCK if args.restore else PATCHED

    dest = args.output or args.binary
    if args.output:
        shutil.copystat(args.binary, args.binary)
    open(dest, "wb").write(data)

    print()
    print("wrote   %s" % dest)
    print("%08X  %s -> %s" % (off,
                              (PATCHED if args.restore else STOCK).hex().upper(),
                              (STOCK if args.restore else PATCHED).hex().upper()))
    print("sha1    %s" % sha1(dest))


if __name__ == "__main__":
    main()
