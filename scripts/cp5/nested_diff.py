"""CP-5J comparison engine: recursive, value-blind structural diff.

This module is the *comparison engine* half of the CP-5J Terraform saved-plan
diff checker. It is deliberately separate from the policy/reporting half
(``plan_diff_checker.py``).

Contract
--------
* Pure functions over in-memory, already-materialized JSON data
  (``dict`` / ``list`` / ``str`` / ``int`` / ``float`` / ``bool`` / ``None``).
* No I/O of any kind: no file access, no environment access, no network,
  no subprocesses, no logging, no printing.
* Results contain attribute *paths* only. No attribute value ever leaves this
  module: not in return values, not in exception messages, not in ``repr``.
* Any structural uncertainty raises :class:`MalformedInput` carrying a fixed,
  generic reason code (never a value).

Path model
----------
A path is a tuple of segments. ``str`` segments are object keys, ``int``
segments are positional list indexes (Terraform nested blocks such as
``environment[0].variables`` are positional, so lists are never sorted).

``after_unknown`` semantics
---------------------------
``after_unknown`` mirrors the shape of ``after``. A boolean ``true`` at a
path means the whole value at that path is unknown until apply. A nested
object/array is *not* itself "unknown": it is recursed into, and only
``true`` leaves are reported as unknown paths. ``false`` or an absent entry
means "known".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, FrozenSet, Tuple, Union

Segment = Union[str, int]
Path = Tuple[Segment, ...]

#: Maximum nesting depth accepted before the input is treated as malformed.
MAX_DEPTH = 64


class _Missing:
    """Sentinel for an absent object key / list index (distinct from null)."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - cosmetic only
        return "<MISSING>"


MISSING: Any = _Missing()


class MalformedInput(Exception):
    """Raised for structurally invalid input.

    Only a fixed reason code is carried. No input value is ever attached to
    the exception, its message, or its ``repr``.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason

    def __repr__(self) -> str:
        return "MalformedInput(%s)" % self.reason

    def __str__(self) -> str:
        return self.reason


@dataclass(frozen=True)
class DiffResult:
    """Sets of changed (known) paths and unknown paths. Paths only."""

    changed: FrozenSet[Path]
    unknown: FrozenSet[Path]


_SCALAR_TYPES = (str, int, float, bool, type(None))


def path_sort_key(path: Path) -> Tuple[Tuple[int, Any], ...]:
    """Deterministic total order over paths mixing int and str segments."""
    return tuple((0, seg) if isinstance(seg, int) else (1, seg) for seg in path)


def _is_container(value: Any) -> bool:
    return isinstance(value, (dict, list))


def validate_json_value(value: Any, depth: int = 0) -> None:
    """Fail closed unless ``value`` is plain JSON data within depth limits."""
    if depth > MAX_DEPTH:
        raise MalformedInput("depth_exceeded")
    if value is MISSING:
        return
    # ``type(...) in`` rather than isinstance: rejects bool/int/str subclasses
    # whose __eq__/__repr__ could be attacker-controlled.
    if type(value) in _SCALAR_TYPES:
        return
    if type(value) is dict:
        for key, child in value.items():
            if type(key) is not str:
                raise MalformedInput("object_key_not_string")
            validate_json_value(child, depth + 1)
        return
    if type(value) is list:
        for child in value:
            validate_json_value(child, depth + 1)
        return
    raise MalformedInput("value_type_invalid")


def validate_marker(marker: Any, depth: int = 0) -> None:
    """Validate an ``after_unknown`` / ``*_sensitive`` marker tree.

    Markers may contain only booleans, objects and arrays.
    """
    if depth > MAX_DEPTH:
        raise MalformedInput("depth_exceeded")
    if marker is MISSING or type(marker) is bool:
        return
    if type(marker) is dict:
        for key, child in marker.items():
            if type(key) is not str:
                raise MalformedInput("marker_key_not_string")
            validate_marker(child, depth + 1)
        return
    if type(marker) is list:
        for child in marker:
            validate_marker(child, depth + 1)
        return
    raise MalformedInput("marker_type_invalid")


def marker_has_true(marker: Any) -> bool:
    """True if any leaf in a (validated) marker tree is boolean true."""
    if marker is True:
        return True
    if type(marker) is dict:
        return any(marker_has_true(child) for child in marker.values())
    if type(marker) is list:
        return any(marker_has_true(child) for child in marker)
    return False


def _strict_equal(left: Any, right: Any) -> bool:
    """Exact structural equality; bool/int/float are never conflated."""
    if left is MISSING or right is MISSING:
        return left is right
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        if set(left) != set(right):
            return False
        return all(_strict_equal(left[k], right[k]) for k in left)
    if type(left) is list:
        if len(left) != len(right):
            return False
        return all(_strict_equal(a, b) for a, b in zip(left, right))
    return bool(left == right)


def _child(container: Any, seg: Segment) -> Any:
    if type(container) is dict and type(seg) is str:
        return container.get(seg, MISSING)
    if type(container) is list and type(seg) is int:
        return container[seg] if seg < len(container) else MISSING
    return MISSING


def diff_values(before: Any, after: Any, after_unknown: Any) -> DiffResult:
    """Recursively compare ``before`` and ``after`` honouring ``after_unknown``.

    Returns every changed known path and every unknown leaf path. Raises
    :class:`MalformedInput` on any structural uncertainty.
    """
    validate_json_value(before)
    validate_json_value(after)
    validate_marker(after_unknown)
    changed: set = set()
    unknown: set = set()
    _walk(before, after, after_unknown, (), 0, changed, unknown)
    return DiffResult(frozenset(changed), frozenset(unknown))


def _walk(
    before: Any,
    after: Any,
    unk: Any,
    path: Path,
    depth: int,
    changed: set,
    unknown: set,
) -> None:
    if depth > MAX_DEPTH:
        raise MalformedInput("depth_exceeded")

    if unk is True:
        # Terraform omits (or nulls) unknown values in ``after``. A concrete
        # value alongside an unknown marker is contradictory input.
        if after is not MISSING and after is not None:
            raise MalformedInput("unknown_with_known_value")
        unknown.add(path)
        return

    if unk is False:
        unk = MISSING

    if type(unk) is dict and type(after) is not dict:
        if marker_has_true(unk):
            raise MalformedInput("unknown_shape_mismatch")
        unk = MISSING
    if type(unk) is list and type(after) is not list:
        if marker_has_true(unk):
            raise MalformedInput("unknown_shape_mismatch")
        unk = MISSING

    if type(before) is dict and type(after) is dict:
        keys = set(before) | set(after)
        if type(unk) is dict:
            keys |= set(unk)
        for key in sorted(keys):
            _walk(
                before.get(key, MISSING),
                after.get(key, MISSING),
                _child(unk, key),
                path + (key,),
                depth + 1,
                changed,
                unknown,
            )
        return

    if type(before) is list and type(after) is list:
        length = max(len(before), len(after))
        if type(unk) is list:
            length = max(length, len(unk))
        for index in range(length):
            _walk(
                _child(before, index),
                _child(after, index),
                _child(unk, index),
                path + (index,),
                depth + 1,
                changed,
                unknown,
            )
        return

    # Absent on both sides with an absent/false marker: nothing to compare.
    if before is MISSING and after is MISSING:
        if unk is not MISSING and marker_has_true(unk):
            raise MalformedInput("unknown_shape_mismatch")
        return

    # Mixed kinds (scalar vs container, null vs missing, ...) or scalars.
    if type(unk) in (dict, list) and marker_has_true(unk):
        # ``after`` is a container here only if before is not the same kind;
        # report nested unknown leaves beneath a replaced container.
        if type(after) is dict or type(after) is list:
            _collect_unknown_leaves(unk, path, depth, unknown)
    if not _strict_equal(before, after):
        changed.add(path)


def _collect_unknown_leaves(unk: Any, path: Path, depth: int, unknown: set) -> None:
    if depth > MAX_DEPTH:
        raise MalformedInput("depth_exceeded")
    if unk is True:
        unknown.add(path)
    elif type(unk) is dict:
        for key in sorted(unk):
            _collect_unknown_leaves(unk[key], path + (key,), depth + 1, unknown)
    elif type(unk) is list:
        for index, child in enumerate(unk):
            _collect_unknown_leaves(child, path + (index,), depth + 1, unknown)


def marker_covers(marker: Any, path: Path) -> bool:
    """Conservative sensitivity lookup in a validated sensitivity marker.

    True when ``true`` is set at ``path``, at any ancestor of ``path``, or at
    any descendant of ``path``. A marker whose shape does not fit the path
    (object marker vs index segment, etc.) is treated as sensitive.
    """
    node = marker
    for seg in path:
        if node is True:
            return True
        if node is MISSING or node is False or node is None:
            return False
        if type(node) is dict:
            if type(seg) is not str:
                return True
            node = node.get(seg, MISSING)
        elif type(node) is list:
            if type(seg) is not int:
                return True
            node = node[seg] if seg < len(node) else MISSING
        else:
            return True
    return marker_has_true(node)


def value_at(root: Any, path: Path) -> Any:
    """Fetch the value at ``path`` (or ``MISSING``). For internal checks only.

    Callers must never emit the returned value.
    """
    node = root
    for seg in path:
        node = _child(node, seg)
        if node is MISSING:
            return MISSING
    return node
