/* Optional Node.js smoke test; no Home Assistant/browser or npm dependencies. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const widgets = new Map();
class FakeButton {
  constructor() { this.disabled = false; this.hidden = false; this.dataset = {}; }
  setAttribute() {}
  addEventListener() {}
}
class FakeRoot {
  constructor() {
    this.arrowContainer = {children: [], append(item) { this.children.push(item); }};
    this.status = {textContent: "", classList: {toggle() {}}};
  }
  querySelector(selector) {
    if (selector === ".arrows") return this.arrowContainer;
    if (selector === ".status") return this.status;
    return null;
  }
}
class FakeHTMLElement {
  attachShadow() { this.shadowRoot = new FakeRoot(); return this.shadowRoot; }
}
class FakeMoreInfoCamera {}
widgets.set("more-info-camera", FakeMoreInfoCamera);
const customElements = {
  get(name) {return widgets.get(name);},
  define(name, cls) {widgets.set(name, cls);},
  whenDefined() {return Promise.resolve();},
};
const script = fs.readFileSync(path.join(__dirname, "../custom_components/xiaomi_camera_native/frontend/camera-controls.js"), "utf8");
vm.runInNewContext(script, {HTMLElement: FakeHTMLElement, document: {createElement: () => new FakeButton()}, customElements, Symbol});
const controls = new (widgets.get("xiaomi-camera-ptz-controls"))();
const read = (buttons, ready) => controls.setContext({
  entity_id: "camera.example", state: "idle",
  attributes: {xiaomi_pan_tilt_buttons: buttons, pan_tilt_ready: ready},
}, {callService() {}});
read({left: "button.ipc_left", right: "button.ipc_right"});
assert.deepEqual(Object.entries(controls._buttons).filter(([, b]) => !b.hidden).map(([dir]) => dir), ["left", "right"]);
assert.equal(controls._buttons.up.disabled, true);
assert.equal(controls._buttons.down.disabled, true);
read({left: "button.ipc_left", right: "button.ipc_right"}, false);
assert.equal(controls._buttons.left.hidden, false);
assert.equal(controls._buttons.left.disabled, true);
assert.equal(controls._buttons.right.disabled, true);
read({left: "button.ipc_left", right: "button.ipc_right"}, true);
assert.equal(controls._buttons.left.disabled, false);
assert.equal(controls._buttons.right.disabled, false);
read({left: "button.full_left", right: "button.full_right", up: "button.full_up", down: "button.full_down"});
assert.deepEqual(Object.entries(controls._buttons).filter(([, b]) => !b.hidden).map(([dir]) => dir), ["left", "up", "down", "right"]);
read({left: "button.ipc_left", right: "button.ipc_right"});
assert.equal(controls._buttons.up.hidden, true);
assert.equal(controls._buttons.down.hidden, true);
console.log("PASS: frontend hides unsupported tilt while preserving full PTZ on other cameras");
