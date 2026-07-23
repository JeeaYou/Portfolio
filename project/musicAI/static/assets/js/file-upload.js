/*
  File-upload logic for upload-section.html.
*/

document.addEventListener("DOMContentLoaded", function () {
  // Upload section elements.
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

  // Stores the audio files currently selected by the user.
  let selectedFiles = [];

  // Formats the translated selected-file count text.
  function formatSelectedFileCount(count) {
    return String(I18N.selectedFileCountDefault || "0").replace("0", String(count));
  }

  // Synchronizes the custom selectedFiles array with the file input.
  function syncAudioFileInput() {
    const dataTransfer = new DataTransfer();

    selectedFiles.forEach(function (file) {
      dataTransfer.items.add(file);
    });

    audioFile.files = dataTransfer.files;
  }

  // Returns the uppercase extension of the specified file name.
  function getFileExtension(fileName) {
    const parts = String(fileName || "").split(".");
    return parts.length < 2 ? "FILE" : parts.pop().toUpperCase();
  }

  // Converts a file size in bytes into KB or MB.
  function formatFileSize(bytes) {
    const size = Number(bytes || 0);

    if (!Number.isFinite(size) || size <= 0) return "-";
    if (size < 1024 * 1024) return (size / 1024).toFixed(1) + " KB";

    return (size / (1024 * 1024)).toFixed(1) + " MB";
  }

  // Filters the supplied file list and returns supported audio files only.
  function getAudioFilesFromList(fileList) {
    return Array.from(fileList || []).filter(function (file) {
      return (
        /\.(mp3|wav|m4a|flac|ogg|aac)$/i.test(file.name) ||
        String(file.type || "").startsWith("audio/")
      );
    });
  }

  // Renders the currently selected audio files in the upload panel.
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

    // Removes previously rendered file items.
    selectedFileList.textContent = "";

    // Restores the empty state when no files are selected.
    if (selectedFiles.length === 0) {
      audioFile.value = "";

      selectedFileName.classList.add("is-empty");
      selectedFileEmptyText.hidden = false;
      selectedFileCountRow.hidden = true;
      selectedFileList.hidden = true;

      if (clearFileBtn) clearFileBtn.style.display = "none";

      return;
    }

    // Displays the selected-file list and file count.
    selectedFileName.classList.remove("is-empty");
    selectedFileEmptyText.hidden = true;
    selectedFileCountRow.hidden = false;
    selectedFileList.hidden = false;
    selectedFileCountText.textContent = formatSelectedFileCount(selectedFiles.length);

    if (clearFileBtn) clearFileBtn.style.display = "inline-flex";

    // Creates one visible file item for each selected file.
    selectedFiles.forEach(function (file, index) {
      const item = selectedFileItemBlueprint.cloneNode(true);
      const fileText = item.querySelector(".selected-file-text");
      const fileSize = item.querySelector(".selected-file-size");
      const fileType = item.querySelector(".selected-file-type");
      const removeButton = item.querySelector(".remove-file-btn");

      item.removeAttribute("id");
      item.hidden = false;

      // Displays a user-friendly file name.
      if (fileText) fileText.textContent = formatDisplayFileName(file.name);
      if (fileSize) fileSize.textContent = formatFileSize(file.size);
      if (fileType) fileType.textContent = getFileExtension(file.name);

      // Stores the file index on the remove button.
      if (removeButton) removeButton.dataset.index = String(index);

      selectedFileList.appendChild(item);
    });

    // Updates the original file input after rendering.
    syncAudioFileInput();
  }

  // Handles files selected through the system file picker.
  if (audioFile) {
    audioFile.addEventListener("change", function () {
      selectedFiles = getAudioFilesFromList(audioFile.files);
      renderSelectedFileList();
    });
  }

  // Handles drag-and-drop visual states and dropped audio files.
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

    // Adds supported dropped audio files to the selected-file list.
    uploadLabel.addEventListener("drop", function (e) {
      selectedFiles = getAudioFilesFromList(e.dataTransfer.files);
      renderSelectedFileList();
    });
  }

  // Removes an individual file when its remove button is clicked.
  if (selectedFileName) {
    selectedFileName.addEventListener("click", function (e) {
      const removeBtn = e.target.closest(".remove-file-btn")
      if (!removeBtn) return;

      const removeIndex = Number(removeBtn.dataset.index);

      selectedFiles.splice(removeIndex, 1);
      renderSelectedFileList()
    });
  }

  // Removes all selected files.
  if (clearFileBtn) {
    clearFileBtn.addEventListener("click", function () {
      selectedFiles = [];
      renderSelectedFileList();
    });
  }

  // Starts the audio analysis request.
  if (analyzeBtn) {
    analyzeBtn.addEventListener("click", async function () {
      // Prevents analysis when no audio file has been selected.
      if (selectedFiles.length === 0) {
        alert(I18N.alertSelectFile);
        return;
      }

      // Stops any previous progress polling operation.
      stopProgressPolling();

      latestAnalysisResult = null;

      // Clears the previous visualization results.
      resetVisualizationDashboard();

      analyzeBtn.disabled = true;
      analyzeBtn.textContent = I18N.analyzingButton;

      // Creates a progress item for each selected file.
      showFileProgressBars(selectedFiles);

      const resultArea = document.getElementById("cat-420");

      // Moves the screen to the analysis result section.
      if (resultArea) {
        resultArea.scrollIntoView({
          behavior: "smooth",
          block: "start"
        });

        syncSidebarToTarget("#cat-420");
      }

      // Creates the multipart request containing all selected files.
      const formData = new FormData();

      selectedFiles.forEach(function (file) {
        formData.append("audio_files", file);
      });

      try {
        // Sends the selected audio files to the analysis start API.
        const response = await fetch(startAnalyzeUrl, {
          method: "POST",
          body: formData
        });

        const data = await response.json();

        if (!response.ok || !data.ok) {
          throw new Error(data.error || I18N.errorStartFailed);
        }

        // Stores the new job information.
        currentJobId = data.job_id;
        isAnalysisRunning = true;

        // Starts polling the analysis progress API.
        startProgressPolling(data.job_id);
      } catch (error) {
        // Restores the interface when the analysis request fails.
        stopProgressPolling()
        resetAnalysisRunningState();

        analyzeBtn.disabled = false;
        analyzeBtn.textContent = I18N.analyzeButton;

        showError(I18N.errorAnalysisFailed, error.message);
      }
    });
  }
});