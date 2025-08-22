* docker-compose.yml: backend(FastAPI), db(Postgres), frontend(Vite+React), (opsional) turn(coturn).
* .env: kredensial Postgres, JWT, CORS, STUN/TURN.
* Backend: FastAPI + SQLAlchemy async + JWT + WebSocket (signaling & chat) + model User/Room/Message.
* Frontend: Vite React; login/register, buat/join room, video grid WebRTC (mesh) + chat.
* Auth & DB
   * POST /auth/register & POST /auth/login → JWT.
   * POST /rooms buat room (slug), POST /rooms/{slug}/join, GET /rooms/{slug}.
* Signaling WebRTC (WS)
   * ws://.../ws/signaling/{slug}?token=...: relay offer/answer/ice antar client; announce peer-joined/peer-left.
   * GET /rtc/config → ICE servers (STUN/TURN dari .env).
* Chat (WS)
   * ws://.../ws/chat/{slug}?token=...: broadcast ke semua & simpan ke Postgres.
* Frontend
   * Ambil media lokal → buat RTCPeerConnection per peer (mesh).
   * Inisiasi offer saat peer join, handle answer & ICE.
   * Tampilkan video lokal + remote, kirim/terima chat.
* Docker up
   * Salin .env.example → .env, sesuaikan.
   * docker compose up --build.
   * Buka http://localhost:5173, register → login → create room → share slug → join dari tab lain.
* TURN (opsional, untuk NAT/Internet)
   * Isi TURN_URI, TURN_USERNAME, TURN_PASSWORD & uncomment service turn di compose.
   * Pastikan port UDP 3478 & 49160-49200 terbuka.
 


1. Buat Folder Project
mkdir webrtc-fastapi-postgres
cd webrtc-fastapi-postgres

2. Struktur Folder yang Dibutuhkan
   webrtc-fastapi-postgres/
        ├── docker-compose.yml
        ├── .env
        ├── .env.example
        ├── backend/
        │   ├── Dockerfile
        │   ├── requirements.txt
        │   └── app/
        │       ├── __init__.py
        │       ├── main.py
        │       ├── config.py
        │       ├── db.py
        │       ├── models.py
        │       ├── schemas.py
        │       ├── auth.py
        │       └── rooms.py
        └── frontend/
            ├── Dockerfile
            ├── package.json
            ├── index.html
            └── src/
                ├── main.tsx
                └── App.tsx
3. cp .env.example .env
4. Jalankan Docker
   # Build dan jalankan semua services
      docker compose up --build
    # Atau jalankan di background
    docker compose up --build -d
5. Testing Aplikasi
      a. Buka browser ke http://localhost:5173
      b. Register user pertama:
              Email: user1@demo.dev
              Password: password
              Display Name: User One
      
      c. Login dengan kredensial yang sama
      d. Create room dengan title "Demo Room"
      e. Copy room slug yang muncul
      f. Buka tab/browser baru ke http://localhost:5173
      g. Register user kedua dengan email berbeda
      h. Login user kedua
      i. Join room dengan slug yang di-copy tadi
      j. Izinkan akses kamera/mikrofon di kedua browser
      k. Test video call dan chat!
6. Troubleshooting
       Problem: Port sudah digunakan
      bash# Cek port yang digunakan
      netstat -tulpn | grep :5432
      netstat -tulpn | grep :8000
      netstat -tulpn | grep :5173
      
      # Ganti port di docker-compose.yml jika perlu
      Problem: Database connection error
      bash# Restart hanya database
      docker compose restart db
      
      # Lihat logs
      docker compose logs db
      docker compose logs backend
      Problem: WebRTC tidak connect (local network)
      
      Pastikan firewall tidak memblokir
      Coba dari device yang sama dulu (2 tab browser)
      Periksa console browser untuk error WebRTC
      
      Problem: Video tidak muncul
      
      Pastikan browser mengizinkan akses kamera/mikrofon
      Cek console browser untuk error media device
      Coba refresh page dan allow permission lagi
      
      🌐 Setup untuk Internet/Remote Access
      Untuk akses dari internet, perlu TURN server:
      
      Uncomment TURN service di docker-compose.yml
      Edit .env:
      
      envTURN_URI=turn:YOUR_PUBLIC_IP:3478
      TURN_USERNAME=turnuser
      TURN_PASSWORD=turnpass123
      
      Buka ports di router/firewall:
      
      3478/udp dan 3478/tcp
      49160-49200/udp
      
      
      Restart services:
      
      bashdocker compose down
      docker compose up --build
      📱 Fitur yang Tersedia
      Authentication
      
      ✅ Register/Login dengan JWT
      ✅ Auto-login dengan localStorage
      ✅ Protected routes
      
      Rooms & Chat
      
      ✅ Create room dengan random slug
      ✅ Join room dengan slug
      ✅ Real-time chat dengan WebSocket
      ✅ Chat history tersimpan di database
      
      Video Call (WebRTC)
      
      ✅ Local video preview
      ✅ Peer-to-peer video call (mesh topology)
      ✅ Audio support
      ✅ Multiple participants
      ✅ Automatic peer discovery
      ✅ WebRTC signaling via WebSocket
      
      Technical Stack
      
      ✅ Backend: FastAPI + PostgreSQL + SQLAlchemy async
      ✅ Frontend: React + TypeScript + Vite
      ✅ WebRTC: Vanilla WebRTC API dengan mesh networking
      ✅ Real-time: WebSocket untuk signaling dan chat
      ✅ Database: PostgreSQL dengan async queries
      ✅ Containerization: Docker Compose
      
      🚀 Next Steps untuk Production
      
      Security: Ganti JWT secret, database password
      HTTPS: Setup SSL certificate
      TURN Server: Deploy coturn atau gunakan service TURN
      Scaling: Consider SFU instead of mesh for >4 participants
      Monitoring: Add logging dan health checks
      CDN: Serve frontend dari CDN
      
      📝 Development Tips
      Untuk development lebih lanjut:
      bash# Watch logs real-time
      docker compose logs -f backend
      docker compose logs -f frontend
      
      # Restart specific service
      docker compose restart backend
      
      # Rebuild after code changes
      docker compose up --build backend
      Hot reload sudah aktif untuk:
      
      ✅ Frontend (Vite dev server)
      ✅ Backend (uvicorn dengan reload)
