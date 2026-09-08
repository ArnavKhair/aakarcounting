import { States } from './state.js';

export class LineTool {
  constructor(state, overlay) {
    this.state = state;
    this.overlay = overlay;
    this._startPos = null;
    this._cursorPos = null;
  }

  onMouseMove(pos) {
    this._cursorPos = pos;
  }

  onClick(pos) {
    console.log('[LineTool] click at', Math.round(pos.x), Math.round(pos.y), 'state:', this.state.state);
    const road = this.state.getActiveRoad();
    if (!road) return;

    if (!this._startPos) {
      this._startPos = { ...pos };
      console.log('[LineTool] start point set');
    } else {
      this.state.setLine({
        start: { ...this._startPos },
        end: { ...pos },
      });
      console.log('[LineTool] line complete');
      this._startPos = null;
      this._cursorPos = null;
      this.state.transition(States.POLYGON_COMPLETE);
    }
  }

  onKeyDown(e) {
    if (e.key === 'Escape') {
      this._startPos = null;
      this._cursorPos = null;
      this.state.transition(States.POLYGON_COMPLETE);
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
      e.preventDefault();
      this._startPos = null;
    }
  }

  render() {
    if (this.state.state !== 'drawing_line') return;

    if (this._startPos && this._cursorPos) {
      const ctx = this.overlay.ctx;
      ctx.beginPath();
      ctx.moveTo(this._startPos.x, this._startPos.y);
      ctx.lineTo(this._cursorPos.x, this._cursorPos.y);
      ctx.strokeStyle = '#dc2626';
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 4]);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.beginPath();
      ctx.arc(this._startPos.x, this._startPos.y, 6, 0, Math.PI * 2);
      ctx.fillStyle = '#dc2626';
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();
    } else if (this._startPos) {
      const ctx = this.overlay.ctx;
      ctx.beginPath();
      ctx.arc(this._startPos.x, this._startPos.y, 6, 0, Math.PI * 2);
      ctx.fillStyle = '#dc2626';
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();
    }
  }

  reset() {
    this._startPos = null;
    this._cursorPos = null;
  }
}
