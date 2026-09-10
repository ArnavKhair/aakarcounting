import { VehicleAIWS } from '/shared/js/ws.js';

const statusText = document.getElementById('status-text');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const etaText = document.getElementById('eta-text');
const framesText = document.getElementById('frames-text');
const fpsText = document.getElementById('fps-text');
const btnStop = document.getElementById('btn-stop');
const frameDisplay = document.getElementById('frame-display');
const framePlaceholder = document.getElementById('frame-placeholder');
const errorBanner = document.getElementById('error-banner');

function getUrlParams() {
  const params = new URLSearchParams(window.location.search);
  return { videoId: params.get('video_id') };
}

function pad(n) {
  return String(n).padStart(2, '0');
}

function formatEta(seconds) {
  if (seconds >= 3600) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `ETA: ${h}h ${pad(m)}m`;
  }
  if (seconds >= 60) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `ETA: ${m}m ${pad(s)}s`;
  }
  return `ETA: ${Math.round(seconds)}s`;
}

function showError(msg) {
  errorBanner.textContent = msg;
  errorBanner.classList.add('visible');
  console.error('[Processing]', msg);
  setTimeout(() => errorBanner.classList.remove('visible'), 8000);
}

const { videoId } = getUrlParams();
console.log('[Processing] video_id:', videoId);

if (!videoId) {
  showError('No video ID found. Redirecting...');
  setTimeout(() => { window.location.href = '../file-input/'; }, 2000);
} else {
  const ws = new VehicleAIWS();
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws`;
  console.log('[Processing] Connecting to', wsUrl);
  ws.connect(wsUrl);

  ws.on('_open', () => {
    console.log('[Processing] WS connected, sending start_processing');
    const annotations = JSON.parse(sessionStorage.getItem('annotations') || '[]');
    console.log('[Processing] Annotations:', annotations);
    ws.send('start_processing', {
      video_id: videoId,
      annotations: annotations,
    });
  });

  ws.on('status', (data) => {
    console.log('[Processing] Status:', data.text);
    statusText.textContent = data.text;
  });

  ws.on('progress', (data) => {
    const { frame, total, percent, fps, eta_seconds } = data;
    progressFill.style.width = percent + '%';
    progressText.textContent = `${percent}%`;
    framesText.textContent = `${frame.toLocaleString()} / ${total.toLocaleString()} frames`;
    fpsText.textContent = `${fps} fps`;
    etaText.textContent = formatEta(eta_seconds);
  });

  ws.on('frame', (data) => {
    frameDisplay.src = `data:image/jpeg;base64,${data}`;
    frameDisplay.classList.add('visible');
    framePlaceholder.classList.add('hidden');
  });

  ws.on('result', (data) => {
    console.log('[Processing] Result received');
    sessionStorage.setItem('results', JSON.stringify(data));
    window.location.href = `../results/?video_id=${videoId}`;
  });

  ws.on('error', (data) => {
    showError('Error: ' + data.message);
    statusText.textContent = 'Error';
    btnStop.disabled = true;
  });

  ws.on('_close', () => {
    if (statusText.textContent !== 'Complete!') {
      showError('Connection lost. Processing may have been interrupted.');
      btnStop.disabled = true;
    }
  });

  btnStop.addEventListener('click', () => {
    ws.send('stop_processing');
    statusText.textContent = 'Stopping...';
    btnStop.disabled = true;
  });

  window.addEventListener('beforeunload', () => {
    ws.send('stop_processing');
    ws.close();
  });
}
