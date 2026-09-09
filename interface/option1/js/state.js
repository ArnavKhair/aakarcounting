export const States = Object.freeze({
  IDLE: 'idle',
  DRAWING_POLYGON: 'drawing_polygon',
  LABELING: 'labeling',
  POLYGON_COMPLETE: 'polygon_complete',
  DRAWING_LINE: 'drawing_line',
  PREVIEW: 'preview',
  EDITING: 'editing',
  COMPLETE: 'complete',
});

const Instructions = {
  [States.IDLE]: {
    icon: 'mouse-pointer-click',
    text: 'Mark the road area by placing points along its boundary. The pen tool is ready — click on the video to start drawing a polygon that covers the entire road surface visible in the frame.',
  },
  [States.DRAWING_POLYGON]: {
    icon: 'pen-tool',
    text: 'Click along the road edges to place vertices. Follow the road boundary closely — include all lanes and shoulders. When you\'re back near the start, click the first point to close the polygon. Press Ctrl+Z to undo the last point, or Escape to cancel.',
  },
  [States.LABELING]: {
    icon: 'type',
    text: 'Give this road a descriptive name (e.g. "Main Street Northbound"). This label will help identify the road in the count results.',
  },
  [States.POLYGON_COMPLETE]: {
    icon: 'minus',
    text: 'Now draw a counting line across the road. The line should span from one side of the road to the other, perpendicular to traffic flow. The line tool is ready — click on one side of the road to begin.',
  },
  [States.DRAWING_LINE]: {
    icon: 'minus',
    text: 'Click once on one side of the road to start the line, then click on the opposite side to finish it. Make sure both edges of the road are visible in the frame at the line\'s position. Press Escape to cancel.',
  },
  [States.PREVIEW]: {
    icon: 'eye',
    text: 'Review your annotations. The video will play through to verify the road area and counting line are correctly placed. Use "Make Changes" to edit, or "Start Processing" when ready.',
  },
  [States.EDITING]: {
    icon: 'eraser',
    text: 'Hover over a vertex or counting line to highlight it in red, then click to remove it. Adjust the polygon shape or counting line as needed. Press Escape to return to preview.',
  },
  [States.COMPLETE]: {
    icon: 'check',
    text: 'All annotations have been saved. The vehicle counting process will begin.',
  },
};

export const ROAD_COLORS = [
  '#2563eb',
  '#16a34a',
  '#ea580c',
  '#9333ea',
  '#dc2626',
  '#0891b2',
  '#ca8a04',
  '#e11d48',
];

export class AppState {
  constructor() {
    this._state = States.IDLE;
    this._roads = [];
    this._activeRoadIndex = -1;
    this._listeners = new Map();
  }

  get state() {
    return this._state;
  }

  get roads() {
    return this._roads;
  }

  get activeRoadIndex() {
    return this._activeRoadIndex;
  }

  get activeRoad() {
    return this._activeRoadIndex >= 0 ? this._roads[this._activeRoadIndex] : null;
  }

  get instruction() {
    return Instructions[this._state] || { icon: 'info', text: '' };
  }

  get hasRoads() {
    return this._roads.length > 0;
  }

  get hasClosedRoads() {
    return this._roads.some(r => r.isClosed);
  }

  get canDrawLine() {
    return this._roads.some(r => r.isClosed && !r.line);
  }

  transition(newState) {
    const prev = this._state;
    this._state = newState;
    this._emit('stateChange', { prev, next: newState });
  }

  addRoad() {
    const road = {
      id: Date.now(),
      polygon: [],
      label: '',
      line: null,
      isClosed: false,
      color: ROAD_COLORS[this._roads.length % ROAD_COLORS.length],
    };
    this._roads.push(road);
    this._activeRoadIndex = this._roads.length - 1;
    this._emit('roadAdded', { road, index: this._activeRoadIndex });
    return road;
  }

  getActiveRoad() {
    return this.activeRoad;
  }

  setPolygon(points) {
    const road = this.activeRoad;
    if (road) {
      road.polygon = points;
      this._emit('polygonUpdated', { road, index: this._activeRoadIndex });
    }
  }

  closeRoad() {
    const road = this.activeRoad;
    if (road) {
      road.isClosed = true;
      this._emit('roadClosed', { road, index: this._activeRoadIndex });
    }
  }

  setLabel(label) {
    const road = this.activeRoad;
    if (road) {
      road.label = label;
      this._emit('labelUpdated', { road, index: this._activeRoadIndex });
    }
  }

  setLine(line) {
    const road = this.activeRoad;
    if (road) {
      road.line = line;
      this._emit('lineUpdated', { road, index: this._activeRoadIndex });
    }
  }

  setActiveRoadByPoint(x, y) {
    for (let i = this._roads.length - 1; i >= 0; i--) {
      const road = this._roads[i];
      if (road.isClosed && this._pointInPolygon(x, y, road.polygon)) {
        this._activeRoadIndex = i;
        this._emit('activeRoadChanged', { road, index: i });
        return road;
      }
    }
    return null;
  }

  removeLastVertex() {
    const road = this.activeRoad;
    if (road && road.polygon.length > 0) {
      road.polygon.pop();
      this._emit('polygonUpdated', { road, index: this._activeRoadIndex });
      return true;
    }
    return false;
  }

  removeVertex(roadIndex, vertexIndex) {
    const road = this._roads[roadIndex];
    if (!road) return false;
    road.polygon.splice(vertexIndex, 1);
    if (road.polygon.length < 3) {
      this._roads.splice(roadIndex, 1);
      if (this._activeRoadIndex >= this._roads.length) {
        this._activeRoadIndex = this._roads.length - 1;
      }
      this._emit('roadRemoved', { index: roadIndex });
    } else {
      this._emit('polygonUpdated', { road, index: roadIndex });
    }
    return true;
  }

  removeLine(roadIndex) {
    const road = this._roads[roadIndex];
    if (!road || !road.line) return false;
    road.line = null;
    this._emit('lineUpdated', { road, index: roadIndex });
    return true;
  }

  removeRoad(roadIndex) {
    if (roadIndex < 0 || roadIndex >= this._roads.length) return false;
    this._roads.splice(roadIndex, 1);
    if (this._activeRoadIndex >= this._roads.length) {
      this._activeRoadIndex = this._roads.length - 1;
    }
    this._emit('roadRemoved', { index: roadIndex });
    return true;
  }

  reset() {
    this._roads = [];
    this._activeRoadIndex = -1;
    this._state = States.IDLE;
    this._emit('reset');
  }

  on(event, callback) {
    if (!this._listeners.has(event)) {
      this._listeners.set(event, []);
    }
    this._listeners.get(event).push(callback);
    return () => {
      const cbs = this._listeners.get(event);
      const idx = cbs.indexOf(callback);
      if (idx >= 0) cbs.splice(idx, 1);
    };
  }

  _emit(event, data) {
    const cbs = this._listeners.get(event) || [];
    cbs.forEach(cb => cb(data));
  }

  _pointInPolygon(x, y, polygon) {
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      const xi = polygon[i].x, yi = polygon[i].y;
      const xj = polygon[j].x, yj = polygon[j].y;
      const intersect = ((yi > y) !== (yj > y)) &&
        (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
      if (intersect) inside = !inside;
    }
    return inside;
  }
}
