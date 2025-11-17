"""
Utility to safely write to .env files.
"""
import re
from pathlib import Path
from typing import Optional


def update_env_file(key: str, value: str, env_path: Optional[Path] = None) -> None:
    """
    Update or add a key-value pair in the .env file.

    This function:
    1. Reads the entire .env file
    2. Uses regex to find and replace the existing key=value pair
    3. If the key doesn't exist, appends it to the file
    4. Writes the updated content back to disk

    Args:
        key: The environment variable name (e.g., "TRADING_TOKEN")
        value: The new value to set
        env_path: Path to the .env file (defaults to .env in current directory)

    Raises:
        IOError: If there's an error reading or writing the file
    """
    if env_path is None:
        env_path = Path(".env")

    # Create .env file if it doesn't exist
    if not env_path.exists():
        env_path.touch()

    # Read existing content
    content = env_path.read_text(encoding="utf-8")

    # Pattern to match the key with any existing value
    # Matches: KEY=value or KEY="value" or KEY='value'
    pattern = rf'^{re.escape(key)}=.*$'

    # New line to insert
    new_line = f'{key}={value}'

    # Check if key exists in file
    if re.search(pattern, content, re.MULTILINE):
        # Replace existing value
        updated_content = re.sub(pattern, new_line, content, flags=re.MULTILINE)
    else:
        # Add new key-value pair
        # Ensure file ends with newline before appending
        if content and not content.endswith('\n'):
            content += '\n'
        updated_content = content + new_line + '\n'

    # Write back to file
    env_path.write_text(updated_content, encoding="utf-8")
