const resultSection = document.getElementById("resultSection");
const resultRoot = document.getElementById("resultRoot");
const analysisProgressCard = document.getElementById("analysisProgressCard");
const fileProgressList = document.getElementById("fileProgressList");
const fileProgressItemBlueprint = document.getElementById("fileProgressItemBlueprint");
const analysisErrorCard = document.getElementById("analysisErrorCard");
const analysisErrorTitle = document.getElementById("analysisErrorTitle");
const analysisErrorMessage = document.getElementById("analysisErrorMessage");
const analysisTrackTabs = document.getElementById("analysisTrackTabs");
const analysisTrackCards = document.getElementById("analysisTrackCards");
const analysisTrackTabBlueprint = document.getElementById("analysisTrackTabBlueprint");
const analysisTrackCardBlueprint = document.getElementById("analysisTrackCardBlueprint");

function displayValue(value, suffix = "") {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  return `${value}${suffix}`;
}

function displayArrayPreview(values) {
  if (!Array.isArray(values) || values.length === 0) {
    return "-";
  }

  const preview = values
    .map(function (value) {
      const numberValue = Number(value);

      if (Number.isFinite(numberValue)) {
        return numberValue.toFixed(4);
      }

      return String(value);
    })
    .join(", ");

  return preview;
}

function setField(root, fieldName, value, suffix = "") {
  if (!root) return;

  const targets = root.querySelectorAll(`[data-field="${fieldName}"]`);

  if (!targets || targets.length === 0) return;

  targets.forEach(function (target) {
    target.textContent = displayValue(value, suffix);
  });
}

function showError(title, message) {
  if (resultRoot) {
    resultRoot.hidden = true;
  }

  if (analysisProgressCard) {
    analysisProgressCard.hidden = true;
  }

  if (analysisErrorTitle) {
    analysisErrorTitle.textContent = title || I18N.errorAnalysisFailed;
  }

  if (analysisErrorMessage) {
    analysisErrorMessage.textContent = message || I18N.errorUnknown;
  }

  if (analysisErrorCard) {
    analysisErrorCard.hidden = false;
  }
}

function showFileProgressBars(files) {
  if (!analysisProgressCard || !fileProgressList || !fileProgressItemBlueprint) return;

  if (resultRoot) {
    resultRoot.hidden = true;
  }

  if (analysisErrorCard) {
    analysisErrorCard.hidden = true;
  }

  analysisProgressCard.hidden = false;
  fileProgressList.textContent = "";

  files.forEach(function (file, index) {
    const item = fileProgressItemBlueprint.cloneNode(true);

    item.removeAttribute("id");
    item.dataset.fileIndex = String(index + 1);
    item.classList.remove("is-waiting", "is-running", "is-done", "is-failed");

    const nameText = item.querySelector(".file-progress-name");
    const percentText = item.querySelector(".file-progress-percent");
    const bar = item.querySelector(".file-progress-bar");
    const statusText = item.querySelector(".file-progress-status");

    if (nameText) {
      nameText.textContent = (index + 1) + ". " + file.name;
    }

    if (percentText) {
      percentText.textContent = "0%";
    }

    if (bar) {
      bar.style.width = "0%";
    }

    if (statusText) {
      statusText.textContent = I18N.progressWaiting;
    }

    fileProgressList.appendChild(item);
  });
}

function updateProgressUI(progress) {
  const title = document.querySelector(".progress-title");
  const desc = document.querySelector(".progress-desc");

  if (title) {
    title.textContent = I18N.progressTitle;
  }

  if (desc) {
    desc.textContent = I18N.progressRunning;
  }

  if (!progress.files) return;

  progress.files.forEach(function (file) {
    const item = document.querySelector(
      `.file-progress-item[data-file-index="${file.index}"]`
    );

    if (!item) return;

    const bar = item.querySelector(".file-progress-bar");
    const percentText = item.querySelector(".file-progress-percent");
    const statusText = item.querySelector(".file-progress-status");

    const percent = Math.max(0, Math.min(100, Number(file.percent || 0)));

    item.classList.remove("is-waiting", "is-running", "is-done", "is-failed");
    item.classList.add(`is-${file.status}`);

    if (bar) {
      bar.style.width = percent + "%";
    }

    if (percentText) {
      percentText.textContent = percent + "%";
    }

    if (statusText) {
      if (file.status === "waiting") {
        statusText.textContent = I18N.progressWaiting;
      } else if (file.status === "running") {
        statusText.textContent = progress.current_step || I18N.progressRunning;
      } else if (file.status === "done") {
        statusText.textContent = I18N.progressDone;
      } else if (file.status === "failed") {
        statusText.textContent = I18N.progressFailed;
      } else {
        statusText.textContent = I18N.progressStatusChecking;
      }
    }
  });
}

function fillSummaryTemplate(summaryNode, result) {
  setField(summaryNode, "summary_total_file_count", result.total_file_count);
  setField(summaryNode, "summary_total_music_duration", result.total_music_duration?.text);
  setField(
    summaryNode,
    "summary_total_program_execution_time",
    result.total_program_execution_time?.text
  );
}

function pickFirstValue() {
  for (let i = 0; i < arguments.length; i += 1) {
    const value = arguments[i];

    if (value !== null && value !== undefined && value !== "") {
      return value;
    }
  }

  return null;
}

function formatPitchWithNote(note, hz) {
  const safeNote = displayValue(note);
  const numberHz = Number(hz);

  if (Number.isFinite(numberHz)) {
    return safeNote + " (" + numberHz + " Hz)";
  }

  return safeNote;
}

function formatPercentLike(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  const numberValue = Number(value);

  if (Number.isFinite(numberValue)) {
    return numberValue.toFixed(2) + " %";
  }

  return String(value).includes("%")
    ? String(value)
    : String(value) + " %";
}

function formatSeconds(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  const numberValue = Number(value);

  if (Number.isFinite(numberValue)) {
    return numberValue + "s";
  }

  return String(value);
}

function fillTrackTemplate(card, item, index) {
  const fileInfo = item.file_info || {};
  const audio = item.original_audio_analysis || {};
  const pitch = item.vocal_pitch_analysis || null;
  const instruments = item.background_instrument_analysis || {};
  const time = item.analysis_time_summary || {};

  const trackNo = String(index + 1).padStart(2, "0");

  setField(card, "track_number", trackNo);
  setField(card, "file_name", fileInfo.file_name);
  setField(card, "duration_text", fileInfo.duration_text);

  setField(card, "key", audio.key);
  setField(card, "tempo", `${displayValue(audio.tempo)} BPM`);
  setField(card, "genre", audio.genre);
  setField(card, "mood", audio.mood);
  setField(card, "rhythm_pattern", audio.rhythm_pattern);

  setField(card, "key_confidence", audio.key_confidence);
  setField(card, "tempo_category", audio.tempo_category);
  setField(card, "tempo_description", audio.tempo_description);

  setField(card, "rhythm_pattern_detail", audio.rhythm_pattern);
  setField(card, "beat_count", audio.beat_count);
  setField(card, "beat_strength", audio.beat_strength);
  setField(card, "beat_regularity", audio.beat_regularity);

  setField(card, "energy_level", audio.energy_level);
  setField(card, "energy_score", audio.energy_score);
  // setField(card, "rms", audio.rms);
  setField(card, "mood_detail", audio.mood);

  setField(card, "spectral_centroid", audio.spectral_centroid);
  // setField(card, "spectral_bandwidth", audio.spectral_bandwidth);
  // setField(card, "spectral_rolloff", audio.spectral_rolloff);
  setField(card, "spectral_flatness", audio.spectral_flatness);
  setField(card, "spectral_flux", audio.spectral_flux);
  setField(card, "zero_crossing_rate", audio.zero_crossing_rate);

  setField(card, "dynamic_range", audio.dynamic_range);
  setField(card, "harmonic_to_noise_ratio", audio.harmonic_to_noise_ratio);
  setField(card, "danceability", audio.danceability);

  // setField(card, "mfcc_mean", displayArrayPreview(audio.mfcc_mean));
  // setField(card, "mfcc_std", displayArrayPreview(audio.mfcc_std));
  // setField(card, "spectral_contrast_mean", displayArrayPreview(audio.spectral_contrast_mean));
  setField(card, "chroma_mean", displayArrayPreview(audio.chroma_mean));
  // setField(card, "tonnetz_mean", displayArrayPreview(audio.tonnetz_mean));

  const pitchResult = card.querySelector('[data-section="pitch_result"]');
  const pitchEmpty = card.querySelector('[data-section="pitch_empty"]');

  if (pitch) {
    if (pitchResult) pitchResult.style.display = "";
    if (pitchEmpty) pitchEmpty.style.display = "none";

    setField(card, "lowest_note", pitch.lowest_note);
    setField(card, "lowest_pitch_hz", pitch.lowest_pitch_hz, " Hz");
    setField(card, "highest_note", pitch.highest_note);
    setField(card, "highest_pitch_hz", pitch.highest_pitch_hz, " Hz");

    setField(
      card,
      "pitch_range_semitones",
      pitch.pitch_range_semitones,
      " " + I18N.semitonesUnit
    );

    setField(
      card,
      "pitch_range_octaves",
      pitch.pitch_range_octaves === null ||
      pitch.pitch_range_octaves === undefined
        ? "-"
        : pitch.pitch_range_octaves + " " + I18N.octavesUnit
    );

    const vocalRatio = pickFirstValue(
      pitch.vocal_ratio,
      pitch.vocal_ratio_percent,
      pitch.vocal_percentage,
      pitch.vocal_presence_ratio,
      item.vocal_ratio
    );

    const pitchMeanNote = pickFirstValue(
      pitch.median_note,
      pitch.mean_note,
      pitch.average_note,
      pitch.vocal_pitch_median_note,
      pitch.vocal_pitch_mean_note
    );

    const pitchMeanHz = pickFirstValue(
      pitch.median_pitch_hz,
      pitch.mean_pitch_hz,
      pitch.average_pitch_hz,
      pitch.vocal_pitch_median_hz,
      pitch.vocal_pitch_mean_hz
    );

    setField(card, "vocal_presence", I18N.vocalDetected);

    setField(
      card,
      "vocal_ratio",
      vocalRatio === null
        ? "-"
        : formatPercentLike(vocalRatio)
    );

    setField(
      card,
      "vocal_pitch_mean",
      pitchMeanNote || pitchMeanHz
        ? formatPitchWithNote(pitchMeanNote, pitchMeanHz)
        : "-"
    );

    setField(
      card,
      "vocal_pitch_min",
      formatPitchWithNote(
        pitch.lowest_note,
        pitch.lowest_pitch_hz
      )
    );

    setField(
      card,
      "vocal_pitch_max",
      formatPitchWithNote(
        pitch.highest_note,
        pitch.highest_pitch_hz
      )
    );
  } else {
    if (pitchResult) pitchResult.style.display = "none";
    if (pitchEmpty) pitchEmpty.style.display = "";

    setField(card, "vocal_presence", I18N.vocalNotDetected);
    setField(card, "vocal_ratio", "-");
    setField(card, "vocal_pitch_mean", "-");
    setField(card, "vocal_pitch_min", "-");
    setField(card, "vocal_pitch_max", "-");
  }

  setField(card, "instrument_count", instruments.instrument_count);

  const instrumentList = card.querySelector(
    '[data-field="instrument_list"]'
  );

  if (instrumentList) {
    instrumentList.textContent = "";

    if (
      instruments.instruments &&
      instruments.instruments.length > 0
    ) {
      instruments.instruments.forEach(function (inst) {
        const chip = document.createElement("span");
        const nameText = document.createElement("span");
        const percentText = document.createElement("strong");

        const instrumentName = displayValue(inst.instrument);
        const percentageValue = displayValue(inst.percentage);

        const percentageText = percentageValue === "-"
          ? "-"
          : (
              String(percentageValue).includes("%")
                ? percentageValue
                : percentageValue + "%"
            );

        chip.className = "instrument-chip";
        nameText.className = "instrument-chip-name";
        percentText.className = "instrument-chip-percent";

        nameText.textContent = instrumentName;
        percentText.textContent = percentageText;

        chip.appendChild(nameText);
        chip.appendChild(percentText);
        instrumentList.appendChild(chip);
      });
    } else {
      const emptyText = document.createElement("span");

      emptyText.className = "instrument-empty-text";
      emptyText.textContent = I18N.noInstrumentsDetected;

      instrumentList.appendChild(emptyText);
    }
  }

  setField(
    card,
    "original_audio_analysis_time",
    formatSeconds(time.original_audio_analysis_time)
  );

  setField(
    card,
    "vocal_separation_time",
    formatSeconds(time.vocal_separation_time)
  );

  setField(
    card,
    "vocal_pitch_analysis_time",
    formatSeconds(time.vocal_pitch_analysis_time)
  );

  setField(
    card,
    "background_instrument_analysis_time",
    formatSeconds(time.background_instrument_analysis_time)
  );

  setField(
    card,
    "total_analysis_time",
    formatSeconds(time.total_analysis_time)
  );
}

function renderResult(result) {
  if (
    !resultRoot ||
    !analysisTrackTabs ||
    !analysisTrackCards ||
    !analysisTrackTabBlueprint ||
    !analysisTrackCardBlueprint
  ) {
    return;
  }

  if (!result) {
    showError(
      I18N.errorNoResultTitle,
      I18N.errorNoResultMessage
    );

    return;
  }

  if (analysisProgressCard) {
    analysisProgressCard.hidden = true;
  }

  if (analysisErrorCard) {
    analysisErrorCard.hidden = true;
  }

  resultRoot.hidden = false;
  analysisTrackTabs.textContent = "";
  analysisTrackCards.textContent = "";

  fillSummaryTemplate(resultRoot, result);

  const results = result.results || [];

  if (results.length === 0) {
    const emptyCard = document.createElement("div");

    emptyCard.className = "analysis-empty-card";
    emptyCard.textContent = I18N.noAnalyzedFileResult;

    analysisTrackCards.appendChild(emptyCard);

    renderVisualizationDashboard(result);

    return;
  }

  results.forEach(function (item, index) {
    const fileInfo = item.file_info || {};
    const trackNo = String(index + 1).padStart(2, "0");
    const fileName = fileInfo.file_name || "Track " + (index + 1);
    const durationText = fileInfo.duration_text || "-";

    const tabButton = analysisTrackTabBlueprint.cloneNode(true);

    tabButton.removeAttribute("id");
    tabButton.dataset.trackIndex = String(index);
    tabButton.classList.toggle("is-active", index === 0);

    setField(
      tabButton,
      "tab_title",
      trackNo + ". " + fileName
    );

    setField(
      tabButton,
      "tab_duration",
      durationText
    );

    analysisTrackTabs.appendChild(tabButton);

    const card = analysisTrackCardBlueprint.cloneNode(true);

    card.removeAttribute("id");

    fillTrackTemplate(card, item, index);

    card.dataset.trackIndex = String(index);
    card.classList.toggle("is-hidden", index !== 0);

    analysisTrackCards.appendChild(card);
  });

  analysisTrackTabs.onclick = function (event) {
    const selectedTab = event.target.closest(
      ".analysis-track-tab"
    );

    if (!selectedTab) return;

    const selectedIndex = selectedTab.dataset.trackIndex;

    analysisTrackTabs
      .querySelectorAll(".analysis-track-tab")
      .forEach(function (tab) {
        tab.classList.toggle(
          "is-active",
          tab.dataset.trackIndex === selectedIndex
        );
      });

    analysisTrackCards
      .querySelectorAll(".analysis-card")
      .forEach(function (card) {
        card.classList.toggle(
          "is-hidden",
          card.dataset.trackIndex !== selectedIndex
        );
      });

    syncSidebarToTarget("#cat-420", false);
  };

  renderVisualizationDashboard(result);
}