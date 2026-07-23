const analyzeBtn = document.getElementById("analyzeBtn");

let progressPollingTimer = null;
let latestAnalysisResult = null;
let currentJobId = null;
let isAnalysisRunning = false;

// Read the MusicAI configuration data rendered by Flask.
const configElement = document.getElementById("musicAiConfig");
const MUSIC_AI_CONFIG = configElement ? JSON.parse(configElement.textContent || "{}") : {};
const URLS = MUSIC_AI_CONFIG.urls || {};
const I18N = MUSIC_AI_CONFIG.i18n || {};

const startAnalyzeUrl = URLS.startAnalysis || "";
const progressUrlTemplate = URLS.progress || "";
const cancelAnalysisUrlTemplate = URLS.cancel || "";

// Replaces placeholders such as {count} in translated text.
function i18nTemplate(template, values) {
  return String(template || "").replace(/\{(\w+)\}/g, function (match, key) {
    return values && values[key] !== undefined ? values[key] : match;
  });
}

// Converts a stored file name into a user-friendly display name.
// Example: 03_The_Dark_Protector.mp3 → The Dark Protector.mp3
function formatDisplayFileName(fileName) {
  const name = String(fileName || "").split(/[\\/]/).pop();
  const dotIndex = name.lastIndexOf(".");
  const extension = dotIndex >= 0 ? name.slice(dotIndex) : "";
  const stem = dotIndex >= 0 ? name.slice(0, dotIndex) : name;
  const cleanStem = stem.replace(/^\d+[\s._-]+/, "").replace(/_+/g, " ").trim();

  return cleanStem + extension;
}

// Escapes HTML special characters before inserting text into HTML.
function escapeHTML(text) {
  if (text === null || text === undefined) return "";

  return String(text).replace(/[&<>"']/g, function (char) {
    return {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;"
    }[char];
  });
}

/* =========================
   Sidebar Active Section
   Updates the active sidebar item based on the current section.
========================= */

const sidebarLinks = Array.from(document.querySelectorAll('.t-nav-list a[href*="#cat-"]'));

// Extracts the target section ID from a sidebar link.
function getSidebarTargetId(link) {
  if (!link) return "";

  const href = link.getAttribute("href") || "";
  if (!href || href === "#") return "";

  try {
    const url = new URL(href, window.location.href);
    return url.hash || "";
  } catch (error) {
    const hashIndex = href.indexOf("#");
    return hashIndex >= 0 ? href.slice(hashIndex) : "";
  }
}

// Creates a list that connects sidebar links with their target sections.
const sidebarSections = sidebarLinks
  .map(function (link) {
    const targetId = getSidebarTargetId(link);
    const target = targetId ? document.querySelector(targetId) : null;

    return { link: link, targetId: targetId, target: target };
  })
  .filter(function (item) {
    return item.target !== null;
  });

// Marks the sidebar link for the specified section as active.
function setActiveSidebarLink(targetId) {
  if (!targetId) return;

  sidebarLinks.forEach(function (link) {
    const isActive = getSidebarTargetId(link) === targetId;

    link.classList.toggle("is-active", isActive);

    if (isActive) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  });
}

// Updates the current URL hash without reloading the page.
function replaceCurrentHash(targetId) {
  if (!targetId || !window.history || !window.history.replaceState) return;
  window.history.replaceState(null, "", targetId);
}

// Synchronizes the active sidebar item and the current URL hash.
function syncSidebarToTarget(targetId, shouldReplaceHash = true) {
  setActiveSidebarLink(targetId);
  if (shouldReplaceHash) replaceCurrentHash(targetId);
}

// Detects which section is currently visible and updates the sidebar.
function updateActiveSidebarByScroll() {
  if (sidebarSections.length === 0) return;

  const checkLine = window.innerHeight * 0.34;
  let activeSection = sidebarSections[0];

  sidebarSections.forEach(function (item) {
    const rect = item.target.getBoundingClientRect();
    if (rect.top <= checkLine) activeSection = item;
  });

  const scrollBottom = Math.ceil(window.scrollY + window.innerHeight);
  const pageHeight = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);

  // Selects the final sidebar item when the user reaches the bottom.
  if (scrollBottom >= pageHeight - 2) activeSection = sidebarSections[sidebarSections.length - 1];

  setActiveSidebarLink(activeSection.targetId);
}

let sidebarScrollTicking = false;

// Uses requestAnimationFrame to prevent excessive scroll event handling.
function requestSidebarScrollSync() {
  if (sidebarScrollTicking) return;

  sidebarScrollTicking = true;

  window.requestAnimationFrame(function () {
    updateActiveSidebarByScroll();
    sidebarScrollTicking = false;
  });
}

// Adds smooth scrolling to each sidebar link.
sidebarSections.forEach(function (item) {
  item.link.addEventListener("click", function (e) {
    e.preventDefault();

    item.target.scrollIntoView({ behavior: "smooth", block: "start" });
    syncSidebarToTarget(item.targetId);

    // Keeps the clicked sidebar item active after smooth scrolling.
    setTimeout(function () {
      setActiveSidebarLink(item.targetId);
    }, 450);
  });
});

// Initializes sidebar state and scroll event listeners.
if (sidebarSections.length > 0) {
  const initialHash = window.location.hash;
  const initialTarget = sidebarSections.find(function (item) {
    return item.targetId === initialHash;
  });

  if (initialTarget) {
    setActiveSidebarLink(initialTarget.targetId);
  } else {
    updateActiveSidebarByScroll();
  }

  window.addEventListener("scroll", requestSidebarScrollSync, { passive: true });
  window.addEventListener("resize", requestSidebarScrollSync);
  setTimeout(updateActiveSidebarByScroll, 250);
}

// Starts repeatedly checking the analysis progress.
function startProgressPolling(jobId) {
  stopProgressPolling();
  pollProgress(jobId);

  progressPollingTimer = setInterval(function () {
    pollProgress(jobId);
  }, 800);
}

// Stops the active progress polling timer.
function stopProgressPolling() {
  if (!progressPollingTimer) return;

  clearInterval(progressPollingTimer);
  progressPollingTimer = null;
}

// Creates the cancellation API URL for the specified analysis job.
function getCancelAnalysisUrl(jobId) {
  return cancelAnalysisUrlTemplate.replace("__JOB_ID__", encodeURIComponent(jobId));
}

// Resets the current analysis state.
function resetAnalysisRunningState() {
  isAnalysisRunning = false;
  currentJobId = null;
}

// Cancels the currently running analysis job.
function cancelCurrentAnalysis(reason = "user_navigation") {
  if (!currentJobId || !isAnalysisRunning) return;

  const jobIdToCancel = currentJobId;
  const cancelUrl = getCancelAnalysisUrl(jobIdToCancel);
  const payload = JSON.stringify({ reason: reason });

  stopProgressPolling();

  /*
    Uses sendBeacon first so that the cancellation request can still
    reach the server while the user is leaving the current page.
  */
  if (navigator.sendBeacon) {
    const blob = new Blob([payload], { type: "application/json" });
    navigator.sendBeacon(cancelUrl, blob);
  } else {
    fetch(cancelUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload,
      keepalive: true
    }).catch(function () {});
  }

  resetAnalysisRunningState();

  if (analyzeBtn) {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = I18N.analyzeButton;
  }
}

/*
  Cancels the analysis when the user clicks a link that leaves
  the current page.

  capture=true ensures that the cancellation request is sent
  before the browser starts navigating to the new page.
*/
document.addEventListener("click", function (e) {
  const link = e.target.closest("a");
  if (!link || !isAnalysisRunning || !currentJobId) return;

  let url = null;

  try {
    url = new URL(link.href, window.location.href);
  } catch (error) {
    return;
  }

  const currentPath = window.location.pathname;

  // Allows navigation between MusicAI sections without cancelling.
  const isSamePageHashMove = url.pathname === currentPath && url.hash && url.hash.startsWith("#cat-");
  if (isSamePageHashMove) return;

  const isLeavingCurrentPage = url.pathname !== currentPath || !url.hash;
  if (isLeavingCurrentPage) cancelCurrentAnalysis("link_navigation");
}, true);

/*
  Cancels the analysis when the page is refreshed, closed,
  hidden, or left through browser navigation.
*/
window.addEventListener("pagehide", function () {
  if (isAnalysisRunning && currentJobId) cancelCurrentAnalysis("page_hide");
});

// Requests the latest progress information from the server.
async function pollProgress(jobId) {
  try {
    const progressUrl = progressUrlTemplate.replace("__JOB_ID__", encodeURIComponent(jobId));
    const response = await fetch(progressUrl, { method: "GET", cache: "no-store" });
    const data = await response.json();

    if (!response.ok || !data.ok) throw new Error(data.error || I18N.errorProgressFailed);

    const progress = data.progress;
    updateProgressUI(progress);

    // Handles successful analysis completion.
    if (progress.status === "completed") {
      stopProgressPolling();
      latestAnalysisResult = progress.result;
      resetAnalysisRunningState();

      analyzeBtn.disabled = false;
      analyzeBtn.textContent = I18N.analyzeButton;

      setTimeout(function () {
        renderResult(latestAnalysisResult);

        resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
        syncSidebarToTarget("#cat-420");

        setTimeout(function () {
          setActiveSidebarLink("#cat-420");
        }, 450);
      }, 600);
    }

    // Handles analysis cancellation.
    if (progress.status === "cancelled") {
      stopProgressPolling();
      resetAnalysisRunningState();

      analyzeBtn.disabled = false;
      analyzeBtn.textContent = I18N.analyzeButton;

      if (analysisProgressCard) analysisProgressCard.hidden = true;
      return;
    }

    // Handles an analysis error reported by the server.
    if (progress.status === "error") {
      stopProgressPolling();
      resetAnalysisRunningState();

      analyzeBtn.disabled = false;
      analyzeBtn.textContent = I18N.analyzeButton;

      showError(I18N.errorAnalysisFailed, progress.error || I18N.errorUnknown);
    }
  } catch (error) {
    // Handles progress API or network errors.
    stopProgressPolling();
    resetAnalysisRunningState();

    analyzeBtn.disabled = false;
    analyzeBtn.textContent = I18N.analyzeButton;

    showError(I18N.errorProgressLookupFailed, error.message);
  }
}