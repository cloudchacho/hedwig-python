import functools
import re
from typing import Tuple


@functools.total_ordering
class StrictVersion:
    """
    A ``major.minor[.patch]`` version, compatible with ``distutils.version.StrictVersion``, which Python 3.12 removed.
    """

    _version_re = re.compile(r'^(\d+)\.(\d+)(?:\.(\d+))?$')

    version: Tuple[int, int, int]

    def __init__(self, vstring: str) -> None:
        match = self._version_re.match(str(vstring))
        if not match:
            raise ValueError(f"invalid version number '{vstring}'")
        major, minor, patch = match.groups()
        self.version = (int(major), int(minor), int(patch or 0))

    def __str__(self) -> str:
        if self.version[2] == 0:
            return f'{self.version[0]}.{self.version[1]}'
        return '.'.join(str(part) for part in self.version)

    def __repr__(self) -> str:
        return f"StrictVersion('{self}')"

    def __hash__(self) -> int:
        return hash(self.version)

    @staticmethod
    def _coerce(other):
        if isinstance(other, StrictVersion):
            return other.version
        if isinstance(other, str):
            return StrictVersion(other).version
        version = getattr(other, 'version', None)
        if isinstance(version, tuple):
            return tuple(version)
        return None

    def __eq__(self, other) -> bool:
        other_version = self._coerce(other)
        if other_version is None:
            return NotImplemented
        return self.version == other_version

    def __lt__(self, other) -> bool:
        other_version = self._coerce(other)
        if other_version is None:
            return NotImplemented
        return self.version < other_version
