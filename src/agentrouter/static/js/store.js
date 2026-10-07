export function createStore(initial = {}) {
  let state = { ...initial };
  const subs = new Set();
  function emit() {
    for (const fn of subs) {
      try { fn(state); } catch { /* keep others alive */ }
    }
  }
  return {
    get(k) { return state[k]; },
    all() { return { ...state }; },
    set(patch) {
      if (!patch || typeof patch !== "object") return;
      let changed = false;
      for (const k of Object.keys(patch)) {
        if (state[k] !== patch[k]) {
          state[k] = patch[k];
          changed = true;
        }
      }
      if (changed) emit();
    },
    subscribe(fn) {
      subs.add(fn);
      return () => subs.delete(fn);
    },
  };
}

export function shellInitialState() {
  return {
    theme: "dark",
    motion: "full",
    density: "comfortable",
    fontScale: 100,
    mode: "chat",
    model: "",
    models: [],
    sessions: [],
    sessionId: "",
    drafts: { chat: "", agent: "" },
    railCollapsed: false,
    railDrawer: false,
    inspectorOpen: true,
    online: true,
    running: false,
    steps: 0,
    status: "boot",
  };
}

export function createShellStore(overrides) {
  return createStore({ ...shellInitialState(), ...(overrides || {}) });
}
