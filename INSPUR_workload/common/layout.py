"""INSPUR physical file layout for the shared logical workload models."""

from workload_common.layout import Layout


INSPUR_LAYOUT = Layout(
    name="inspur",
    sizes_mib=(16, 32, 64, 128, 256),
    files_per_unit=(16, 8, 4, 2, 1),
)
