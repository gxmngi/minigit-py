# RFC: Git Packfile (.pack) and Index (.idx v2) Architecture

## 1. Context & Motivation
Loose objects stored in `.git/objects/??/` incur significant inode overhead on disk. Git bundles objects into compact `.pack` archives accompanied by `.idx` v2 files for fast $O(\log N)$ binary search lookup.

---

## 2. Packfile Index (.idx v2) Binary Layout

```text
+-------------------------------------------------------------------+
| Magic Header: \xff t O c (4 Bytes)                                |
| Version Number: 0x00 0x00 0x00 0x02 (4 Bytes)                     |
+-------------------------------------------------------------------+
| Level-1 Fan-Out Table (256 entries x 4B = 1024 Bytes)             |
| Cumulative count of objects with first byte <= index              |
+-------------------------------------------------------------------+
| SHA-1 Table (N x 20 Bytes)                                        |
| Sorted lexicographically by 20-byte binary object hash            |
+-------------------------------------------------------------------+
| CRC32 Table (N x 4 Bytes)                                         |
| Cyclic redundancy check values for compressed data integrity      |
+-------------------------------------------------------------------+
| Byte-Offset Table (N x 4 Bytes)                                   |
| 31-bit file offset into the companion .pack archive               |
+-------------------------------------------------------------------+
| Checksums:                                                        |
| - 20B Packfile SHA-1 Checksum                                     |
| - 20B Index SHA-1 Checksum                                        |
+-------------------------------------------------------------------+
```

---

## 3. Packfile (.pack) Format

1. **Header (12 Bytes)**:
   - `4B`: Signature `'PACK'`
   - `4B`: Version `2`
   - `4B`: Number of objects `N`
2. **Object Entries**:
   - Variable-length size/type encoded byte
   - Delta compression chain (`OBJ_OFS_DELTA` or `OBJ_REF_DELTA`)
   - Deflate compressed object payload
3. **Trailer**:
   - `20B`: SHA-1 checksum over all preceding bytes

---

## 4. Acceptance Invariants
- Binary search through Level-1 fanout resolves object offsets in $O(1) + O(\log M)$ time.
- SHA-1 trailer match asserts non-corrupt archive state before payload decompression.
