# 🧠 Homework Buddy (Local Best Brains Worksheet Grader & Reading Tutor)

A zero-auth local-network web application for Krisha (3rd Grade) and Vedant (Kindergarten / Advanced 1st-Grade Reader) to automatically grade Best Brains Math and English worksheets and test reading comprehension via mobile camera.

Powered by a local **LM Studio** instance running on an RTX 5090 Windows desktop, local neural TTS via **Kokoro-82M**, and backed by **PostgreSQL** in Docker.

---

## 🚀 Features

- **Kid-Friendly Mobile UI**: One-tap child profile selection, instant camera scan (`capture="environment"`), image preview, and cheerful feedback.
- **Worksheet Scanning & Anti-Duplication**:
  - Top-Right Best Brains page code recognition (e.g. `GM0aV7.5`, `GM0aV7.8`).
  - Strict completeness verification (flags unanswered questions or cropped pages).
  - Anti-duplicate detection: Prevents duplicate points if an already-mastered page is rescanned.
  - Correction Recovery Bonus: If a child rescans after fixing mistakes, restores streak and awards bonus points!
  - Technical Shield: Preserves streak if AI or camera has difficulty reading the page, prompting child to show to parent.
- **Local Kokoro-82M Neural Voice**:
  - Realistic, warm, ultra-low-latency human voice running 100% locally on port 8880.
  - Custom phonetic pronunciation fixes for names: `Vedant` -> *Vay-daanth*, `Krisha` -> *Krish-uh*.
- **"Professor Sunny" Interactive Voice Tutor (Phase 2)**:
  - Funny, energetic owl teacher persona with silly analogies, jokes, and mini-stories.
  - Two-way voice chat (Web Speech STT + Kokoro TTS) for kids to ask questions about mistakes or concepts.
- **Parent Dashboard & Adminer**:
  - Built-in quick modal in the UI to adjust points (+5, +10, etc.) and view recent submission audit logs.
  - **Adminer** web UI running on `http://localhost:8081` for direct SQL queries and editing.
- **Local & Unraid Ready**: Docker Compose setup ready for local testing and seamless migration to Unraid (`anandhomenas.local`).

---

## 📚 Bookworm Club (Reading Comprehension & Book Checker) — Phase 3

- **Library & School Book Support**: Scan front cover or ISBN / barcode from McKinney Public Library or school library.
- **Targeted Comprehension Checks**:
  - **Vedant** (Late 1st Grade Reading Level): Cause-and-effect, character decisions, and plot humor (e.g., *Elephant & Piggie*, *Fly Guy*, *Nate the Great*).
  - **Krisha** (3rd Grade Reading Level): Chapter developments, problem-solving, and character motivations (e.g., *Magic Tree House*, *Bad Guys*, *Ramona*).
- **Spoken Voice Response**: Child speaks their answer via microphone; Professor Sunny evaluates understanding and awards **+15 Reading Points** + trophy badge.
- **Virtual Bookshelf**: Visual gallery tracking all completed books.

---

## 🔮 Backlog & Future Roadmap

### 1. 📢 Google Nest Speaker Cast Integration
- **Automated After-School Reminders (Push via `pychromecast`)**:
  - **3:45 PM Weekdays**: Professor Sunny broadcasts over Google Home speakers: *"Welcome home! Change into comfy clothes and bring your lunchboxes to the kitchen sink for washing!"*
  - **5:00 PM Post-Class Homework Call**: Automatically reminds kids to scan their worksheets after their classes (customized to their weekly schedule).
- **Inbound Queries ("Hey Google, how many points do I have?")**:
  - Integration via Home Assistant / Google Assistant webhook to query Postgres points.

### 2. 🏰 Hogwarts House Points System
- **House Sorting**: Krisha and Vedant sorted into Hogwarts Houses (Gryffindor, Ravenclaw, etc.).
- **Visual Gem Hourglasses**: Animated glass tubes filling with floating red/blue gems for points.
- **Parent-Only Voice / App Authorization (Headmaster Access)**:
  - Only Parents can award points for real-world good actions (e.g., *"10 points to Gryffindor for helping clear the dinner table"*).
  - Google Assistant Voice Match or Pin-protected parent screen prevents kids from granting themselves points.
- **House Cup Milestones**: Reaching 100 points unlocks real-world family rewards (ice cream trip, Friday movie pick).

---

## 🛠️ Quick Start (Local Docker)

### Prerequisites
1. **LM Studio** running on this Windows host.
   - Start the local server under the **Developer** tab (default port `1234`).
2. **Docker Desktop** running.

### Launching the Stack
In PowerShell / Terminal in this folder:
```bash
docker compose up --build -d
```

### Access Endpoints
- **Homework Buddy App**: [http://localhost:8080](http://localhost:8080)
- **Parent Database Viewer (Adminer)**: [http://localhost:8081](http://localhost:8081)
  - System: `PostgreSQL`
  - Server: `db`
  - Username: `homework`
  - Password: `homeworkpass`
  - Database: `homework_buddy`
- **Kokoro Neural Voice API**: [http://localhost:8880](http://localhost:8880)
- **FastAPI OpenAPI Docs**: [http://localhost:8080/docs](http://localhost:8080/docs)

---

## 📱 Kid Experience & Rules

| Activity | Points Awarded | Streak Effect |
|---|---|---|
| **Worksheet: Perfect Score (First Try)** | +10 base + (Streak × 2) + 5 (if neat) | Streak + 1 |
| **Worksheet: Corrections Mastered** | +8 base + (Streak × 2) + 5 (if neat) | Streak Restored & +1 |
| **Worksheet: Corrections Needed** | 0 points | Streak reset to 0 |
| **Worksheet: Technical/Camera Error** | 0 points | Streak Preserved |
| **Book: Comprehension Mastered** | +15 Reading Points | Added to Bookshelf Trophy 🏆 |
| **House Point (Good Deed / Chore)** | +5 to +20 points (Parent Awarded) | Adds to House Hourglass 🦁 |

---

## 🌐 Moving to Unraid (`anandhomenas.local`)

When you are ready to deploy on Unraid:
1. In `docker-compose.yml`, update `LM_STUDIO_URL` to point to this Windows machine's LAN IP:
   ```yaml
   LM_STUDIO_URL: http://192.168.1.214:1234/v1/chat/completions
   ```
2. Map the postgres volume to an Unraid user share (e.g. `/mnt/user/appdata/homework_buddy/db_data:/var/lib/postgresql/data`).
3. Run with Docker Compose Manager on Unraid.
