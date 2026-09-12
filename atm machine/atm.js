/**
 * MULTI-BANK CARDLESS ATM — CLIENT ENGINE
 * Handles ATM Session State Machine, Touch Keypad, OTP Verification,
 * Real-time Timers, Audio Synthesizer & MongoDB Bank Integrations.
 */

// ============================================================================
// CONFIGURATION & GLOBAL STATE
// ============================================================================
// Automatically use backend URL:
// - Relative path when running directly on port 8000
// - Full URL http://127.0.0.1:8000 when running on standalone port (e.g. 8080)
const API_BASE = (window.location.port === "8000") ? "" : "http://127.0.0.1:8000";

const atmState = {
  sessionId: null,
  userId: null,
  userName: "Customer",
  maskedMobile: null,
  currentStep: "HOME",
  otpVerified: false,
  demoOtp: null,
  linkedBanks: [],
  selectedBank: null,
  selectedAmount: 0,
  mobileInput: "",
  pinInput: "",
  otpInput: ["", "", "", "", "", ""],
  bankPinInput: "",
  customAmountInput: "",
  activeKeypadTarget: null,
  otpTimerInterval: null,
  otpTimeRemaining: 300, // 5 minutes
  resendCooldownRemaining: 0,
  resendTimerInterval: null
};

// ============================================================================
// WEB AUDIO SYNTHESIZER (REALISTIC ATM SOUNDS)
// ============================================================================
class ATMAudio {
  constructor() {
    this.ctx = null;
  }

  init() {
    if (!this.ctx) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) this.ctx = new AudioContext();
    }
  }

  playKeyBeep() {
    try {
      this.init();
      if (!this.ctx) return;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(1200, this.ctx.currentTime);
      gain.gain.setValueAtTime(0.04, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.05);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start();
      osc.stop(this.ctx.currentTime + 0.05);
    } catch (_) {}
  }

  playSuccessChime() {
    try {
      this.init();
      if (!this.ctx) return;
      const notes = [523.25, 659.25, 783.99, 1046.50]; // C5, E5, G5, C6
      notes.forEach((freq, idx) => {
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.type = "triangle";
        osc.frequency.setValueAtTime(freq, this.ctx.currentTime + idx * 0.09);
        gain.gain.setValueAtTime(0.08, this.ctx.currentTime + idx * 0.09);
        gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + idx * 0.09 + 0.25);
        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.start(this.ctx.currentTime + idx * 0.09);
        osc.stop(this.ctx.currentTime + idx * 0.09 + 0.25);
      });
    } catch (_) {}
  }

  playErrorBuzz() {
    try {
      this.init();
      if (!this.ctx) return;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(160, this.ctx.currentTime);
      gain.gain.setValueAtTime(0.08, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.22);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start();
      osc.stop(this.ctx.currentTime + 0.22);
    } catch (_) {}
  }
}

const audio = new ATMAudio();

// ============================================================================
// DIGITAL CLOCK
// ============================================================================
function initKioskClock() {
  const clockEl = document.getElementById("kiosk-clock");
  function update() {
    const now = new Date();
    if (clockEl) {
      clockEl.textContent = now.toLocaleTimeString("en-GB", { hour12: false });
    }
  }
  update();
  setInterval(update, 1000);
}

// ============================================================================
// TOAST NOTIFICATIONS
// ============================================================================
function showATMToast(message, type = "info", duration = 4000) {
  const toast = document.getElementById("atm-toast");
  const msgEl = document.getElementById("atm-toast-msg");
  if (!toast || !msgEl) return;

  msgEl.textContent = message;
  toast.className = `atm-toast ${type}`;
  toast.classList.remove("hidden");

  if (type === "error") audio.playErrorBuzz();

  clearTimeout(toast._timeout);
  toast._timeout = setTimeout(() => {
    toast.classList.add("hidden");
  }, duration);
}

// ============================================================================
// API CLIENT
// ============================================================================
async function atmApi(endpoint, method = "GET", body = null) {
  const headers = { "Content-Type": "application/json" };
  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  const res = await fetch(`${API_BASE}${endpoint}`, opts);
  const text = await res.text();
  let data = {};
  try {
    data = JSON.parse(text);
  } catch (_) {
    data = { detail: text };
  }

  if (!res.ok) {
    const errMsg = data.detail || (Array.isArray(data) ? data[0]?.msg : "Server request failed");
    throw new Error(errMsg);
  }
  return data;
}

// ============================================================================
// SCREEN SWITCHER
// ============================================================================
const screens = {
  home: document.getElementById("screen-home"),
  mobile: document.getElementById("screen-mobile"),
  pin: document.getElementById("screen-pin"),
  otp: document.getElementById("screen-otp"),
  bankSelect: document.getElementById("screen-bank-select"),
  bankPin: document.getElementById("screen-bank-pin"),
  amount: document.getElementById("screen-amount"),
  confirm: document.getElementById("screen-confirm"),
  success: document.getElementById("screen-success")
};

function switchScreen(targetScreenKey) {
  Object.keys(screens).forEach(key => {
    if (screens[key]) {
      if (key === targetScreenKey) {
        screens[key].classList.remove("hidden");
        screens[key].classList.add("active-screen");
      } else {
        screens[key].classList.add("hidden");
        screens[key].classList.remove("active-screen");
      }
    }
  });

  // Set active keypad target
  if (targetScreenKey === "mobile") atmState.activeKeypadTarget = "mobile";
  else if (targetScreenKey === "pin") atmState.activeKeypadTarget = "pin";
  else if (targetScreenKey === "otp") atmState.activeKeypadTarget = "otp";
  else if (targetScreenKey === "bankPin") atmState.activeKeypadTarget = "bankpin";
  else if (targetScreenKey === "amount") atmState.activeKeypadTarget = "amount";
  else atmState.activeKeypadTarget = null;
}

// ============================================================================
// KEYPAD DISPATCHER (CLICKS & TOUCH)
// ============================================================================
function handleKeypadPress(targetName, key) {
  audio.playKeyBeep();

  if (targetName === "mobile") {
    handleMobileKey(key);
  } else if (targetName === "pin") {
    handlePinKey(key);
  } else if (targetName === "otp") {
    handleOtpKey(key);
  } else if (targetName === "bankpin") {
    handleBankPinKey(key);
  } else if (targetName === "amount") {
    handleAmountKey(key);
  }
}

// Global delegated click handler for all keypad buttons
document.addEventListener("click", (e) => {
  const keyBtn = e.target.closest(".key-btn");
  if (!keyBtn) return;
  const keypad = keyBtn.closest(".atm-keypad");
  const target = keypad ? keypad.getAttribute("data-target") : atmState.activeKeypadTarget;
  const key = keyBtn.getAttribute("data-key");
  if (target && key) {
    handleKeypadPress(target, key);
  }
});

// Hardware keyboard support
document.addEventListener("keydown", (e) => {
  if (!atmState.activeKeypadTarget) return;

  if (e.key >= "0" && e.key <= "9") {
    handleKeypadPress(atmState.activeKeypadTarget, e.key);
  } else if (e.key === "Backspace") {
    handleKeypadPress(atmState.activeKeypadTarget, "BACKSPACE");
  } else if (e.key === "Escape") {
    handleKeypadPress(atmState.activeKeypadTarget, "CLEAR");
  }
});


// ============================================================================
// STEP 1 & 2: ATM HOME SCREEN
// ============================================================================
const btnStartCardless = document.getElementById("btn-start-cardless");

btnStartCardless?.addEventListener("click", async () => {
  audio.playKeyBeep();
  try {
    const session = await atmApi("/api/atm/session/start", "POST");
    atmState.sessionId = session.session_id;
    atmState.currentStep = "MOBILE_ENTRY";
    atmState.mobileInput = "";
    updateMobileDisplay();
    switchScreen("mobile");
    showATMToast("ATM Session Initialized. Please enter your mobile number.", "info");
  } catch (err) {
    showATMToast(err.message, "error");
  }
});


// ============================================================================
// STEP 3: REGISTERED MOBILE NUMBER SCREEN
// ============================================================================
const displayMobile = document.getElementById("display-mobile");
const mobileErrorMsg = document.getElementById("mobile-error-msg");
const btnMobileNext = document.getElementById("btn-mobile-next");
const btnMobileCancel = document.getElementById("btn-mobile-cancel");

function handleMobileKey(key) {
  if (key === "CLEAR") {
    atmState.mobileInput = "";
  } else if (key === "BACKSPACE") {
    atmState.mobileInput = atmState.mobileInput.slice(0, -1);
  } else if (/^\d$/.test(key)) {
    if (atmState.mobileInput.length < 10) {
      atmState.mobileInput += key;
    }
  }
  updateMobileDisplay();
}

function updateMobileDisplay() {
  if (!displayMobile) return;
  displayMobile.textContent = atmState.mobileInput;

  // Format validation
  const val = atmState.mobileInput;
  const isValid = val.length >= 9 && /^[6-9]\d+$/.test(val);

  if (val.length === 0) {
    mobileErrorMsg.textContent = "Enter 10 digits starting with 6, 7, 8, or 9";
    mobileErrorMsg.classList.remove("error");
    btnMobileNext.disabled = true;
  } else if (!/^[6-9]/.test(val)) {
    mobileErrorMsg.textContent = "Indian mobile numbers must begin with 6, 7, 8, or 9";
    mobileErrorMsg.classList.add("error");
    btnMobileNext.disabled = true;
  } else if (val.length < 9) {
    mobileErrorMsg.textContent = `Entering phone number (${val.length}/10 digits)`;
    mobileErrorMsg.classList.remove("error");
    btnMobileNext.disabled = true;
  } else {
    mobileErrorMsg.textContent = "Valid phone number format ready for verification.";
    mobileErrorMsg.classList.remove("error");
    btnMobileNext.disabled = false;
  }
}

// Quick demo buttons on mobile screen
document.querySelectorAll(".btn-demo-quick").forEach(btn => {
  btn.addEventListener("click", () => {
    audio.playKeyBeep();
    const m = btn.getAttribute("data-mobile");
    if (m) {
      atmState.mobileInput = m;
      updateMobileDisplay();
    }
  });
});

btnMobileNext?.addEventListener("click", async () => {
  audio.playKeyBeep();
  btnMobileNext.disabled = true;

  try {
    const res = await atmApi("/api/atm/session/verify-mobile", "POST", {
      session_id: atmState.sessionId,
      mobile: atmState.mobileInput
    });

    atmState.userId = res.user_id;
    atmState.maskedMobile = res.masked_mobile;
    atmState.userName = res.user_name;
    atmState.pinInput = "";

    // Update PIN screen indicators
    const pinMobEl = document.getElementById("pin-screen-mobile");
    if (pinMobEl) pinMobEl.textContent = `+91 ${res.masked_mobile} (${res.user_name})`;

    const demoHintText = document.getElementById("demo-pin-hint-text");
    if (demoHintText) {
      if (atmState.mobileInput.includes("9876543210")) {
        demoHintText.innerHTML = "Demo PIN for Arun Kumar: <strong>Password@123</strong> (Use quick autofill below or type)";
      } else if (atmState.mobileInput.includes("987654321")) {
        demoHintText.innerHTML = "Demo PIN for Vishnu: <strong>2006</strong> (Numeric Keypad: 2-0-0-6)";
      } else {
        demoHintText.innerHTML = "Enter the PIN/Password configured for your account.";
      }
    }

    updatePinSlots();
    switchScreen("pin");
    showATMToast(`User identified: ${res.user_name}. Please enter ATM App PIN.`, "success");
  } catch (err) {
    mobileErrorMsg.textContent = err.message;
    mobileErrorMsg.classList.add("error");
    showATMToast(err.message, "error");
  } finally {
    btnMobileNext.disabled = false;
  }
});

btnMobileCancel?.addEventListener("click", () => resetToHome());


// ============================================================================
// STEP 4: ENTER ATM APP PIN SCREEN
// ============================================================================
const pinSlots = document.querySelectorAll("#pin-slots .pin-slot");
const pinErrorMsg = document.getElementById("pin-error-msg");
const btnPinNext = document.getElementById("btn-pin-next");
const btnPinCancel = document.getElementById("btn-pin-cancel");

function handlePinKey(key) {
  if (key === "CLEAR") {
    atmState.pinInput = "";
  } else if (key === "BACKSPACE") {
    atmState.pinInput = atmState.pinInput.slice(0, -1);
  } else if (/^\d$/.test(key)) {
    if (atmState.pinInput.length < 4) {
      atmState.pinInput += key;
    }
  }
  updatePinSlots();
}

function updatePinSlots() {
  const len = atmState.pinInput.length;
  pinSlots.forEach((slot, idx) => {
    if (idx < len) {
      slot.classList.add("filled");
      slot.classList.remove("active-focus");
    } else if (idx === len) {
      slot.classList.remove("filled");
      slot.classList.add("active-focus");
    } else {
      slot.classList.remove("filled", "active-focus");
    }
  });

  if (len === 4) {
    btnPinNext.disabled = false;
    pinErrorMsg.textContent = "PIN ready for verification.";
    pinErrorMsg.classList.remove("error");
  } else {
    btnPinNext.disabled = true;
    pinErrorMsg.textContent = `Enter your 4-digit ATM App PIN (${len}/4 entered)`;
    pinErrorMsg.classList.remove("error");
  }
}

btnPinNext?.addEventListener("click", async () => {
  audio.playKeyBeep();
  btnPinNext.disabled = true;

  try {
    const res = await atmApi("/api/atm/session/verify-pin", "POST", {
      session_id: atmState.sessionId,
      pin: atmState.pinInput
    });

    atmState.demoOtp = res.demo_otp;
    atmState.currentStep = "OTP_VERIFICATION";

    // Setup Screen 5 (OTP Verification)
    setupOtpVerificationScreen();
    switchScreen("otp");
    showATMToast("PIN verified! An OTP has been sent to your ATM App.", "info", 5000);
  } catch (err) {
    pinErrorMsg.textContent = err.message;
    pinErrorMsg.classList.add("error");
    showATMToast(err.message, "error");
    // Shake slots animation
    const wrapper = document.getElementById("pin-slots");
    if (wrapper) {
      wrapper.style.animation = "shake 0.3s ease";
      setTimeout(() => wrapper.style.animation = "", 300);
    }
  } finally {
    btnPinNext.disabled = false;
  }
});

btnPinCancel?.addEventListener("click", () => resetToHome());


// ============================================================================
// STEP 5: OTP VERIFICATION SCREEN (CORE FOCUS)
// ============================================================================
const otpBoxes = document.querySelectorAll(".otp-box");
const otpMaskedDisplay = document.getElementById("otp-masked-display");
const otpCountdownTimer = document.getElementById("otp-countdown-timer");
const otpStatusFeedback = document.getElementById("otp-status-feedback");
const btnVerifyOtp = document.getElementById("btn-verify-otp");
const btnResendOtp = document.getElementById("btn-resend-otp");
const resendBtnText = document.getElementById("resend-btn-text");
const btnOtpCancel = document.getElementById("btn-otp-cancel");

function setupOtpVerificationScreen() {
  // 1. Display masked phone/app notification notice
  if (otpMaskedDisplay) {
    otpMaskedDisplay.textContent = `OTP sent to your registered ATM App (${atmState.maskedMobile || "******1234"})`;
  }

  // 2. Clear all OTP input boxes
  atmState.otpInput = ["", "", "", "", "", ""];
  otpBoxes.forEach((box, idx) => {
    box.value = "";
    box.classList.remove("filled", "error-box", "active-box");
    if (idx === 0) box.classList.add("active-box");
  });
  if (otpBoxes[0]) otpBoxes[0].focus();

  // 3. Start 5-Minute Countdown Timer
  startOtpCountdown(300);

  // 4. Initial state of buttons
  if (btnVerifyOtp) btnVerifyOtp.disabled = true;
  if (otpStatusFeedback) {
    otpStatusFeedback.textContent = "";
    otpStatusFeedback.className = "otp-feedback-msg hidden";
  }
}

function startOtpCountdown(seconds = 300) {
  clearInterval(atmState.otpTimerInterval);
  atmState.otpTimeRemaining = seconds;

  function tick() {
    const mins = Math.floor(atmState.otpTimeRemaining / 60);
    const secs = atmState.otpTimeRemaining % 60;
    const formatted = `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;

    if (otpCountdownTimer) {
      otpCountdownTimer.textContent = formatted;
    }

    if (atmState.otpTimeRemaining <= 0) {
      clearInterval(atmState.otpTimerInterval);
      if (otpCountdownTimer) otpCountdownTimer.textContent = "00:00";
      if (otpStatusFeedback) {
        otpStatusFeedback.textContent = "OTP expired. Please click 'RESEND OTP'.";
        otpStatusFeedback.className = "otp-feedback-msg error";
      }
      if (btnVerifyOtp) btnVerifyOtp.disabled = true;
      return;
    }
    atmState.otpTimeRemaining--;
  }

  tick();
  atmState.otpTimerInterval = setInterval(tick, 1000);
}

function startResendCooldown(seconds = 30) {
  clearInterval(atmState.resendTimerInterval);
  atmState.resendCooldownRemaining = seconds;
  if (btnResendOtp) btnResendOtp.disabled = true;

  function tick() {
    if (resendBtnText) {
      resendBtnText.textContent = `RESEND OTP (${atmState.resendCooldownRemaining}s)`;
    }

    if (atmState.resendCooldownRemaining <= 0) {
      clearInterval(atmState.resendTimerInterval);
      if (btnResendOtp) btnResendOtp.disabled = false;
      if (resendBtnText) resendBtnText.textContent = "RESEND OTP";
      return;
    }
    atmState.resendCooldownRemaining--;
  }

  tick();
  atmState.resendTimerInterval = setInterval(tick, 1000);
}

// Handling 6 individual touch boxes
function updateOtpBoxesUI() {
  let allFilled = true;
  let firstEmptyIndex = -1;

  otpBoxes.forEach((box, idx) => {
    const val = atmState.otpInput[idx] || "";
    box.value = val;
    box.classList.remove("error-box");

    if (val) {
      box.classList.add("filled");
    } else {
      box.classList.remove("filled");
      allFilled = false;
      if (firstEmptyIndex === -1) firstEmptyIndex = idx;
    }
  });

  // Active focus ring
  otpBoxes.forEach((box, idx) => {
    if (idx === (firstEmptyIndex === -1 ? 5 : firstEmptyIndex)) {
      box.classList.add("active-box");
    } else {
      box.classList.remove("active-box");
    }
  });

  if (btnVerifyOtp) {
    btnVerifyOtp.disabled = !allFilled;
  }
}

// Handling keypad input directed at OTP screen
function handleOtpKey(key) {
  if (key === "CLEAR") {
    atmState.otpInput = ["", "", "", "", "", ""];
    updateOtpBoxesUI();
    if (otpBoxes[0]) otpBoxes[0].focus();
  } else if (key === "BACKSPACE") {
    // Find last filled box
    for (let i = 5; i >= 0; i--) {
      if (atmState.otpInput[i] !== "") {
        atmState.otpInput[i] = "";
        break;
      }
    }
    updateOtpBoxesUI();
  } else if (/^\d$/.test(key)) {
    // Fill first empty box
    for (let i = 0; i < 6; i++) {
      if (atmState.otpInput[i] === "") {
        atmState.otpInput[i] = key;
        break;
      }
    }
    updateOtpBoxesUI();
  }
}

// Box keyboard & touch interactions
otpBoxes.forEach((box, idx) => {
  box.addEventListener("focus", () => {
    otpBoxes.forEach(b => b.classList.remove("active-box"));
    box.classList.add("active-box");
  });

  box.addEventListener("input", (e) => {
    const val = e.target.value;
    if (/^\d$/.test(val)) {
      atmState.otpInput[idx] = val;
      if (idx < 5) otpBoxes[idx + 1].focus();
    } else {
      atmState.otpInput[idx] = "";
    }
    updateOtpBoxesUI();
  });

  box.addEventListener("keydown", (e) => {
    if (e.key === "Backspace" && !box.value && idx > 0) {
      otpBoxes[idx - 1].focus();
      atmState.otpInput[idx - 1] = "";
      updateOtpBoxesUI();
    }
  });

  // Support pasting full 6-digit OTP
  box.addEventListener("paste", (e) => {
    e.preventDefault();
    const pasteData = (e.clipboardData || window.clipboardData).getData("text").trim();
    if (/^\d{6}$/.test(pasteData)) {
      for (let i = 0; i < 6; i++) {
        atmState.otpInput[i] = pasteData[i];
      }
      updateOtpBoxesUI();
      if (btnVerifyOtp) btnVerifyOtp.disabled = false;
      showATMToast("OTP pasted into boxes.", "info");
    }
  });
});

// ============================================================================
// VERIFY OTP BUTTON ACTION
// ============================================================================
btnVerifyOtp?.addEventListener("click", async () => {
  audio.playKeyBeep();
  const enteredOtp = atmState.otpInput.join("");

  if (enteredOtp.length !== 6) {
    showATMToast("Please enter all 6 digits of the OTP.", "error");
    return;
  }

  btnVerifyOtp.disabled = true;

  try {
    const res = await atmApi("/api/atm/otp/verify", "POST", {
      session_id: atmState.sessionId,
      otp: enteredOtp
    });

    atmState.otpVerified = true;
    atmState.currentStep = "BANK_SELECTION";
    clearInterval(atmState.otpTimerInterval);

    audio.playSuccessChime();
    showATMToast("OTP verified successfully! Loading your linked banks...", "success");

    // Fetch user's linked banks from MongoDB dynamically
    await loadUserLinkedBanks();
    switchScreen("bankSelect");
  } catch (err) {
    // Show error shake and red highlight on OTP boxes
    otpBoxes.forEach(box => box.classList.add("error-box"));
    if (otpStatusFeedback) {
      otpStatusFeedback.textContent = err.message;
      otpStatusFeedback.className = "otp-feedback-msg error";
    }
    showATMToast(err.message, "error");
  } finally {
    btnVerifyOtp.disabled = false;
  }
});

// ============================================================================
// RESEND OTP BUTTON ACTION
// ============================================================================
btnResendOtp?.addEventListener("click", async () => {
  audio.playKeyBeep();
  btnResendOtp.disabled = true;

  try {
    const res = await atmApi("/api/atm/otp/resend", "POST", {
      session_id: atmState.sessionId
    });

    atmState.demoOtp = res.demo_otp;

    // Reset OTP boxes
    atmState.otpInput = ["", "", "", "", "", ""];
    updateOtpBoxesUI();
    if (otpBoxes[0]) otpBoxes[0].focus();

    // Reset 5-minute timer & start 30s cooldown
    startOtpCountdown(300);
    startResendCooldown(30);

    if (otpStatusFeedback) {
      otpStatusFeedback.textContent = "New OTP sent to your ATM App. Please check your app.";
      otpStatusFeedback.className = "otp-feedback-msg success";
    }
    showATMToast("New OTP dispatched to your ATM App. Resend available in 30 seconds.", "info");
  } catch (err) {
    showATMToast(err.message, "error");
    btnResendOtp.disabled = false;
  }
});

btnOtpCancel?.addEventListener("click", () => resetToHome());


// ============================================================================
// STEP 6: SELECT BANK SCREEN (FETCH DYNAMICALLY FROM MONGODB)
// ============================================================================
const atmBanksGrid = document.getElementById("atm-banks-grid");
const bankSelectUserName = document.getElementById("bank-select-user-name");
const btnBankSelectCancel = document.getElementById("btn-bank-select-cancel");

async function loadUserLinkedBanks() {
  if (bankSelectUserName) bankSelectUserName.textContent = atmState.userName;

  // Retrieve user's linked banks directly from MongoDB
  const banks = await atmApi(`/api/atm/session/${atmState.sessionId}/banks`);
  atmState.linkedBanks = banks;
  renderBanksList(banks);
}

function renderBanksList(banks) {
  if (!atmBanksGrid) return;
  atmBanksGrid.innerHTML = "";

  banks.forEach((bank, idx) => {
    const card = document.createElement("div");
    card.className = "atm-bank-card";
    card.style.background = bank.theme_gradient || "linear-gradient(135deg, #1e3a8a, #3b82f6)";

    card.innerHTML = `
      <div class="bc-top">
        <span class="bc-name">${bank.bank_name}</span>
        <span class="bc-badge">${bank.status || "Verified"}</span>
      </div>
      <div class="bc-middle">
        <span>${bank.account_masked}</span>
      </div>
      <div class="bc-bottom">
        <div>
          <div class="bc-limit-label">DAILY WITHDRAWAL LIMIT</div>
          <div class="bc-limit-val">${bank.currency || "₹"}${Number(bank.withdrawal_limit).toLocaleString("en-IN")}</div>
        </div>
        <div class="bc-tap-label">TAP TO SELECT &rarr;</div>
      </div>
    `;

    card.addEventListener("click", () => {
      audio.playKeyBeep();
      atmState.selectedBank = bank;
      selectBankAndProceed(bank);
    });

    atmBanksGrid.appendChild(card);
  });
}

function selectBankAndProceed(bank) {
  const bankDisplayName = document.getElementById("selected-bank-display-name");
  if (bankDisplayName) bankDisplayName.textContent = `${bank.bank_name} (${bank.account_masked})`;

  atmState.bankPinInput = "";
  updateBankPinSlots();
  switchScreen("bankPin");
  showATMToast(`Selected ${bank.bank_name}. Enter 4-digit bank PIN.`, "info");
}

btnBankSelectCancel?.addEventListener("click", () => resetToHome());


// ============================================================================
// STEP 7: ENTER DEMO BANK PIN SCREEN
// ============================================================================
const bankPinSlots = document.querySelectorAll("#bank-pin-slots .pin-slot");
const btnBankPinNext = document.getElementById("btn-bank-pin-next");
const btnBankPinCancel = document.getElementById("btn-bank-pin-cancel");

function handleBankPinKey(key) {
  if (key === "CLEAR") {
    atmState.bankPinInput = "";
  } else if (key === "BACKSPACE") {
    atmState.bankPinInput = atmState.bankPinInput.slice(0, -1);
  } else if (/^\d$/.test(key)) {
    if (atmState.bankPinInput.length < 4) {
      atmState.bankPinInput += key;
    }
  }
  updateBankPinSlots();
}

function updateBankPinSlots() {
  const len = atmState.bankPinInput.length;
  bankPinSlots.forEach((slot, idx) => {
    if (idx < len) {
      slot.classList.add("filled");
      slot.classList.remove("active-focus");
    } else if (idx === len) {
      slot.classList.remove("filled");
      slot.classList.add("active-focus");
    } else {
      slot.classList.remove("filled", "active-focus");
    }
  });

  if (btnBankPinNext) {
    btnBankPinNext.disabled = len !== 4;
  }
}

btnBankPinNext?.addEventListener("click", () => {
  audio.playKeyBeep();
  if (atmState.bankPinInput.length === 4) {
    // Setup Screen 8: Amount
    setupAmountScreen();
    switchScreen("amount");
  }
});

btnBankPinCancel?.addEventListener("click", () => resetToHome());


// ============================================================================
// STEP 8: WITHDRAWAL AMOUNT SCREEN
// ============================================================================
const displayCustomAmount = document.getElementById("display-custom-amount");
const amountErrorMsg = document.getElementById("amount-error-msg");
const amountBankSummary = document.getElementById("amount-bank-summary");
const amountLimitSummary = document.getElementById("amount-limit-summary");
const btnAmountNext = document.getElementById("btn-amount-next");
const btnAmountCancel = document.getElementById("btn-amount-cancel");

function setupAmountScreen() {
  const bank = atmState.selectedBank;
  if (amountBankSummary && bank) {
    amountBankSummary.textContent = `${bank.bank_name} (${bank.account_masked})`;
  }
  if (amountLimitSummary && bank) {
    amountLimitSummary.textContent = `${bank.currency || "₹"}${Number(bank.withdrawal_limit).toLocaleString("en-IN")}`;
  }

  atmState.selectedAmount = 0;
  atmState.customAmountInput = "";
  if (displayCustomAmount) displayCustomAmount.textContent = "0";

  document.querySelectorAll(".btn-fast-cash").forEach(btn => btn.classList.remove("selected"));
  if (btnAmountNext) btnAmountNext.disabled = true;
}

// Fast Cash Buttons
document.querySelectorAll(".btn-fast-cash").forEach(btn => {
  btn.addEventListener("click", () => {
    audio.playKeyBeep();
    document.querySelectorAll(".btn-fast-cash").forEach(b => b.classList.remove("selected"));
    btn.classList.add("selected");

    const amt = parseInt(btn.getAttribute("data-amount"), 10);
    atmState.selectedAmount = amt;
    atmState.customAmountInput = String(amt);
    if (displayCustomAmount) displayCustomAmount.textContent = amt.toLocaleString("en-IN");

    validateAmount(amt);
  });
});

function handleAmountKey(key) {
  document.querySelectorAll(".btn-fast-cash").forEach(b => b.classList.remove("selected"));

  if (key === "CLEAR") {
    atmState.customAmountInput = "";
  } else if (key === "BACKSPACE") {
    atmState.customAmountInput = atmState.customAmountInput.slice(0, -1);
  } else if (/^\d$/.test(key)) {
    if (atmState.customAmountInput.length < 6) {
      atmState.customAmountInput += key;
    }
  }

  const amt = parseInt(atmState.customAmountInput, 10) || 0;
  atmState.selectedAmount = amt;
  if (displayCustomAmount) displayCustomAmount.textContent = amt.toLocaleString("en-IN");
  validateAmount(amt);
}

function validateAmount(amt) {
  const limit = atmState.selectedBank ? atmState.selectedBank.withdrawal_limit : 40000;

  if (amt <= 0) {
    amountErrorMsg.textContent = "Please select or enter an amount";
    amountErrorMsg.style.color = "var(--text-muted)";
    btnAmountNext.disabled = true;
  } else if (amt % 100 !== 0) {
    amountErrorMsg.textContent = "Amount must be in multiples of ₹100";
    amountErrorMsg.style.color = "var(--accent-rose)";
    btnAmountNext.disabled = true;
  } else if (amt > limit) {
    amountErrorMsg.textContent = `Amount exceeds daily limit of ₹${limit.toLocaleString("en-IN")}`;
    amountErrorMsg.style.color = "var(--accent-rose)";
    btnAmountNext.disabled = true;
  } else {
    amountErrorMsg.textContent = `Valid amount: ₹${amt.toLocaleString("en-IN")}`;
    amountErrorMsg.style.color = "var(--accent-emerald)";
    btnAmountNext.disabled = false;
  }
}

btnAmountNext?.addEventListener("click", () => {
  audio.playKeyBeep();
  if (atmState.selectedAmount > 0) {
    setupConfirmScreen();
    switchScreen("confirm");
  }
});

btnAmountCancel?.addEventListener("click", () => resetToHome());


// ============================================================================
// STEP 9: CONFIRM WITHDRAWAL SCREEN
// ============================================================================
const rcCustomerName = document.getElementById("rc-customer-name");
const rcBankName = document.getElementById("rc-bank-name");
const rcBankAcc = document.getElementById("rc-bank-acc");
const rcTotalAmount = document.getElementById("rc-total-amount");
const btnConfirmDispense = document.getElementById("btn-confirm-dispense");
const btnConfirmCancel = document.getElementById("btn-confirm-cancel");

function setupConfirmScreen() {
  if (rcCustomerName) rcCustomerName.textContent = atmState.userName;
  if (rcBankName && atmState.selectedBank) rcBankName.textContent = atmState.selectedBank.bank_name;
  if (rcBankAcc && atmState.selectedBank) rcBankAcc.textContent = atmState.selectedBank.account_masked;
  if (rcTotalAmount) rcTotalAmount.textContent = `₹${atmState.selectedAmount.toLocaleString("en-IN")}.00`;
}

btnConfirmDispense?.addEventListener("click", async () => {
  audio.playKeyBeep();
  btnConfirmDispense.disabled = true;

  try {
    const res = await atmApi("/api/atm/session/withdraw", "POST", {
      session_id: atmState.sessionId,
      bank_id: atmState.selectedBank.id,
      bank_pin: atmState.bankPinInput,
      amount: atmState.selectedAmount
    });

    audio.playSuccessChime();

    // Setup Screen 10: Success
    const sdTxnId = document.getElementById("sd-txn-id");
    const sdAmount = document.getElementById("sd-amount");
    const sdBank = document.getElementById("sd-bank");
    const sdTimestamp = document.getElementById("sd-timestamp");

    if (sdTxnId) sdTxnId.textContent = res.transaction_id;
    if (sdAmount) sdAmount.textContent = `₹${res.amount.toLocaleString("en-IN")}.00`;
    if (sdBank) sdBank.textContent = `${res.bank_name} (${res.account_masked})`;
    if (sdTimestamp) sdTimestamp.textContent = new Date(res.timestamp).toLocaleString("en-IN");

    switchScreen("success");
    showATMToast("Cash dispensed successfully! Please take your cash.", "success", 7000);
  } catch (err) {
    showATMToast(err.message, "error");
    btnConfirmDispense.disabled = false;
  }
});

btnConfirmCancel?.addEventListener("click", () => resetToHome());


// ============================================================================
// STEP 10: SUCCESS & RECEIPT
// ============================================================================
const btnPrintReceipt = document.getElementById("btn-print-receipt");
const btnNewTransaction = document.getElementById("btn-new-transaction");

btnPrintReceipt?.addEventListener("click", () => {
  audio.playKeyBeep();
  showATMToast("🖨️ Printing thermal receipt...", "info");
  setTimeout(() => {
    window.print();
  }, 300);
});

btnNewTransaction?.addEventListener("click", () => {
  audio.playKeyBeep();
  resetToHome();
});


// ============================================================================
// RESET SESSION HELPER
// ============================================================================
function resetToHome() {
  clearInterval(atmState.otpTimerInterval);
  clearInterval(atmState.resendTimerInterval);

  if (atmState.sessionId) {
    // Notify backend
    atmApi("/api/atm/session/cancel", "POST", { session_id: atmState.sessionId }).catch(() => {});
  }

  atmState.sessionId = null;
  atmState.userId = null;
  atmState.userName = "Customer";
  atmState.maskedMobile = null;
  atmState.currentStep = "HOME";
  atmState.otpVerified = false;
  atmState.demoOtp = null;
  atmState.linkedBanks = [];
  atmState.selectedBank = null;
  atmState.selectedAmount = 0;
  atmState.mobileInput = "";
  atmState.pinInput = "";
  atmState.otpInput = ["", "", "", "", "", ""];
  atmState.bankPinInput = "";
  atmState.customAmountInput = "";
  atmState.activeKeypadTarget = null;

  switchScreen("home");
}

// ============================================================================
// INITIALIZATION ON LOAD
// ============================================================================
window.addEventListener("DOMContentLoaded", () => {
  initKioskClock();
  switchScreen("home");
});
