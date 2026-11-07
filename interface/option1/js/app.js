import { AppState, States } from './state.js';
import { AnnotationOverlay } from './canvas.js';
import { PenTool } from './pen-tool.js';
import { LineTool } from './line-tool.js';
import { centroid, distance, pointNearLineSegment } from './utils.js';

const VERTEX_THRESHOLD = 15;
const LINE_THRESHOLD = 10;

function getUrlParams() {
  const params = new URLSearchParams(window.location.search);
  return {
    videoId: params.get('video_id'),
    filename: params.get('filename'),
  };
}

class App {
  constructor() {
    this.state = new AppState();
    this.overlay = null;
    this.penTool = null;
    this.lineTool = null;
    this._cursorPos = null;
    this._animFrame = null;
    this._video = null;
    this._videoId = null;
  }

  async init() {
    const { videoId, filename } = getUrlParams();
    this._videoId = videoId;

    if (!videoId) {
      this._showError('No video selected. Redirecting...');
      setTimeout(() => { window.location.href = '../file-input/'; }, 2000);
      return;
    }

    this._video = document.getElementById('video-player');
    const canvas = document.getElementById('annotation-canvas');

    try {
      await this._loadVideo(this._video, videoId);
    } catch (err) {
      this._showError('Video failed to load: ' + err.message);
      console.error('Video load error:', err);
    }

    this._setupPlayPause();
    this.overlay = new AnnotationOverlay(canvas, this._video);
    this.penTool = new PenTool(this.state, this.overlay);
    this.lineTool = new LineTool(this.state, this.overlay);

    this._bindEvents();
    this._bindStateListeners();
    this._updateUI();
    this._startRenderLoop();
  }

  _loadVideo(video, videoId) {
    return new Promise((resolve, reject) => {
      let attempts = 0;
      const MAX_ATTEMPTS = 120;

      const tryLoad = () => {
        const timeout = setTimeout(() => {
          video.oncanplay = null;
          video.onerror = null;
          // A long video may still be having its preview made. Wait for it
          // and try again rather than giving up on the upload.
          if (attempts < MAX_ATTEMPTS) {
            attempts++;
            this._waitForPreview(videoId).then(tryLoad).catch(reject);
          } else {
            reject(new Error('Load timed out'));
          }
        }, 30000);

        video.oncanplay = () => {
          clearTimeout(timeout);
          resolve();
        };

        video.onerror = () => {
          clearTimeout(timeout);
          if (attempts < MAX_ATTEMPTS) {
            attempts++;
            this._waitForPreview(videoId).then(tryLoad).catch(reject);
          } else {
            const err = video.error;
            reject(new Error(`Media error ${err?.code}: ${err?.message || 'unknown'}`));
          }
        };

        video.src = `/api/video/${videoId}`;
        video.load();
      };

      tryLoad();
    });
  }

  async _waitForPreview(videoId) {
    try {
      const resp = await fetch(`/api/video/${videoId}/status`);
      if (!resp.ok) return;
      const data = await resp.json();
      if (data.preview_ready) {
        await new Promise(r => setTimeout(r, 200));
        return;
      }
      // Still being made. Say so, then look again shortly.
      this._showError('Preparing the video for preview...');
      await new Promise(r => setTimeout(r, 2000));
    } catch (e) {
      await new Promise(r => setTimeout(r, 2000));
    }
  }

  _setupPlayPause() {
    const btn = document.getElementById('btn-play-pause');
    const updateIcon = () => {
      if (this._video.paused) {
        btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>';
      } else {
        btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>';
      }
    };

    btn.addEventListener('click', () => {
      if (this._video.paused) {
        this._video.play();
      } else {
        this._video.pause();
      }
    });

    this._video.addEventListener('play', updateIcon);
    this._video.addEventListener('pause', updateIcon);
    updateIcon();
  }

  _showError(msg) {
    const banner = document.getElementById('error-banner');
    banner.textContent = msg;
    banner.classList.add('visible');
    setTimeout(() => banner.classList.remove('visible'), 8000);
  }

  _positionLabelPanel() {
    const road = this.state.getActiveRoad();
    if (!road || road.polygon.length < 3) return;

    const panel = document.getElementById('label-panel');
    const workspace = document.querySelector('.workspace');
    const cent = centroid(road.polygon);
    const screen = this.overlay.canvasToScreen(cent.x, cent.y);

    const panelW = panel.offsetWidth || 240;
    const panelH = panel.offsetHeight || 120;
    const pad = 12;

    const wsRect = workspace.getBoundingClientRect();

    let x = screen.x - wsRect.left;
    let y = screen.y - wsRect.top;

    const minX = pad + panelW / 2;
    const maxX = wsRect.width - pad - panelW / 2;
    const minY = pad + panelH / 2;
    const maxY = wsRect.height - pad - panelH / 2;

    x = Math.max(minX, Math.min(maxX, x));
    y = Math.max(minY, Math.min(maxY, y));

    panel.style.left = x + 'px';
    panel.style.top = y + 'px';
  }

  _handleEraseClick(pos) {
    for (let ri = this.state.roads.length - 1; ri >= 0; ri--) {
      const road = this.state.roads[ri];
      if (!road.isClosed) continue;

      if (road.line) {
        if (pointNearLineSegment(pos, road.line.start, road.line.end, LINE_THRESHOLD)) {
          this.state.removeLine(ri);
          return;
        }
      }

      for (let vi = 0; vi < road.polygon.length; vi++) {
        if (distance(pos, road.polygon[vi]) <= VERTEX_THRESHOLD) {
          this.state.removeVertex(ri, vi);
          return;
        }
      }
    }
  }

  _collectAnnotations() {
    // Points are sent as fractions (0-1) of the video frame box, not pixels.
    // The preview the user drew on may be a smaller copy of the source, so
    // its pixels mean nothing to the server; a fraction of the frame is the
    // same place at any resolution. The server scales it to the real frames.
    const norm = (p) => this.overlay.toNormalized(p);
    return this.state.roads
      .filter(r => r.isClosed)
      .map(r => ({
        polygon: r.polygon.map(norm),
        line: r.line ? { start: norm(r.line.start), end: norm(r.line.end) } : null,
        label: r.label,
        normalized: true,
      }));
  }

  /**
   * Show or hide the processing view. The image comes from the server, which
   * draws the counting lines with the same code a real run uses, so the
   * preview matches the processing screen 1:1.
   */
  _showModelPreview(show) {
    const img = document.getElementById('model-preview');
    const badge = document.getElementById('model-preview-badge');
    img.classList.toggle('visible', show);
    badge.classList.toggle('visible', show);

    if (!this._previewBound) {
      this._previewBound = true;
      // Refresh on pause and after a seek, and keep refreshing while playing.
      this._video.addEventListener('pause', () => this._refreshModelPreview());
      this._video.addEventListener('seeked', () => this._refreshModelPreview());
      this._video.addEventListener('play', () => this._previewLoop());
    }

    if (show) {
      this._refreshModelPreview();
    }
  }

  _previewLoop() {
    if (this.state.state !== States.PREVIEW || this._video.paused) return;
    this._refreshModelPreview().then(() => {
      setTimeout(() => this._previewLoop(), 150);
    });
  }

  async _refreshModelPreview() {
    if (this.state.state !== States.PREVIEW) return;
    if (this._previewInFlight) return this._previewInFlight;

    const badge = document.getElementById('model-preview-badge');
    this._previewInFlight = (async () => {
      try {
        const resp = await fetch(`/api/line-preview/${this._videoId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            annotations: this._collectAnnotations(),
            time: this._video.currentTime || 0,
          }),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const blob = await resp.blob();
        const img = document.getElementById('model-preview');
        const old = img.src;
        img.src = URL.createObjectURL(blob);
        if (old && old.startsWith('blob:')) URL.revokeObjectURL(old);
        badge.textContent = 'Processing view';
      } catch (err) {
        console.error('[Preview] could not render processing view:', err);
        badge.textContent = 'Processing view unavailable';
      } finally {
        this._previewInFlight = null;
      }
    })();
    return this._previewInFlight;
  }

  // ── Debug snapshot ───────────────────────────────────────────────────────
  // Records where clicks land and, on Preview, saves the drawing canvas next
  // to the server's processing view (see /api/debug/snapshot), so a mismatch
  // on any machine can be inspected from files in the project's debug folder.

  _recordClick(e, pos) {
    const r = this.overlay.canvas.getBoundingClientRect();
    this._clicks = this._clicks || [];
    this._clicks.push({
      state: this.state.state,
      client: [e.clientX, e.clientY],
      offset: [e.offsetX, e.offsetY],
      canvasRect: [r.left, r.top, r.width, r.height],
      videoPx: [pos.x, pos.y],
      normalized: this.overlay.toNormalized(pos),
    });
    if (this._clicks.length > 50) this._clicks.shift();
  }

  _rectOf(el) {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return [r.left, r.top, r.width, r.height];
  }

  _sendDebugSnapshot() {
    try {
      const v = this._video;
      const c = this.overlay.canvas;
      const cs = getComputedStyle(c);
      const client = {
        userAgent: navigator.userAgent,
        window: [window.innerWidth, window.innerHeight],
        screen: [screen.width, screen.height],
        devicePixelRatio: window.devicePixelRatio,
        visualViewportScale: window.visualViewport ? window.visualViewport.scale : null,
        video: { intrinsic: [v.videoWidth, v.videoHeight], rect: this._rectOf(v),
                 currentTime: v.currentTime, src: v.currentSrc },
        canvas: { buffer: [c.width, c.height], rect: this._rectOf(c),
                  cssSize: [cs.width, cs.height], transform: cs.transform },
        frameBox: { rect: this._rectOf(document.getElementById('video-frame')),
                    style: document.getElementById('video-frame').getAttribute('style') },
        container: this._rectOf(document.getElementById('annotation-container')),
        workspace: this._rectOf(document.querySelector('.workspace')),
        stylesheetHasTopLeft: [...document.styleSheets].some(ss => {
          try { return [...ss.cssRules].some(r => r.selectorText === '.video-frame' && r.style.left === '0px'); }
          catch (_) { return false; }
        }),
      };
      let canvasPng = null;
      try { canvasPng = c.toDataURL('image/png'); } catch (err) { client.canvasExportError = String(err); }

      fetch(`/api/debug/snapshot/${this._videoId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client,
          clicks: this._clicks || [],
          annotations: this._collectAnnotations(),
          time: v.currentTime || 0,
          canvas_png: canvasPng,
        }),
      }).catch(err => console.error('[Debug] snapshot failed:', err));
    } catch (err) {
      console.error('[Debug] snapshot failed:', err);
    }
  }

  _startProcessing() {
    const annotations = this._collectAnnotations();
    if (annotations.length === 0) {
      this._showError('No annotations to process. Draw at least one road with a counting line.');
      return;
    }

    sessionStorage.setItem('annotations', JSON.stringify(annotations));
    window.location.href = `../processing/?video_id=${this._videoId}`;
  }

  _bindEvents() {
    const canvas = this.overlay.canvas;

    canvas.addEventListener('mousemove', (e) => {
      const pos = this.overlay.screenToCanvas(e.clientX, e.clientY);
      this._cursorPos = pos;

      if (this.state.state === States.DRAWING_POLYGON) {
        this.penTool.onMouseMove(pos);
      } else if (this.state.state === States.DRAWING_LINE) {
        this.lineTool.onMouseMove(pos);
      }
    });

    canvas.addEventListener('click', (e) => {
      const pos = this.overlay.screenToCanvas(e.clientX, e.clientY);
      this._recordClick(e, pos);

      if (this.state.state === States.DRAWING_POLYGON) {
        this.penTool.onClick(pos);
      } else if (this.state.state === States.DRAWING_LINE) {
        this.lineTool.onClick(pos);
      } else if (this.state.state === States.EDITING) {
        this._handleEraseClick(pos);
      } else if (this.state.state === States.IDLE && this.state.hasRoads) {
        const road = this.state.setActiveRoadByPoint(pos.x, pos.y);
        if (road) {
          this.state.transition(States.POLYGON_COMPLETE);
        }
      }
    });

    canvas.addEventListener('mouseleave', () => {
      this._cursorPos = null;
      if (this.lineTool) this.lineTool.onMouseMove(null);
    });

    document.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT') return;

      const s = this.state.state;

      if (s === States.DRAWING_POLYGON) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
          e.preventDefault();
          this.state.removeLastVertex();
        }
        if (e.key === 'Escape') {
          this.state.transition(States.IDLE);
          this.penTool.reset();
        }
      } else if (s === States.DRAWING_LINE) {
        this.lineTool.onKeyDown(e);
      } else if (s === States.IDLE) {
        if ((e.key === 'p' || e.key === 'P') && !document.getElementById('btn-pen-tool').classList.contains('active')) {
          document.getElementById('btn-pen-tool').click();
        }
        if (e.key === ' ') {
          e.preventDefault();
          document.getElementById('btn-play-pause').click();
        }
      } else if (s === States.POLYGON_COMPLETE) {
        if ((e.key === 'l' || e.key === 'L') && !document.getElementById('btn-line-tool').classList.contains('active')) {
          document.getElementById('btn-line-tool').click();
        }
        if (e.key === ' ') {
          e.preventDefault();
          document.getElementById('btn-play-pause').click();
        }
      } else if (s === States.PREVIEW) {
        if (e.key === ' ') {
          e.preventDefault();
          document.getElementById('btn-play-pause').click();
        }
      } else if (s === States.EDITING) {
        if (e.key === 'e' || e.key === 'E') {
          document.getElementById('btn-erase-tool').click();
        }
        if (e.key === 'Escape') {
          this.state.transition(States.PREVIEW);
        }
      }
    });

    document.getElementById('btn-pen-tool').addEventListener('click', () => {
      if (this.state.state === States.IDLE) {
        this._video.pause();
        this.state.addRoad();
        this.state.transition(States.DRAWING_POLYGON);
      }
    });

    document.getElementById('btn-line-tool').addEventListener('click', () => {
      if (this.state.state === States.POLYGON_COMPLETE) {
        this._video.pause();
        this.state.transition(States.DRAWING_LINE);
      }
    });

    document.getElementById('btn-save-label').addEventListener('click', () => {
      const input = document.getElementById('label-input');
      this.state.setLabel(input.value.trim() || 'Unnamed Road');
      this.state.transition(States.POLYGON_COMPLETE);
    });

    document.getElementById('label-input').addEventListener('keydown', (e) => {
      e.stopPropagation();
      if (e.key === 'Enter') {
        document.getElementById('btn-save-label').click();
      }
    });

    document.getElementById('btn-mark-more').addEventListener('click', () => {
      this.state.transition(States.IDLE);
    });

    document.getElementById('btn-preview').addEventListener('click', () => {
      this.state.transition(States.PREVIEW);
    });

    document.getElementById('btn-start-processing').addEventListener('click', () => {
      this._startProcessing();
    });

    document.getElementById('btn-make-changes').addEventListener('click', () => {
      this.state.transition(States.EDITING);
    });

    document.getElementById('btn-start-processing-final').addEventListener('click', () => {
      this._startProcessing();
    });
  }

  _bindStateListeners() {
    this.state.on('stateChange', (data) => {
      this._updateUI();

      if (data.next === States.LABELING) {
        this._positionLabelPanel();
      }

      if (data.next === States.PREVIEW) {
        this._video.pause();
        this._sendDebugSnapshot();
        this._showModelPreview(true);
      } else if (data.prev === States.PREVIEW) {
        this._video.pause();
        this._showModelPreview(false);
      }

      const container = document.getElementById('annotation-container');
      const penBtn = document.getElementById('btn-pen-tool');
      const lineBtn = document.getElementById('btn-line-tool');

      if (data.next === States.IDLE) {
        if (!penBtn.classList.contains('active')) {
          penBtn.click();
        }
        container.setAttribute('data-mode', 'drawing-polygon');
      } else if (data.next === States.POLYGON_COMPLETE) {
        const activeRoad = this.state.getActiveRoad();
        if (activeRoad && !activeRoad.line) {
          if (!lineBtn.classList.contains('active')) {
            lineBtn.click();
          }
          container.setAttribute('data-mode', 'drawing-line');
        } else {
          container.setAttribute('data-mode', 'idle');
        }
      } else if (data.next === States.DRAWING_POLYGON) {
        container.setAttribute('data-mode', 'drawing-polygon');
      } else if (data.next === States.DRAWING_LINE) {
        container.setAttribute('data-mode', 'drawing-line');
      } else if (data.next === States.EDITING) {
        container.setAttribute('data-mode', 'editing');
      } else {
        container.setAttribute('data-mode', 'idle');
      }
    });
  }

  _updateUI() {
    const s = this.state.state;
    const instruction = this.state.instruction;

    document.getElementById('instruction-icon').innerHTML = this._getIcon(instruction.icon);
    document.getElementById('instruction-text').textContent = instruction.text;

    const penBtn = document.getElementById('btn-pen-tool');
    const lineBtn = document.getElementById('btn-line-tool');
    const eraseBtn = document.getElementById('btn-erase-tool');

    const showPen = s === States.IDLE || s === States.DRAWING_POLYGON;
    const activeRoad = this.state.getActiveRoad();
    const hasLine = activeRoad && activeRoad.line;
    const showLine = s === States.POLYGON_COMPLETE && !hasLine;
    const showErase = s === States.EDITING;

    penBtn.style.display = showPen ? '' : 'none';
    penBtn.classList.toggle('active', s === States.DRAWING_POLYGON);
    lineBtn.style.display = showLine ? '' : 'none';
    lineBtn.classList.toggle('active', s === States.DRAWING_LINE);
    eraseBtn.style.display = showErase ? '' : 'none';
    eraseBtn.classList.toggle('active', s === States.EDITING);

    const labelPanel = document.getElementById('label-panel');
    const actionBar = document.getElementById('action-bar');

    const showLabel = s === States.LABELING;
    labelPanel.classList.toggle('visible', showLabel);
    if (showLabel) {
      this._positionLabelPanel();
    }

    actionBar.classList.toggle('visible', s === States.PREVIEW);

    const markMoreBtn = document.getElementById('btn-mark-more');
    const previewBtn = document.getElementById('btn-preview');
    const showNextCTAs = (s === States.POLYGON_COMPLETE && hasLine) || s === States.EDITING;
    markMoreBtn.style.display = showNextCTAs ? '' : 'none';
    previewBtn.style.display = showNextCTAs ? '' : 'none';

    const completeScreen = document.getElementById('complete-screen');
    completeScreen.classList.toggle('visible', s === States.COMPLETE);
  }

  _getIcon(name) {
    const icons = {
      'mouse-pointer-click': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 9l5 12 1.774-5.226L21 14 9 9z"/><path d="m16.5 12.5 5-5-1.414-1.414L15 9.086l-5-5L8.586 5.5 14 11z"/><path d="M2 2l7.586 7.586"/><circle cx="11" cy="11" r="2"/></svg>',
      'pen-tool': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19l7-7 3 3-7 7-3-3z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/><path d="M2 2l7.586 7.586"/><circle cx="11" cy="11" r="2"/></svg>',
      'check-circle': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
      'type': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 7 4 4 20 4 20 7"/><line x1="9" y1="20" x2="15" y2="20"/><line x1="12" y1="4" x2="12" y2="20"/></svg>',
      'minus': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/></svg>',
      'eye': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>',
      'eraser': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m7 21-4.3-4.3c-1-1-1-2.5 0-3.4l9.6-9.6c1-1 2.5-1 3.4 0l5.6 5.6c1 1 1 2.5 0 3.4L13 21"/><path d="M22 21H7"/><path d="m5 11 9 9"/></svg>',
      'check': '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
    };
    return icons[name] || '';
  }

  _startRenderLoop() {
    const loop = () => {
      if (this.overlay) {
        this.overlay.render(this.state, this._cursorPos);
        this.penTool.render();
        this.lineTool.render();
      }
      this._animFrame = requestAnimationFrame(loop);
    };
    loop();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const app = new App();
  app.init().catch(err => {
    console.error('Init failed:', err);
    const el = document.getElementById('error-banner');
    el.textContent = 'Fatal: ' + err.message;
    el.classList.add('visible');
  });
});
