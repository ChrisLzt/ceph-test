"""Compatibility access to the repository-level shared generators."""

from workload_common.layout import SYSU_LAYOUT, Bucket, Layout, make_rank_buckets, rank_bucket_skews

__all__ = [
    "Bucket",
    "Layout",
    "SYSU_LAYOUT",
    "make_rank_buckets",
    "rank_bucket_skews",
]
