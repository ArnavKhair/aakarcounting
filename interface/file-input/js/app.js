const btnSelect = document.getElementById('btn-select');
const fileInput = document.getElementById('file-input');
const uploadInfo = document.getElementById('upload-info');
const infoFilename = document.getElementById('info-filename');
const infoMeta = document.getElementById('info-meta');
const infoEstimate = document.getElementById('info-estimate');
const uploadWarning = document.getElementById('upload-warning');
const warningText = document.getElementById('warning-text');
const btnContinue = document.getElementById('btn-continue');
const uploadProgress = document.getElementById('upload-progress');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const errorBanner = document.getElementById('error-banner');
const resumeDialog = document.getElementById('resume-dialog');
const resumeMessage = document.getElementById('resume-message');
const btnResume = document.getElementById('btn-resume');
const btnStartFresh = document.getElementById('btn-start-fresh');
const versionEl = document.getElementById('version');

const PROCESSING_FPS = 10;
const RECOMMENDED_SIZE_BYTES = 2 * 1024 * 1024 * 1024;
const LARGE_FILE_SIZE_BYTES = 2 * 1024 * 1024 * 1024;

let selectedFile = null;
let uploadedVideoId = null;

function showError(msg) {
  errorBanner.textContent = msg;
  errorBanner.classList.add('visible');
  setTimeout(() => errorBanner.classList.remove('visible'), 8000);
}

async function loadVersion() {
  try {
    const resp = await fetch('/api/version');
    if (!resp.ok) return;
    const data = await resp.json();
    if (data.version) versionEl.textContent = data.version;
  } catch (e) {
    console.warn('Failed to load version:', e);
  }
}

loadVersion();

function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function formatDuration(seconds) {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function estimateDuration(file) {
  const bitrate = 5 * 1024 * 1024;
  return file.size / bitrate;
}

function formatEta(seconds) {
  if (seconds < 60) return `~${Math.round(seconds)}s`;
  if (seconds < 3600) return `~${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `~${h}h ${m}m`;
}

async function checkForCheckpoint(videoId) {
  try {
    const resp = await fetch(`/api/checkpoint/${videoId}`);
    if (resp.ok) {
      const data = await resp.json();
      return data;
    }
  } catch (e) {
    console.warn('Failed to check checkpoint:', e);
  }
  return { exists: false };
}

function navigateToAnnotation(videoId, filename, resumeFrame = null) {
  const meta = JSON.parse(sessionStorage.getItem('video_meta') || '{}');
  if (resumeFrame !== null) {
    meta.resume_frame = resumeFrame;
    sessionStorage.setItem('video_meta', JSON.stringify(meta));
  }
  window.location.href = `../option1/?video_id=${videoId}&filename=${encodeURIComponent(filename)}`;
}

btnSelect.addEventListener('click', () => {
  fileInput.click();
});

fileInput.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;
  selectedFile = file;

  const estDuration = estimateDuration(file);
  const estProcessingTime = estDuration / (30 / PROCESSING_FPS);

  infoFilename.textContent = file.name;
  infoMeta.textContent = `${formatSize(file.size)} — est. ${formatDuration(estDuration)} video`;
  infoEstimate.textContent = `Est. processing time: ${formatEta(estProcessingTime)}`;
  infoEstimate.style.display = '';

  if (file.size > LARGE_FILE_SIZE_BYTES) {
    warningText.textContent = 'Large file detected. Processing may take several hours. Results are auto-saved and will resume if interrupted.';
    uploadWarning.style.display = '';
  } else {
    uploadWarning.style.display = 'none';
  }

  uploadInfo.style.display = '';
  btnContinue.style.display = '';
  btnSelect.style.display = 'none';
});

btnContinue.addEventListener('click', async () => {
  if (!selectedFile) return;

  btnContinue.style.display = 'none';
  uploadProgress.style.display = '';
  progressText.textContent = 'Uploading...';

  const formData = new FormData();
  formData.append('file', selectedFile);

  try {
    const result = await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          const pct = (e.loaded / e.total) * 100;
          progressFill.style.width = pct + '%';
          progressText.textContent = `Uploading... ${Math.round(pct)}%`;
        }
      });

      xhr.upload.addEventListener('load', () => {
        progressFill.style.width = '100%';
        progressText.textContent = 'Preparing video for preview...';
      });

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText));
        } else {
          let message = xhr.responseText || 'Upload failed';
          try {
            message = JSON.parse(xhr.responseText).detail || message;
          } catch (e) {}
          reject(new Error(message));
        }
      };
      xhr.onerror = () => reject(new Error('Network error'));
      xhr.open('POST', '/upload');
      xhr.send(formData);
    });

    progressText.textContent = 'Upload complete!';
    progressFill.style.width = '100%';

    uploadedVideoId = result.video_id;
    sessionStorage.setItem('video_id', result.video_id);
    sessionStorage.setItem('video_meta', JSON.stringify(result));

    // Check for existing checkpoint
    const checkpoint = await checkForCheckpoint(result.video_id);
    if (checkpoint.exists) {
      const estFrame = checkpoint.frame_num.toLocaleString();
      resumeMessage.textContent = `A previous processing session was interrupted at frame ${estFrame}. Resume from where it left off?`;
      resumeDialog.style.display = '';
    } else {
      setTimeout(() => {
        navigateToAnnotation(result.video_id, result.filename);
      }, 300);
    }

  } catch (err) {
    showError('Upload failed: ' + err.message);
    uploadProgress.style.display = 'none';
    btnContinue.style.display = '';
  }
});

btnResume.addEventListener('click', () => {
  if (!uploadedVideoId) return;
  const meta = JSON.parse(sessionStorage.getItem('video_meta') || '{}');
  const filename = meta.filename || 'video.mp4';
  // Fetch checkpoint to get frame number
  checkForCheckpoint(uploadedVideoId).then((checkpoint) => {
    navigateToAnnotation(uploadedVideoId, filename, checkpoint.frame_num);
  });
});

btnStartFresh.addEventListener('click', async () => {
  if (!uploadedVideoId) return;
  // Delete checkpoint by calling a fresh start (server will handle it)
  const meta = JSON.parse(sessionStorage.getItem('video_meta') || '{}');
  const filename = meta.filename || 'video.mp4';
  navigateToAnnotation(uploadedVideoId, filename);
});
