"""Single-node host-definition helper."""


def hd_lines(*, host: str, remote_user: str, vdbench_home: str) -> str:
    if not host or not remote_user or not vdbench_home:
        raise ValueError("single-node host settings must be non-empty")
    return (
        f"hd=default,vdbench={vdbench_home},user={remote_user},shell=ssh\n"
        f"hd=hd1,system={host}"
    )
