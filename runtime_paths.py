# SPDX-License-Identifier: AGPL-3.0-only
"""Separate immutable program resources from local user recordings."""
import os
from pathlib import Path


def data_directory():
    override = os.environ.get('A350_REPORTER_DATA_DIR')
    if override:
        return Path(override).expanduser().resolve()
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    else:
        base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
    return base / 'A350FuelReporter'
