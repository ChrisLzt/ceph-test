"""Shared generators for the single-node and SYSU Vdbench workloads."""

from .layout import SINGLE_LAYOUT, SYSU_LAYOUT, Bucket, Layout

__all__ = ["Bucket", "Layout", "SINGLE_LAYOUT", "SYSU_LAYOUT"]
