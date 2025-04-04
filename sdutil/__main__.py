import argparse
import sys

from sdutil import DEFAULT_MOUNT_POINT, DEFAULT_TREE_DEPTH, SDUtil
from sdutil.fstree import size_spec


class SDUtilMain:
    def __init__(self) -> None:
        parsed_args = self.parse_args(sys.argv[1:])
        self.mount_point = parsed_args.mount_point
        self.debug = parsed_args.verbose
        self.browse_only = parsed_args.browse
        self.size_threshold = parsed_args.size
        self.tree_depth = parsed_args.depth

    @staticmethod
    def parse_args(args: list[str]) -> argparse.Namespace:
        parser = argparse.ArgumentParser(description='Manage System Data files and local Time Machine snapshots'
                                                     ' on macOS.')
        parser.add_argument('mount_point', nargs='?', default=DEFAULT_MOUNT_POINT,
                            help=f'Path to filesystem mount point (default: "{DEFAULT_MOUNT_POINT}")')
        parser.add_argument('-b', '--browse', action='store_true',
                            help='Browse system library directories only (skip the main menu)')
        parser.add_argument('-d', '--depth', type=int, default=DEFAULT_TREE_DEPTH,
                            help='Number of levels to show when browsing system library directories'
                                 f' (default: {DEFAULT_TREE_DEPTH})')
        parser.add_argument('-s', '--size', type=size_spec, default='1G',
                            help='Minimum size for system library directories/files to be included (default: "1G";'
                                 ' allowed units: B, K, M, G)')
        parser.add_argument('-v', '--verbose', action='store_true', help='Enable debug logging')
        return parser.parse_args(args)

    def run(self) -> None:
        SDUtil(
            mount_point=self.mount_point,
            browse_only=self.browse_only,
            size_threshold=self.size_threshold,
            tree_depth=self.tree_depth,
            debug_mode=self.debug
        ).run()


def main() -> None:
    SDUtilMain().run()


if __name__ == '__main__':
    main()
