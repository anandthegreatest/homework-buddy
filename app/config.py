import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Homework Buddy"
    PORT: int = 8080
    HOST: str = "0.0.0.0"

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://homework:homeworkpass@db:5432/homework_buddy"
    )

    # LM Studio API endpoint and model
    # On Windows local docker, host.docker.internal reaches the Windows host LM Studio
    LM_STUDIO_URL: str = os.getenv(
        "LM_STUDIO_URL", 
        "http://host.docker.internal:1234/v1/chat/completions"
    )
    LM_STUDIO_MODEL: str = os.getenv(
        "LM_STUDIO_MODEL", 
        "auto"
    )
    
    # Local Kokoro Neural TTS
    KOKORO_TTS_URL: str = os.getenv("KOKORO_TTS_URL", "http://tts:8880/v1/audio/speech")
    KOKORO_VOICE: str = os.getenv("KOKORO_VOICE", "af_heart")
    
    # Local Whisper Neural STT
    WHISPER_STT_URL: str = os.getenv("WHISPER_STT_URL", "http://whisper:9000/asr")
    
    # Grading rule settings
    POINTS_PER_CORRECT: int = 10
    POINTS_PER_STREAK: int = 2
    POINTS_HANDWRITING_BONUS: int = 5
    POINTS_CORRECTION_FIX: int = 8

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
