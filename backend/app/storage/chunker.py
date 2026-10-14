import hashlib
from collections.abc import Iterator


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def chunk_bytes(data: bytes, chunk_size: int) -> Iterator[tuple[int, str, bytes]]:
    """Yield (block_index, sha256_hex, chunk_bytes) for content-addressed storage."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    if not data:
        digest = sha256_hex(b"")
        yield 0, digest, b""
        return

    index = 0
    offset = 0
    length = len(data)
    while offset < length:
        chunk = data[offset : offset + chunk_size]
        yield index, sha256_hex(chunk), chunk
        index += 1
        offset += chunk_size
