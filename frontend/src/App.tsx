import React, { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

function useLocalStorage<T>(key: string, initial: T) {
  const [val, setVal] = useState<T>(() => {
    const v = localStorage.getItem(key);
    return v ? (JSON.parse(v) as T) : initial;
  });
  useEffect(() => localStorage.setItem(key, JSON.stringify(val)), [key, val]);
  return [val, setVal] as const;
}

type PeerInfo = { id: number };

type Signal = {
  type: "signal";
  signal_type: "offer" | "answer" | "ice";
  from: number;
  data: any;
};

export default function App() {
  const [email, setEmail] = useLocalStorage("email", "user@demo.dev");
  const [password, setPassword] = useLocalStorage("password", "password");
  const [displayName, setDisplayName] = useLocalStorage("displayName", "User");
  const [token, setToken] = useLocalStorage<string | null>("token", null);
  const [me, setMe] = useState<{ id: number; email: string; display_name: string } | null>(null);

  const [roomTitle, setRoomTitle] = useState("Demo Room");
  const [roomSlug, setRoomSlug] = useLocalStorage<string | null>("room", null);

  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState<any[]>([]);

  const [iceServers, setIceServers] = useState<any[]>([]);
  const localVideoRef = useRef<HTMLVideoElement>(null);
  const [streams, setStreams] = useState<Record<number, MediaStream>>({});

  const peersRef = useRef<Map<number, RTCPeerConnection>>(new Map());
  const chatSocketRef = useRef<WebSocket | null>(null);
  const sigSocketRef = useRef<WebSocket | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    if (!token) return;
    axios
      .get(`${API_BASE}/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => setMe(r.data))
      .catch(() => setMe(null));
  }, [token]);

  useEffect(() => {
    axios.get(`${API_BASE}/rtc/config`).then((r) => setIceServers(r.data.iceServers || []));
  }, []);

  async function register() {
    await axios.post(`${API_BASE}/auth/register`, { email, password, display_name: displayName });
    await login();
  }

  async function login() {
    const r = await axios.post(`${API_BASE}/auth/login`, { email, password });
    setToken(r.data.access_token);
  }

  async function createRoom() {
    if (!token) return;
    const r = await axios.post(
      `${API_BASE}/rooms`,
      { title: roomTitle },
      { headers: { Authorization: `Bearer ${token}` } }
    );
    setRoomSlug(r.data.slug);
  }

  async function joinRoom() {
    if (!token || !roomSlug) return;
    await axios.post(
      `${API_BASE}/rooms/${roomSlug}/join`,
      {},
      { headers: { Authorization: `Bearer ${token}` } }
    );
    await startSession();
  }

  async function startSession() {
    if (!token || !roomSlug) return;

    const local = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    localStreamRef.current = local;
    if (localVideoRef.current) {
      localVideoRef.current.srcObject = local;
      localVideoRef.current.muted = true;
      await localVideoRef.current.play();
    }

    const sig = new WebSocket(`${API_BASE.replace("http", "ws")}/ws/signaling/${roomSlug}?token=${token}`);
    const chat = new WebSocket(`${API_BASE.replace("http", "ws")}/ws/chat/${roomSlug}?token=${token}`);
    sigSocketRef.current = sig;
    chatSocketRef.current = chat;

    sig.onmessage = async (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "peers") {
        for (const pid of msg.peers as number[]) {
          await ensurePeer(pid, true);
        }
      } else if (msg.type === "peer-joined") {
        await ensurePeer(msg.user_id, true);
      } else if (msg.type === "peer-left") {
        const pc = peersRef.current.get(msg.user_id);
        pc?.close();
        peersRef.current.delete(msg.user_id);
        setStreams((s) => {
          const n = { ...s };
          delete n[msg.user_id];
          return n;
        });
      } else if (msg.type === "signal") {
        await handleSignal(msg as Signal);
      }
    };

    chat.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.type === "chat") setMessages((prev) => [...prev, m]);
    };
  }

  async function ensurePeer(peerId: number, isInitiator: boolean) {
    if (!me || peersRef.current.has(peerId) || peerId === me.id) return;

    const pc = new RTCPeerConnection({ iceServers });
    peersRef.current.set(peerId, pc);

    localStreamRef.current?.getTracks().forEach((t) => pc.addTrack(t, localStreamRef.current!));

    pc.onicecandidate = (ev) => {
      if (ev.candidate)
        sigSocketRef.current?.send(
          JSON.stringify({
            type: "signal",
            signal_type: "ice",
            to: peerId,
            data: ev.candidate,
          })
        );
    };

    pc.ontrack = (ev) => {
      setStreams((prev) => ({ ...prev, [peerId]: ev.streams[0] }));
    };

    if (isInitiator) {
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      sigSocketRef.current?.send(
        JSON.stringify({ type: "signal", signal_type: "offer", to: peerId, data: offer })
      );
    }
  }

  async function handleSignal(msg: Signal) {
    const from = msg.from;
    const pc = peersRef.current.get(from) || (await (async () => { await ensurePeer(from, false); return peersRef.current.get(from)!; })());

    if (msg.signal_type === "offer") {
      await pc.setRemoteDescription(new RTCSessionDescription(msg.data));
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      sigSocketRef.current?.send(
        JSON.stringify({ type: "signal", signal_type: "answer", to: from, data: answer })
      );
    } else if (msg.signal_type === "answer") {
      if (!pc.currentRemoteDescription) await pc.setRemoteDescription(new RTCSessionDescription(msg.data));
    } else if (msg.signal_type === "ice") {
      try { await pc.addIceCandidate(new RTCIceCandidate(msg.data)); } catch {}
    }
  }

  function sendChat() {
    if (!chatSocketRef.current || !me || !chatInput) return;
    chatSocketRef.current.send(JSON.stringify({ type: "chat", content: chatInput }));
    setChatInput("");
  }

  return (
    <div className="wrap">
      <aside className="sidebar">
        <h3>Auth</h3>
        <div>
          <input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <input placeholder="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <input placeholder="Display name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button onClick={register}>Register</button>
            <button onClick={login}>Login</button>
          </div>
        </div>
        <hr />
        <h3>Room</h3>
        <div>
          <input placeholder="Room title" value={roomTitle} onChange={(e) => setRoomTitle(e.target.value)} />
          <button onClick={createRoom} disabled={!token}>Create</button>
        </div>
        <div>
          <input placeholder="Room slug" value={roomSlug ?? ""} onChange={(e) => setRoomSlug(e.target.value)} />
          <button onClick={joinRoom} disabled={!token || !roomSlug}>Join</button>
        </div>
        <div style={{ marginTop: 8, fontSize: 12, color: "#666" }}>
          {me ? `Logged in as #${me.id} ${me.display_name}` : "Not logged in"}
        </div>
      </aside>

      <main className="main">
        <section className="videos">
          <video ref={localVideoRef} playsInline autoPlay muted></video>
          {Object.entries(streams).map(([uid, stream]) => (
            <video key={uid} playsInline autoPlay ref={(el) => el && (el.srcObject = stream)}></video>
          ))}
        </section>
        <section className="chat">
          <div className="msgs">
            {messages.map((m, i) => (
              <div className="msg" key={i}>
                <div className="meta">#{m.sender_id} · {new Date(m.created_at).toLocaleTimeString()}</div>
                <div>{m.content}</div>
              </div>
            ))}
          </div>
          <div className="input">
            <input
              placeholder="Type a message"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendChat()}
            />
            <button onClick={sendChat}>Send</button>
          </div>
        </section>
      </main>
    </div>
  );
}