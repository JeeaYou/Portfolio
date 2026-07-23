document.addEventListener("DOMContentLoaded", function () {
  const analyzeBtn = document.getElementById("analyzeBtn");
  const audioFile = document.getElementById("audioFile");
  const uploadLabel = document.querySelector(".upload-label");
  const selectedFileName = document.getElementById("selectedFileName");
  const selectedFileEmptyText = document.getElementById("selectedFileEmptyText");
  const selectedFileCountRow = document.getElementById("selectedFileCountRow");
  const selectedFileCountText = document.getElementById("selectedFileCountText");
  const selectedFileList = document.getElementById("selectedFileList");
  const selectedFileItemBlueprint = document.getElementById("selectedFileItemBlueprint");
  const clearFileBtn = document.getElementById("clearFileBtn");

  let selectedFiles = [];

  function formatSelectedFileCount(count) {
    return String(I18N.selectedFileCountDefault || "0").replace("0", String(count));
  }

  function syncAudioFileInput() {
    const dataTransfer = new DataTransfer();

    selectedFiles.forEach(function (file) {
      dataTransfer.items.add(file);
    });

    audioFile.files = dataTransfer.files;
  }

  function getFileExtension(fileName) {
    const parts = String(fileName || "").split(".");

    if (parts.length < 2) {
      return "FILE";
    }

    return parts.pop().toUpperCase();
  }

  function formatFileSize(bytes) {
    const size = Number(bytes || 0);

    if (!Number.isFinite(size) || size <= 0) {
      return "-";
    }

    if (size < 1024 * 1024) {
      return (size / 1024).toFixed(1) + " KB";
    }

    return (size / (1024 * 1024)).toFixed(1) + " MB";
  }

  function getAudioFilesFromList(fileList) {
    return Array.from(fileList || []).filter(function (file) {
      return (
        /\.(mp3|wav|m4a|flac|ogg|aac)$/i.test(file.name) ||
        String(file.type || "").startsWith("audio/")
      );
    });
  }

  function renderSelectedFileList() {
    if (
      !selectedFileName ||
      !selectedFileEmptyText ||
      !selectedFileCountRow ||
      !selectedFileCountText ||
      !selectedFileList ||
      !selectedFileItemBlueprint
    ) {
      return;
    }

    selectedFileList.textContent = "";

    if (selectedFiles.length === 0) {
      audioFile.value = "";

      selectedFileName.classList.add("is-empty");
      selectedFileEmptyText.hidden = false;
      selectedFileCountRow.hidden = true;
      selectedFileList.hidden = true;

      if (clearFileBtn) {
        clearFileBtn.style.display = "none";
      }

      return;
    }

    selectedFileName.classList.remove("is-empty");
    selectedFileEmptyText.hidden = true;
    selectedFileCountRow.hidden = false;
    selectedFileList.hidden = false;

    selectedFileCountText.textContent =
      formatSelectedFileCount(selectedFiles.length);

    if (clearFileBtn) {
      clearFileBtn.style.display = "inline-flex";
    }

    selectedFiles.forEach(function (file, index) {
      const item = selectedFileItemBlueprint.cloneNode(true);
      const fileText = item.querySelector(".selected-file-text");
      const fileSize = item.querySelector(".selected-file-size");
      const fileType = item.querySelector(".selected-file-type");
      const removeButton = item.querySelector(".remove-file-btn");

      item.removeAttribute("id");
      item.hidden = false;

      if (fileText) {
        fileText.textContent = formatDisplayFileName(file.name);
      }

      if (fileSize) {
        fileSize.textContent = formatFileSize(file.size);
      }

      if (fileType) {
        fileType.textContent = getFileExtension(file.name);
      }

      if (removeButton) {
        removeButton.dataset.index = String(index);
      }

      selectedFileList.appendChild(item);
    });

    syncAudioFileInput();
  }

  if (audioFile) {
    audioFile.addEventListener("change", function () {
      selectedFiles = getAudioFilesFromList(audioFile.files);
      renderSelectedFileList();
    });
  }

  if (uploadLabel) {
    ["dragenter", "dragover"].forEach(function (eventName) {
      uploadLabel.addEventListener(eventName, function (e) {
        e.preventDefault();
        uploadLabel.classList.add("is-dragover");
      });
    });

    ["dragleave", "drop"].forEach(function (eventName) {
      uploadLabel.addEventListener(eventName, function (e) {
        e.preventDefault();
        uploadLabel.classList.remove("is-dragover");
      });
    });

    uploadLabel.addEventListener("drop", function (e) {
      selectedFiles = getAudioFilesFromList(e.dataTransfer.files);
      renderSelectedFileList();
    });
  }

  if (selectedFileName) {
    selectedFileName.addEventListener("click", function (e) {
      const removeBtn = e.target.closest(".remove-file-btn");

      if (!removeBtn) return;

      const removeIndex = Number(removeBtn.dataset.index);
      selectedFiles.splice(removeIndex, 1);

      renderSelectedFileList();
    });
  }

  if (clearFileBtn) {
    clearFileBtn.addEventListener("click", function () {
      selectedFiles = [];
      renderSelectedFileList();
    });
  }

  if (analyzeBtn) {
    analyzeBtn.addEventListener("click", async function () {
      if (selectedFiles.length === 0) {
        alert(I18N.alertSelectFile);
        return;
      }

      stopProgressPolling();

      latestAnalysisResult = null;
      resetVisualizationDashboard();

      analyzeBtn.disabled = true;
      analyzeBtn.textContent = I18N.analyzingButton;

      showFileProgressBars(selectedFiles);

      const resultArea = document.getElementById("cat-420");

      if (resultArea) {
        resultArea.scrollIntoView({
          behavior: "smooth",
          block: "start"
        });

        syncSidebarToTarget("#cat-420");
      }

      const formData = new FormData();

      selectedFiles.forEach(function (file) {
        formData.append("audio_files", file);
      });

      try {
        const response = await fetch(startAnalyzeUrl, {
          method: "POST",
          body: formData
        });

        const data = await response.json();

        if (!response.ok || !data.ok) {
          throw new Error(data.error || I18N.errorStartFailed);
        }

        currentJobId = data.job_id;
        isAnalysisRunning = true;

        startProgressPolling(data.job_id);
      } catch (error) {
        stopProgressPolling();

        resetAnalysisRunningState();

        analyzeBtn.disabled = false;
        analyzeBtn.textContent = I18N.analyzeButton;

        showError(
          I18N.errorAnalysisFailed,
          error.message
        );
      }
    });
  }
});