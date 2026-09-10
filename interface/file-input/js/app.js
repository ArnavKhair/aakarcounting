const btnSelect = document.getElementById('btn-select');
const fileInput = document.getElementById('file-input');
const uploadInfo = document.getElementById('upload-info');
const infoFilename = document.getElementById('info-filename');
const infoMeta = document.getElementById('info-meta');
const btnContinue = document.getElementById('btn-continue');
const uploadProgress = document.getElementById('upload-progress');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const errorBanner = document.getElementById('error-banner');

let selectedFile = null;

function showError(msg) {
  errorBanner.textContent = msg;
  errorBanner.classList.add('visible');
  setTimeout(() => errorBanner.classList.remove('visible'), 8000);
}

function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

btnSelect.addEventListener('click', () => {
  fileInput.click();
});

fileInput.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;
  selectedFile = file;

  infoFilename.textContent = file.name;
  infoMeta.textContent = formatSize(file.size);
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

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText));
        } else {
          reject(new Error(xhr.responseText || 'Upload failed'));
        }
      };
      xhr.onerror = () => reject(new Error('Network error'));
      xhr.open('POST', '/upload');
      xhr.send(formData);
    });

    progressText.textContent = 'Upload complete!';
    progressFill.style.width = '100%';

    sessionStorage.setItem('video_id', result.video_id);
    sessionStorage.setItem('video_meta', JSON.stringify(result));

    setTimeout(() => {
      window.location.href = `../option1/?video_id=${result.video_id}&filename=${encodeURIComponent(result.filename)}`;
    }, 300);

  } catch (err) {
    showError('Upload failed: ' + err.message);
    uploadProgress.style.display = 'none';
    btnContinue.style.display = '';
  }
});
