/* Xiaomi Camera Native: single-step controls in the standard camera pop-up. */
(() => {
  "use strict";
  const TAG = "xiaomi-camera-ptz-controls";
  const PATCH = Symbol.for("xiaomi_camera_native.camera_controls");
  const DIRECTIONS = [
    ["left", "Pan left", "M20 12H4m7-7-7 7 7 7"],
    ["up", "Tilt up", "M12 20V4m-7 7 7-7 7 7"],
    ["down", "Tilt down", "M12 4v16m-7-7 7 7 7-7"],
    ["right", "Pan right", "M4 12h16m-7-7 7 7-7 7"],
  ];

  class CameraControls extends HTMLElement {
    constructor() {
      super();
      this._busy = false;
      this._generation = 0;
      this._entityId = null;
      this._buttons = {};
      this.attachShadow({ mode: "open" });
      // All markup is fixed; state, entity IDs and errors never enter HTML.
      this.shadowRoot.innerHTML = `
        <style>
          :host { display: block; flex: 1 1 260px; min-width: 0;
            margin-inline-end: auto; color: var(--primary-text-color, #222); }
          .row { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
          .label { font: 500 13px/1.4 var(--primary-font-family, sans-serif);
            color: var(--secondary-text-color, #666); }
          .arrows { display: flex; gap: 6px; }
          button { display: inline-flex; justify-content: center; align-items: center;
            width: 44px; height: 44px; padding: 10px; box-sizing: border-box;
            border: 1px solid var(--divider-color, #ddd); border-radius: 12px;
            background: var(--card-background-color, #fff);
            color: var(--primary-text-color, #222); cursor: pointer;
            touch-action: manipulation; -webkit-tap-highlight-color: transparent; }
          button:hover:not(:disabled), button:active:not(:disabled) {
            background: var(--secondary-background-color, #eee);
            color: var(--primary-color, #03a9f4); }
          button:focus-visible { outline: 2px solid var(--primary-color, #03a9f4);
            outline-offset: 2px; }
          button:disabled { opacity: .4; cursor: default; }
          svg { width: 24px; height: 24px; fill: none; stroke: currentColor;
            stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
          .status { font: 12px/1.4 var(--primary-font-family, sans-serif);
            margin-top: 6px; color: var(--secondary-text-color, #666); }
          .status:empty { display: none; }
          .status.error { color: var(--error-color, #db4437); }
          @media (max-width: 420px) { .row { gap: 8px; } }
        </style>
        <div class="row" role="group" aria-label="Camera movement">
          <span class="label">Move camera</span>
          <div class="arrows"></div>
        </div>
        <div class="status" role="status" aria-live="polite"></div>`;
      const arrows = this.shadowRoot.querySelector(".arrows");
      for (const [direction, label, path] of DIRECTIONS) {
        const button = document.createElement("button");
        button.type = "button";
        button.title = label;
        button.setAttribute("aria-label", label);
        button.dataset.direction = direction;
        button.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${path}"/></svg>`;
        button.addEventListener("click", () => this._press(direction));
        arrows.append(button);
        this._buttons[direction] = button;
      }
    }

    setContext(stateObj, api) {
      if (this._entityId !== stateObj.entity_id) {
        this._generation++;
        this._busy = false;
        this._setStatus("");
      }
      this._entityId = stateObj.entity_id;
      this._stateObj = stateObj;
      this._api = api;
      this._targets = stateObj.attributes.xiaomi_pan_tilt_buttons;
      this._updateDisabled();
    }

    disconnectedCallback() {
      // A completed request from a closed pop-up must not update a new view.
      this._generation++;
      this._busy = false;
    }

    _updateDisabled() {
      const unavailable = ["unavailable", "unknown"].includes(this._stateObj?.state);
      for (const [direction, button] of Object.entries(this._buttons)) {
        const target = this._targets?.[direction];
        button.disabled = this._busy || unavailable ||
          typeof target !== "string" || !/^button\.[a-z0-9_]+$/.test(target);
      }
    }

    _setStatus(message, error = false) {
      const status = this.shadowRoot.querySelector(".status");
      status.textContent = message;
      status.classList.toggle("error", error);
    }

    async _press(direction) {
      if (this._buttons[direction]?.disabled || !this._api?.callService) return;
      const generation = this._generation;
      const target = this._targets[direction];
      this._busy = true;
      this._updateDisabled();
      this._setStatus("Moving…");
      try {
        // Exactly one normal HA action; no new player or media request.
        await this._api.callService("button", "press", { entity_id: target });
        if (generation === this._generation) this._setStatus("");
      } catch (err) {
        if (generation === this._generation) {
          this._setStatus(typeof err?.message === "string" ? err.message :
            "The camera movement command failed. Try again.", true);
        }
      } finally {
        if (generation === this._generation) {
          this._busy = false;
          this._updateDisabled();
        }
      }
    }
  }

  if (!customElements.get(TAG)) customElements.define(TAG, CameraControls);

  function synchronize(camera) {
    const root = camera.shadowRoot;
    if (!root) return;
    let controls = root.querySelector(TAG);
    const state = camera.stateObj;
    const targets = state?.attributes?.xiaomi_pan_tilt_buttons;
    // Older HA versions pass hass; newer versions consume an API context.
    const api = camera.hass?.callService ? camera.hass : camera._api;
    if (!camera.isConnected || !targets || typeof targets !== "object" || !api?.callService) {
      controls?.remove();
      return;
    }
    if (!controls) {
      controls = document.createElement(TAG);
      const footer = root.querySelector(".actions");
      if (footer) footer.prepend(controls);
      else root.append(controls);
    }
    controls.setContext(state, api);
  }

  customElements.whenDefined("more-info-camera").then(() => {
    const prototype = customElements.get("more-info-camera").prototype;
    if (prototype[PATCH]) return;
    const originalUpdated = prototype.updated;
    prototype.updated = function (...args) {
      const result = originalUpdated?.apply(this, args);
      // Keep HA's render, video element, snapshot action and lifecycle intact.
      synchronize(this);
      return result;
    };
    Object.defineProperty(prototype, PATCH, { value: true });
  });
})();
