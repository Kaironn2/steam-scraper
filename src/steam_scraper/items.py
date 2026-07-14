"""Project items, as pydantic models — validated when the spiders build them."""

from pydantic import BaseModel


class Game(BaseModel):
    appid: int
    name: str
    achievements_total: int | None = None


class Achievement(BaseModel):
    title: str
    description: str | None
    unlocked: bool
    unlock_time: str | None
    progress_current: int | None
    progress_total: int | None


class GameAchievements(BaseModel):
    username: str
    appid: int
    game: str
    achievements_total: int | None
    language: str
    achievements: list[Achievement]
