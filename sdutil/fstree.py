from dataclasses import dataclass, field
from typing import Optional
import glob
import itertools
import os
import os.path
import re

import treelib

from sdutil.colorize import green, red, yellow


SIZE_COLORS = {
    'B': green,
    'K': green,
    'M': yellow,
    'G': red,
    'T': red,
}
SIZE_UNITS = {
    None: 2**0,
    'B': 2**0,
    'K': 2**10,
    'M': 2**20,
    'G': 2**30,
}
SIZE_PATTERN = re.compile(r'^(?P<size>\d+)(?P<unit>[BKMG])?$', re.IGNORECASE)


def size_spec(spec: int | str) -> int:
    if isinstance(spec, int):
        return spec
    if match := SIZE_PATTERN.match(spec):
        factor = SIZE_UNITS[match.group('unit').upper()] if match.group('unit') else 1
        return int(match.group('size')) * factor
    raise ValueError(f'Invalid size specification: {spec!r}')


def format_file_size(size: int, colorize: bool = True, always_include_fraction: bool = False) -> str:
    for unit in list(SIZE_COLORS.keys())[:-1]:
        if abs(size) < 1024.0:
            break
        size /= 1024.0
    else:
        unit = list(SIZE_COLORS.keys())[-1]
    precision = 1 if always_include_fraction or (unit != 'B' and size < 10.0 and size - int(size) > 0.01) else 0
    color_fn = SIZE_COLORS[unit] if colorize else lambda s: s
    return color_fn(f'{size:.{precision}f}{unit}')


@dataclass
class FilesystemNode:
    path: str
    depth: int = 0

    @property
    def is_directory(self) -> bool:
        return isinstance(self, DirectoryNode)

    @property
    def size(self) -> int:
        raise NotImplementedError()

    @property
    def human_readable_size(self) -> str:
        return format_file_size(self.size)

    @property
    def stat(self) -> str:
        name = self.path if self.depth == 0 else os.path.basename(self.path)
        return f'{self.human_readable_size:>4}  {name}'


@dataclass
class FileNode(FilesystemNode):
    @property
    def size(self) -> int:
        try:
            return os.path.getsize(self.path)
        except FileNotFoundError:
            # FileNotFoundError happens for symlinks, which don't consume any space on disk.
            return 0


@dataclass
class DirectoryNode(FilesystemNode):
    subdirectories: list['DirectoryNode'] = field(default_factory=list)
    files: list[FileNode] = field(default_factory=list)

    @property
    def size(self) -> int:
        return sum(file.size for file in self.files) + sum(directory.size for directory in self.subdirectories)


class FilesystemTree(treelib.Tree):

    def __init__(self, root_path: str, include_paths: Optional[set[str]] = None) -> None:
        super().__init__()
        root = os.path.abspath(os.path.expanduser(root_path))
        if not os.path.exists(root) or not os.path.isdir(root):
            raise ValueError(f'Root path "{root_path}" must be a directory!')
        if include_paths is not None and not include_paths:
            raise ValueError(f'If provided, include paths must not be empty!')
        self.root_path = root
        self.include_paths = self.expand_include_paths(include_paths)
        self.populate_tree()

    def expand_include_paths(self, include_paths: Optional[set[str]]) -> set[str]:
        if include_paths is None:
            return set()
        return set(itertools.chain(*(
            (os.path.join(self.root_path, match) for match in glob.glob(path, root_dir=self.root_path, recursive=True))
            for path in include_paths
        )))

    def should_include_path(self, path: str) -> bool:
        if not self.include_paths or path in self.include_paths:
            return True
        while path != self.root_path:
            path = os.path.dirname(path)
            if path in self.include_paths:
                return True
        return False

    def populate_tree(self) -> None:
        self.create_node(self.root_path, self.root_path, data=DirectoryNode(self.root_path))

        for dir_path, dir_names, file_names in os.walk(self.root_path):
            parent = self.get_node(dir_path)
            for dir_name in dir_names:
                path = os.path.join(dir_path, dir_name)
                if self.should_include_path(path):
                    dir_node = DirectoryNode(path, depth=parent.data.depth + 1)
                    parent.data.subdirectories.append(dir_node)
                    self.create_node(dir_name, path, parent=parent, data=dir_node)
            for file_name in file_names:
                path = os.path.join(dir_path, file_name)
                if self.should_include_path(path):
                    file_node = FileNode(path, depth=parent.data.depth + 1)
                    parent.data.files.append(file_node)
                    self.create_node(file_name, path, parent=parent, data=file_node)

    def show(self, depth: int = 0, min_size: Optional[int | str] = None, **kwargs) -> None:
        kwargs.setdefault('data_property', 'stat')
        kwargs.setdefault('key', lambda n: n.data.size)
        kwargs.setdefault('reverse', True)

        default_filter = lambda n: True
        user_filter = kwargs.get('filter', default_filter)
        depth_filter = (lambda n: n.data.depth <= depth) if depth > 0 else default_filter
        min_size_spec = size_spec(min_size) if min_size else 0
        size_filter = lambda n: n.data.size >= min_size_spec
        kwargs['filter'] = lambda n: user_filter(n) and depth_filter(n) and size_filter(n)

        super().show(**kwargs)
