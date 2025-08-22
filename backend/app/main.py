from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from .config import settings
from .db import SessionLocal, init_db
from .models import User, Room, RoomMember, Message
from .schemas import UserCreate, UserOut, LoginIn, Token, RoomCreate, RoomOut, MessageOut
from .auth import get_password_hash, verify_password, create_access_token, get_current_user_id, decode_token
from .rooms import presence
import secrets
import json

app = FastAPI(title="WebRTC + Chat Backend")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
async def get_db():
    async with SessionLocal() as session:
        yield session

@app.on_event("startup")
async def on_startup():
    await init_db()

@app.get("/health")
async def health():
    return {"status": "ok"}

# ---------------------- AUTH ----------------------
@app.post("/auth/register", response_model=UserOut)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    user = User(email=payload.email, password_hash=get_password_hash(payload.password), display_name=payload.display_name)
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered")
    await db.refresh(user)
    return user

@app.post("/auth/login", response_model=Token)
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.email == payload.email))
    user = res.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    token = create_access_token(str(user.id))
    return Token(access_token=token)

@app.get("/me", response_model=UserOut)
async def me(user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    res = await db.get(User, user_id)
    return UserOut.model_validate(res)

# ---------------------- ROOMS ----------------------
@app.post("/rooms", response_model=RoomOut)
async def create_room(body: RoomCreate, user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    slug = secrets.token_urlsafe(6)
    room = Room(slug=slug, title=body.title)
    db.add(room)
    await db.flush()
    db.add(RoomMember(room_id=room.id, user_id=user_id))
    await db.commit()
    await db.refresh(room)
    return room

@app.get("/rooms/{slug}", response_model=RoomOut)
async def get_room(slug: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Room).where(Room.slug == slug))
    room = res.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room

@app.post("/rooms/{slug}/join")
async def join_room(slug: str, user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Room).where(Room.slug == slug))
    room = res.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    exists = await db.execute(select(RoomMember).where(RoomMember.room_id == room.id, RoomMember.user_id == user_id))
    if not exists.scalar_one_or_none():
        db.add(RoomMember(room_id=room.id, user_id=user_id))
        await db.commit()
    return {"ok": True}

@app.get("/rooms/{slug}/peers")
async def list_peers(slug: str):
    return {"peers": presence.peers(slug)}

@app.get("/rtc/config")
async def rtc_config():
    ice_servers = []
    if settings.stun_servers:
        for stun in settings.stun_servers.split(","):
            ice_servers.append({"urls": stun.strip()})
    if settings.turn_uri and settings.turn_username and settings.turn_password:
        ice_servers.append({
            "urls": settings.turn_uri,
            "username": settings.turn_username,
            "credential": settings.turn_password,
        })
    return {"iceServers": ice_servers}

# ---------------------- WEBSOCKETS ----------------------
# Signaling WS: relays offers/answers/candidates and announces join/leave. Also supports targeted personal signaling via `to`.
@app.websocket("/ws/signaling/{slug}")
async def ws_signaling(ws: WebSocket, slug: str):
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4401)
        return
    try:
        data = decode_token(token)
        user_id = int(data["sub"])
    except Exception:
        await ws.close(code=4401)
        return

    await ws.accept()
    presence.add(slug, user_id, ws)

    # notify others
    for peer_id, peer_ws in presence.all(slug).items():
        if peer_id != user_id:
            await peer_ws.send_text(json.dumps({"type": "peer-joined", "user_id": user_id}))

    # send current peers to the new user
    await ws.send_text(json.dumps({"type": "peers", "peers": [pid for pid in presence.peers(slug) if pid != user_id]}))

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            mtype = msg.get("type")
            if mtype == "signal":
                to_id = int(msg["to"])  # required for targeted signaling
                target = presence.get_ws(slug, to_id)
                if target:
                    await target.send_text(json.dumps({
                        "type": "signal",
                        "signal_type": msg.get("signal_type"),
                        "from": user_id,
                        "data": msg.get("data"),
                    }))
            elif mtype == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        presence.remove(slug, user_id)
        for peer_id, peer_ws in presence.all(slug).items():
            await peer_ws.send_text(json.dumps({"type": "peer-left", "user_id": user_id}))

# Chat WS: broadcast to room + persist in DB.
@app.websocket("/ws/chat/{slug}")
async def ws_chat(ws: WebSocket, slug: str):
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4401)
        return
    try:
        data = decode_token(token)
        user_id = int(data["sub"])
    except Exception:
        await ws.close(code=4401)
        return

    await ws.accept()
    presence.add(f"chat:{slug}", user_id, ws)

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            if msg.get("type") == "chat":
                content = str(msg.get("content", ""))[:4000]
                # persist
                async with SessionLocal() as db:
                    res = await db.execute(select(Room).where(Room.slug == slug))
                    room = res.scalar_one_or_none()
                    if room:
                        m = Message(room_id=room.id, sender_id=user_id, content=content)
                        db.add(m)
                        await db.commit()
                        await db.refresh(m)
                        payload = {
                            "type": "chat",
                            "id": m.id,
                            "room_id": room.id,
                            "sender_id": user_id,
                            "content": m.content,
                            "created_at": m.created_at.isoformat(),
                        }
                        # broadcast
                        for peer_id, peer_ws in presence.all(f"chat:{slug}").items():
                            await peer_ws.send_text(json.dumps(payload))
            else:
                await ws.send_text(json.dumps({"type": "error", "message": "unknown message"}))
    except WebSocketDisconnect:
        pass
    finally:
        presence.remove(f"chat:{slug}", user_id)