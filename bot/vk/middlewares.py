from vkbottle import BaseMiddleware
from vkbottle.bot import Message

from bot.db.database import SessionLocal


class DBSessionMiddleware(BaseMiddleware[Message]):
    async def pre(self) -> None:
        self.session_context = SessionLocal()
        self.session = await self.session_context.__aenter__()
        self.send({"session": self.session})

    async def post(self) -> None:
        if hasattr(self, "session_context"):
            await self.session_context.__aexit__(None, None, None)
