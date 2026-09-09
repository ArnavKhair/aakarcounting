/**
 * VehicleAI WebSocket client with auto-reconnect and event-based messaging.
 *
 * Usage:
 *   const ws = new VehicleAIWS();
 *   ws.connect('ws://localhost:8080/ws');
 *   ws.on('progress', (data) => { ... });
 *   ws.send('start_processing', { video_id: '...' });
 */
export class VehicleAIWS {
  constructor() {
    this._ws = null;
    this._url = '';
    this._listeners = new Map();
    this._reconnectDelay = 1000;
    this._maxReconnectDelay = 16000;
    this._shouldReconnect = true;
    this._reconnectTimer = null;
    this._connected = false;
  }

  get connected() {
    return this._connected;
  }

  connect(url) {
    this._url = url;
    this._shouldReconnect = true;
    this._doConnect();
  }

  _doConnect() {
    if (this._ws) {
      this._ws.onclose = null;
      this._ws.close();
    }

    this._ws = new WebSocket(this._url);

    this._ws.onopen = () => {
      this._connected = true;
      this._reconnectDelay = 1000;
      this._emit('_open');
    };

    this._ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type) {
          this._emit(msg.type, msg.data);
        }
      } catch (e) {
        console.error('[WS] Failed to parse message:', e);
      }
    };

    this._ws.onclose = () => {
      this._connected = false;
      this._emit('_close');
      if (this._shouldReconnect) {
        this._scheduleReconnect();
      }
    };

    this._ws.onerror = (err) => {
      console.error('[WS] Error:', err);
    };
  }

  _scheduleReconnect() {
    clearTimeout(this._reconnectTimer);
    this._reconnectTimer = setTimeout(() => {
      this._doConnect();
    }, this._reconnectDelay);
    this._reconnectDelay = Math.min(this._reconnectDelay * 2, this._maxReconnectDelay);
  }

  send(type, data = {}) {
    if (this._ws && this._ws.readyState === WebSocket.OPEN) {
      this._ws.send(JSON.stringify({ type, data }));
    } else {
      console.warn('[WS] Not connected, cannot send:', type);
    }
  }

  on(type, callback) {
    if (!this._listeners.has(type)) {
      this._listeners.set(type, []);
    }
    this._listeners.get(type).push(callback);
    return () => {
      const cbs = this._listeners.get(type);
      const idx = cbs.indexOf(callback);
      if (idx >= 0) cbs.splice(idx, 1);
    };
  }

  _emit(type, data) {
    const cbs = this._listeners.get(type) || [];
    cbs.forEach(cb => cb(data));
  }

  close() {
    this._shouldReconnect = false;
    clearTimeout(this._reconnectTimer);
    if (this._ws) {
      this._ws.onclose = null;
      this._ws.close();
    }
    this._connected = false;
  }
}
