# SyncSelectedFilesToOtherPaneForWindows

A Windows-only fman plugin that syncs selected files and folders to the other pane using robocopy.

## Features

- Uses robocopy for fast and efficient file synchronization
- Shows progress in the status bar
- Two modes of operation:
  - Dry run: Logs commands to ~/.fman/sync_commands_dry_run.log
  - Actual execution: Executes commands and logs to ~/.fman/sync_commands.log
- Only works on Windows (uses robocopy)

## Usage

### Dry Run Mode

1. Select files/folders in one pane
2. Run the "Sync selected files to other pane - dry run" command from the command palette
3. Check ~/.fman/sync_commands_dry_run.log to preview the robocopy commands that would be executed

### Actual Execution Mode

1. Select files/folders in one pane
2. Run the "Sync selected files to other pane" command from the command palette
3. The files will be synced to the other pane using robocopy
4. Check ~/.fman/sync_commands.log for the executed commands and their output

## Technical Details

- Uses robocopy with /e /MT:32 flags for efficient copying
- /e flag copies subdirectories including empty ones
- /MT:32 flag uses 32 threads for multi-threaded copying
- Robocopy's built-in file comparison ensures only changed files are copied
- Detailed logging includes:
  - Timestamps for each operation
  - Full robocopy commands
  - Command output and error messages
  - Exit codes

## Requirements

- Windows operating system (plugin uses robocopy)
- fman file manager
