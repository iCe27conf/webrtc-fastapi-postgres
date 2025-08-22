from typing import Dict
from fastapi import WebSocket
from collections import defaultdict

class RoomPresence:
    def __init__(self) -> None:
        self.rooms: Dict[str, dict[int, WebSocket]] = defaultdict(dict)

    def add(self, room_slug: str, user_id: int, ws: WebSocket):
        self.rooms[room_slug][user_id] = ws

    def remove(self, room_slug: str, user_id: int):
        if room_slug in self.rooms and user_id in self.rooms[room_slug]:
            self.rooms[room_slug].pop(user_id, None)
            if not self.rooms[room_slug]:
                self.rooms.pop(room_slug, None)

    def peers(self, room_slug: str) -> list[int]:
        return list(self.rooms.get(room_slug, {}).keys())

    def get_ws(self, room_slug: str, user_id: int) -> WebSocket | None:
        return self.rooms.get(room_slug, {}).get(user_id)

    def all(self, room_slug: str) -> dict[int, WebSocket]:
        return self.rooms.get(room_slug, {})

presence = RoomPresence()