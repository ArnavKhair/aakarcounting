const modelName = document.getElementById('model-name');
const metricCrossings = document.getElementById('metric-crossings');
const metricRoads = document.getElementById('metric-roads');
const statFps = document.getElementById('stat-fps');
const statTime = document.getElementById('stat-time');
const statFrames = document.getElementById('stat-frames');
const statDetections = document.getElementById('stat-detections');
const roadSections = document.getElementById('road-sections');
const infoGrid = document.getElementById('info-grid');
const errorBanner = document.getElementById('error-banner');

function getUrlParams() {
  const params = new URLSearchParams(window.location.search);
  return {
    videoId: params.get('video_id'),
  };
}

function showError(msg) {
  errorBanner.textContent = msg;
  errorBanner.classList.add('visible');
  setTimeout(() => errorBanner.classList.remove('visible'), 8000);
}

function formatDuration(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m ${s}s`;
}

function classDisplayName(cls) {
  return cls.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

const { videoId } = getUrlParams();

if (!videoId) {
  showError('No video ID found. Redirecting...');
  setTimeout(() => { window.location.href = '../file-input/'; }, 2000);
} else {
  let results = null;
  const cached = sessionStorage.getItem('results');
  if (cached) {
    try {
      results = JSON.parse(cached);
    } catch (e) {
      results = null;
    }
  }

  if (results) {
    renderResults(results);
  } else {
    fetch(`/api/results/${videoId}`)
      .then(res => {
        if (!res.ok) throw new Error('Results not found');
        return res.json();
      })
      .then(data => {
        results = data;
        renderResults(data);
      })
      .catch(err => {
        showError('Failed to load results: ' + err.message);
      });
  }

  const btnDownloadSummary = document.getElementById('btn-download-summary');
  const btnDownloadCrossings = document.getElementById('btn-download-crossings');
  const btnDownloadJson = document.getElementById('btn-download-json');
  const btnNewVideo = document.getElementById('btn-new-video');

  btnDownloadSummary.addEventListener('click', () => {
    window.location.href = `/api/download/${videoId}/vehicle_summary.csv`;
  });

  btnDownloadCrossings.addEventListener('click', () => {
    if (results && results.models) {
      const modelNames = Object.keys(results.models);
      if (modelNames.length > 0) {
        const csvPath = results.models[modelNames[0]].crossings_csv_path;
        const filename = csvPath.split('/').pop();
        window.location.href = `/api/download/${videoId}/${filename}`;
      }
    }
  });

  btnDownloadJson.addEventListener('click', () => {
    window.location.href = `/api/download/${videoId}/summary.json`;
  });

  btnNewVideo.addEventListener('click', () => {
    sessionStorage.clear();
    window.location.href = '../file-input/';
  });
}

function renderResults(results) {
  const modelNames = Object.keys(results.models || {});
  if (modelNames.length === 0) {
    showError('No model results found');
    return;
  }

  const modelNameStr = modelNames[0];
  const data = results.models[modelNameStr];

  modelName.textContent = modelNameStr;

  // Key metrics
  metricCrossings.textContent = data.total_crossings || 0;
  const roadCounts = data.road_counts || {};
  metricRoads.textContent = Object.keys(roadCounts).length;

  // Processing stats
  statFps.textContent = (data.processing_fps || 0).toFixed(1);
  statTime.textContent = formatDuration(data.elapsed_seconds || 0);
  statFrames.textContent = (data.total_frames || 0).toLocaleString();
  statDetections.textContent = (data.total_detections || 0).toLocaleString();

  // Per-road stacked sections
  roadSections.innerHTML = '';
  const roadEntries = Object.entries(roadCounts);

  if (roadEntries.length === 0) {
    // Fallback: show aggregate data if no per-road data
    const section = createRoadSection('All Roads', {
      total: data.total_crossings || 0,
      by_type: data.vehicle_counts || {},
      by_canonical: data.canonical_counts || {},
    }, 0);
    roadSections.appendChild(section);
  } else {
    roadEntries.forEach(([label, roadData], index) => {
      const section = createRoadSection(label, roadData, index);
      roadSections.appendChild(section);
    });
  }

  // Video info
  const infoItems = [
    { label: 'Video', value: results.video_name || 'N/A' },
    { label: 'Resolution', value: results.resolution || 'N/A' },
    { label: 'FPS', value: (results.fps || 0).toFixed(1) },
    { label: 'Total Frames', value: (results.total_frames || 0).toLocaleString() },
    { label: 'Counting Method', value: results.counting_method || 'N/A' },
  ];

  infoGrid.innerHTML = '';
  for (const item of infoItems) {
    const div = document.createElement('div');
    div.className = 'info-item';
    div.innerHTML = `
      <div class="info-item__label">${item.label}</div>
      <div class="info-item__value">${item.value}</div>
    `;
    infoGrid.appendChild(div);
  }
}

function createRoadSection(label, roadData, index) {
  const section = document.createElement('div');
  section.className = 'road-section';

  const colors = [
    '#2563eb', '#16a34a', '#ea580c', '#9333ea',
    '#dc2626', '#0891b2', '#ca8a04', '#e11d48',
  ];
  const color = colors[index % colors.length];

  const total = roadData.total || 0;
  const byType = roadData.by_type || {};

  section.innerHTML = `
    <div class="road-section__header">
      <div class="road-section__name" style="color: ${color}">${label}</div>
      <div>
        <span class="road-section__total">${total}</span>
        <span class="road-section__total-label">crossings</span>
      </div>
    </div>
    <div class="road-section__body">
      <div class="road-section__chart">
        <canvas id="chart-road-${index}"></canvas>
      </div>
      <table class="road-table">
        <thead>
          <tr>
            <th>Vehicle Type</th>
            <th>Count</th>
          </tr>
        </thead>
        <tbody>
          ${Object.entries(byType).map(([cls, count]) => `
            <tr>
              <td>${classDisplayName(cls)}</td>
              <td>${count}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;

  // Render chart after DOM insertion
  requestAnimationFrame(() => {
    const canvas = document.getElementById(`chart-road-${index}`);
    if (canvas) {
      renderRoadChart(canvas, byType, color);
    }
  });

  return section;
}

function renderRoadChart(canvas, byType, baseColor) {
  const ctx = canvas.getContext('2d');
  const labels = Object.keys(byType).map(classDisplayName);
  const values = Object.values(byType);

  // Generate color shades from base color
  const colors = values.map((_, i) => {
    const opacity = 1 - (i * 0.15);
    return baseColor + Math.round(opacity * 255).toString(16).padStart(2, '0');
  });

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Count',
        data: values,
        backgroundColor: colors,
        borderRadius: 4,
        maxBarThickness: 60,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(26, 26, 26, 0.9)',
          titleFont: { family: "'Inter', sans-serif", size: 13 },
          bodyFont: { family: "'Inter', sans-serif", size: 12 },
          padding: 10,
          cornerRadius: 6,
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            stepSize: 1,
            font: { family: "'Inter', sans-serif", size: 12 },
          },
          grid: { color: '#f0f0f0' },
        },
        x: {
          ticks: {
            font: { family: "'Inter', sans-serif", size: 11 },
          },
          grid: { display: false },
        },
      },
    },
  });
}
