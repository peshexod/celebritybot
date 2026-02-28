import asyncio

from elevenlabs import ElevenLabs

from bot.config import get_settings


class VoiceService:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.elevenlabs_api_key:
            raise ValueError("ELEVENLABS_API_KEY is not configured")
        self.client = ElevenLabs(api_key=settings.elevenlabs_api_key)

    def _sync_generate(self, text: str, voice_id: str) -> bytes:
        audio_stream = self.client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )
        chunks = list(audio_stream)
        return b"".join(chunks)

    async def generate_audio(self, text: str, voice_id: str) -> bytes:
        return await asyncio.to_thread(self._sync_generate, text, voice_id)
