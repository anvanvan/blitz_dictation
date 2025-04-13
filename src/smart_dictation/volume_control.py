"""
Module for controlling the volume of specific applications on macOS.
"""
import subprocess
import asyncio
import structlog

log = structlog.get_logger(__name__)


async def _run_osascript(script):
    """
    Run an AppleScript command and return the result.

    Args:
        script (str): The AppleScript command to run.

    Returns:
        str: The output of the command, or None if an error occurred.
    """
    try:
        cmd = ['osascript', '-e', script]
        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await result.communicate()

        if result.returncode == 0:
            return stdout.decode().strip().lower()
        else:
            log.warning("AppleScript command failed", script=script, error=stderr.decode().strip())
            return None
    except Exception as e:
        log.warning("Error running AppleScript", script=script, error=str(e))
        return None


async def get_music_app_volume():
    """
    Get the current volume of the Music app.

    Returns:
        int: The current volume (0-100) or None if Music app is not running.
    """
    result = await _run_osascript('tell application "Music" to get sound volume')
    if result is not None:
        try:
            return int(result)
        except ValueError:
            log.warning("Failed to parse Music app volume", result=result)
    return None


async def set_music_app_volume(volume):
    """
    Set the volume of the Music app.

    Args:
        volume (int): Volume level (0-100).

    Returns:
        bool: True if successful, False otherwise.
    """
    # Ensure volume is within valid range
    volume = max(0, min(100, int(volume)))

    result = await _run_osascript(f'tell application "Music" to set sound volume to {volume}')
    if result is not None:
        log.debug(f"Set Music app volume to {volume}")
        return True
    else:
        log.warning(f"Failed to set Music app volume to {volume}")
        return False


async def mute_music_app():
    """
    Mute the Music app by setting volume to 0.

    Returns:
        bool: True if successful, False otherwise.
    """
    return await set_music_app_volume(0)


async def restore_music_app_volume(original_volume):
    """
    Restore the Music app volume to its original value.

    Args:
        original_volume (int): The original volume to restore (0-100).

    Returns:
        bool: True if successful, False otherwise.
    """
    if original_volume is not None:
        return await set_music_app_volume(original_volume)
    return False


async def is_music_app_running():
    """
    Check if the Music app is running.

    Returns:
        bool: True if running, False otherwise.
    """
    result = await _run_osascript('tell application "System Events" to (name of processes) contains "Music"')
    return result == "true"


async def is_music_playing():
    """
    Check if music is currently playing in the Music app.

    Returns:
        bool: True if music is playing, False otherwise.
    """
    # First check if Music app is running
    if not await is_music_app_running():
        return False

    # If Music app is running, check if it's playing
    result = await _run_osascript('tell application "Music" to player state is playing')
    return result == "true"
