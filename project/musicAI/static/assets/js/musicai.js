const analyzeBtn = document.getElementById("analyzeBtn");

let progressPollingTimer = null;
let latestAnalysisResult = null;
let currentJobId = null;
let isAnalysisRunning = false;

const configElement = document.getElementById("musicAiConfig");

const MUSIC_AI_CONFIG = configElement
  ? JSON.parse(configElement.textContent || "{}")
  : {};

const URLS = MUSIC_AI_CONFIG.urls || {};
const I18N = MUSIC_AI_CONFIG.i18n || {};

const startAnalyzeUrl = URLS.startAnalysis || "";
const progressUrlTemplate = URLS.progress || "";
const cancelAnalysisUrlTemplate = URLS.cancel || "";

function i18nTemplate(template, values) {
  return String(template || "").replace(/\{(\w+)\}/g, function (match, key) {
    return values && values[key] !== undefined ? values[key] : match;
  });
}

function formatDisplayFileName(fileName) {
  const name = String(fileName || "").split(/[\\/]/).pop();
  const dotIndex = name.lastIndexOf(".");
  const extension = dotIndex >= 0 ? name.slice(dotIndex) : "";
  const stem = dotIndex >= 0 ? name.slice(0, dotIndex) : name;

  const cleanStem = stem
    .replace(/^\d+[\s._-]+/, "")
    .replace(/_+/g, " ")
    .trim();

  return cleanStem + extension;
}

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
   현재 보고 있는 섹션에 맞춰 사이드바 선택 표시
========================= */

const sidebarLinks = Array.from(
  document.querySelectorAll('.t-nav-list a[href*="#cat-"]')
);

function getSidebarTargetId(link) {
  if (!link) return "";

  const href = link.getAttribute("href") || "";

  if (!href || href === "#") {
    return "";
  }

  try {
    const url = new URL(href, window.location.href);
    return url.hash || "";
  } catch (error) {
    const hashIndex = href.indexOf("#");
    return hashIndex >= 0 ? href.slice(hashIndex) : "";
  }
}

const sidebarSections = sidebarLinks
  .map(function (link) {
    const targetId = getSidebarTargetId(link);
    const target = targetId ? document.querySelector(targetId) : null;

    return {
      link: link,
      targetId: targetId,
      target: target
    };
  })
  .filter(function (item) {
    return item.target !== null;
  });

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

function replaceCurrentHash(targetId) {
  if (!targetId || !window.history || !window.history.replaceState) return;

  window.history.replaceState(null, "", targetId);
}

function syncSidebarToTarget(targetId, shouldReplaceHash = true) {
  setActiveSidebarLink(targetId);

  if (shouldReplaceHash) {
    replaceCurrentHash(targetId);
  }
}

function updateActiveSidebarByScroll() {
  if (sidebarSections.length === 0) return;

  const checkLine = window.innerHeight * 0.34;
  let activeSection = sidebarSections[0];

  sidebarSections.forEach(function (item) {
    const rect = item.target.getBoundingClientRect();

    if (rect.top <= checkLine) {
      activeSection = item;
    }
  });

  const scrollBottom = Math.ceil(window.scrollY + window.innerHeight);

  const pageHeight = Math.max(
    document.body.scrollHeight,
    document.documentElement.scrollHeight
  );

  if (scrollBottom >= pageHeight - 2) {
    activeSection = sidebarSections[sidebarSections.length - 1];
  }

  setActiveSidebarLink(activeSection.targetId);
}

let sidebarScrollTicking = false;

function requestSidebarScrollSync() {
  if (sidebarScrollTicking) return;

  sidebarScrollTicking = true;

  window.requestAnimationFrame(function () {
    updateActiveSidebarByScroll();
    sidebarScrollTicking = false;
  });
}

sidebarSections.forEach(function (item) {
  item.link.addEventListener("click", function (e) {
    e.preventDefault();

    item.target.scrollIntoView({
      behavior: "smooth",
      block: "start"
    });

    syncSidebarToTarget(item.targetId);

    setTimeout(function () {
      setActiveSidebarLink(item.targetId);
    }, 450);
  });
});

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

  window.addEventListener("scroll", requestSidebarScrollSync, {
    passive: true
  });

  window.addEventListener("resize", requestSidebarScrollSync);

  setTimeout(updateActiveSidebarByScroll, 250);
}

function startProgressPolling(jobId) {
  stopProgressPolling();

  pollProgress(jobId);

  progressPollingTimer = setInterval(function () {
    pollProgress(jobId);
  }, 800);
}

function stopProgressPolling() {
  if (progressPollingTimer) {
    clearInterval(progressPollingTimer);
    progressPollingTimer = null;
  }
}

function getCancelAnalysisUrl(jobId) {
  return cancelAnalysisUrlTemplate.replace(
    "__JOB_ID__",
    encodeURIComponent(jobId)
  );
}

function resetAnalysisRunningState() {
  isAnalysisRunning = false;
  currentJobId = null;
}

function cancelCurrentAnalysis(reason = "user_navigation") {
  if (!currentJobId || !isAnalysisRunning) return;

  const jobIdToCancel = currentJobId;
  const cancelUrl = getCancelAnalysisUrl(jobIdToCancel);

  const payload = JSON.stringify({
    reason: reason
  });

  stopProgressPolling();

  /*
    페이지가 Home으로 이동하는 순간에도 요청이 서버에 전달되도록
    sendBeacon을 우선 사용한다.
  */
  if (navigator.sendBeacon) {
    const blob = new Blob([payload], {
      type: "application/json"
    });

    navigator.sendBeacon(cancelUrl, blob);
  } else {
    fetch(cancelUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
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
  Home / 다른 페이지 이동 클릭 시 분석 취소.
  capture=true로 걸어야 실제 링크 이동 전에 취소 요청을 먼저 보낼 수 있다.
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

  const isSamePageHashMove =
    url.pathname === currentPath &&
    url.hash &&
    url.hash.startsWith("#cat-");

  if (isSamePageHashMove) return;

  const isLeavingCurrentPage =
    url.pathname !== currentPath ||
    !url.hash;

  if (isLeavingCurrentPage) {
    cancelCurrentAnalysis("link_navigation");
  }
}, true);

/*
  새로고침, 탭 닫기, 브라우저 뒤로가기 같은 경우도 취소 요청.
*/
window.addEventListener("pagehide", function () {
  if (isAnalysisRunning && currentJobId) {
    cancelCurrentAnalysis("page_hide");
  }
});

async function pollProgress(jobId) {
  try {
    const progressUrl = progressUrlTemplate.replace(
      "__JOB_ID__",
      encodeURIComponent(jobId)
    );

    const response = await fetch(progressUrl, {
      method: "GET",
      cache: "no-store"
    });

    const data = await response.json();

    if (!response.ok || !data.ok) {
      throw new Error(data.error || I18N.errorProgressFailed);
    }

    const progress = data.progress;

    updateProgressUI(progress);

    if (progress.status === "completed") {
      stopProgressPolling();

      latestAnalysisResult = progress.result;

      resetAnalysisRunningState();

      analyzeBtn.disabled = false;
      analyzeBtn.textContent = I18N.analyzeButton;

      setTimeout(function () {
        renderResult(latestAnalysisResult);

        resultSection.scrollIntoView({
          behavior: "smooth",
          block: "start"
        });

        syncSidebarToTarget("#cat-420");

        setTimeout(function () {
          setActiveSidebarLink("#cat-420");
        }, 450);
      }, 600);
    }

    if (progress.status === "cancelled") {
      stopProgressPolling();

      resetAnalysisRunningState();

      analyzeBtn.disabled = false;
      analyzeBtn.textContent = I18N.analyzeButton;

      if (analysisProgressCard) {
        analysisProgressCard.hidden = true;
      }

      return;
    }

    if (progress.status === "error") {
      stopProgressPolling();

      resetAnalysisRunningState();

      analyzeBtn.disabled = false;
      analyzeBtn.textContent = I18N.analyzeButton;

      showError(
        I18N.errorAnalysisFailed,
        progress.error || I18N.errorUnknown
      );
    }
  } catch (error) {
    stopProgressPolling();

    resetAnalysisRunningState();

    analyzeBtn.disabled = false;
    analyzeBtn.textContent = I18N.analyzeButton;

    showError(
      I18N.errorProgressLookupFailed,
      error.message
    );
  }
}