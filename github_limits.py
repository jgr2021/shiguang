"""Application limits, below GitHub's ordinary Git file-size ceiling."""
FILE_LIMIT = 50 * 1024 * 1024
TOTAL_LIMIT = 500 * 1024 * 1024
FILE_COUNT_LIMIT = 1000
MANIFEST_LIMIT = 16 * 1024 * 1024
JSON_RESPONSE_LIMIT = 24 * 1024 * 1024
# Base64 plus JSON/newline overhead for a 50 MiB attachment.
BLOB_RESPONSE_LIMIT = 80 * 1024 * 1024
BLOB_TIMEOUT_SECONDS = 180
