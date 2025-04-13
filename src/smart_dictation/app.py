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
