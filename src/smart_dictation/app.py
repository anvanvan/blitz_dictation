import asyncio
import structlog

from smart_dictation import clipboard, hotkeys
from smart_dictation.audio import (
    get_device_info,
    get_sound_devices,
    record_audio,
    get_default_device,
)
from smart_dictation.config import WhisperImpl, cfg
from smart_dictation.local_whisper import WhisperCppTranscriber, to_whisper_ndarray
from smart_dictation.volume_control import get_music_app_volume, mute_music_app, restore_music_app_volume, is_music_playing

log = structlog.get_logger(__name__)

match (cfg.whisper_impl):
    case WhisperImpl.cpp:
        transcribe = WhisperCppTranscriber()
    case WhisperImpl.openai:
        raise NotImplementedError("API not implemented")
    case WhisperImpl.realtime:
        raise NotImplementedError("Realtime not implemented")
    case _:
        raise ValueError(f"Invalid whisper implementation: {cfg.whisper_impl}")


async def dictate(key_released):
    # Save original Music app volume if it's playing
    original_volume = None
    music_playing = await is_music_playing()

    if music_playing:
        original_volume = await get_music_app_volume()
        await log.ainfo("Saving Music app volume: %s", original_volume)
        await mute_music_app()
        await log.ainfo("Muted Music app for recording")

    try:
        device_info = get_device_info(cfg.input_device_index)
        await log.ainfo("Recording, device: %s", device_info["name"])

        # Create a wrapper for the key_released event to restore volume when recording stops
        volume_restored = False

        # Define a function to handle the key release event
        async def on_key_released():
            nonlocal volume_restored
            # Wait for the original key_released event
            await key_released.wait()

            # Restore volume immediately after recording stops
            if music_playing and original_volume is not None and not volume_restored:
                await log.ainfo("Restoring Music app volume to: %s", original_volume)
                await restore_music_app_volume(original_volume)
                volume_restored = True

            # Signal that recording should stop
            return True

        # Start a task to handle key release and volume restoration
        restore_task = asyncio.create_task(on_key_released())

        # Record audio with the original key_released event
        wave = await record_audio(
            key_released, convert=to_whisper_ndarray, device=cfg.input_device_index
        )

        # Wait for the restore task to complete if it hasn't already
        if not restore_task.done():
            await restore_task

        # Continue with transcription and pasting
        await log.ainfo("Transcribing ...")
        text = await transcribe(wave)
        await log.ainfo("Pasting: %s", text)
        await clipboard.paste_text(text)
    finally:
        # Ensure volume is restored if it hasn't been already
        if music_playing and original_volume is not None and not volume_restored:
            await log.ainfo("Restoring Music app volume to: %s", original_volume)
            await restore_music_app_volume(original_volume)


def select_device_from_menu():
    """Display a menu of available input devices and let the user select one."""
    devices = get_sound_devices()

    # Show current default device
    _, default_name = get_default_device()
    print(f"Current default device: {default_name}")

    # Display device selection menu
    print("\nSelect an input device:")
    for i, (_, device_name) in enumerate(devices, 1):
        print(f"{i}. {device_name}")

    # Get default device index for empty input handling
    default_idx, _ = get_default_device()

    while True:
        try:
            choice = input("\nEnter the number of your choice (or Enter = default device): ")

            # If user presses Enter, use the default device
            if choice.strip() == '':
                print(f"\nUsing default device: {default_name}")
                return default_idx

            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(devices):
                selected_id, selected_name = devices[choice_idx]
                print(f"\nSelected device: {selected_name}")
                return selected_id
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Please enter a valid number.")

async def start_listening():
    if cfg.input_device_index is None:
        # Display device selection menu
        selected_device = select_device_from_menu()

        # Update the configuration with the selected device
        cfg.input_device_index = selected_device

        # Show the selected device
        device_info = get_device_info(cfg.input_device_index)
        print(f"Using device: {device_info['name']}")
    else:
        device_info = get_device_info(cfg.input_device_index)
        print(f"Using device: {device_info['name']}")

    transcribe.preload()
    await hotkeys.listen_for_hotkeys({cfg.hotkey: dictate})


def list_sound_devices():
    """Print the list of input sound devices."""
    devices = get_sound_devices()
    print("Available input devices:")
    for device_id, device_name in devices:
        print(f"Input Device id: {device_id} - {device_name}")


def main():
    asyncio.run(start_listening())


if __name__ == "__main__":
    main()
