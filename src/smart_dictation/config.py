import enum
import os
import platform
from pathlib import Path

import pywhispercpp.constants
import pywhispercpp.model
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# from pywhispercpp.constants import MODELS_DIR
MODEL_DIR = pywhispercpp.constants.MODELS_DIR
print(MODEL_DIR)


class WhisperImpl(enum.Enum):
    cpp = "cpp"
    openai = "openai"
    realtime = "realtime"


class WhisperConfig(BaseSettings):
    whisper_model: str = Field(default="large-v3-turbo", alias="model")
    whisper_impl: WhisperImpl = Field(default=WhisperImpl.cpp, alias="implementation")
    whisper_models_dir: Path = Field(default=Path(MODEL_DIR), alias="models_dir")
    n_threads: int = Field(default=6, alias="threads")
    hotkey: str = Field(default="<ctrl>")
    input_device_index: int | None = Field(default=None)

    model_config = SettingsConfigDict(
        env_prefix="smart_dictation_", cli_parse_args=True
    )


cfg = WhisperConfig()

nice_level = -20

# Always set high process priority
def set_process_priority():
    try:
        if platform.system() == "Darwin":  # macOS
            # Lower values mean higher priority (-20 to 20)
            # -20 is a good balance between high priority and system stability
            os.nice(nice_level)
            print(f"Process priority set to {nice_level} (high performance mode)")
    except (OSError, AttributeError) as e:
        print(f"Failed to set process priority: {e}")
        print("You may need to run the app with sudo for higher priority.")

# Call this function to set the priority when the module is imported
set_process_priority()
