/**
 * The Interview Agent — Frontend Application Logic (Phase 6)
 */

let candidatesData = [];
let selectedCandidate = null;
let currentSessionId = "";
let questionCount = 0;
const API_BASE = "";

document.addEventListener("DOMContentLoaded", () => {
  loadCandidates();

  const answerInput = document.getElementById("answer-input");
  if (answerInput) {
    answerInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        submitAnswer();
      }
    });
  }
});

/** Fetch candidates list from API endpoint */
async function loadCandidates() {
  const dropdown = document.getElementById("candidate-dropdown");
  try {
    const res = await fetch(`${API_BASE}/api/candidates`);
    if (!res.ok) throw new Error("Failed to fetch candidates");
    const data = await res.json();
    candidatesData = data.candidates || [];

    dropdown.innerHTML = `<option value="" disabled selected>Select candidate profile...</option>`;
    candidatesData.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.member.id;
      opt.textContent = `${c.member.id}: ${c.member.name} (${c.member.jobRole}, ${c.member.yearsExperience} yrs)`;
      dropdown.appendChild(opt);
    });
  } catch (err) {
    console.error("Error loading candidates:", err);
    dropdown.innerHTML = `<option value="" disabled>Error loading candidates</option>`;
  }
}

/** Called when candidate is selected from dropdown */
function onCandidateSelect(candId) {
  selectedCandidate = candidatesData.find((c) => c.member.id === candId);
  if (!selectedCandidate) return;

  const box = document.getElementById("candidate-detail");
  box.classList.remove("hidden");

  const m = selectedCandidate.member;
  const s = selectedCandidate.signals;
  const firstTryPct = Math.round((s.missionsFirstTry / (s.missionsCompleted || 1)) * 100);
  const commitPct = Math.round((s.commitDays / 31) * 100);

  const skippedMissions = selectedCandidate.missions.filter((x) => x.skipped);
  const failedMissions = selectedCandidate.missions.filter((x) => x.passed === false);
  const struggleMissions = selectedCandidate.missions.filter((x) => x.passed && x.attempts >= 4);

  box.innerHTML = `
    <div class="detail-grid">
      <div class="detail-item">
        <span class="label">Candidate Name</span>
        <span class="value">${m.name}</span>
      </div>
      <div class="detail-item">
        <span class="label">Target Role</span>
        <span class="value">${m.jobRole} (${m.yearsExperience} yrs exp)</span>
      </div>
      <div class="detail-item">
        <span class="label">Education</span>
        <span class="value">${m.education}</span>
      </div>
      <div class="detail-item">
        <span class="label">First-Try Pass Rate</span>
        <span class="value">${firstTryPct}% (${s.missionsFirstTry}/${s.missionsCompleted})</span>
      </div>
    </div>

    <div class="mission-summary-bar">
      <span class="mini-badge badge-info">Commit Days: ${s.commitDays}/31 (${commitPct}%)</span>
      ${failedMissions.length ? `<span class="mini-badge badge-danger">Failed Missions: ${failedMissions.length}</span>` : ""}
      ${skippedMissions.length ? `<span class="mini-badge badge-warning">Skipped Missions: ${skippedMissions.length}</span>` : ""}
      ${struggleMissions.length ? `<span class="mini-badge badge-warning">Struggle (≥4 att): ${struggleMissions.length}</span>` : ""}
    </div>
  `;

  document.getElementById("start-interview-btn").disabled = false;
}

/** Initialize interview session */
async function startInterview() {
  if (!selectedCandidate) return;

  currentSessionId = `session-${Date.now()}`;
  questionCount = 1;

  const startBtn = document.getElementById("start-interview-btn");
  startBtn.disabled = true;
  startBtn.innerHTML = `<span>Initializing Session...</span>`;

  try {
    const res = await fetch(`${API_BASE}/api/interview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sessionId: currentSessionId,
        candidate: selectedCandidate,
      }),
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || "Initialization failed");
    }

    const data = await res.json();

    // Switch view
    switchView("interview-view");
    document.getElementById("session-badge").classList.remove("hidden");
    document.getElementById("reset-btn").classList.remove("hidden");
    document.getElementById("session-id-display").textContent = `Session: ${currentSessionId.slice(-8)}`;

    // Clear chat & append initial welcome/Q1 bubble
    const chatContainer = document.getElementById("chat-messages");
    chatContainer.innerHTML = "";
    appendMessage("ai", data.reply);

    updateProgress(1, 10);
  } catch (err) {
    showError(`Failed to start interview: ${err.message}`);
    startBtn.disabled = false;
    startBtn.innerHTML = `🚀 Start Personalized Interview`;
  }
}

/** Submit candidate answer for turn N */
async function submitAnswer() {
  const input = document.getElementById("answer-input");
  const text = input.value.trim();
  if (!text) return;

  // Append user bubble
  appendMessage("user", text);
  input.value = "";

  // Disable input & show typing indicator
  setFormLoading(true);
  dismissError();

  try {
    const res = await fetch(`${API_BASE}/api/interview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sessionId: currentSessionId,
        message: text,
      }),
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || "Turn request failed");
    }

    const data = await res.json();
    setFormLoading(false);

    questionCount += 1;
    updateProgress(questionCount, 10);

    // Append AI reply
    appendMessage("ai", data.reply);

    // If done, show completion feedback view
    if (data.done) {
      setTimeout(() => {
        showCompletionFeedback(data.feedback);
      }, 1500);
    }
  } catch (err) {
    setFormLoading(false);
    showError(`Error submitting answer: ${err.message}`);
  }
}

/** Display final completion feedback modal/view */
function showCompletionFeedback(feedback) {
  if (!feedback) return;

  switchView("completion-view");

  document.getElementById("feedback-candidate-info").textContent = 
    `Assessment for ${selectedCandidate.member.name} (${selectedCandidate.member.jobRole})`;

  // Summary
  document.getElementById("feedback-summary-text").textContent = feedback.summary || "Interview completed successfully.";

  // Strengths
  const sList = document.getElementById("feedback-strengths-list");
  sList.innerHTML = "";
  (feedback.strengths || []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    sList.appendChild(li);
  });
  if (!feedback.strengths || feedback.strengths.length === 0) {
    sList.innerHTML = `<li>Baseline understanding demonstrated across core technical topics.</li>`;
  }

  // Gaps
  const gList = document.getElementById("feedback-gaps-list");
  gList.innerHTML = "";
  (feedback.gaps || []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    gList.appendChild(li);
  });
  if (!feedback.gaps || feedback.gaps.length === 0) {
    gList.innerHTML = `<li>No critical technical gaps demonstrated during the interview.</li>`;
  }

  // Next steps & Unassessed
  const nList = document.getElementById("feedback-next-list");
  nList.innerHTML = "";
  (feedback.next || []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    nList.appendChild(li);
  });
}

/** Reset application back to candidate selection */
function resetInterview() {
  selectedCandidate = null;
  currentSessionId = "";
  questionCount = 0;

  document.getElementById("candidate-dropdown").value = "";
  document.getElementById("candidate-detail").classList.add("hidden");
  document.getElementById("start-interview-btn").disabled = true;
  document.getElementById("start-interview-btn").innerHTML = `🚀 Start Personalized Interview`;

  document.getElementById("session-badge").classList.add("hidden");
  document.getElementById("reset-btn").classList.add("hidden");

  switchView("candidate-select-view");
}

/** Append bubble to chat area */
function appendMessage(role, text) {
  const container = document.getElementById("chat-messages");
  const div = document.createElement("div");
  div.className = `message-bubble ${role}`;

  const name = role === "ai" ? "Interviewer" : selectedCandidate ? selectedCandidate.member.name : "Candidate";
  const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  div.innerHTML = `
    <div class="message-header">
      <span>${name}</span> • <span>${time}</span>
    </div>
    <div class="message-content">${escapeHtml(text)}</div>
  `;

  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

/** Update progress bar */
function updateProgress(current, target) {
  const pct = Math.min(100, Math.round((current / target) * 100));
  document.getElementById("progress-text").textContent = `Question ${current} of ~${target}`;
  document.getElementById("progress-percentage").textContent = `${pct}%`;
  document.getElementById("progress-fill").style.width = `${pct}%`;
}

/** Enable/disable input form during async operations */
function setFormLoading(loading) {
  const input = document.getElementById("answer-input");
  const btn = document.getElementById("submit-answer-btn");
  const typing = document.getElementById("typing-indicator");

  input.disabled = loading;
  btn.disabled = loading;
  if (loading) {
    typing.classList.remove("hidden");
  } else {
    typing.classList.add("hidden");
    input.focus();
  }
}

/** Switch active view section */
function switchView(viewId) {
  document.querySelectorAll(".view-section").forEach((sec) => {
    sec.classList.remove("active");
    sec.classList.add("hidden");
  });
  const target = document.getElementById(viewId);
  if (target) {
    target.classList.remove("hidden");
    target.classList.add("active");
  }
}

/** Error helpers */
function showError(msg) {
  const banner = document.getElementById("error-banner");
  document.getElementById("error-text").textContent = msg;
  banner.classList.remove("hidden");
}

function dismissError() {
  document.getElementById("error-banner").classList.add("hidden");
}

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
