from fman import DirectoryPaneCommand, show_status_message, clear_status_message, show_alert, Task, submit_task
from fman.url import as_human_readable
import os
import sys
import datetime
import subprocess
import time
from abc import ABC

class SyncFilesTask(Task):
    def __init__(self, files_to_sync, target_path, target_pane):
        super().__init__('Syncing Files')
        self._files = files_to_sync
        self._target_path = target_path
        self._target_pane = target_pane
        self._current_process = None
        self.set_size(len(files_to_sync))

    def _interpret_robocopy_exit_code(self, exit_code):
        """Interpret robocopy exit codes and return a tuple of (success, message)"""
        if exit_code <= 7:  # Success codes
            return True, {
                0: "No files copied",
                1: "Files copied successfully",
                2: "Extra files or directories detected",
                3: "Some files copied, extra files detected",
                4: "Some mismatched files or directories detected",
                5: "Some files copied, some failed",
                6: "Additional files and mismatched files exist",
                7: "Files and directories copied with errors"
            }.get(exit_code, "Operation completed with code " + str(exit_code))
        elif exit_code == 8:
            return False, "Some files or directories could not be copied"
        else:
            return False, f"Serious error occurred (code {exit_code})"

    def __call__(self):
        try:
            # Setup log file
            log_dir = os.path.expanduser("~/.fman")
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, "sync_commands.log")

            # Process each file
            for i, (source_path, is_dir) in enumerate(self._files, 1):
                filename = os.path.basename(source_path)
                self.set_text(f'Copying {i} of {len(self._files)}: {filename}')

                # Generate robocopy command with progress output
                if is_dir:
                    cmd = f'robocopy "{source_path}" "{self._target_path}/{filename}" /e /MT:32 /bytes /np'
                else:
                    cmd = f'robocopy "{os.path.dirname(source_path)}" "{self._target_path}" "{filename}" /MT:32 /bytes /np'

                # Log command with timestamp
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f'[{timestamp}] {cmd}\n')

                # Setup process startup info for Windows
                startupinfo = None
                if sys.platform.startswith('win'):
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                # Execute robocopy command
                self._current_process = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    startupinfo=startupinfo,
                    encoding='utf-8',
                    errors='replace'
                )

                # Monitor output and progress
                while True:
                    self.check_canceled()
                    
                    # Read a line of output
                    output_line = self._current_process.stdout.readline()
                    if not output_line and self._current_process.poll() is not None:
                        break
                        
                    # Log output
                    with open(log_file, 'a', encoding='utf-8') as f:
                        f.write(output_line)
                        
                    # Update status if it contains progress information
                    if "%" in output_line:
                        self.set_text(f'Copying {i} of {len(self._files)}: {filename} - {output_line.strip()}')

                # Get remaining output and exit code
                stdout, stderr = self._current_process.communicate()
                exit_code = self._current_process.returncode
                success, message = self._interpret_robocopy_exit_code(exit_code)

                # Log completion and status
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f'[{timestamp}] {message} (Exit Code: {exit_code})\n')
                    if stderr:
                        f.write(f'[{timestamp}] Errors: {stderr}\n')

                if not success:
                    show_status_message(f'Warning: {message} while copying {filename}')

                # Update progress
                self.set_progress(i)

                # Refresh the target pane
                self._target_pane.reload()

        except Task.Canceled:
            # Handle cancellation
            if self._current_process and self._current_process.poll() is None:
                self._current_process.kill()
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f'[{timestamp}] Task canceled by user\n')
            show_status_message('Sync canceled')
            raise
        except Exception as e:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f'[{timestamp}] Error: {str(e)}\n')
            raise

class SyncFilesBase(ABC):
    def __init__(self, pane):
        self.pane = pane

    def _check_windows(self):
        if not sys.platform.startswith('win'):
            show_alert("This plugin only works on Windows")
            return False
        return True

    def _get_selected_files(self):
        selected_files = self.pane.get_selected_files()
        if not selected_files:
            show_alert("No elements selected")
            return None
        return selected_files

    def _get_opposite_pane(self, pane):
        try:
            panes = pane.window.get_panes()
            if len(panes) < 2:
                show_alert("No other pane available")
                return None
            current_index = panes.index(pane)
            if current_index == 0:
                return panes[1]  # If we're in first pane, return second
            return panes[0]  # Otherwise return first
        except Exception as e:
            show_alert(f"Error getting target pane: {str(e)}")
            return None

    def _ensure_log_dir(self):
        log_dir = os.path.expanduser("~/.fman")
        os.makedirs(log_dir, exist_ok=True)
        return log_dir

class SyncSelectedFilesToOtherPaneDryRunForWindows(DirectoryPaneCommand, SyncFilesBase):
    aliases = ('Sync selected files to other pane - dry run',)

    def __call__(self):
        super().__init__(self.pane)
        if not self._check_windows():
            return

        selected_files = self._get_selected_files()
        if not selected_files:
            return

        target_pane = self._get_opposite_pane(self.pane)
        if not target_pane:
            return
            
        target_path = as_human_readable(target_pane.get_path())

        # Setup log file
        log_dir = self._ensure_log_dir()
        log_file = os.path.join(log_dir, "sync_commands_dry_run.log")
        
        # Delete existing log file
        if os.path.exists(log_file):
            os.remove(log_file)

        # Process each selected file/folder
        total_elements = len(selected_files)
        for i, file_url in enumerate(selected_files, 1):
            show_status_message(f'Processing element {i} of {total_elements}: {os.path.basename(file_url)}')
            source_path = as_human_readable(file_url)
            
            # Generate robocopy command with progress output flags
            if os.path.isdir(source_path):
                cmd = f'robocopy "{source_path}" "{target_path}/{os.path.basename(source_path)}" /e /MT:32 /bytes /np'
            else:
                cmd = f'robocopy "{os.path.dirname(source_path)}" "{target_path}" "{os.path.basename(source_path)}" /MT:32 /bytes /np'

            # Log command with timestamp
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f'[{timestamp}] {cmd}\n')

        show_status_message('Robocopy commands logged to ~/.fman/sync_commands_dry_run.log')

class SyncSelectedFilesToOtherPaneForWindows(DirectoryPaneCommand, SyncFilesBase):
    aliases = ('Sync selected files to other pane',)

    def __call__(self):
        super().__init__(self.pane)
        if not self._check_windows():
            return

        selected_files = self._get_selected_files()
        if not selected_files:
            return

        target_pane = self._get_opposite_pane(self.pane)
        if not target_pane:
            return
            
        target_path = as_human_readable(target_pane.get_path())

        # Setup log file
        log_dir = self._ensure_log_dir()
        log_file = os.path.join(log_dir, "sync_commands.log")
        
        # Delete existing log file
        if os.path.exists(log_file):
            os.remove(log_file)

        # Prepare files list
        files_to_sync = [
            (as_human_readable(file_url), os.path.isdir(as_human_readable(file_url))) 
            for file_url in selected_files
        ]

        # Create and submit single task for all files
        task = SyncFilesTask(files_to_sync, target_path, target_pane)
        submit_task(task)
