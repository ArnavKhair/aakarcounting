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
const subtitle = document.getElementById('results-subtitle');
const categoryLegend = document.getElementById('category-legend');
const folderName = document.getElementById('folder-name');
const toast = document.getElementById('toast');

const DASH = '-';

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

function showToast(msg) {
  toast.textContent = msg;
  toast.classList.add('visible');
  clearTimeout(toast._hideTimer);
  toast._hideTimer = setTimeout(() => toast.classList.remove('visible'), 3000);
}

function formatDuration(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m ${s}s`;
}

function classDisplayName(cls) {
  return cls.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

// Road names and the video name are typed by the user, so they go into the
// page as text, never as markup.
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[ch]));
}

function formatProcessedAt(iso) {
  const date = iso ? new Date(iso) : null;
  if (!date || isNaN(date)) return '';
  const day = date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  const time = date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  return `${day}, ${time}`;
}

// navigator.clipboard only exists on localhost or https. The page can also be
// opened from another machine over a plain LAN address, where the older
// copy command is the only one there is.
async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (e) {
      // fall through to the older way
    }
  }
  const area = document.createElement('textarea');
  area.value = text;
  area.setAttribute('readonly', '');
  area.style.position = 'fixed';
  area.style.opacity = '0';
  document.body.appendChild(area);
  area.select();
  let ok = false;
  try {
    ok = document.execCommand('copy');
  } catch (e) {
    ok = false;
  }
  document.body.removeChild(area);
  return ok;
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
  // Results left over from another video are not this video's results.
  if (results && results.video_id && results.video_id !== videoId) {
    results = null;
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

  const download = kind => { window.location.href = `/api/download/${videoId}/${kind}`; };

  document.getElementById('btn-copy-whatsapp').addEventListener('click', async () => {
    if (!results || !results.share_text) {
      showError('The results are not loaded yet.');
      return;
    }
    if (await copyText(results.share_text)) {
      showToast('Copied. Paste it into a WhatsApp chat.');
    } else {
      showError('Could not copy. Your browser blocked access to the clipboard.');
    }
  });

  document.getElementById('btn-download-report').addEventListener('click', () => {
    if (results && results.report_error) {
      showError('The Excel report could not be written for this run: ' + results.report_error);
      return;
    }
    download('report');
  });

  document.getElementById('btn-open-folder').addEventListener('click', () => {
    fetch(`/api/open-folder/${videoId}`, { method: 'POST' })
      .then(res => {
        if (!res.ok) throw new Error('Folder not found');
        showToast('Opened the results folder on the computer running the software.');
      })
      .catch(err => showError('Could not open the folder: ' + err.message));
  });

  document.getElementById('btn-download-crossings').addEventListener('click', () => download('crossings'));
  document.getElementById('btn-download-json').addEventListener('click', () => download('summary'));

  document.getElementById('btn-new-video').addEventListener('click', () => {
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

  // Which video, and when
  subtitle.textContent = [results.video_name, formatProcessedAt(results.processed_at)]
    .filter(Boolean).join(' · ');
  folderName.textContent = results.results_folder
    ? `Saved in Final Results / ${results.results_folder}`
    : '';

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
  const headings = results.category_headings || {};

  if (roadEntries.length === 0) {
    // Fallback: show aggregate data if no per-road data
    const section = createRoadSection('All Roads', {
      total: data.total_crossings || 0,
      by_type: data.vehicle_counts || {},
      by_category: data.category_counts,
    }, 0, headings);
    roadSections.appendChild(section);
  } else {
    roadEntries.forEach(([label, roadData], index) => {
      const section = createRoadSection(label, roadData, index, headings);
      roadSections.appendChild(section);
    });
  }

  // What a dash means
  const legend = results.category_legend || [];
  categoryLegend.innerHTML = legend.length === 0 ? '' : `
    <div class="category-legend__title">${DASH} = not yet separated by the software. These vehicles are counted in another row:</div>
    <ul>${legend.map(line => `<li>${escapeHtml(line)}</li>`).join('')}</ul>
  `;

  // Video info
  const infoItems = [
    { label: 'Video', value: results.video_name || 'N/A' },
    { label: 'Processed on', value: formatProcessedAt(results.processed_at) || 'N/A' },
    { label: 'Video length', value: results.duration_seconds ? formatDuration(results.duration_seconds) : 'N/A' },
    { label: 'Resolution', value: results.resolution || 'N/A' },
    { label: 'FPS', value: (results.fps || 0).toFixed(1) },
    { label: 'Total Frames', value: (results.total_frames || 0).toLocaleString() },
    { label: 'Counting Method', value: results.counting_method || 'N/A' },
    { label: 'Software version', value: results.app_version || 'N/A' },
  ];

  infoGrid.innerHTML = '';
  for (const item of infoItems) {
    const div = document.createElement('div');
    div.className = 'info-item';
    div.innerHTML = `
      <div class="info-item__label">${escapeHtml(item.label)}</div>
      <div class="info-item__value">${escapeHtml(item.value)}</div>
    `;
    infoGrid.appendChild(div);
  }
}

// Rows for one road: Aakar's categories when the results carry them, the
// model's own types for results saved before v1.3.
function roadRows(roadData, headings) {
  const byCategory = roadData.by_category;
  if (byCategory) {
    return Object.entries(byCategory).map(([category, count]) => ({
      name: category,
      heading: headings[category] || category,
      count,
    }));
  }
  return Object.entries(roadData.by_type || {}).map(([cls, count]) => ({
    name: classDisplayName(cls),
    heading: classDisplayName(cls),
    count,
  }));
}

function createRoadSection(label, roadData, index, headings) {
  const section = document.createElement('div');
  section.className = 'road-section';

  const colors = [
    '#2563eb', '#16a34a', '#ea580c', '#9333ea',
    '#dc2626', '#0891b2', '#ca8a04', '#e11d48',
  ];
  const color = colors[index % colors.length];

  const total = roadData.total || 0;
  const rows = roadRows(roadData, headings);

  section.innerHTML = `
    <div class="road-section__header">
      <div class="road-section__name" style="color: ${color}">${escapeHtml(label)}</div>
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
            <th>Vehicle Category</th>
            <th>Count</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map(row => `
            <tr${row.count === null ? ' class="road-table__unsplit"' : ''}>
              <td>${escapeHtml(row.heading)}</td>
              <td>${row.count === null ? DASH : row.count}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;

  // The chart shows what was counted; rows with nothing in them only add
  // empty bars. Render after DOM insertion.
  const counted = rows.filter(row => row.count);
  requestAnimationFrame(() => {
    const canvas = document.getElementById(`chart-road-${index}`);
    if (canvas) {
      renderRoadChart(canvas, counted, color);
    }
  });

  return section;
}

function renderRoadChart(canvas, rows, baseColor) {
  const ctx = canvas.getContext('2d');
  const labels = rows.map(row => row.name);
  const values = rows.map(row => row.count);

  // Generate color shades from base color
  const colors = values.map((_, i) => {
    const opacity = Math.max(0.25, 1 - (i * 0.12));
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
            precision: 0,
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
