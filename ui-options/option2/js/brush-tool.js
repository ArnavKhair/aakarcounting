import { convexHull } from './utils.js';

const MIN_POINT_DISTANCE = 5;

export class BrushTool {
  constructor(state, overlay) {
    this.state = state;
    this.overlay = overlay;
    this._isDragging = false;
    this._path = [];
    this._cursorPos = null;
  }

  onMouseDown(pos) {
    if (this.state.state !== 'drawing_polygon') return;
    this._isDragging = true;
    this._path = [pos];
    this._cursorPos = pos;
  }

  onMouseMove(pos) {
    this._cursorPos = pos;
    if (!this._isDragging) return;

    const last = this._path[this._path.length - 1];
    const dx = pos.x - last.x;
    const dy = pos.y - last.y;
    if (dx * dx + dy * dy >= MIN_POINT_DISTANCE * MIN_POINT_DISTANCE) {
      this._path.push(pos);
    }
  }

  onMouseUp(pos) {
    if (!this._isDragging) return;
    this._isDragging = false;

    if (pos) {
      const last = this._path[this._path.length - 1];
      const dx = pos.x - last.x;
      const dy = pos.y - last.y;
      if (dx * dx + dy * dy >= MIN_POINT_DISTANCE * MIN_POINT_DISTANCE) {
        this._path.push(pos);
      }
    }

    if (this._path.length < 2) {
      this._path = [];
      return;
    }

    const polygon = convexHull(this._path);
    if (polygon.length >= 3) {
      this.state.setPolygon(polygon);
      this.state.closeRoad();
      this.state.transition('labeling');
    }

    this._path = [];
    this._cursorPos = null;
  }

  onKeyDown(e) {
    if (e.key === 'Escape') {
      this._isDragging = false;
      this._path = [];
      this._cursorPos = null;
      this.state.transition('idle');
    }
  }

  render() {
    if (!this._isDragging || this._path.length < 2) return;

    const ctx = this.overlay.ctx;
    const color = '#2563eb';

    ctx.beginPath();
    ctx.moveTo(this._path[0].x, this._path[0].y);
    for (let i = 1; i < this._path.length; i++) {
      ctx.lineTo(this._path[i].x, this._path[i].y);
    }
    ctx.strokeStyle = color + '60';
    ctx.lineWidth = 20;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.stroke();
  }

  reset() {
    this._isDragging = false;
    this._path = [];
    this._cursorPos = null;
  }
}
