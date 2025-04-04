from threading import Thread
import os
import os.path
import readline  # Not used directly, but required for previous input completion.
import shlex
import subprocess
import sys

from sdutil.colorize import cyan, red, yellow
from sdutil.fstree import FilesystemTree, format_file_size, size_spec


DEFAULT_MOUNT_POINT = '/'
DEFAULT_SIZE_THRESHOLD = 2**30  # 1 GiB
DEFAULT_TREE_DEPTH = 2

ENCODING = 'utf-8'

SYSTEM_LIBRARY_BASE_DIR = os.path.expanduser('~/Library')
SYSTEM_LIBRARY_DIRS = {'Application Support', 'Caches', 'Containers', 'Group Containers', 'Logs'}


class SDUtil:
    def __init__(self, mount_point: str = DEFAULT_MOUNT_POINT, browse_only: bool = False,
                 size_threshold: int = DEFAULT_SIZE_THRESHOLD, tree_depth: int = DEFAULT_TREE_DEPTH,
                 debug_mode: bool = False) -> None:
        self.mount_point = mount_point
        self.browse_only = browse_only
        self.size_threshold = size_threshold
        self.tree_depth = tree_depth
        self.debug_mode = debug_mode
        self._time_machine_snapshots = None

        self._library_tree = None
        self._library_tree_thread = Thread(target=self.build_library_tree)
        self._library_tree_thread.start()

    @property
    def time_machine_snapshots(self) -> list[str]:
        if self._time_machine_snapshots is None:
            self._time_machine_snapshots = self.get_local_time_machine_snapshots()
        return self._time_machine_snapshots

    @property
    def library_tree(self) -> FilesystemTree:
        if self._library_tree is None:
            self._library_tree_thread.join()
        return self._library_tree

    def build_library_tree(self) -> None:
        self._library_tree = FilesystemTree(SYSTEM_LIBRARY_BASE_DIR, include_paths=SYSTEM_LIBRARY_DIRS)

    def get_output(self, *args) -> str:
        cmd = shlex.join(args)
        self.debug(f'Running command: {cmd}')
        process = subprocess.run(args, capture_output=True)
        if process.returncode != 0:
            err = f'process exited with code {process.returncode}'
            if process.stderr:
                err = process.stderr.decode(ENCODING).strip()
            elif process.stdout:
                err = process.stdout.decode(ENCODING).strip()
            self.log(red(f'Failed to run command: {err}'))
            sys.exit(process.returncode)
        return process.stdout.decode(ENCODING)

    def debug(self, *args) -> None:
        if self.debug_mode:
            print(*(yellow(arg) for arg in args))

    @staticmethod
    def log(*args) -> None:
        print(*args)

    def get_local_time_machine_snapshots(self) -> list[str]:
        lines = self.get_output('tmutil', 'listlocalsnapshots', self.mount_point).splitlines()
        if len(lines) < 2:
            return []
        return [
            line.replace('com.apple.TimeMachine.', '').replace('.local', '')
            for line in lines[1:]
        ]

    def check_time_machine_snapshots(self) -> None:
        self.log(cyan(f'Checking local Time Machine snapshots for {self.mount_point}...'))
        if snapshots := self.time_machine_snapshots:
            self.log(f'  Found {len(snapshots):,} local Time Machine snapshots:')
            for snapshot in snapshots:
                self.log(f'    {snapshot}')
        else:
            self.log(f'  No Time Machine snapshots found for {self.mount_point}.')

    def browse_library_directories(self) -> bool:
        threshold = (
            'to clean' if self.size_threshold <= 0
            else f'over {format_file_size(self.size_threshold, colorize=False)}'
        )
        if self.tree_depth:
            threshold += f' (max depth: {self.tree_depth})'
        if not self.browse_only:
            self.log()
        self.log(cyan(f'Showing system library directories {threshold}...\n'))
        self.library_tree.show(depth=self.tree_depth, min_size=self.size_threshold)

        while True:
            try:
                self.log(cyan('Choose from the following options:'))
                self.log(cyan('[d]'),
                         f'Change tree depth (e.g., "d {self.tree_depth + 1}" to show one more level)')
                self.log(cyan('[s]'), 'Change size threshold (e.g., "s 10G")')
                if not self.browse_only:
                    self.log(cyan('[b]'), 'Back to main menu')
                self.log(cyan('[q]'), 'Quit')
                self.log()
                if selection := input('Enter your choice: ').strip().lower().split():
                    if selection[0] == 'q':
                        break
                    elif selection[0] == 'b' and not self.browse_only:
                        break
                    elif selection[0] == 'd':
                        try:
                            selection[1] = int(selection[1])
                            break
                        except ValueError:
                            pass
                    elif selection[0] == 's':
                        try:
                            selection[1] = size_spec(selection[1])
                            break
                        except ValueError:
                            pass
                self.log(red('Invalid choice.\n'))
            except (EOFError, KeyboardInterrupt):
                return False

        if selection[0] == 'b':
            return True
        if selection[0] == 'q':
            return False
        if selection[0] == 'd':
            self.tree_depth = selection[1]
        if selection[0] == 's':
            self.size_threshold = selection[1]

        if self.browse_only:
            self.log()
        return self.browse_library_directories()

    def delete_time_machine_snapshot(self, snapshot: str) -> None:
        self.log(cyan('\nDeleting local Time Machine snapshot ') + snapshot + cyan('...'))
        self.get_output('tmutil', 'deletelocalsnapshots', snapshot)
        self.time_machine_snapshots.remove(snapshot)
        self.log(cyan('Snapshot deleted successfully.'))

    def delete_time_machine_snapshots_by_date(self) -> bool:
        if not self.time_machine_snapshots:
            return True

        while True:
            try:
                self.log(cyan('\nChoose a snapshot to delete:'))
                for i, snapshot in enumerate(self.time_machine_snapshots):
                    self.log(cyan(f'[{i+1}]'), snapshot)
                self.log(cyan('[b]'), 'Back to main menu')
                self.log(cyan('[q]'), 'Quit')
                self.log()
                selection = input('Enter your choice: ').strip().lower()
                if selection == 'b':
                    return True
                if selection == 'q':
                    return False
                try:
                    index = int(selection)
                except ValueError:
                    index = 0
                if 1 <= index <= len(self.time_machine_snapshots):
                    snapshot_to_delete = self.time_machine_snapshots[index - 1]
                    break
                else:
                    self.log(red('Invalid choice.'))
            except (EOFError, KeyboardInterrupt):
                return False

        self.delete_time_machine_snapshot(snapshot_to_delete)
        return self.delete_time_machine_snapshots_by_date()

    def trim_time_machine_snapshots(self) -> bool:
        while True:
            try:
                selection = input(
                    cyan('\nEnter the minimum amount of space you wish to reclaim (e.g., "1G"): ')
                ).strip().upper()
            except (EOFError, KeyboardInterrupt):
                return True
            try:
                purge_size = size_spec(selection)
                break
            except ValueError:
                self.log(red('Invalid entry.'))

        self.log(cyan('\nAttempting to purge'), format_file_size(purge_size, colorize=False),
                 cyan('of Time Machine snapshots...'))
        self.log(self.get_output('tmutil', 'thinlocalsnapshots', self.mount_point, purge_size, 4))
        self.log(cyan('Finished thinning local Time Machine snapshots.'))
        self._time_machine_snapshots = None
        self.log()
        self.check_time_machine_snapshots()
        return True

    def menu(self) -> None:
        i = 1
        choices = {}
        if self.time_machine_snapshots:
            choices[str(i)] = (
                'Delete specific Time Machine snapshots by date',
                self.delete_time_machine_snapshots_by_date,
            )
            choices[str(i+1)] = (
                'Trim Time Machine snapshots by specifying purge size',
                self.trim_time_machine_snapshots,
            )
            i += 2
        choices[str(i)] = (
            'Browse system library directories to clean',
            self.browse_library_directories,
        )
        choices['q'] = ('Quit', None)

        while True:
            try:
                self.log(cyan('\nChoose from the following options:'))
                for i, (choice, _) in choices.items():
                    self.log(cyan(f'[{i}]'), choice)
                self.log()
                selection = input('Enter your choice: ').strip().lower()
                if selection in choices:
                    break
                else:
                    self.log(red('Invalid choice.'))
            except (EOFError, KeyboardInterrupt):
                return

        if handler := choices[selection][1]:
            if handler():  # Handler returns True to indicate main menu should be shown again.
                self.menu()

    def run(self) -> None:
        if not os.isatty(sys.stdout.fileno()):
            raise RuntimeError('SDUtil must be run in an interactive shell!')
        if self.browse_only:
            self.browse_library_directories()
        else:
            self.check_time_machine_snapshots()
            self.menu()
