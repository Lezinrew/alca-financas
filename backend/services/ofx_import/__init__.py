"""
Pacote de importação OFX especializado do AlcaHub.
"""
from .parser import decode_ofx_bytes, extract_account_metadata, parse_raw_ofx_transactions
from .nature import classify_nature, TransactionNature
from .dedup import build_dedup_key, compute_dedup_key, deduplicate_batch
from .categorizer import AliasCategorizer
from .normalizer import normalize_batch_objects
from .pipeline import OfxImportPipeline

__all__ = [
    'decode_ofx_bytes',
    'extract_account_metadata',
    'parse_raw_ofx_transactions',
    'classify_nature',
    'TransactionNature',
    'build_dedup_key',
    'compute_dedup_key',
    'deduplicate_batch',
    'AliasCategorizer',
    'normalize_batch_objects',
    'OfxImportPipeline'
]
