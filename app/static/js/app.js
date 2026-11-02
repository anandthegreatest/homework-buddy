let activeName = "";
let activeGrade = "";
let selectedFile = null;
let soundEnabled = true;
let audioCtx = null;
let currentTeacherText = "";
let lastGradedPageId = "";
let lastEvaluationText = "";
let teacherChatHistory = [];
let recognition = null;
let isRecording = false;
let currentMode = "worksheet"; // "worksheet" or "book"
let currentBookData = null;
let bookRecognition = null;
let isBookRecording = false;
const SERVER_URL = window.location.origin;

// Initialize Web Audio Context on user interaction (required by mobile browsers)
function initAudioContext() {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.state === 'suspended') {
        audioCtx.resume();
    }
}

function toggleSound() {
    soundEnabled = !soundEnabled;
    const btn = document.getElementById('btnSoundToggle');
    if (soundEnabled) {
        btn.innerText = "🔊 Sound ON";
        btn.classList.remove('muted');
        initAudioContext();
        playCoinSound(1800, 0.08); // Friendly ping to confirm sound works
    } else {
        btn.innerText = "🔇 Sound OFF";
        btn.classList.add('muted');
        stopSpeech();
    }
}

// --- Casino & Arcade Audio Synthesizer (Web Audio API) ---
function playCoinSound(freq = 1500, duration = 0.08, delay = 0) {
    if (!soundEnabled) return;
    initAudioContext();
    const startTime = audioCtx.currentTime + delay;

    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(freq, startTime);
    osc.frequency.exponentialRampToValueAtTime(freq * 1.4, startTime + duration);

    gain.gain.setValueAtTime(0.2, startTime);
    gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration);

    osc.connect(gain);
    gain.connect(audioCtx.destination);

    osc.start(startTime);
    osc.stop(startTime + duration);
}

function playCasinoJackpot() {
    if (!soundEnabled) return;
    initAudioContext();

    // 1. Rapid casino coin cascade (ascending coin clinks)
    const coinPitches = [988, 1175, 1318, 1480, 1661, 1865, 2093, 2349, 2637, 2960];
    coinPitches.forEach((p, idx) => {
        playCoinSound(p, 0.07, idx * 0.055);
    });

    // 2. Victorious Fanfare Chord (Major triad celebratory finish)
    const fanfareNotes = [523.25, 659.25, 783.99, 1046.50]; // C5, E5, G5, C6
    const fanfareStart = audioCtx.currentTime + (coinPitches.length * 0.055) + 0.1;

    fanfareNotes.forEach((freq, i) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, fanfareStart + (i * 0.05));

        gain.gain.setValueAtTime(0.25, fanfareStart + (i * 0.05));
        gain.gain.exponentialRampToValueAtTime(0.001, fanfareStart + 1.2);

        osc.connect(gain);
        gain.connect(audioCtx.destination);

        osc.start(fanfareStart + (i * 0.05));
        osc.stop(fanfareStart + 1.2);
    });
}

function playSoftEncouragement() {
    if (!soundEnabled) return;
    initAudioContext();
    const t = audioCtx.currentTime;
    // Gentle warm two-chord chime (F4 -> A4)
    [349.23, 440.00].forEach((freq, idx) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, t + (idx * 0.18));
        gain.gain.setValueAtTime(0.18, t + (idx * 0.18));
        gain.gain.exponentialRampToValueAtTime(0.001, t + (idx * 0.18) + 0.6);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start(t + (idx * 0.18));
        osc.stop(t + (idx * 0.18) + 0.6);
    });
}

// --- Confetti Animation ---
function launchConfetti() {
    const canvas = document.getElementById('confettiCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    const pieces = [];
    const colors = ['#2ecc71', '#3498db', '#f1c40f', '#e74c3c', '#9b59b6', '#ff7675', '#fdcb6e'];

    for (let i = 0; i < 90; i++) {
        pieces.push({
            x: canvas.width / 2,
            y: canvas.height * 0.4,
            vx: (Math.random() - 0.5) * 14,
            vy: (Math.random() - 1.2) * 12,
            size: Math.random() * 8 + 6,
            color: colors[Math.floor(Math.random() * colors.length)],
            rotation: Math.random() * 360,
            rotationSpeed: (Math.random() - 0.5) * 10,
            opacity: 1
        });
    }

    let start = null;
    function animate(timestamp) {
        if (!start) start = timestamp;
        const elapsed = timestamp - start;

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        let alive = false;

        pieces.forEach(p => {
            p.x += p.vx;
            p.y += p.vy;
            p.vy += 0.35; // gravity
            p.vx *= 0.98; // air drag
            p.rotation += p.rotationSpeed;
            p.opacity -= 0.008;

            if (p.opacity > 0) {
                alive = true;
                ctx.save();
                ctx.translate(p.x, p.y);
                ctx.rotate((p.rotation * Math.PI) / 180);
                ctx.fillStyle = p.color;
                ctx.globalAlpha = Math.max(0, p.opacity);
                ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
                ctx.restore();
            }
        });

        if (alive && elapsed < 3200) {
            requestAnimationFrame(animate);
        } else {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
    }
    requestAnimationFrame(animate);
}

// --- Spoken Instructions & Feedback (Kokoro Neural AI Voice) ---
let currentAudio = null;

function stopSpeech() {
    if (currentAudio) {
        currentAudio.pause();
        currentAudio.currentTime = 0;
        currentAudio = null;
    }
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
    }
    const voiceBtn = document.getElementById('btnVoiceReplay');
    if (voiceBtn) {
        voiceBtn.classList.remove('speaking');
        voiceBtn.innerText = "🔊 Read to Me";
    }
}

function speakTeacherNotes(childName, text, isCorrect, pointsEarned, status) {
    if (!soundEnabled) return;
    stopSpeech();

    // Clean text for speech: remove markdown symbols, bullets, brackets
    let cleaned = text.replace(/[#*_`]/g, '').replace(/\[.*?\]/g, '').replace(/•/g, '').trim();

    let spokenIntro = "";
    if (isCorrect) {
        spokenIntro = `Super job, ${childName}! You scored ${pointsEarned} points! `;
    } else if (status === "TECH_ERROR") {
        spokenIntro = `Oops! I had a little trouble reading this page. Please show it to a parent to check your answers. Your streak is safe! `;
    } else {
        spokenIntro = `Good try, ${childName}! Here are your teacher notes to help you make corrections. `;
    }

    currentTeacherText = spokenIntro + (status === "TECH_ERROR" ? "" : cleaned);

    // Delay slightly so casino fanfare plays first
    setTimeout(() => {
        if (!soundEnabled) return;
        playNeuralVoice(currentTeacherText);
    }, isCorrect ? 900 : 400);
}

function playNeuralVoice(text) {
    stopSpeech();
    const voiceBtn = document.getElementById('btnVoiceReplay');
    if (voiceBtn) {
        voiceBtn.classList.add('speaking');
        voiceBtn.innerText = "⏳ Loading Voice...";
    }

    const audioUrl = `${SERVER_URL}/api/v1/tts?text=` + encodeURIComponent(text);
    const audio = new Audio(audioUrl);
    currentAudio = audio;

    audio.onplay = () => {
        if (voiceBtn) {
            voiceBtn.classList.add('speaking');
            voiceBtn.innerText = "⏹️ Stop Voice";
        }
    };

    audio.onended = () => {
        if (voiceBtn) {
            voiceBtn.classList.remove('speaking');
            voiceBtn.innerText = "🔊 Read to Me";
        }
        currentAudio = null;
    };

    audio.onerror = () => {
        console.warn("Kokoro TTS failed, falling back to browser voice");
        if (voiceBtn) {
            voiceBtn.classList.remove('speaking');
            voiceBtn.innerText = "🔊 Read to Me";
        }
        if ('speechSynthesis' in window) {
            const utt = new SpeechSynthesisUtterance(text);
            window.speechSynthesis.speak(utt);
        }
    };

    audio.play().catch(e => {
        console.warn("Audio autoplay blocked:", e);
        if (voiceBtn) {
            voiceBtn.classList.remove('speaking');
            voiceBtn.innerText = "🔊 Read to Me";
        }
    });
}

function toggleVoiceReplay() {
    if (currentAudio && !currentAudio.paused) {
        stopSpeech();
    } else if (currentTeacherText) {
        playNeuralVoice(currentTeacherText);
    }
}

// --- Profile & Data Management ---
async function fetchPoints() {
    ['Krisha', 'Vedant'].forEach(async name => {
        try {
            const res = await fetch(`${SERVER_URL}/api/v1/profiles/${name}/points`);
            if (!res.ok) throw new Error("Profile not found");
            const data = await res.json();
            document.getElementById(`pts-${name}`).innerText = `${data.points} pts`;
            document.getElementById(`streak-${name}`).innerText = `🔥 ${data.streak}`;
        } catch(e) {
            document.getElementById(`pts-${name}`).innerText = "Offline";
        }
    });
}

function switchMode(mode) {
    currentMode = mode;
    initAudioContext();
    playCoinSound(1700, 0.05);

    const tabWs = document.getElementById('tabWorksheet');
    const tabBk = document.getElementById('tabBook');
    const btnScan = document.getElementById('btnScanPrompt');
    const btnSubmit = document.getElementById('btnSubmitGrade');
    const fbZone = document.getElementById('feedbackZone');
    const teacherCard = document.getElementById('teacherChatCard');
    const quizZone = document.getElementById('bookQuizZone');
    const resultZone = document.getElementById('bookResultZone');
    const shelfZone = document.getElementById('bookshelfZone');

    stopSpeech();
    resetScan();

    if (fbZone) fbZone.style.display = 'none';
    if (teacherCard) teacherCard.style.display = 'none';
    if (quizZone) quizZone.style.display = 'none';
    if (resultZone) resultZone.style.display = 'none';

    if (mode === 'book') {
        if (tabBk) tabBk.classList.add('active');
        if (tabWs) tabWs.classList.remove('active');
        if (btnScan) btnScan.innerText = "📖 Scan Book Cover or Barcode";
        if (btnSubmit) btnSubmit.innerText = "📖 Ask Book Question!";
        loadChildBookshelf(activeName);
    } else {
        if (tabWs) tabWs.classList.add('active');
        if (tabBk) tabBk.classList.remove('active');
        if (btnScan) btnScan.innerText = "📸 Scan Homework Page";
        if (btnSubmit) btnSubmit.innerText = "✨ Check My Work!";
        if (shelfZone) shelfZone.style.display = 'none';
    }
}

function handleSubmitAction() {
    if (currentMode === 'book') {
        scanAndQuizBook();
    } else {
        uploadAndGrade();
    }
}

function selectProfile(name, grade, element) {
    activeName = name;
    activeGrade = grade;
    initAudioContext();
    playCoinSound(1600, 0.05);

    document.querySelectorAll('.profile-card').forEach(c => c.classList.remove('selected'));
    element.classList.add('selected');

    document.getElementById('selectedNameDisplay').innerText = `${name} (${grade})`;
    
    // Show mode tabs
    const modeTabs = document.getElementById('modeTabs');
    if (modeTabs) modeTabs.style.display = 'flex';

    document.getElementById('actionZone').style.display = 'block';
    document.getElementById('feedbackZone').style.display = 'none';
    const teacherCard = document.getElementById('teacherChatCard');
    if (teacherCard) teacherCard.style.display = 'none';
    const quizZone = document.getElementById('bookQuizZone');
    if (quizZone) quizZone.style.display = 'none';
    const resultZone = document.getElementById('bookResultZone');
    if (resultZone) resultZone.style.display = 'none';

    stopSpeech();
    resetScan();

    if (currentMode === 'book') {
        loadChildBookshelf(name);
    }
}

function onFileSelected() {
    const fileInput = document.getElementById('cameraInput');
    if (!fileInput.files || fileInput.files.length === 0) return;

    selectedFile = fileInput.files[0];
    const reader = new FileReader();
    reader.onload = function(e) {
        document.getElementById('imagePreview').src = e.target.result;
        document.getElementById('imagePreviewContainer').style.display = 'block';
    };
    reader.readAsDataURL(selectedFile);
}

function resetScan() {
    selectedFile = null;
    document.getElementById('cameraInput').value = "";
    document.getElementById('imagePreviewContainer').style.display = 'none';
}

function rotatePreview() {
    const img = document.getElementById('imagePreview');
    if (!img.src) return;

    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');

    const nw = img.naturalWidth || img.width;
    const nh = img.naturalHeight || img.height;

    // Swap width and height for 90 degree rotation
    canvas.width = nh;
    canvas.height = nw;

    ctx.translate(canvas.width / 2, canvas.height / 2);
    ctx.rotate((90 * Math.PI) / 180);
    ctx.drawImage(img, -nw / 2, -nh / 2);

    const rotatedDataUrl = canvas.toDataURL('image/jpeg', 0.92);
    img.src = rotatedDataUrl;

    canvas.toBlob(blob => {
        if (blob) {
            selectedFile = new File([blob], "scan_rotated.jpg", { type: "image/jpeg" });
        }
    }, 'image/jpeg', 0.92);
}

async function uploadAndGrade() {
    if (!selectedFile) return;

    initAudioContext();
    stopSpeech();
    document.getElementById('loadingZone').style.display = 'block';
    document.getElementById('feedbackZone').style.display = 'none';
    document.getElementById('btnSubmitGrade').disabled = true;

    // Immediately auto-scroll to the loading tile
    document.getElementById('loadingZone').scrollIntoView({ behavior: 'smooth' });

    const formData = new FormData();
    formData.append("name", activeName);
    formData.append("gradeLevel", activeGrade);
    formData.append("file", selectedFile);

    try {
        const response = await fetch(`${SERVER_URL}/api/v1/grade`, {
            method: "POST",
            body: formData
        });

        const result = await response.json();
        document.getElementById('loadingZone').style.display = 'none';
        document.getElementById('btnSubmitGrade').disabled = false;

        if (!response.ok) {
            throw new Error(result.detail || "Server error occurred during grading.");
        }

        renderResult(result);
        fetchPoints();
    } catch (e) {
        document.getElementById('loadingZone').style.display = 'none';
        document.getElementById('btnSubmitGrade').disabled = false;
        alert("Error during grading: " + e.message);
    }
}

function renderResult(result) {
    const zone = document.getElementById('feedbackZone');
    const card = document.getElementById('feedbackCard');
    zone.style.display = 'block';

    let headerHtml = "";
    let pointsHtml = "";

    const pageBadge = result.page_identifier 
        ? `<span class="result-tag tag-page">📄 ${result.page_identifier}</span>` 
        : "";
    const hwBadge = result.handwriting_bonus 
        ? `<span class="result-tag tag-handwriting">✍️ Super Neat!</span>` 
        : "";

    if (result.status === "CORRECT") {
        headerHtml = `<h2 style="color: #27ae60;">🎉 Perfect Score!</h2>`;
        pointsHtml = `
            <div class="points-banner">
                <div class="pts-highlight">+${result.points_earned}</div>
                <div>
                    <div><strong>Points Earned!</strong></div>
                    <div style="font-size: 13px; color: #555;">Current Streak: 🔥 <strong>${result.current_streak}</strong> worksheets</div>
                </div>
            </div>`;
        playCasinoJackpot();
        launchConfetti();
    } else if (result.status === "CORRECTED") {
        headerHtml = `<h2 style="color: #2980b9;">🌟 Corrections Mastered!</h2>`;
        pointsHtml = `
            <div class="points-banner">
                <div class="pts-highlight">+${result.points_earned}</div>
                <div>
                    <div><strong>Mistakes Fixed! Bonus Earned!</strong></div>
                    <div style="font-size: 13px; color: #555;">Streak Restored: 🔥 <strong>${result.current_streak}</strong> worksheets</div>
                </div>
            </div>`;
        playCasinoJackpot();
        launchConfetti();
    } else if (result.status === "ALREADY_COMPLETED") {
        headerHtml = `<h2 style="color: #8e44ad;">⭐ Already Mastered!</h2>`;
        pointsHtml = `
            <div class="points-banner" style="background: #f5f3ff; border-color: #ddd6fe;">
                <div class="pts-highlight" style="color: #7c3aed;">0</div>
                <div>
                    <div><strong>Already Graded Page</strong></div>
                    <div style="font-size: 13px; color: #555;">You already aced this page earlier!</div>
                </div>
            </div>`;
        playSoftEncouragement();
    } else if (result.status === "TECH_ERROR") {
        headerHtml = `<h2 style="color: #e67e22;">🤖 Show to a Parent!</h2>`;
        pointsHtml = `
            <div class="points-banner" style="background: #fffbeb; border-color: #fde68a;">
                <div class="pts-highlight" style="color: #d97706;">0</div>
                <div>
                    <div><strong>AI Reading Trouble</strong></div>
                    <div style="font-size: 13px; color: #555;">Streak Preserved: 🔥 <strong>${result.current_streak}</strong> worksheets (Safe!)</div>
                </div>
            </div>`;
        playSoftEncouragement();
    } else {
        headerHtml = `<h2 style="color: #e74c3c;">✍️ Corrections Needed</h2>`;
        pointsHtml = `
            <div class="points-banner" style="background: #fef2f2; border-color: #fecaca;">
                <div class="pts-highlight" style="color: #dc2626;">0</div>
                <div>
                    <div><strong>Give it another try!</strong></div>
                    <div style="font-size: 13px; color: #555;">Streak reset. Fix mistakes and rescan to recover points!</div>
                </div>
            </div>`;
        playSoftEncouragement();
    }

    card.innerHTML = `
        <div>
            ${pageBadge}
            ${hwBadge}
        </div>
        ${headerHtml}
        <p class="result-msg">${result.message}</p>
        ${pointsHtml}
        <div class="explanation-box">
            <strong>Teacher's Notes:</strong><br>
            ${result.evaluation_text || "Keep up the great effort!"}
        </div>
        <div class="result-action-bar">
            <button class="btn-voice-replay" id="btnVoiceReplay" onclick="toggleVoiceReplay()">
                🔊 Read to Me
            </button>
            <button class="btn-scan-next" onclick="scanNextPage()">
                📸 Scan Next Page
            </button>
        </div>
    `;

    // Start spoken voice feedback automatically
    speakTeacherNotes(
        result.name, 
        result.evaluation_text || result.message, 
        result.is_correct, 
        result.points_earned,
        result.status
    );

    // Save worksheet context for Funny Teacher voice chat (Phase 2)
    lastGradedPageId = result.page_identifier || "";
    lastEvaluationText = result.evaluation_text || result.message || "";
    teacherChatHistory = [];

    const teacherCard = document.getElementById('teacherChatCard');
    if (teacherCard) {
        teacherCard.style.display = 'block';
        const bubble = document.getElementById('teacherSpeechBubble');
        if (bubble) {
            if (result.is_correct) {
                bubble.innerText = `Awesome job, ${result.name}! Ask me anything about this page, or ask for a hilarious random fact!`;
            } else if (result.status === "TECH_ERROR") {
                bubble.innerText = `I had a little trouble reading that page, but your streak is safe! Want to hear a funny fact while your parent checks it?`;
            } else {
                bubble.innerText = `Good effort, ${result.name}! Tap "Explain my mistake" or ask me how to solve any tricky question on this page!`;
            }
        }
    }

    // Scroll to feedback smoothly
    zone.scrollIntoView({ behavior: 'smooth' });
}

function scanNextPage() {
    stopSpeech();
    if (recognition && isRecording) {
        try { recognition.stop(); } catch (e) {}
    }
    resetScan();
    document.getElementById('feedbackZone').style.display = 'none';
    const teacherCard = document.getElementById('teacherChatCard');
    if (teacherCard) teacherCard.style.display = 'none';

    const actionZone = document.getElementById('actionZone');
    actionZone.scrollIntoView({ behavior: 'smooth' });
    setTimeout(() => {
        document.getElementById('cameraInput').click();
    }, 450);
}

// --- Funny Teacher (Professor Sunny) Voice Chat & Speech Recognition ---
function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        console.warn("Speech recognition not supported in this browser.");
        return null;
    }

    const rec = new SpeechRecognition();
    rec.continuous = false;
    rec.interimResults = false;
    rec.lang = 'en-US';

    rec.onstart = () => {
        isRecording = true;
        updateMicUI(true);
    };

    rec.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        const input = document.getElementById('teacherTextInput');
        if (input) input.value = transcript;
        sendTeacherMessage(transcript);
    };

    rec.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
        isRecording = false;
        updateMicUI(false);
    };

    rec.onend = () => {
        isRecording = false;
        updateMicUI(false);
    };

    return rec;
}

function updateMicUI(recording) {
    const micBtn = document.getElementById('btnVoiceMic');
    const micIcon = document.getElementById('micIcon');
    const micLabel = document.getElementById('micLabel');
    if (!micBtn) return;

    if (recording) {
        micBtn.classList.add('recording');
        if (micIcon) micIcon.innerText = "🛑";
        if (micLabel) micLabel.innerText = "Listening...";
    } else {
        micBtn.classList.remove('recording');
        if (micIcon) micIcon.innerText = "🎙️";
        if (micLabel) micLabel.innerText = "Tap to Talk";
    }
}

function toggleVoiceRecording() {
    stopSpeech();
    if (!recognition) {
        recognition = initSpeechRecognition();
        if (!recognition) {
            alert("Speech recognition isn't supported on this browser. You can type in the box below instead!");
            return;
        }
    }

    if (isRecording) {
        recognition.stop();
    } else {
        try {
            recognition.start();
        } catch (e) {
            console.warn("Recognition start issue:", e);
        }
    }
}

async function sendTeacherMessage(textOverride) {
    const input = document.getElementById('teacherTextInput');
    const message = textOverride || (input ? input.value.trim() : "");
    if (!message) return;

    if (input) input.value = "";

    const bubble = document.getElementById('teacherSpeechBubble');
    if (bubble) {
        bubble.innerHTML = `<em>Thinking... 🤔</em>`;
    }

    stopSpeech();

    // Add child prompt to local history
    teacherChatHistory.push({ role: "user", content: message });

    try {
        const res = await fetch(`${SERVER_URL}/api/v1/teacher/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                child_name: activeName || "Student",
                grade_level: activeGrade || "Kindergarten",
                message: message,
                page_identifier: lastGradedPageId,
                evaluation_text: lastEvaluationText,
                history: teacherChatHistory.slice(-6)
            })
        });

        if (!res.ok) {
            throw new Error(`Teacher chat failed: ${res.statusText}`);
        }

        const data = await res.json();
        const reply = data.reply;

        teacherChatHistory.push({ role: "assistant", content: reply });

        if (bubble) {
            bubble.innerText = `"${reply}"`;
        }

        // Play teacher voice with Kokoro
        if (soundEnabled) {
            playNeuralVoice(reply);
        }
    } catch (e) {
        console.error("Teacher chat error:", e);
        if (bubble) {
            bubble.innerText = `"Hoot! My owl brain had a hiccup: ${e.message}. Try asking me again!"`;
        }
    }
}

function askTeacherQuick(promptText) {
    sendTeacherMessage(promptText);
}

// Parent Zone Functions
function toggleParentModal() {
    const modal = document.getElementById('parentModal');
    const isVisible = modal.style.display === 'flex';
    if (isVisible) {
        modal.style.display = 'none';
    } else {
        modal.style.display = 'flex';
        loadSubmissionsHistory();
    }
}

async function adjustPoints(name, amount) {
    try {
        const res = await fetch(`${SERVER_URL}/api/v1/profiles/${name}/adjust-points`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ adjustment: amount, reason: "Parent adjustment" })
        });
        if (res.ok) {
            playCoinSound(1500, 0.08);
            fetchPoints();
            loadSubmissionsHistory();
        }
    } catch (e) {
        alert("Failed to adjust points: " + e.message);
    }
}

async function resetAllData() {
    const confirmed = confirm("Are you sure you want to reset all points, streaks, and submission records back to 0? This cannot be undone.");
    if (!confirmed) return;

    try {
        const res = await fetch(`${SERVER_URL}/api/v1/admin/reset-all`, {
            method: "POST"
        });
        const data = await res.json();
        if (res.ok) {
            alert(data.message || "All data reset successfully!");
            fetchPoints();
            loadSubmissionsHistory();
        } else {
            alert("Error resetting data: " + (data.detail || "Server error"));
        }
    } catch (e) {
        alert("Failed to reset: " + e.message);
    }
}

async function loadSubmissionsHistory() {
    const tbody = document.getElementById('historyTableBody');
    try {
        const res = await fetch(`${SERVER_URL}/api/v1/submissions?limit=15`);
        const data = await res.json();
        if (data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5">No submissions recorded yet.</td></tr>';
            return;
        }
        tbody.innerHTML = data.map(item => {
            const date = new Date(item.submitted_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            return `
                <tr>
                    <td>${date}</td>
                    <td><strong>${item.child_name}</strong></td>
                    <td>${item.page_identifier || '—'}</td>
                    <td><span class="status-pill">${item.status}</span></td>
                    <td><strong>${item.points_awarded > 0 ? '+' : ''}${item.points_awarded}</strong></td>
                </tr>
            `;
        }).join('');
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="5">Could not load history.</td></tr>';
    }
}

// --- Bookworm Club (Phase 3) ---
async function scanAndQuizBook() {
    if (!selectedFile) return;

    initAudioContext();
    stopSpeech();
    
    const loadTitle = document.getElementById('loadingTitle');
    const loadText = document.getElementById('loadingText');
    if (loadTitle) loadTitle.innerText = "✨ Inspecting your book...";
    if (loadText) loadText.innerText = "Our smart reading tutor is reading the title and formulating a fun question!";
    
    document.getElementById('loadingZone').style.display = 'block';
    const quizZone = document.getElementById('bookQuizZone');
    const resultZone = document.getElementById('bookResultZone');
    if (quizZone) quizZone.style.display = 'none';
    if (resultZone) resultZone.style.display = 'none';

    document.getElementById('btnSubmitGrade').disabled = true;
    document.getElementById('loadingZone').scrollIntoView({ behavior: 'smooth' });

    const formData = new FormData();
    formData.append("name", activeName);
    formData.append("gradeLevel", activeGrade);
    formData.append("file", selectedFile);

    try {
        const response = await fetch(`${SERVER_URL}/api/v1/books/scan`, {
            method: "POST",
            body: formData
        });

        const result = await response.json();
        document.getElementById('loadingZone').style.display = 'none';
        document.getElementById('btnSubmitGrade').disabled = false;

        if (!response.ok) {
            throw new Error(result.detail || "Server error while inspecting book.");
        }

        renderBookQuiz(result);
    } catch (e) {
        document.getElementById('loadingZone').style.display = 'none';
        document.getElementById('btnSubmitGrade').disabled = false;
        alert("Error during book scan: " + e.message);
    }
}

function renderBookQuiz(data) {
    currentBookData = data;
    const titleEl = document.getElementById('bookTitleDisplay');
    const authorEl = document.getElementById('bookAuthorDisplay');
    const readBadge = document.getElementById('bookAlreadyReadBadge');
    const bubble = document.getElementById('bookQuestionBubble');
    const input = document.getElementById('bookAnswerInput');

    if (titleEl) titleEl.innerText = data.title;
    if (authorEl) authorEl.innerText = data.author ? `by ${data.author}` : "";
    if (readBadge) readBadge.style.display = data.already_read ? 'inline-block' : 'none';
    if (bubble) bubble.innerText = `"${data.question}"`;
    if (input) input.value = "";

    const quizZone = document.getElementById('bookQuizZone');
    if (quizZone) {
        quizZone.style.display = 'block';
        quizZone.scrollIntoView({ behavior: 'smooth' });
    }

    if (soundEnabled) {
        playNeuralVoice(data.message || data.question);
    }
}

async function submitBookAnswer() {
    if (!currentBookData) return;
    const input = document.getElementById('bookAnswerInput');
    const answer = input ? input.value.trim() : "";
    if (!answer) {
        alert("Please speak or type your answer!");
        return;
    }

    initAudioContext();
    stopSpeech();

    const submitBtn = document.getElementById('btnSubmitBookAnswer');
    if (submitBtn) submitBtn.disabled = true;

    try {
        const response = await fetch(`${SERVER_URL}/api/v1/books/verify`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                child_name: activeName,
                grade_level: activeGrade,
                title: currentBookData.title,
                author: currentBookData.author,
                isbn: currentBookData.isbn,
                question: currentBookData.question,
                child_answer: answer
            })
        });

        const result = await response.json();
        if (submitBtn) submitBtn.disabled = false;

        if (!response.ok) {
            throw new Error(result.detail || "Server error verifying answer.");
        }

        renderBookResult(result);
        fetchPoints();
        loadChildBookshelf(activeName);
    } catch (e) {
        if (submitBtn) submitBtn.disabled = false;
        alert("Error submitting answer: " + e.message);
    }
}

function renderBookResult(result) {
    const zone = document.getElementById('bookResultZone');
    const card = document.getElementById('bookResultCard');
    if (!zone || !card) return;

    zone.style.display = 'block';

    if (result.passed) {
        card.innerHTML = `
            <div style="margin-bottom: 8px;">
                <span class="result-tag tag-page">📖 ${result.title}</span>
                <span class="result-tag tag-handwriting">⭐ Mastered!</span>
            </div>
            <h2 style="color: #27ae60;">🎉 Reading Star Achieved!</h2>
            <div class="points-banner">
                <div class="pts-highlight">+${result.points_earned}</div>
                <div>
                    <div><strong>Reading Points Earned!</strong></div>
                    <div style="font-size: 13px; color: #555;">Added to your Virtual Bookshelf! 📚</div>
                </div>
            </div>
            <div class="explanation-box">
                <strong>Professor Sunny's Review:</strong><br>
                ${result.feedback}
            </div>
            <div class="result-action-bar">
                <button class="btn-scan-next" onclick="resetBookFlow()">
                    📖 Scan Another Book
                </button>
            </div>
        `;
        playCasinoJackpot();
        launchConfetti();
    } else {
        card.innerHTML = `
            <div style="margin-bottom: 8px;">
                <span class="result-tag tag-page">📖 ${result.title}</span>
            </div>
            <h2 style="color: #e67e22;">💡 Almost There!</h2>
            <div class="points-banner" style="background: #fffbeb; border-color: #fde68a;">
                <div class="pts-highlight" style="color: #d97706;">0</div>
                <div>
                    <div><strong>Give It Another Shot!</strong></div>
                    <div style="font-size: 13px; color: #555;">Listen to Professor Sunny's hint and try again!</div>
                </div>
            </div>
            <div class="explanation-box">
                <strong>Professor Sunny's Hint:</strong><br>
                ${result.feedback}
            </div>
            <div class="result-action-bar">
                <button class="btn-voice-replay" onclick="document.getElementById('bookQuizZone').scrollIntoView({ behavior: 'smooth' })">
                    🔄 Try Answering Again
                </button>
            </div>
        `;
        playSoftEncouragement();
    }

    if (soundEnabled) {
        playNeuralVoice(result.feedback);
    }
    zone.scrollIntoView({ behavior: 'smooth' });
}

function resetBookFlow() {
    stopSpeech();
    resetScan();
    const quizZone = document.getElementById('bookQuizZone');
    const resultZone = document.getElementById('bookResultZone');
    if (quizZone) quizZone.style.display = 'none';
    if (resultZone) resultZone.style.display = 'none';

    const actionZone = document.getElementById('actionZone');
    if (actionZone) actionZone.scrollIntoView({ behavior: 'smooth' });
    setTimeout(() => {
        document.getElementById('cameraInput').click();
    }, 450);
}

async function loadChildBookshelf(childName) {
    if (!childName) return;
    const shelfZone = document.getElementById('bookshelfZone');
    const shelfName = document.getElementById('shelfChildName');
    const badge = document.getElementById('booksCountBadge');
    const grid = document.getElementById('shelfGrid');

    if (shelfName) shelfName.innerText = childName;
    if (shelfZone) shelfZone.style.display = 'block';

    try {
        const res = await fetch(`${SERVER_URL}/api/v1/books/shelf/${childName}`);
        if (!res.ok) return;
        const books = await res.json();
        if (badge) badge.innerText = `${books.length} book${books.length === 1 ? '' : 's'} read`;

        if (!grid) return;
        if (books.length === 0) {
            grid.innerHTML = `<div class="shelf-empty-msg">No books conquered yet. Scan a library book above to earn your first Reading Star! ⭐</div>`;
            return;
        }

        grid.innerHTML = books.map((b, idx) => `
            <div class="book-badge-card color-${idx % 5}">
                <div class="badge-book-title">${b.title}</div>
                <div class="badge-book-author">${b.author || 'Children’s Library'}</div>
                <div class="badge-book-pts">🌟 +${b.points_awarded} pts</div>
            </div>
        `).join('');
    } catch (e) {
        console.warn("Could not load bookshelf:", e);
    }
}

// Book Speech Recognition
function initBookSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return null;

    const rec = new SpeechRecognition();
    rec.continuous = false;
    rec.interimResults = false;
    rec.lang = 'en-US';

    rec.onstart = () => {
        isBookRecording = true;
        updateBookMicUI(true);
    };

    rec.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        const input = document.getElementById('bookAnswerInput');
        if (input) input.value = transcript;
        submitBookAnswer();
    };

    rec.onerror = () => {
        isBookRecording = false;
        updateBookMicUI(false);
    };

    rec.onend = () => {
        isBookRecording = false;
        updateBookMicUI(false);
    };

    return rec;
}

function updateBookMicUI(recording) {
    const micBtn = document.getElementById('btnBookMic');
    const micIcon = document.getElementById('bookMicIcon');
    const micLabel = document.getElementById('bookMicLabel');
    if (!micBtn) return;

    if (recording) {
        micBtn.classList.add('recording');
        if (micIcon) micIcon.innerText = "🛑";
        if (micLabel) micLabel.innerText = "Listening...";
    } else {
        micBtn.classList.remove('recording');
        if (micIcon) micIcon.innerText = "🎙️";
        if (micLabel) micLabel.innerText = "Tap to Answer";
    }
}

function toggleBookVoiceRecording() {
    stopSpeech();
    if (!bookRecognition) {
        bookRecognition = initBookSpeechRecognition();
        if (!bookRecognition) {
            alert("Speech recognition isn't supported on this browser. You can type your answer in the box below!");
            return;
        }
    }

    if (isBookRecording) {
        bookRecognition.stop();
    } else {
        try {
            bookRecognition.start();
        } catch (e) {
            console.warn("Book recognition start error:", e);
        }
    }
}

// Initial fetch on page load
fetchPoints();
