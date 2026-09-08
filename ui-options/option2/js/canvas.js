import { distance, centroid, pointNearLineSegment } from './utils.js';

const CLOSE_THRESHOLD = 20;

if (!CanvasRenderingContext2D.prototype.roundRect) {
  CanvasRenderingContext2D.prototype.roundRect = function (x, y, w, h, r) {
    if (typeof r === 'number') r = [r, r, r, r];
    const [tl, tr, br, bl] = r;
    this.moveTo(x + tl, y);
    this.lineTo(x + w - tr, y);
    this.quadraticCurveTo(x + w, y, x + w, y + tr);
    this.lineTo(x + w, y + h - br);
    this.quadraticCurveTo(x + w, y + h, x + w - br, y + h);
    this.lineTo(x + bl, y + h);
    this.quadraticCurveTo(x, y + h, x, y + h - bl);
    this.lineTo(x, y + tl);
    this.quadraticCurveTo(x, y, x + tl, y);
    this.closePath();
    return this;
  };
}

export class AnnotationOverlay {
  constructor(canvas, video) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.video = video;

    this._syncSize();
  }

  _syncSize() {
    const vw = this.video.videoWidth || 1280;
    const vh = this.video.videoHeight || 720;
    const dpr = window.devicePixelRatio || 1;

    this.canvas.width = vw * dpr;
    this.canvas.height = vh * dpr;
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  syncSize() {
    this._syncSize();
  }

  screenToCanvas(screenX, screenY) {
    const rect = this.canvas.getBoundingClientRect();
    const vw = this.video.videoWidth || 1280;
    const vh = this.video.videoHeight || 720;
    const displayW = rect.width;
    const displayH = rect.height;

    if (displayW === 0 || displayH === 0) return { x: 0, y: 0 };

    return {
      x: ((screenX - rect.left) / displayW) * vw,
      y: ((screenY - rect.top) / displayH) * vh,
    };
  }

  canvasToScreen(cx, cy) {
    const rect = this.canvas.getBoundingClientRect();
    const vw = this.video.videoWidth || 1280;
    const vh = this.video.videoHeight || 720;
    const displayW = rect.width;
    const displayH = rect.height;

    return {
      x: rect.left + (cx / vw) * displayW,
      y: rect.top + (cy / vh) * displayH,
    };
  }

  clear() {
    const vw = this.video.videoWidth || 1280;
    const vh = this.video.videoHeight || 720;
    this.ctx.clearRect(0, 0, vw, vh);
  }

  drawDimOverlay() {
    const vw = this.video.videoWidth || 1280;
    const vh = this.video.videoHeight || 720;
    this.ctx.fillStyle = 'rgba(0, 0, 0, 0.35)';
    this.ctx.fillRect(0, 0, vw, vh);
  }

  drawPolygon(points, { fill, stroke, lineWidth = 2, dash = null, vertexRadius = 4 } = {}) {
    if (points.length < 1) return;

    if (points.length >= 2) {
      this.ctx.beginPath();
      this.ctx.moveTo(points[0].x, points[0].y);
      for (let i = 1; i < points.length; i++) {
        this.ctx.lineTo(points[i].x, points[i].y);
      }
      this.ctx.closePath();

      if (dash) this.ctx.setLineDash(dash);

      if (fill) {
        this.ctx.fillStyle = fill;
        this.ctx.fill();
      }

      if (stroke) {
        this.ctx.strokeStyle = stroke;
        this.ctx.lineWidth = lineWidth;
        this.ctx.stroke();
      }

      this.ctx.setLineDash([]);
    }

    for (const p of points) {
      this.ctx.beginPath();
      this.ctx.arc(p.x, p.y, vertexRadius, 0, Math.PI * 2);
      this.ctx.fillStyle = stroke || '#2563eb';
      this.ctx.fill();
      this.ctx.strokeStyle = '#ffffff';
      this.ctx.lineWidth = 1.5;
      this.ctx.stroke();
    }
  }

  drawClosingLine(points, cursorPos, { stroke = '#2563eb', lineWidth = 1.5, dash = [6, 4] } = {}) {
    if (points.length < 1 || !cursorPos) return;
    const last = points[points.length - 1];

    this.ctx.beginPath();
    this.ctx.moveTo(last.x, last.y);
    this.ctx.lineTo(cursorPos.x, cursorPos.y);
    this.ctx.strokeStyle = stroke;
    this.ctx.lineWidth = lineWidth;
    this.ctx.setLineDash(dash);
    this.ctx.stroke();
    this.ctx.setLineDash([]);

    for (const p of points) {
      if (distance(cursorPos, p) <= CLOSE_THRESHOLD) {
        this.ctx.beginPath();
        this.ctx.arc(p.x, p.y, 12, 0, Math.PI * 2);
        this.ctx.strokeStyle = stroke;
        this.ctx.lineWidth = 2;
        this.ctx.stroke();
        break;
      }
    }
  }

  drawLine(line, { stroke = '#dc2626', lineWidth = 3, handleRadius = 6 } = {}) {
    if (!line) return;

    this.ctx.beginPath();
    this.ctx.moveTo(line.start.x, line.start.y);
    this.ctx.lineTo(line.end.x, line.end.y);
    this.ctx.strokeStyle = stroke;
    this.ctx.lineWidth = lineWidth;
    this.ctx.stroke();

    for (const p of [line.start, line.end]) {
      this.ctx.beginPath();
      this.ctx.arc(p.x, p.y, handleRadius, 0, Math.PI * 2);
      this.ctx.fillStyle = stroke;
      this.ctx.fill();
      this.ctx.strokeStyle = '#ffffff';
      this.ctx.lineWidth = 2;
      this.ctx.stroke();
    }
  }

  drawLabel(text, position, { bg = 'rgba(26,26,26,0.85)', color = '#ffffff', fontSize = 14 } = {}) {
    if (!text) return;

    this.ctx.font = `500 ${fontSize}px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
    const metrics = this.ctx.measureText(text);
    const padding = 8;
    const height = fontSize + padding * 2;
    const width = metrics.width + padding * 2;

    const x = position.x - width / 2;
    const y = position.y - height / 2;

    this.ctx.fillStyle = bg;
    this.ctx.beginPath();
    this.ctx.roundRect(x, y, width, height, 4);
    this.ctx.fill();

    this.ctx.fillStyle = color;
    this.ctx.textAlign = 'center';
    this.ctx.textBaseline = 'middle';
    this.ctx.fillText(text, position.x, position.y);
  }

  drawRoadCount(count) {
    const vw = this.video.videoWidth || 1280;
    const x = vw - 16;
    const y = 16;
    const text = `${count} road${count !== 1 ? 's' : ''}`;

    this.ctx.font = '500 14px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
    const metrics = this.ctx.measureText(text);
    const padding = 8;
    const width = metrics.width + padding * 2;
    const height = 28;

    this.ctx.fillStyle = 'rgba(37, 99, 235, 0.9)';
    this.ctx.beginPath();
    this.ctx.roundRect(x - width, y, width, height, 6);
    this.ctx.fill();

    this.ctx.fillStyle = '#ffffff';
    this.ctx.textAlign = 'right';
    this.ctx.textBaseline = 'middle';
    this.ctx.fillText(text, x - padding, y + height / 2);
  }

  render(state, cursorPos = null) {
    this.clear();

    const roads = state.roads;
    const hasClosedRoads = roads.some(r => r.isClosed);

    if (hasClosedRoads) {
      this.drawDimOverlay();
    }

    const activeRoad = state.activeRoad;
    const isDrawing = state.state === 'drawing_polygon';
    const isDrawingLine = state.state === 'drawing_line';
    const isEditing = state.state === 'editing';

    for (let i = 0; i < roads.length; i++) {
      const road = roads[i];
      const isActive = isDrawing && road === activeRoad;

      if (road.isClosed && !isActive) {
        const c = road.color || '#2563eb';
        const fillAlpha = c + '1f';
        this.drawPolygon(road.polygon, {
          fill: fillAlpha,
          stroke: c,
          vertexRadius: isEditing ? 6 : 4,
        });
        if (road.line) {
          this.drawLine(road.line, { stroke: '#dc2626' });
        }
        if (road.label) {
          const cent = centroid(road.polygon);
          this.drawLabel(road.label, cent, { bg: c + 'dd' });
        }
      }
    }

    if (isDrawing && activeRoad && activeRoad.polygon.length > 0) {
      const c = activeRoad.color || '#2563eb';
      const pts = activeRoad.polygon;

      // Draw solid lines between placed vertices
      if (pts.length >= 2) {
        this.ctx.beginPath();
        this.ctx.moveTo(pts[0].x, pts[0].y);
        for (let i = 1; i < pts.length; i++) {
          this.ctx.lineTo(pts[i].x, pts[i].y);
        }
        this.ctx.strokeStyle = c;
        this.ctx.lineWidth = 2;
        this.ctx.stroke();
      }

      // Draw vertex dots
      for (const p of pts) {
        this.ctx.beginPath();
        this.ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
        this.ctx.fillStyle = c;
        this.ctx.fill();
        this.ctx.strokeStyle = '#ffffff';
        this.ctx.lineWidth = 1.5;
        this.ctx.stroke();
      }

      // Dashed rubber-band line from last vertex to cursor
      if (cursorPos) {
        this.drawClosingLine(pts, cursorPos, { stroke: c });
      }
    }

    if (isEditing && cursorPos) {
      const ctx = this.ctx;
      for (let ri = roads.length - 1; ri >= 0; ri--) {
        const road = roads[ri];
        if (!road.isClosed) continue;

        if (road.line) {
          if (pointNearLineSegment(cursorPos, road.line.start, road.line.end, 10)) {
            ctx.beginPath();
            ctx.arc(
              (road.line.start.x + road.line.end.x) / 2,
              (road.line.start.y + road.line.end.y) / 2,
              8, 0, Math.PI * 2
            );
            ctx.fillStyle = 'rgba(220, 38, 38, 0.3)';
            ctx.fill();
          }
        }

        for (const p of road.polygon) {
          if (distance(cursorPos, p) <= 15) {
            ctx.beginPath();
            ctx.arc(p.x, p.y, 10, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(220, 38, 38, 0.3)';
            ctx.fill();
            ctx.beginPath();
            ctx.arc(p.x, p.y, 6, 0, Math.PI * 2);
            ctx.fillStyle = '#dc2626';
            ctx.fill();
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2;
            ctx.stroke();
            break;
          }
        }
      }
    }

    const finishedCount = roads.filter(r => r.isClosed).length;
    if (finishedCount > 0) {
      this.drawRoadCount(finishedCount);
    }
  }
}
