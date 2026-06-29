document.addEventListener("DOMContentLoaded", function () {
  const resumePage = document.querySelector(".resume-page");
  const resumePaper = document.querySelector(".resume-paper");

  const editBtn = document.getElementById("resumeEditBtn");
  const saveBtn = document.getElementById("resumeSaveBtn");
  const pdfBtn = document.getElementById("resumePdfBtn");

  const sendForm = document.getElementById("resumeSendForm");
  const emailInput = document.getElementById("resumeEmail");
  const messageBox = document.getElementById("resumeSendMessage");

  if (!resumePaper) return;

  /* =========================
     현재 언어 가져오기
  ========================= */

  function getCurrentLang() {
    if (resumePage && resumePage.dataset.currentLang) {
      const pageLang = resumePage.dataset.currentLang;

      if (pageLang === "ko" || pageLang === "en" || pageLang === "zh") {
        return pageLang;
      }
    }

    const htmlLang = document.documentElement.getAttribute("lang");

    if (htmlLang === "ko" || htmlLang === "en" || htmlLang === "zh") {
      return htmlLang;
    }

    const params = new URLSearchParams(window.location.search);
    const queryLang = params.get("lang");

    if (queryLang === "ko" || queryLang === "en" || queryLang === "zh") {
      return queryLang;
    }

    return "ko";
  }

  /* =========================
     메시지 출력
  ========================= */

  function setMessage(text, type) {
    if (!messageBox) return;

    messageBox.textContent = text || "";
    messageBox.classList.remove("is-success", "is-error");

    if (type === "success") {
      messageBox.classList.add("is-success");
    }

    if (type === "error") {
      messageBox.classList.add("is-error");
    }
  }

  /* =========================
     fetch 결과 안전하게 JSON 변환
  ========================= */

  async function readJsonResponse(response) {
    const text = await response.text();

    try {
      return JSON.parse(text);
    } catch (error) {
      return {
        success: false,
        message: text || "서버 응답을 읽을 수 없습니다."
      };
    }
  }

  /* =========================
     수정 가능한 요소 가져오기
  ========================= */

  function getEditableElements() {
    return Array.from(resumePaper.querySelectorAll("[data-key]"));
  }

  /* =========================
     Edit Mode ON
  ========================= */

  function enableEditMode() {
    const editableElements = getEditableElements();

    if (!editableElements.length) {
      setMessage("수정 가능한 이력서 항목을 찾을 수 없습니다.", "error");
      return;
    }

    resumePaper.classList.add("is-editing");

    editableElements.forEach(function (el) {
      el.setAttribute("contenteditable", "true");
      el.setAttribute("spellcheck", "false");

      if (el.tagName.toLowerCase() === "a") {
        el.dataset.originalHref = el.getAttribute("href") || "";
        el.setAttribute("href", "javascript:void(0)");
      }
    });

    setMessage("수정 모드가 켜졌습니다. 텍스트를 클릭해서 수정하세요.", "");
  }

  /* =========================
     Edit Mode OFF
  ========================= */

  function disableEditMode() {
    const editableElements = getEditableElements();

    resumePaper.classList.remove("is-editing");

    editableElements.forEach(function (el) {
      el.removeAttribute("contenteditable");
      el.removeAttribute("spellcheck");

      if (el.tagName.toLowerCase() === "a" && el.dataset.originalHref) {
        el.setAttribute("href", el.dataset.originalHref);
        delete el.dataset.originalHref;
      }
    });
  }

  /* =========================
     수정된 데이터 수집
  ========================= */

  function collectResumeItems() {
    const editableElements = getEditableElements();

    return editableElements
      .map(function (el) {
        return {
          content_key: el.dataset.key,
          content: el.innerText.trim()
        };
      })
      .filter(function (item) {
        return item.content_key;
      });
  }

  /* =========================
     저장 버튼 상태 변경
  ========================= */

  function setSavingState(isSaving) {
    if (!saveBtn) return;

    saveBtn.disabled = isSaving;

    if (isSaving) {
      saveBtn.dataset.originalText = saveBtn.textContent;
      saveBtn.textContent = "Saving...";
    } else {
      saveBtn.textContent = saveBtn.dataset.originalText || "Save Changes";
    }
  }

  /* =========================
     PDF 버튼 상태 변경
  ========================= */

  function setPdfState(isDownloading) {
    if (!pdfBtn) return;

    pdfBtn.disabled = isDownloading;

    if (isDownloading) {
      pdfBtn.dataset.originalText = pdfBtn.textContent;
      pdfBtn.textContent = "Downloading...";
    } else {
      pdfBtn.textContent = pdfBtn.dataset.originalText || "Download PDF";
    }
  }

  /* =========================
     메일 버튼 상태 변경
  ========================= */

  function setSendingState(isSending) {
    const sendBtn = document.querySelector(".resume-send-btn");

    if (!sendBtn) return;

    sendBtn.disabled = isSending;

    if (isSending) {
      sendBtn.dataset.originalText = sendBtn.textContent;
      sendBtn.textContent = "Sending...";
    } else {
      sendBtn.textContent = sendBtn.dataset.originalText || "Send Resume";
    }
  }

  /* =========================
     PDF/메일용 이력서 HTML 복사본 생성
  ========================= */

  function getCleanResumeHtml() {
    const clonedPaper = resumePaper.cloneNode(true);

    clonedPaper.classList.remove("is-editing");

    clonedPaper.querySelectorAll("[contenteditable]").forEach(function (el) {
      el.removeAttribute("contenteditable");
      el.removeAttribute("spellcheck");
    });

    clonedPaper.querySelectorAll("a").forEach(function (el) {
      if (el.dataset.originalHref) {
        el.setAttribute("href", el.dataset.originalHref);
        delete el.dataset.originalHref;
      }
    });

    return clonedPaper.outerHTML;
  }

  /* =========================
     DB 저장
  ========================= */

  async function saveResumeToDatabase() {
    const items = collectResumeItems();

    if (!items.length) {
      setMessage("저장할 이력서 데이터가 없습니다.", "error");
      return;
    }

    setSavingState(true);
    setMessage("이력서 데이터를 DB에 저장하는 중입니다...", "");

    const response = await fetch("/resume/update", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      credentials: "same-origin",
      body: JSON.stringify({
        lang: getCurrentLang(),
        items: items
      })
    });

    const result = await readJsonResponse(response);

    if (!response.ok || !result.success) {
      throw new Error(result.message || "이력서 저장에 실패했습니다.");
    }

    disableEditMode();

    setMessage(result.message || "이력서 데이터가 DB에 저장되었습니다.", "success");
  }

  /* =========================
     이력서 PDF 다운로드
  ========================= */

  async function downloadResumePdf() {
    setPdfState(true);
    setMessage("PDF를 생성하는 중입니다...", "");

    const response = await fetch("/resume/download", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      credentials: "same-origin",
      body: JSON.stringify({
        lang: getCurrentLang(),
        resume_html: getCleanResumeHtml()
      })
    });

    if (!response.ok) {
      const result = await readJsonResponse(response);
      throw new Error(result.message || "PDF 다운로드에 실패했습니다.");
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = "Jeea_You_Resume.pdf";

    document.body.appendChild(a);
    a.click();

    a.remove();
    window.URL.revokeObjectURL(url);

    setMessage("PDF 다운로드가 완료되었습니다.", "success");
  }

  /* =========================
     이력서 메일 발송
  ========================= */

  async function sendResume(email) {
    setSendingState(true);
    setMessage("이력서를 전송하는 중입니다...", "");

    const response = await fetch("/resume/send", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      credentials: "same-origin",
      body: JSON.stringify({
        email: email,
        lang: getCurrentLang(),
        resume_html: getCleanResumeHtml()
      })
    });

    const result = await readJsonResponse(response);

    if (!response.ok || !result.success) {
      throw new Error(result.message || "이력서 전송에 실패했습니다.");
    }

    setMessage(result.message || "이력서가 성공적으로 전송되었습니다.", "success");
  }

  /* =========================
     Event
  ========================= */

  if (editBtn) {
    editBtn.addEventListener("click", function () {
      enableEditMode();
    });
  }

  if (saveBtn) {
    saveBtn.addEventListener("click", async function () {
      try {
        await saveResumeToDatabase();
      } catch (error) {
        setMessage(error.message, "error");
      } finally {
        setSavingState(false);
      }
    });
  }

  if (pdfBtn) {
    pdfBtn.addEventListener("click", async function () {
      try {
        await downloadResumePdf();
      } catch (error) {
        setMessage(error.message, "error");
      } finally {
        setPdfState(false);
      }
    });
  }

  if (sendForm) {
    sendForm.addEventListener("submit", async function (event) {
      event.preventDefault();

      console.log("[resume.js] Send form submit captured");

      const email = emailInput.value.trim();

      if (!email) {
        setMessage("이메일 주소를 입력해주세요.", "error");
        return;
      }

      try {
        await sendResume(email);
      } catch (error) {
        setMessage(error.message, "error");
      } finally {
        setSendingState(false);
      }
    });
  }
});