import { distance } from './utils.js';
import { States } from './state.js';

const CLOSE_THRESHOLD = 20;

export class PenTool {
  constructor(state, overlay) {
    this.state = state;
    this.overlay = overlay;
    this._cursorPos = null;
  }

  onMouseMove(pos) {
    this._cursorPos = pos;
  }

  onClick(pos) {
    console.log('[PenTool] click at', Math.round(pos.x), Math.round(pos.y), 'state:', this.state.state);
    const road = this.state.getActiveRoad();
    if (!road) return;

    const polygon = road.polygon;

    if (polygon.length >= 3) {
      for (let i = 0; i < polygon.length; i++) {
        if (distance(pos, polygon[i]) <= CLOSE_THRESHOLD) {
          console.log('[PenTool] closing polygon near point', i, 'with', polygon.length, 'points');
          this.state.setPolygon([...polygon]);
          this.state.closeRoad();
          this.state.transition(States.LABELING);
          this._cursorPos = null;
          return;
        }
      }
    }

    const newPoints = [...polygon, pos];
    console.log('[PenTool] adding point', newPoints.length, 'total points');
    this.state.setPolygon(newPoints);
  }

  onKeyDown(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
      e.preventDefault();
      this.state.removeLastVertex();
    }
  }

  render() {
    if (this._cursorPos && this.state.state === States.DRAWING_POLYGON) {
      const road = this.state.getActiveRoad();
      if (road && road.polygon.length > 0) {
        const c = road.color || '#2563eb';
        this.overlay.drawClosingLine(road.polygon, this._cursorPos, { stroke: c });
      }
    }
  }

  reset() {
    this._cursorPos = null;
  }
}
