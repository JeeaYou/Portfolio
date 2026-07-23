/*
  visualization-section.html 전용 코드

  기존 파일의 로직을 변경하지 않고 그대로 분리했습니다.
  다음 공통 값/함수는 먼저 로드되는 공통 JS에 있어야 합니다.
  - I18N
  - latestAnalysisResult
  - i18nTemplate()
  - displayValue()
*/

const visualizationSection = document.getElementById("visualizationSection");
const visualizationDashboard = document.getElementById("visualizationDashboard");
const visualizationEmptyText = document.getElementById("visualizationEmptyText");
const resetVisualizationFilterBtn = document.getElementById("resetVisualizationFilterBtn");
const visualCurrentFilter = document.getElementById("visualCurrentFilter");
const visualFilterSummary = document.getElementById("visualFilterSummary");

let songDnaChart = null;
let genreDistributionChart = null;
let keyDistributionChart = null;
let instrumentChart = null;
let analysisTimeChart = null;

let selectedVocalNoteMidi = null;
let activeGenreLabel = "";
let activeGenreTracks = null;

activeGenreLabel = I18N.allGenre;

const PIANO_MIN_MIDI = 36;
const PIANO_MAX_MIDI = 84;

if (resetVisualizationFilterBtn) {
  resetVisualizationFilterBtn.addEventListener("click", function () {
    resetAllVisualizationFilters();
  });
}

function destroyChart(chart) {
  if (chart) {
    chart.destroy();
  }
}

function toNumber(value, defaultValue = 0) {
  if (value === null || value === undefined || value === "") return defaultValue;

  const numberValue = Number(value);

  return Number.isFinite(numberValue) ? numberValue : defaultValue;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function resetVisualizationDashboard() {
  if (visualizationSection) {
    visualizationSection.classList.add("is-empty");
  }

  if (visualizationDashboard) {
    visualizationDashboard.style.display = "none";
  }

  if (visualizationEmptyText) {
    visualizationEmptyText.style.display = "block";
    visualizationEmptyText.textContent = I18N.visualEmpty;
  }

  const visualMainGenre = document.getElementById("visualMainGenre");

  if (visualMainGenre) {
    visualMainGenre.textContent = I18N.allGenre;
  }

  const visualMainKey = document.getElementById("visualMainKey");

  if (visualMainKey) {
    visualMainKey.textContent = "-";
  }

  const selectedKeySongsList = document.getElementById("selectedKeySongsList");

  if (selectedKeySongsList) {
    selectedKeySongsList.textContent = "";

    const emptyText = document.createElement("p");

    emptyText.className = "empty-section-text";
    emptyText.textContent = I18N.noKeySelected;

    selectedKeySongsList.appendChild(emptyText);
  }

  const lowestNote = document.getElementById("visualLowestNote");
  const highestNote = document.getElementById("visualHighestNote");
  const rangeOctaves = document.getElementById("visualRangeOctaves");
  const rangeFill = document.getElementById("visualVocalRangeFill");
  const rangeText = document.getElementById("visualVocalRangeText");
  const startMarker = document.getElementById("visualRangeStartMarker");
  const endMarker = document.getElementById("visualRangeEndMarker");

  if (lowestNote) lowestNote.textContent = "-";
  if (highestNote) highestNote.textContent = "-";
  if (rangeOctaves) rangeOctaves.textContent = "-";

  if (rangeFill) {
    rangeFill.style.left = "0%";
    rangeFill.style.width = "0%";
  }

  if (startMarker) startMarker.style.left = "0%";
  if (endMarker) endMarker.style.left = "0%";
  if (rangeText) rangeText.textContent = I18N.vocalRangeNoData;

  updateVisualizationFilterState(I18N.filterAll, "all", 0);

  buildPianoKeyboard(null, null);

  destroyChart(songDnaChart);
  destroyChart(genreDistributionChart);
  destroyChart(keyDistributionChart);
  destroyChart(instrumentChart);
  destroyChart(analysisTimeChart);

  songDnaChart = null;
  genreDistributionChart = null;
  keyDistributionChart = null;
  instrumentChart = null;
  analysisTimeChart = null;
}

function getAllTracks(result) {
  if (!result || !Array.isArray(result.results)) {
    return [];
  }

  return result.results;
}

function getAudioList(tracks) {
  return tracks
    .map(function (track) {
      return track.original_audio_analysis || {};
    })
    .filter(function (audio) {
      return Object.keys(audio).length > 0;
    });
}

function getAverageValue(list, key) {
  const values = list
    .map(function (item) {
      return toNumber(item[key], null);
    })
    .filter(function (value) {
      return value !== null && Number.isFinite(value);
    });

  if (values.length === 0) {
    return 0;
  }

  const sum = values.reduce(function (total, value) {
    return total + value;
  }, 0);

  return sum / values.length;
}

function updateVisualizationFilterState(
  label = I18N.filterAll,
  filterType = "all",
  trackCount = 0
) {
  const isAllFilter = filterType === "all";

  const hasGenreFilter =
    activeGenreLabel &&
    activeGenreLabel !== I18N.allGenre;

  if (visualCurrentFilter) {
    if (isAllFilter) {
      visualCurrentFilter.textContent = I18N.allTracks;
    } else if (filterType === "genre") {
      visualCurrentFilter.textContent =
        I18N.filterGenreLabel + " · " + label;
    } else if (filterType === "key") {
      visualCurrentFilter.textContent = hasGenreFilter
        ? I18N.filterGenreLabel + " · " + activeGenreLabel +
          " / " + I18N.filterKeyLabel + " · " + label
        : I18N.filterKeyLabel + " · " + label;
    } else if (filterType === "note") {
      visualCurrentFilter.textContent = hasGenreFilter
        ? I18N.filterGenreLabel + " · " + activeGenreLabel +
          " / " + I18N.filterVocalNoteLabel + " · " + label
        : I18N.filterVocalNoteLabel + " · " + label;
    } else {
      visualCurrentFilter.textContent = label;
    }
  }

  if (visualFilterSummary) {
    if (isAllFilter) {
      visualFilterSummary.textContent = I18N.filterSummaryAll;
    } else if (filterType === "genre") {
      visualFilterSummary.textContent = i18nTemplate(
        I18N.filterGenreSummaryTemplate,
        {
          genre: label,
          count: trackCount
        }
      );
    } else if (filterType === "key") {
      visualFilterSummary.textContent = hasGenreFilter
        ? i18nTemplate(
            I18N.filterGenreKeySummaryTemplate,
            {
              genre: activeGenreLabel,
              key: label,
              count: trackCount
            }
          )
        : i18nTemplate(
            I18N.filterKeySummaryTemplate,
            {
              key: label,
              count: trackCount
            }
          );
    } else if (filterType === "note") {
      visualFilterSummary.textContent = hasGenreFilter
        ? i18nTemplate(
            I18N.filterGenreNoteSummaryTemplate,
            {
              genre: activeGenreLabel,
              note: label,
              count: trackCount
            }
          )
        : i18nTemplate(
            I18N.filterNoteSummaryTemplate,
            {
              note: label,
              count: trackCount
            }
          );
    } else {
      visualFilterSummary.textContent = i18nTemplate(
        I18N.filterCountSummaryTemplate,
        {
          count: trackCount
        }
      );
    }
  }

  if (resetVisualizationFilterBtn) {
    resetVisualizationFilterBtn.disabled = isAllFilter;

    resetVisualizationFilterBtn.classList.toggle(
      "is-active",
      !isAllFilter
    );
  }
}

function resetAllVisualizationFilters() {
  const tracks = getAllTracks(latestAnalysisResult);

  if (!tracks.length) {
    return;
  }

  selectedVocalNoteMidi = null;
  activeGenreLabel = I18N.allGenre;
  activeGenreTracks = null;

  const visualMainGenre = document.getElementById("visualMainGenre");
  const visualMainKey = document.getElementById("visualMainKey");

  if (visualMainGenre) {
    visualMainGenre.textContent = I18N.allGenre;
  }

  if (visualMainKey) {
    visualMainKey.textContent = I18N.filterAll;
  }

  renderGenreDistributionChartForAllTracks(tracks);
  renderKeyDistributionChartForAllTracks(tracks);
  applyDashboardTrackScope(tracks, I18N.filterAll, "all");
}

function applyGenreFilter(genreTracks, genreLabel) {
  const safeTracks = Array.isArray(genreTracks) ? genreTracks : [];

  activeGenreLabel = genreLabel || I18N.allGenre;
  activeGenreTracks = safeTracks;
  selectedVocalNoteMidi = null;

  const visualMainGenre = document.getElementById("visualMainGenre");
  const visualMainKey = document.getElementById("visualMainKey");

  if (visualMainGenre) {
    visualMainGenre.textContent = activeGenreLabel;
  }

  if (visualMainKey) {
    visualMainKey.textContent = I18N.filterAll;
  }

  renderKeyDistributionChartForAllTracks(safeTracks);
  applyDashboardTrackScope(safeTracks, activeGenreLabel, "genre");
}

function renderVisualizationDashboard(result) {
  const tracks = getAllTracks(result);

  if (!tracks.length || !visualizationDashboard) {
    return;
  }

  if (visualizationSection) {
    visualizationSection.classList.remove("is-empty");
  }

  if (visualizationEmptyText) {
    visualizationEmptyText.style.display = "none";
  }

  visualizationDashboard.style.display = "block";

  renderGenreDistributionChartForAllTracks(tracks);
  renderKeyDistributionChartForAllTracks(tracks);
  applyDashboardTrackScope(tracks, I18N.filterAll, "all");
}

function renderGenreDistributionChartForAllTracks(tracks) {
  const canvas = document.getElementById("genreDistributionChart");
  const visualMainGenre = document.getElementById("visualMainGenre");

  if (!canvas || typeof Chart === "undefined") {
    return;
  }

  destroyChart(genreDistributionChart);

  const genreCountMap = {};
  const genreTrackMap = {};

  tracks.forEach(function (track) {
    const audio = track.original_audio_analysis || {};
    const genre = audio.genre || "Unknown";

    genreCountMap[genre] = (genreCountMap[genre] || 0) + 1;

    if (!genreTrackMap[genre]) {
      genreTrackMap[genre] = [];
    }

    genreTrackMap[genre].push(track);
  });

  const totalTracks = tracks.length;

  const genreDistribution = Object.keys(genreCountMap)
    .map(function (genre) {
      return {
        genre: genre,
        count: genreCountMap[genre],
        percentage: Number(
          ((genreCountMap[genre] / totalTracks) * 100).toFixed(1)
        ),
        tracks: genreTrackMap[genre] || []
      };
    })
    .sort(function (a, b) {
      return b.count - a.count;
    });

  if (visualMainGenre) {
    visualMainGenre.textContent = I18N.allGenre;
  }

  genreDistributionChart = new Chart(canvas, {
    type: "doughnut",

    data: {
      labels: genreDistribution.map(function (item) {
        return item.genre + " (" + item.percentage + "%)";
      }),

      datasets: [
        {
          label: "Genre Distribution",

          data: genreDistribution.map(function (item) {
            return item.count;
          }),

          borderWidth: 1
        }
      ]
    },

    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "62%",

      onClick: function (event, elements) {
        if (!elements.length) return;

        const clickedIndex = elements[0].index;
        const selectedItem = genreDistribution[clickedIndex];

        applyGenreFilter(selectedItem.tracks, selectedItem.genre);
      },

      onHover: function (event, elements) {
        event.native.target.style.cursor =
          elements.length ? "pointer" : "default";
      },

      plugins: {
        legend: {
          display: true,
          position: "bottom",

          onClick: function (event, legendItem) {
            const clickedIndex = legendItem.index;
            const selectedItem = genreDistribution[clickedIndex];

            applyGenreFilter(selectedItem.tracks, selectedItem.genre);
          }
        },

        tooltip: {
          callbacks: {
            label: function (context) {
              const item = genreDistribution[context.dataIndex];

              return item.genre +
                ": " +
                item.count +
                " tracks / " +
                item.percentage +
                "%";
            }
          }
        }
      }
    }
  });
}

function renderSongDnaChartForAllTracks(tracks) {
  const canvas = document.getElementById("songDnaChart");

  if (!canvas || typeof Chart === "undefined") {
    return;
  }

  destroyChart(songDnaChart);

  const audioList = getAudioList(tracks);

  const avgEnergy = clamp(
    getAverageValue(audioList, "energy_score"),
    0,
    100
  );

  const avgDanceability = clamp(
    getAverageValue(audioList, "danceability_value"),
    0,
    100
  );

  const avgBrightness = clamp(
    (getAverageValue(audioList, "spectral_centroid_value") / 4000) * 100,
    0,
    100
  );

  const avgDynamics = clamp(
    (getAverageValue(audioList, "dynamic_range_value") / 30) * 100,
    0,
    100
  );

  const avgClarity = clamp(
    (getAverageValue(
      audioList,
      "harmonic_to_noise_ratio_value"
    ) / 20) * 100,
    0,
    100
  );

  songDnaChart = new Chart(canvas, {
    type: "radar",

    data: {
      labels: [
        I18N.songDnaEnergy,
        I18N.songDnaDanceability,
        I18N.songDnaBrightness,
        I18N.songDnaDynamics,
        I18N.songDnaClarity
      ],

      datasets: [
        {
          label: I18N.songDnaAverage,

          data: [
            Math.round(avgEnergy),
            Math.round(avgDanceability),
            Math.round(avgBrightness),
            Math.round(avgDynamics),
            Math.round(avgClarity)
          ],

          borderWidth: 2,
          pointRadius: 4
        }
      ]
    },

    options: {
      responsive: true,
      maintainAspectRatio: false,

      scales: {
        r: {
          min: 0,
          max: 100,

          ticks: {
            stepSize: 20
          }
        }
      },

      plugins: {
        legend: {
          display: false
        }
      }
    }
  });
}

function renderKeyDistributionChartForAllTracks(tracks) {
  const canvas = document.getElementById("keyDistributionChart");
  const visualMainKey = document.getElementById("visualMainKey");

  if (!canvas || typeof Chart === "undefined") {
    return;
  }

  destroyChart(keyDistributionChart);

  const keyCountMap = {};
  const keyTrackMap = {};

  tracks.forEach(function (track) {
    const audio = track.original_audio_analysis || {};
    const key = audio.key || "Unknown";

    keyCountMap[key] = (keyCountMap[key] || 0) + 1;

    if (!keyTrackMap[key]) {
      keyTrackMap[key] = [];
    }

    keyTrackMap[key].push(track);
  });

  const totalTracks = tracks.length;

  const keyDistribution = Object.keys(keyCountMap)
    .map(function (key) {
      return {
        key: key,
        count: keyCountMap[key],
        percentage: Number(
          ((keyCountMap[key] / totalTracks) * 100).toFixed(1)
        ),
        tracks: keyTrackMap[key] || []
      };
    })
    .sort(function (a, b) {
      return b.count - a.count;
    });

  if (visualMainKey) {
    visualMainKey.textContent = I18N.filterAll;
  }

  keyDistributionChart = new Chart(canvas, {
    type: "pie",

    data: {
      labels: keyDistribution.map(function (item) {
        return item.key + " (" + item.percentage + "%)";
      }),

      datasets: [
        {
          label: "Key Distribution",

          data: keyDistribution.map(function (item) {
            return item.count;
          }),

          borderWidth: 1
        }
      ]
    },

    options: {
      responsive: true,
      maintainAspectRatio: false,

      onClick: function (event, elements) {
        if (!elements.length) return;

        const clickedIndex = elements[0].index;
        const selectedItem = keyDistribution[clickedIndex];

        if (visualMainKey) {
          visualMainKey.textContent = selectedItem.key;
        }

        applyDashboardTrackScope(
          selectedItem.tracks,
          selectedItem.key,
          "key"
        );
      },

      plugins: {
        legend: {
          display: true,
          position: "bottom",

          onClick: function (event, legendItem) {
            const clickedIndex = legendItem.index;
            const selectedItem = keyDistribution[clickedIndex];

            if (visualMainKey) {
              visualMainKey.textContent = selectedItem.key;
            }

            applyDashboardTrackScope(
              selectedItem.tracks,
              selectedItem.key,
              "key"
            );
          }
        },

        tooltip: {
          callbacks: {
            label: function (context) {
              const item = keyDistribution[context.dataIndex];

              return item.key +
                ": " +
                item.count +
                " tracks / " +
                item.percentage +
                "%";
            }
          }
        }
      }
    }
  });
}

function renderInstrumentChartForAllTracks(tracks) {
  const canvas = document.getElementById("instrumentChart");

  if (!canvas || typeof Chart === "undefined") {
    return;
  }

  destroyChart(instrumentChart);

  const instrumentMap = {};

  tracks.forEach(function (track) {
    const instruments =
      track.background_instrument_analysis || {};

    const list = Array.isArray(instruments.instruments)
      ? instruments.instruments
      : [];

    list.forEach(function (item) {
      const name = item.instrument || "Unknown";
      const percentage = toNumber(item.percentage);

      if (!instrumentMap[name]) {
        instrumentMap[name] = {
          total: 0,
          count: 0
        };
      }

      instrumentMap[name].total += percentage;
      instrumentMap[name].count += 1;
    });
  });

  const instrumentDistribution = Object.keys(instrumentMap)
    .map(function (name) {
      return {
        instrument: name,

        percentage: Number(
          (
            instrumentMap[name].total /
            instrumentMap[name].count
          ).toFixed(1)
        )
      };
    })
    .sort(function (a, b) {
      return b.percentage - a.percentage;
    })
    .slice(0, 6);

  const labels = instrumentDistribution.length
    ? instrumentDistribution.map(function (item) {
        return item.instrument;
      })
    : ["No data"];

  const values = instrumentDistribution.length
    ? instrumentDistribution.map(function (item) {
        return item.percentage;
      })
    : [0];

  instrumentChart = new Chart(canvas, {
    type: "bar",

    data: {
      labels: labels,

      datasets: [
        {
          label: "Average instrument confidence",
          data: values,
          borderWidth: 1,
          borderRadius: 8
        }
      ]
    },

    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,

      scales: {
        x: {
          beginAtZero: true,
          max: 100
        }
      },

      plugins: {
        legend: {
          display: false
        },

        tooltip: {
          callbacks: {
            label: function (context) {
              return context.raw + "% average";
            }
          }
        }
      }
    }
  });
}

function getFirstPitchValue(pitch, keys) {
  if (!pitch) return null;

  for (const key of keys) {
    const value = pitch[key];

    if (
      value !== null &&
      value !== undefined &&
      value !== "" &&
      value !== "-"
    ) {
      return value;
    }
  }

  return null;
}

function noteToMidi(note) {
  if (note === null || note === undefined) return null;

  const normalizedNote = String(note)
    .trim()
    .normalize("NFKC")
    .replace(/[♯＃]/g, "#")
    .replace(/[♭]/g, "b")
    .replace(/\s+/g, "");

  const match = normalizedNote.match(/([A-Ga-g])([#b]?)(-?\d+)/);

  if (!match) return null;

  const noteName = match[1].toUpperCase();
  const accidental = match[2];
  const octave = Number(match[3]);

  if (!Number.isFinite(octave)) return null;

  const baseMap = {
    C: 0,
    D: 2,
    E: 4,
    F: 5,
    G: 7,
    A: 9,
    B: 11
  };

  let semitone = baseMap[noteName];

  if (accidental === "#") semitone += 1;
  if (accidental === "b") semitone -= 1;

  return (octave + 1) * 12 + semitone;
}

function pitchHzToMidi(value) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return null;
  }

  const cleanedValue = String(value)
    .replace(/,/g, "")
    .replace(/[^0-9.\-]/g, "");

  const frequency = Number(cleanedValue);

  if (!Number.isFinite(frequency) || frequency <= 0) {
    return null;
  }

  return Math.round(
    69 +
    12 *
    (
      Math.log(frequency / 440) /
      Math.log(2)
    )
  );
}

function getPitchMidi(pitch, noteKeys, hzKeys) {
  const noteValue = getFirstPitchValue(pitch, noteKeys);
  const midiFromNote = noteToMidi(noteValue);

  if (midiFromNote !== null) {
    return midiFromNote;
  }

  const hzValue = getFirstPitchValue(pitch, hzKeys);

  return pitchHzToMidi(hzValue);
}

function midiToNote(midi) {
  const names = [
    "C",
    "C#",
    "D",
    "D#",
    "E",
    "F",
    "F#",
    "G",
    "G#",
    "A",
    "A#",
    "B"
  ];

  const name = names[midi % 12];
  const octave = Math.floor(midi / 12) - 1;

  return name + octave;
}

function isBlackKey(midi) {
  return midiToNote(midi).includes("#");
}

function hexToRgb(hex) {
  const cleanHex = hex.replace("#", "");
  const value = parseInt(cleanHex, 16);

  return {
    r: (value >> 16) & 255,
    g: (value >> 8) & 255,
    b: value & 255
  };
}

function mixColor(colorA, colorB, amount) {
  const a = hexToRgb(colorA);
  const b = hexToRgb(colorB);

  const r = Math.round(
    a.r + (b.r - a.r) * amount
  );

  const g = Math.round(
    a.g + (b.g - a.g) * amount
  );

  const bValue = Math.round(
    a.b + (b.b - a.b) * amount
  );

  return `rgb(${r}, ${g}, ${bValue})`;
}

function getRangeGradientColor(position) {
  const blue = "#5367f5";
  const sky = "#18a9e6";
  const purple = "#8b5cf6";
  const pink = "#ec4899";

  if (position <= 0.35) {
    return mixColor(
      blue,
      sky,
      position / 0.35
    );
  }

  if (position <= 0.68) {
    return mixColor(
      sky,
      purple,
      (position - 0.35) / 0.33
    );
  }

  return mixColor(
    purple,
    pink,
    (position - 0.68) / 0.32
  );
}

function buildPianoKeyboard(
  lowMidi,
  highMidi,
  trackScope = [],
  scopeLabel = "All"
) {
  const keyboard =
    document.getElementById("visualPianoKeyboard");

  if (!keyboard) return;

  keyboard.textContent = "";

  const safeTrackScope = Array.isArray(trackScope)
    ? trackScope
    : [];

  const whiteKeys = [];
  const blackKeys = [];

  for (
    let midi = PIANO_MIN_MIDI;
    midi <= PIANO_MAX_MIDI;
    midi++
  ) {
    if (isBlackKey(midi)) {
      blackKeys.push(midi);
    } else {
      whiteKeys.push(midi);
    }
  }

  const whiteKeyIndexMap = {};

  whiteKeys.forEach(function (midi, index) {
    whiteKeyIndexMap[midi] = index;
  });

  function decoratePianoKey(key, midi, inRange) {
    const noteName = midiToNote(midi);

    key.dataset.note = noteName;
    key.dataset.midi = String(midi);

    if (inRange) {
      key.classList.add("is-in-range");

      if (safeTrackScope.length > 0) {
        key.classList.add("is-clickable-note");

        key.title = i18nTemplate(
          I18N.noteSongListDescTemplate,
          {
            note: noteName
          }
        );

        key.addEventListener("click", function () {
          handleVocalNoteClick(
            midi,
            safeTrackScope,
            scopeLabel
          );
        });
      }
    }

    if (selectedVocalNoteMidi === midi) {
      key.classList.add("is-selected-note");
    }
  }

  whiteKeys.forEach(function (midi) {
    const key = document.createElement("div");

    const inRange =
      lowMidi !== null &&
      highMidi !== null &&
      midi >= lowMidi &&
      midi <= highMidi;

    key.className = "piano-key piano-white-key";

    decoratePianoKey(key, midi, inRange);

    if (inRange) {
      const position =
        (midi - lowMidi) /
        Math.max(highMidi - lowMidi, 1);

      const color =
        getRangeGradientColor(position);

      key.style.background =
        `linear-gradient(180deg, ${color} 0%, ` +
        `${color} 72%, rgba(255,255,255,0.92) 100%)`;

      key.style.borderColor = color;
    }

    keyboard.appendChild(key);
  });

  blackKeys.forEach(function (midi) {
    let previousWhiteMidi = midi - 1;

    while (
      previousWhiteMidi >= PIANO_MIN_MIDI &&
      isBlackKey(previousWhiteMidi)
    ) {
      previousWhiteMidi -= 1;
    }

    const previousWhiteIndex =
      whiteKeyIndexMap[previousWhiteMidi];

    if (previousWhiteIndex === undefined) return;

    const key = document.createElement("div");

    const inRange =
      lowMidi !== null &&
      highMidi !== null &&
      midi >= lowMidi &&
      midi <= highMidi;

    key.className = "piano-key piano-black-key";

    decoratePianoKey(key, midi, inRange);

    key.style.left =
      `calc(${previousWhiteIndex + 1} * ` +
      `(100% / ${whiteKeys.length}) - ` +
      `((100% / ${whiteKeys.length}) * 0.33))`;

    if (inRange) {
      const position =
        (midi - lowMidi) /
        Math.max(highMidi - lowMidi, 1);

      const color =
        getRangeGradientColor(position);

      key.style.background =
        `linear-gradient(180deg, #151827 0%, ${color} 100%)`;

      key.style.boxShadow =
        "0 8px 18px rgba(83, 103, 245, 0.28)";
    }

    keyboard.appendChild(key);
  });
}

function getTrackPitchRangeMidi(track) {
  const pitch =
    track?.vocal_pitch_analysis ||
    track?.pitch_range ||
    null;

  if (!pitch) {
    return null;
  }

  const lowMidi = getPitchMidi(
    pitch,
    [
      "lowest_note",
      "lowestNote",
      "low_note",
      "lowNote"
    ],
    [
      "lowest_pitch_hz",
      "lowestPitchHz",
      "lowest_pitch",
      "low_pitch_hz",
      "lowPitchHz"
    ]
  );

  const highMidi = getPitchMidi(
    pitch,
    [
      "highest_note",
      "highestNote",
      "high_note",
      "highNote"
    ],
    [
      "highest_pitch_hz",
      "highestPitchHz",
      "highest_pitch",
      "high_pitch_hz",
      "highPitchHz"
    ]
  );

  if (lowMidi === null || highMidi === null) {
    return null;
  }

  return {
    lowMidi: Math.min(lowMidi, highMidi),
    highMidi: Math.max(lowMidi, highMidi)
  };
}

function getTracksContainingVocalNote(
  tracks,
  selectedMidi
) {
  const safeTracks = Array.isArray(tracks)
    ? tracks
    : [];

  return safeTracks.filter(function (track) {
    const range = getTrackPitchRangeMidi(track);

    if (!range) {
      return false;
    }

    return (
      selectedMidi >= range.lowMidi &&
      selectedMidi <= range.highMidi
    );
  });
}

function setSelectedPianoNote(selectedMidi) {
  selectedVocalNoteMidi = selectedMidi;

  document
    .querySelectorAll(
      "#visualPianoKeyboard .piano-key"
    )
    .forEach(function (key) {
      const keyMidi = Number(key.dataset.midi);

      key.classList.toggle(
        "is-selected-note",
        keyMidi === selectedMidi
      );
    });
}

function applyDashboardTrackScope(
  tracks,
  label = I18N.filterAll,
  filterType = "all"
) {
  const safeTracks = Array.isArray(tracks)
    ? tracks
    : [];

  const visualMainGenre =
    document.getElementById("visualMainGenre");

  const visualMainKey =
    document.getElementById("visualMainKey");

  selectedVocalNoteMidi = null;

  if (filterType === "all") {
    activeGenreLabel = I18N.allGenre;
    activeGenreTracks = null;
  }

  if (visualMainGenre) {
    visualMainGenre.textContent =
      activeGenreLabel || I18N.allGenre;
  }

  if (visualMainKey) {
    visualMainKey.textContent =
      filterType === "key"
        ? label
        : I18N.filterAll;
  }

  updateVisualizationFilterState(
    label,
    filterType,
    safeTracks.length
  );

  renderVocalRangeVisualForAllTracks(
    safeTracks,
    label
  );

  renderSelectedKeySongsForAllTracks(
    safeTracks,
    label,
    filterType
  );

  renderSongDnaChartForAllTracks(safeTracks);
  renderInstrumentChartForAllTracks(safeTracks);
}

function handleVocalNoteClick(
  noteMidi,
  trackScope,
  scopeLabel = "All"
) {
  const noteName = midiToNote(noteMidi);

  const matchedTracks =
    getTracksContainingVocalNote(
      trackScope,
      noteMidi
    );

  const rangeText =
    document.getElementById(
      "visualVocalRangeText"
    );

  setSelectedPianoNote(noteMidi);

  updateVisualizationFilterState(
    noteName,
    "note",
    matchedTracks.length
  );

  renderSelectedKeySongsForAllTracks(
    matchedTracks,
    noteName,
    "note"
  );

  renderSongDnaChartForAllTracks(matchedTracks);
  renderInstrumentChartForAllTracks(matchedTracks);

  if (rangeText) {
    rangeText.textContent = i18nTemplate(
      I18N.filterNoteSummaryTemplate,
      {
        note: noteName,
        count: matchedTracks.length
      }
    );
  }
}

function renderVocalRangeVisualForAllTracks(
  tracks,
  selectedKey = "All"
) {
  const lowestNote =
    document.getElementById("visualLowestNote");

  const highestNote =
    document.getElementById("visualHighestNote");

  const rangeOctaves =
    document.getElementById("visualRangeOctaves");

  const rangeFill =
    document.getElementById(
      "visualVocalRangeFill"
    );

  const rangeText =
    document.getElementById(
      "visualVocalRangeText"
    );

  const startMarker =
    document.getElementById(
      "visualRangeStartMarker"
    );

  const endMarker =
    document.getElementById(
      "visualRangeEndMarker"
    );

  const vocalRangeDesc =
    document.getElementById("vocalRangeDesc");

  if (
    !lowestNote ||
    !highestNote ||
    !rangeOctaves ||
    !rangeFill ||
    !rangeText
  ) {
    return;
  }

  const safeTracks = Array.isArray(tracks)
    ? tracks
    : [];

  const isAllKey =
    !selectedKey ||
    selectedKey === "All";

  const rangeTargetText = isAllKey
    ? I18N.allTracks
    : selectedKey + " Key";

  if (vocalRangeDesc) {
    vocalRangeDesc.textContent = isAllKey
      ? I18N.vocalRangeDesc
      : i18nTemplate(
          I18N.keySongListDescTemplate,
          {
            key: selectedKey
          }
        );
  }

  const pitchList = safeTracks
    .map(function (track) {
      return (
        track.vocal_pitch_analysis ||
        track.pitch_range ||
        null
      );
    })
    .filter(function (pitch) {
      return pitch !== null;
    });

  if (!pitchList.length) {
    lowestNote.textContent = "-";
    highestNote.textContent = "-";
    rangeOctaves.textContent = "-";

    rangeFill.style.left = "0%";
    rangeFill.style.width = "0%";

    if (startMarker) {
      startMarker.style.left = "0%";
    }

    if (endMarker) {
      endMarker.style.left = "0%";
    }

    buildPianoKeyboard(null, null);

    rangeText.textContent = i18nTemplate(
      I18N.vocalRangeNoScopeDataTemplate,
      {
        scope: rangeTargetText
      }
    );

    return;
  }

  const noteItems = safeTracks
    .map(function (track) {
      return getTrackPitchRangeMidi(track);
    })
    .filter(function (item) {
      return (
        item !== null &&
        Number.isFinite(item.lowMidi) &&
        Number.isFinite(item.highMidi)
      );
    });

  if (!noteItems.length) {
    lowestNote.textContent = "-";
    highestNote.textContent = "-";
    rangeOctaves.textContent = "-";

    rangeFill.style.left = "0%";
    rangeFill.style.width = "0%";

    if (startMarker) {
      startMarker.style.left = "0%";
    }

    if (endMarker) {
      endMarker.style.left = "0%";
    }

    buildPianoKeyboard(null, null);

    rangeText.textContent = i18nTemplate(
      I18N.vocalRangeUnavailableTemplate,
      {
        scope: rangeTargetText
      }
    );

    return;
  }

  const rawLowMidi = noteItems.reduce(
    function (lowest, item) {
      return item.lowMidi < lowest
        ? item.lowMidi
        : lowest;
    },
    noteItems[0].lowMidi
  );

  const rawHighMidi = noteItems.reduce(
    function (highest, item) {
      return item.highMidi > highest
        ? item.highMidi
        : highest;
    },
    noteItems[0].highMidi
  );

  if (
    rawHighMidi < PIANO_MIN_MIDI ||
    rawLowMidi > PIANO_MAX_MIDI
  ) {
    lowestNote.textContent =
      midiToNote(rawLowMidi);

    highestNote.textContent =
      midiToNote(rawHighMidi);

    rangeOctaves.textContent = "-";

    rangeFill.style.left = "0%";
    rangeFill.style.width = "0%";

    if (startMarker) {
      startMarker.style.left = "0%";
    }

    if (endMarker) {
      endMarker.style.left = "0%";
    }

    buildPianoKeyboard(null, null);

    rangeText.textContent = i18nTemplate(
      I18N.vocalRangeOutOfKeyboardTemplate,
      {
        scope: rangeTargetText
      }
    );

    return;
  }

  const lowMidi = clamp(
    rawLowMidi,
    PIANO_MIN_MIDI,
    PIANO_MAX_MIDI
  );

  const highMidi = clamp(
    rawHighMidi,
    PIANO_MIN_MIDI,
    PIANO_MAX_MIDI
  );

  const lowNote = midiToNote(lowMidi);
  const highNote = midiToNote(highMidi);

  const octaveValue =
    ((highMidi - lowMidi) / 12).toFixed(2);

  const octaveText =
    octaveValue.replace(/\.00$/, "") +
    " " +
    I18N.octavesUnit;

  lowestNote.textContent = lowNote;
  highestNote.textContent = highNote;
  rangeOctaves.textContent = octaveText;

  const totalKeys =
    PIANO_MAX_MIDI -
    PIANO_MIN_MIDI +
    1;

  const leftPercent =
    (
      (lowMidi - PIANO_MIN_MIDI) /
      totalKeys
    ) * 100;

  const widthPercent =
    (
      (highMidi - lowMidi + 1) /
      totalKeys
    ) * 100;

  const endPercent =
    leftPercent + widthPercent;

  rangeFill.style.left =
    leftPercent + "%";

  rangeFill.style.width =
    widthPercent + "%";

  if (startMarker) {
    startMarker.style.left =
      leftPercent + "%";
  }

  if (endMarker) {
    endMarker.style.left =
      endPercent + "%";
  }

  buildPianoKeyboard(
    lowMidi,
    highMidi,
    safeTracks,
    rangeTargetText
  );

  rangeText.textContent = i18nTemplate(
    I18N.songVocalRangeTemplate,
    {
      range:
        rangeTargetText +
        " · " +
        lowNote +
        " ~ " +
        highNote +
        " · " +
        octaveText
    }
  );
}

function renderSelectedKeySongsForAllTracks(
  tracks,
  selectedLabel = "All",
  filterType = "all"
) {
  const list =
    document.getElementById(
      "selectedKeySongsList"
    );

  const desc =
    document.getElementById(
      "selectedKeySongsDesc"
    );

  if (!list) return;

  const safeTracks = Array.isArray(tracks)
    ? tracks
    : [];

  const displayLabel =
    selectedLabel || "All";

  if (desc) {
    if (filterType === "note") {
      desc.textContent = i18nTemplate(
        I18N.noteSongListDescTemplate,
        {
          note: displayLabel
        }
      );
    } else if (filterType === "genre") {
      desc.textContent = i18nTemplate(
        I18N.genreSongListDescTemplate,
        {
          genre: displayLabel
        }
      );
    } else if (filterType === "key") {
      desc.textContent = i18nTemplate(
        I18N.keySongListDescTemplate,
        {
          key: displayLabel
        }
      );
    } else {
      desc.textContent =
        I18N.allSongListDesc;
    }
  }

  list.textContent = "";

  if (!safeTracks.length) {
    const emptyMessage =
      I18N.noKeySelected;

    const emptyText =
      document.createElement("p");

    emptyText.className =
      "empty-section-text";

    emptyText.textContent =
      emptyMessage;

    list.appendChild(emptyText);

    return;
  }

  safeTracks.forEach(function (track, index) {
    const fileInfo =
      track.file_info || {};

    const audio =
      track.original_audio_analysis || {};

    const pitch =
      track.vocal_pitch_analysis ||
      track.pitch_range ||
      null;

    const rangeMidi =
      getTrackPitchRangeMidi(track);

    const fileName =
      fileInfo.file_name || "Unknown";

    const key =
      audio.key || "-";

    const tempo =
      audio.tempo
        ? audio.tempo + " bpm"
        : "-";

    const genre =
      audio.genre || "-";

    const rangeText = pitch
      ? displayValue(
          pitch.lowest_note ||
          (
            rangeMidi
              ? midiToNote(rangeMidi.lowMidi)
              : "-"
          )
        ) +
        " ~ " +
        displayValue(
          pitch.highest_note ||
          (
            rangeMidi
              ? midiToNote(rangeMidi.highMidi)
              : "-"
          )
        )
      : I18N.vocalRangeNoData;

    const item =
      document.createElement("div");

    item.className =
      "selected-key-song-item";

    const body =
      document.createElement("div");

    const title =
      document.createElement("strong");

    const meta =
      document.createElement("p");

    const range =
      document.createElement("p");

    title.textContent =
      (index + 1) +
      ". " +
      fileName;

    meta.textContent = i18nTemplate(
      I18N.songMetaTemplate,
      {
        key: key,
        tempo: tempo,
        genre: genre
      }
    );

    range.textContent = i18nTemplate(
      I18N.songVocalRangeTemplate,
      {
        range: rangeText
      }
    );

    body.appendChild(title);
    body.appendChild(meta);
    body.appendChild(range);

    item.appendChild(body);
    list.appendChild(item);
  });
}

buildPianoKeyboard(null, null);