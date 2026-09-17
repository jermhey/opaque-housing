"""Union-find clustering. Pure functions."""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def cluster_members(
    nodes: Iterable[str],
    pairs: Sequence[tuple[str, str]],
) -> dict[str, str]:
    """Return owner_key → cluster root (the cluster_id)."""
    parent: dict[str, str] = {}

    def add(node: str) -> None:
        if node and node not in parent:
            parent[node] = node

    for node in nodes:
        add(node)
    for left, right in pairs:
        add(left)
        add(right)

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: str, right: str) -> None:
        if not left or not right:
            return
        root_l = find(left)
        root_r = find(right)
        if root_l != root_r:
            parent[root_r] = root_l

    for left, right in pairs:
        union(left, right)
    return {node: find(node) for node in parent}


def component_sizes(membership: dict[str, str], keep: set[str] | None = None) -> dict[str, int]:
    sizes: dict[str, int] = {}
    for node, root in membership.items():
        if keep is not None and node not in keep:
            continue
        sizes[root] = sizes.get(root, 0) + 1
    return sizes
