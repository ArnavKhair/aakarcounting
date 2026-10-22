import { VehicleAIWS } from '/shared/js/ws.js';

const statusText = document.getElementById('status-text');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const etaText = document.getElementById('eta-text');
const framesText = document.getElementById('frames-text');
const fpsText = document.getElementById('fps-text');
const btnStop = document.getElementById('btn-stop');
const btnPause = document.getElementById('btn-pause');
const btnPauseLabel = document.getElementById('btn-pause-label');
const btnPauseIcon = document.getElementById('btn-pause-icon');
const frameDisplay = document.getElementById('frame-display');
const framePlaceholder = document.getElementById('frame-placeholder');
const errorBanner = document.getElementById('error-banner');

// Two bars is pause; a triangle is resume. The stop button keeps a circle
// with a minus, so it never reads as "hold the position".
const ICON_PAUSE = '<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>';
const ICON_PLAY = '<polygon points="6 4 20 12 6 20 6 4"/>';

let paused = false;

function setPaused(next) {
  paused = next;
  btnPauseLabel.textContent = next ? 'Resume Processing' : 'Pause Processing';
  btnPauseIcon.innerHTML = next ? ICON_PLAY : ICON_PAUSE;
}

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

function showQuicksavedToast(frame, total) {
  let toast = document.getElementById('quicksaved-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'quicksaved-toast';
    toast.className = 'quicksaved-toast';
    toast.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
        <polyline points="22 4 12 14.01 9 11.01"/>
      </svg>
      <span>Quicksaved at ${frame.toLocaleString()} / ${total.toLocaleString()} frames</span>
    `;
    document.body.appendChild(toast);
  }
  toast.classList.add('visible');
  clearTimeout(toast._hideTimer);
  toast._hideTimer = setTimeout(() => {
    toast.classList.remove('visible');
  }, 3000);
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

  let started = false;

  ws.on('_open', () => {
    console.log('[Processing] WS connected, sending start_processing');
    const annotations = JSON.parse(sessionStorage.getItem('annotations') || '[]');
    const videoMeta = JSON.parse(sessionStorage.getItem('video_meta') || '{}');
    console.log('[Processing] Annotations:', annotations);

    const message = {
      video_id: videoId,
      annotations: annotations,
    };

    // Only the first connection carries the frame to resume from. A
    // reconnect re-sends this message, and the frame it was given is stale
    // by then -- the server picks up from its own latest checkpoint
    // instead, which is further along.
    if (!started && videoMeta.resume_frame) {
      message.resume_frame = videoMeta.resume_frame;
    }
    started = true;

    ws.send('start_processing', message);
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

  ws.on('quicksaved', (data) => {
    console.log('[Processing] Checkpoint saved:', data);
    showQuicksavedToast(data.frame, data.total);
  });

  ws.on('paused', (data) => {
    console.log('[Processing] Paused at', data);
    setPaused(true);
    statusText.textContent = 'Paused';
  });

  ws.on('resumed', (data) => {
    console.log('[Processing] Resumed at', data);
    setPaused(false);
    statusText.textContent = 'Processing...';
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
    btnPause.disabled = true;
  });

  ws.on('_close', () => {
    if (statusText.textContent !== 'Complete!') {
      showError('Connection lost. Processing may have been interrupted.');
      btnStop.disabled = true;
      btnPause.disabled = true;
    }
  });

  btnStop.addEventListener('click', () => {
    ws.send('stop_processing');
    statusText.textContent = 'Stopping...';
    btnStop.disabled = true;
    btnPause.disabled = true;
  });

  btnPause.addEventListener('click', () => {
    if (paused) {
      ws.send('resume_processing');
      setPaused(false);
      statusText.textContent = 'Resuming...';
    } else {
      ws.send('pause_processing');
      setPaused(true);
      statusText.textContent = 'Pausing...';
    }
  });

  window.addEventListener('beforeunload', () => {
    ws.send('stop_processing');
    ws.close();
  });
}
