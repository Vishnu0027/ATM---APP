/**
 * MULTI-BANK CARDLESS ATM — CLIENT ENGINE
 * Handles SPA navigation, real-time validations, API communication,
 * password strength metering, and dashboard rendering.
 */

// ============================================================================
// CONFIGURATION & STATE
// ============================================================================
const API_BASE = ""; // Relative path to FastAPI backend
const STORAGE_TOKEN_KEY = "atm_auth_token";
const STORAGE_USER_KEY = "atm_auth_user";

const state = {
  token: localStorage.getItem(STORAGE_TOKEN_KEY) || null,
  user: null,
  dashboardData: null
};

// ============================================================================
// DOM ELEMENTS
// ============================================================================
const authSection = document.getElementById("auth-section");
const dashboardSection = document.getElementById("dashboard-section");
const loginView = document.getElementById("login-view");
const registerView = document.getElementById("register-view");

const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");

const loginAlert = document.getElementById("login-alert");
const registerAlert = document.getElementById("register-alert");

const toastContainer = document.getElementById("toast-container");
const appModal = document.getElementById("app-modal");
const modalTitle = document.getElementById("modal-title");
const modalBody = document.getElementById("modal-body");
const modalCloseBtn = document.getElementById("modal-close-btn");
const modalConfirmBtn = document.getElementById("modal-confirm-btn");

// ============================================================================
// TOAST & MODAL HELPERS
// ============================================================================
function showToast(message, type = "info", duration = 4000) {
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;

  const icon = type === "success" 
    ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>`
    : type === "error"
    ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`
    : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;

  toast.innerHTML = `<span>${icon}</span><div>${message}</div>`;
  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = "fadeOutRight 0.3s ease forwards";
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

function openModal(title, messageHtml) {
  modalTitle.textContent = title;
  modalBody.innerHTML = messageHtml;
  appModal.classList.remove("hidden");
}

function closeModal() {
  appModal.classList.add("hidden");
}

modalCloseBtn.addEventListener("click", closeModal);
modalConfirmBtn.addEventListener("click", closeModal);
appModal.addEventListener("click", (e) => {
  if (e.target === appModal) closeModal();
});

// ============================================================================
// API CLIENT
// ============================================================================
async function apiRequest(endpoint, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {})
  };

  if (state.token) {
    headers["Authorization"] = `Bearer ${state.token}`;
  }

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers
    });

    const text = await response.text();
    let data = {};
    try {
      data = JSON.parse(text);
    } catch (_) {
      data = { detail: text };
    }

    if (!response.ok) {
      const errorMsg = data.detail || (Array.isArray(data) ? data[0]?.msg : null) || `Server error (${response.status}): ${response.statusText}`;
      throw new Error(errorMsg);
    }

    return data;
  } catch (err) {
    throw err;
  }
}

// ============================================================================
// AUTH NAVIGATION & VIEW SWITCHING & INPUT CLEARING
// ============================================================================
function clearAuthInputs() {
  const inputIds = [
    "login-username", "login-email", "login-mobile", "login-password",
    "reg-name", "reg-email", "reg-mobile", "reg-password", "reg-confirm-password"
  ];
  inputIds.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = "";
  });
  loginForm?.reset();
  registerForm?.reset();
}

function showLoginView() {
  stopOtpPolling();
  hideActiveOtp();
  loginView.classList.add("active-view");
  registerView.classList.remove("active-view");
  authSection.classList.remove("hidden");
  dashboardSection.classList.add("hidden");
  clearAlerts();
  clearAuthInputs();
}

function showRegisterView() {
  stopOtpPolling();
  hideActiveOtp();
  registerView.classList.add("active-view");
  loginView.classList.remove("active-view");
  authSection.classList.remove("hidden");
  dashboardSection.classList.add("hidden");
  clearAlerts();
  clearAuthInputs();
}

function showDashboardView() {
  authSection.classList.add("hidden");
  dashboardSection.classList.remove("hidden");
  startOtpPolling();
}

function clearAlerts() {
  loginAlert.classList.add("hidden");
  loginAlert.textContent = "";
  registerAlert.classList.add("hidden");
  registerAlert.textContent = "";
}

// Switch button events
document.getElementById("switch-to-register")?.addEventListener("click", showRegisterView);
document.getElementById("switch-to-login")?.addEventListener("click", showLoginView);

// ============================================================================
// PASSWORD TOGGLE VISIBILITY
// ============================================================================
document.querySelectorAll(".password-toggle-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const targetId = btn.getAttribute("data-target");
    const input = document.getElementById(targetId);
    if (!input) return;

    const eyeOpen = btn.querySelector(".eye-open");
    const eyeClosed = btn.querySelector(".eye-closed");

    if (input.type === "password") {
      input.type = "text";
      eyeOpen?.classList.add("hidden");
      eyeClosed?.classList.remove("hidden");
    } else {
      input.type = "password";
      eyeOpen?.classList.remove("hidden");
      eyeClosed?.classList.add("hidden");
    }
  });
});

// ============================================================================
// NUMERIC-ONLY PIN RESTRICTIONS & HELPERS
// ============================================================================
function setupNumericPinInputs() {
  const pinInputs = document.querySelectorAll(".pin-input");
  pinInputs.forEach(input => {
    // Prevent typing any character or symbol (allow only 0-9 and navigation keys)
    input.addEventListener("keydown", (e) => {
      const allowed = ["Backspace", "Tab", "Delete", "ArrowLeft", "ArrowRight", "Enter", "Escape"];
      if (allowed.includes(e.key)) return;
      if (e.ctrlKey || e.metaKey) return;
      if (!/^\d$/.test(e.key)) {
        e.preventDefault();
      }
    });

    // Strip any non-digits immediately
    input.addEventListener("input", (e) => {
      e.target.value = e.target.value.replace(/\D/g, "");
    });

    // Strip non-digits on paste
    input.addEventListener("paste", (e) => {
      e.preventDefault();
      const text = (e.clipboardData || window.clipboardData).getData("text") || "";
      const digitsOnly = text.replace(/\D/g, "").slice(0, 6);
      e.target.value = digitsOnly;
    });
  });
}

document.getElementById("forgot-password-btn")?.addEventListener("click", () => {
  openModal(
    "PIN Assistance",
    `<p>PIN reset is managed securely via registered phone verification or branch assistance.</p>
     <br>
     <p><strong>Security Tip:</strong> Never share your 4 to 6 digit PIN with anyone.</p>`
  );
});

document.getElementById("terms-link")?.addEventListener("click", (e) => {
  e.preventDefault();
  openModal(
    "Terms & Conditions",
    `<p><strong>Multi-Bank Cardless ATM — Prototype Terms:</strong></p>
     <br>
     <p>1. This software is an experimental prototype demonstrating cardless multi-banking terminal workflows.</p>
     <p>2. All account numbers, limits, and bank identities (SBI, Canara Bank, KVB) are simulated.</p>
     <p>3. Real debit cards, bank credentials, and live banking PINs are strictly prohibited.</p>`
  );
});

// ============================================================================
// REGISTRATION FORM SUBMISSION & VALIDATION
// ============================================================================
registerForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearAlerts();

  const fullName = document.getElementById("reg-name").value.trim();
  const emailInput = document.getElementById("reg-email");
  const email = emailInput ? emailInput.value.trim() : "";
  const mobile = document.getElementById("reg-mobile").value.trim();
  const password = document.getElementById("reg-password").value.trim();
  const confirmPassword = document.getElementById("reg-confirm-password").value.trim();
  const termsAccepted = document.getElementById("reg-terms").checked;

  let hasError = false;

  // Clear field errors
  document.getElementById("reg-name-error").textContent = "";
  const regEmailErrorEl = document.getElementById("reg-email-error");
  if (regEmailErrorEl) regEmailErrorEl.textContent = "";
  document.getElementById("reg-mobile-error").textContent = "";
  document.getElementById("reg-password-error").textContent = "";
  document.getElementById("reg-confirm-password-error").textContent = "";
  document.getElementById("reg-terms-error").textContent = "";

  if (fullName.length < 2) {
    document.getElementById("reg-name-error").textContent = "User name must be at least 2 characters.";
    hasError = true;
  }

  // Validate email (required)
  if (!email) {
    if (regEmailErrorEl) regEmailErrorEl.textContent = "Please enter your email address.";
    hasError = true;
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    if (regEmailErrorEl) regEmailErrorEl.textContent = "Please enter a valid email address.";
    hasError = true;
  }

  // Indian mobile: 10 digits starting with 6,7,8,9
  const indianMobileRegex = /^[6-9]\d{9}$/;
  if (!indianMobileRegex.test(mobile)) {
    document.getElementById("reg-mobile-error").textContent = "Enter a valid 10-digit Indian phone number (e.g. 9876543210).";
    hasError = true;
  }

  // PIN: 4 to 6 numeric digits only
  if (!/^\d{4,6}$/.test(password)) {
    document.getElementById("reg-password-error").textContent = "PIN must be 4 to 6 numbers only. No letters or symbols allowed.";
    hasError = true;
  }

  if (password !== confirmPassword) {
    document.getElementById("reg-confirm-password-error").textContent = "PINs do not match.";
    hasError = true;
  }

  if (!termsAccepted) {
    document.getElementById("reg-terms-error").textContent = "You must accept the terms and conditions.";
    hasError = true;
  }

  if (hasError) return;

  // Submit to backend
  const submitBtn = document.getElementById("register-submit-btn");
  const btnText = submitBtn.querySelector(".btn-text");
  const btnSpinner = submitBtn.querySelector(".btn-spinner");

  try {
    submitBtn.disabled = true;
    btnText.textContent = "Creating Account...";
    btnSpinner.classList.remove("hidden");

    const regPayload = {
      full_name: fullName,
      email,
      mobile,
      password,
      confirm_password: confirmPassword,
      terms_accepted: true
    };

    await apiRequest("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(regPayload)
    });

    showToast("Registration successful! Please log in with your phone number and PIN.", "success");
    registerForm.reset();

    // Switch to login view
    showLoginView();
    loginForm.reset();
    document.getElementById("login-username")?.focus();

  } catch (err) {
    registerAlert.textContent = err.message;
    registerAlert.classList.remove("hidden");
    showToast(err.message, "error");
  } finally {
    submitBtn.disabled = false;
    btnText.textContent = "Create Account \u2192";
    btnSpinner.classList.add("hidden");
  }
});

// ============================================================================
// LOGIN FORM SUBMISSION
// ============================================================================
loginForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearAlerts();

  const usernameInput = document.getElementById("login-username");
  const emailInput = document.getElementById("login-email");
  const mobileInput = document.getElementById("login-mobile");
  const passwordInput = document.getElementById("login-password");

  const userName = usernameInput ? usernameInput.value.trim() : "";
  const email = emailInput ? emailInput.value.trim() : "";
  const mobile = mobileInput ? mobileInput.value.trim() : "";
  const password = passwordInput ? passwordInput.value.trim() : "";

  let hasError = false;
  const usernameErrorEl = document.getElementById("login-username-error");
  const emailErrorEl = document.getElementById("login-email-error");
  const mobileErrorEl = document.getElementById("login-mobile-error");
  const passwordErrorEl = document.getElementById("login-password-error");

  if (usernameErrorEl) usernameErrorEl.textContent = "";
  if (emailErrorEl) emailErrorEl.textContent = "";
  if (mobileErrorEl) mobileErrorEl.textContent = "";
  if (passwordErrorEl) passwordErrorEl.textContent = "";

  if (!userName && !email && !mobile) {
    if (usernameErrorEl) usernameErrorEl.textContent = "Please enter your User Name, Email, or Phone Number.";
    hasError = true;
  }

  if (!password) {
    if (passwordErrorEl) passwordErrorEl.textContent = "Please enter your PIN.";
    hasError = true;
  }

  if (hasError) return;

  const submitBtn = document.getElementById("login-submit-btn");
  const btnText = submitBtn.querySelector(".btn-text");
  const btnSpinner = submitBtn.querySelector(".btn-spinner");

  try {
    submitBtn.disabled = true;
    btnText.textContent = "Authenticating...";
    btnSpinner.classList.remove("hidden");

    const payload = {
      password
    };
    if (userName) payload.user_name = userName;
    if (email) payload.email = email;
    if (mobile) payload.mobile = mobile;
    payload.identifier = email || mobile || userName;

    const result = await apiRequest("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    state.token = result.access_token;
    state.user = result.user;
    localStorage.setItem(STORAGE_TOKEN_KEY, state.token);
    localStorage.setItem(STORAGE_USER_KEY, JSON.stringify(state.user));

    showToast(`Welcome back, ${state.user.full_name}!`, "success");

    await loadDashboard();

  } catch (err) {
    loginAlert.textContent = err.message || "Invalid credentials. Please verify your details and PIN.";
    loginAlert.classList.remove("hidden");
    showToast("Login failed. Check your details and PIN.", "error");
  } finally {
    submitBtn.disabled = false;
    btnText.textContent = "Sign In to ATM \u2192";
    btnSpinner.classList.add("hidden");
  }
});

// ============================================================================
// DASHBOARD DATA LOADER & RENDERER
// ============================================================================
async function loadDashboard() {
  try {
    const summary = await apiRequest("/api/dashboard/summary");
    state.dashboardData = summary;
    state.user = summary.user;

    renderDashboard(summary);
    showDashboardView();
  } catch (err) {
    showToast("Session expired or invalid. Please sign in again.", "error");
    logoutUser();
  }
}

function renderDashboard(data) {
  const user = data.user;
  const firstName = user.full_name.split(" ")[0];
  const initials = user.full_name.split(" ").map(n => n[0]).join("").slice(0, 2).toUpperCase();

  // Welcome Greeting
  const greetingEl = document.getElementById("dash-greeting");
  if (greetingEl) {
    greetingEl.textContent = `Welcome back, ${firstName}`;
  }

  // Header user info
  const headerUserDisplay = document.getElementById("header-user-name");
  const headerAvatar = document.getElementById("header-user-avatar");
  if (headerUserDisplay) headerUserDisplay.textContent = firstName;
  if (headerAvatar) headerAvatar.textContent = initials;

  // Sidebar user info
  const sidebarUserName = document.getElementById("sidebar-user-name");
  const sidebarUserEmail = document.getElementById("sidebar-user-email");
  const sidebarAvatar = document.getElementById("sidebar-user-avatar");
  if (sidebarUserName) sidebarUserName.textContent = user.full_name;
  if (sidebarUserEmail) sidebarUserEmail.textContent = user.email;
  if (sidebarAvatar) sidebarAvatar.textContent = initials;

  // Summary Stat Cards
  document.getElementById("stat-linked-banks").textContent = data.linked_banks_count;
  document.getElementById("stat-active-accounts").textContent = data.active_accounts_count;
  document.getElementById("stat-today-txns").textContent = data.today_transactions_count;
  document.getElementById("stat-security-status").textContent = data.security_status;

  // Render My Banks Grid
  renderBankCards(data.banks);
}

function renderBankCards(banks) {
  const container = document.getElementById("banks-grid");
  if (!container) return;

  if (!banks || banks.length === 0) {
    container.innerHTML = `<p class="empty-desc">No linked banks found.</p>`;
    return;
  }

  container.innerHTML = banks.map(bank => {
    return `
      <div class="bank-card" style="background: ${bank.theme_gradient};" data-bank-code="${bank.bank_code}">
        <div class="card-top-row">
          <div class="bank-badge-title">
            <span class="card-bank-name">${bank.bank_name}</span>
            <div class="card-status-badge">
              <span class="status-dot"></span>
              <span>${bank.status}</span>
            </div>
          </div>
          <div class="card-contactless-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M8.5 16.5a5 5 0 0 1 0-9"></path>
              <path d="M12 19a8.5 8.5 0 0 0 0-14"></path>
              <path d="M15.5 21.5a12 12 0 0 0 0-19"></path>
            </svg>
          </div>
        </div>

        <div class="card-mid-row">
          <div class="emv-chip" title="EMV Smart Chip"></div>
        </div>

        <div class="card-bottom-row">
          <span class="card-account-number">${bank.account_masked}</span>
          <span class="card-prototype-tag">DEMO CARD</span>
        </div>
      </div>
    `;
  }).join("");
}

// ============================================================================
// "+ ADD BANK" & PLACEHOLDER INTERACTIONS
// ============================================================================
document.getElementById("add-bank-btn")?.addEventListener("click", () => {
  openModal(
    "Add Bank Account",
    `<div style="text-align: center; padding: 10px 0;">
       <div style="width: 56px; height: 56px; margin: 0 auto 16px; background: rgba(6, 182, 212, 0.12); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: var(--accent-cyan);">
         <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
           <path d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 14v4M12 14v4M16 14v4"></path>
         </svg>
       </div>
       <h4 style="font-size: 1.1rem; color: #fff; margin-bottom: 8px;">Bank linking feature will be available in the next version.</h4>
       <p style="font-size: 0.88rem; color: var(--text-secondary); line-height: 1.5;">
         In Version 2, you will be able to link your real and test net-banking accounts using secure instant tokenization.
       </p>
     </div>`
  );
});

// Navigation item clicks (Coming Soon notices)
document.querySelectorAll(".nav-link-future").forEach(btn => {
  btn.addEventListener("click", () => {
    const featureName = btn.getAttribute("data-feature") || "Feature";
    openModal(
      `${featureName} Module`,
      `<p>The <strong>${featureName}</strong> module is currently scheduled for development in Version 2.</p>
       <br>
       <p>Version 1 focuses on core user authentication and dashboard overview.</p>`
    );
  });
});

document.getElementById("nav-my-banks")?.addEventListener("click", () => {
  const section = document.getElementById("section-my-banks");
  if (section) {
    section.scrollIntoView({ behavior: "smooth" });
  }
});

// ============================================================================
// REAL-TIME ATM 2FA OTP NOTIFICATION POLLING
// ============================================================================
let otpPollInterval = null;
let currentOtpRemaining = 0;
let otpLocalCountdownInterval = null;

const atmOtpNotification = document.getElementById("atm-otp-notification");
const notifAtmId = document.getElementById("notif-atm-id");
const notifTimer = document.getElementById("notif-timer");
const notifOtpCode = document.getElementById("notif-otp-code");
const btnCopyOtp = document.getElementById("btn-copy-otp");
const copyBtnText = document.getElementById("copy-btn-text");

function startOtpPolling() {
  stopOtpPolling();
  checkActiveOtp();
  otpPollInterval = setInterval(checkActiveOtp, 3000);
}

function stopOtpPolling() {
  if (otpPollInterval) {
    clearInterval(otpPollInterval);
    otpPollInterval = null;
  }
  if (otpLocalCountdownInterval) {
    clearInterval(otpLocalCountdownInterval);
    otpLocalCountdownInterval = null;
  }
}

async function checkActiveOtp() {
  if (!state.token) {
    stopOtpPolling();
    return;
  }

  try {
    const res = await apiRequest("/api/dashboard/active-otp");
    if (res && res.has_active_otp && res.otp) {
      displayActiveOtp(res.otp);
    } else {
      hideActiveOtp();
    }
  } catch (_) {
    // Polling error silently suppressed to avoid interrupting UI
  }
}

function displayActiveOtp(otpData) {
  if (!atmOtpNotification) return;

  if (notifAtmId) notifAtmId.textContent = otpData.atm_id || "ATM-BLR-042";
  if (notifOtpCode) notifOtpCode.textContent = otpData.otp_code || "------";

  const wasHidden = atmOtpNotification.classList.contains("hidden");
  atmOtpNotification.classList.remove("hidden");

  if (wasHidden) {
    showToast(`🔔 New ATM OTP received: ${otpData.otp_code} (from ${otpData.atm_id})`, "info", 5000);
  }

  // Synchronize local 1-second countdown
  currentOtpRemaining = otpData.expires_in_seconds;
  clearInterval(otpLocalCountdownInterval);

  function updateTimer() {
    if (currentOtpRemaining <= 0) {
      if (notifTimer) notifTimer.textContent = "00:00";
      clearInterval(otpLocalCountdownInterval);
      return;
    }
    const mins = Math.floor(currentOtpRemaining / 60);
    const secs = currentOtpRemaining % 60;
    if (notifTimer) {
      notifTimer.textContent = `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
    }
    currentOtpRemaining--;
  }

  updateTimer();
  otpLocalCountdownInterval = setInterval(updateTimer, 1000);
}

function hideActiveOtp() {
  if (atmOtpNotification && !atmOtpNotification.classList.contains("hidden")) {
    atmOtpNotification.classList.add("hidden");
  }
  clearInterval(otpLocalCountdownInterval);
}

btnCopyOtp?.addEventListener("click", () => {
  const code = notifOtpCode?.textContent?.trim();
  if (code && code !== "------") {
    navigator.clipboard.writeText(code).then(() => {
      if (copyBtnText) copyBtnText.textContent = "Copied!";
      showToast("OTP copied to clipboard!", "success", 2500);
      setTimeout(() => {
        if (copyBtnText) copyBtnText.textContent = "Copy";
      }, 2000);
    }).catch(() => {
      showToast(`OTP Code: ${code}`, "info");
    });
  }
});

// ============================================================================
// LOGOUT FUNCTIONALITY
// ============================================================================
async function logoutUser() {
  stopOtpPolling();
  hideActiveOtp();
  if (state.token) {
    try {
      await apiRequest("/api/auth/logout", { method: "POST" });
    } catch (_) {}
  }

  state.token = null;
  state.user = null;
  state.dashboardData = null;
  localStorage.removeItem(STORAGE_TOKEN_KEY);
  localStorage.removeItem(STORAGE_USER_KEY);

  showToast("Logged out successfully.", "info");
  showLoginView();
}

document.getElementById("sidebar-logout-btn")?.addEventListener("click", logoutUser);
document.getElementById("top-logout-btn")?.addEventListener("click", logoutUser);

// ============================================================================
// EDIT EMAIL IN DASHBOARD
// ============================================================================
document.getElementById("sidebar-edit-email-btn")?.addEventListener("click", async () => {
  const currentEmail = state.user?.email || "";
  const newEmail = prompt("Enter your email address:", currentEmail);
  if (!newEmail || newEmail.trim() === "" || newEmail.trim().toLowerCase() === currentEmail.toLowerCase()) {
    return;
  }
  const cleanEmail = newEmail.trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail)) {
    showToast("Please enter a valid email address.", "error");
    return;
  }

  try {
    const updatedUser = await apiRequest("/api/auth/update-email", {
      method: "POST",
      body: JSON.stringify({ email: cleanEmail })
    });
    state.user = updatedUser;
    localStorage.setItem(STORAGE_USER_KEY, JSON.stringify(updatedUser));
    const sidebarUserEmail = document.getElementById("sidebar-user-email");
    if (sidebarUserEmail) sidebarUserEmail.textContent = updatedUser.email;
    showToast("Email address updated successfully!", "success");
  } catch (err) {
    showToast(err.message || "Failed to update email address.", "error");
  }
});

// ============================================================================
// MOBILE DRAWER NAVIGATION
// ============================================================================
const mobileMenuToggle = document.getElementById("mobile-menu-toggle");
const sidebar = document.getElementById("sidebar");
const sidebarCloseBtn = document.getElementById("sidebar-close-btn");

mobileMenuToggle?.addEventListener("click", () => {
  sidebar?.classList.add("open");
});

sidebarCloseBtn?.addEventListener("click", () => {
  sidebar?.classList.remove("open");
});

// ============================================================================
// INITIALIZATION ON PAGE LOAD
// ============================================================================
clearAuthInputs();
setupNumericPinInputs();

window.addEventListener("DOMContentLoaded", async () => {
  setupNumericPinInputs();
  clearAuthInputs();
  setTimeout(clearAuthInputs, 50);
  setTimeout(clearAuthInputs, 200);

  if (state.token) {
    try {
      await loadDashboard();
    } catch (e) {
      showLoginView();
    }
  } else {
    showLoginView();
  }
});

window.addEventListener("pageshow", () => {
  clearAuthInputs();
  setTimeout(clearAuthInputs, 100);
});

