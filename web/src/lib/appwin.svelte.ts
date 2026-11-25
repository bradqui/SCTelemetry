// The Windows app's window, when the page runs inside it (pywebview: window.pywebview.api,
// starglance/app.py's Api). In a browser none of this exists and `inApp` stays false.

export interface AppState {
  /** No Windows title bar: the page's top bar drags the window and has its own buttons. */
  frameless: boolean;
  on_top: boolean;
  maximized: boolean;
  /** Start with Windows; null when it isn't available (running from source). */
  autostart: boolean | null;
}

interface AppApi {
  state(): Promise<AppState>;
  minimize(): Promise<void>;
  toggle_maximize(): Promise<AppState>;
  hide(): Promise<void>;
  set_on_top(on: boolean): Promise<AppState>;
  start_resize(edge: string): Promise<void>;
  set_frameless(on: boolean): Promise<AppState>;
  set_autostart(on: boolean): Promise<AppState>;
  open_external(url: string): Promise<boolean>;
}

declare global {
  interface Window {
    pywebview?: { api?: Partial<AppApi> };
  }
}

class AppWindow {
  inApp = $state(false);
  state = $state<AppState | null>(null);

  constructor() {
    if (typeof window === "undefined") return;
    const init = () => {
      void this.refresh();
      // Maximized by a double click, Win+Up or snapping: keep up (the resize edges hide).
      let pending = 0;
      window.addEventListener("resize", () => {
        clearTimeout(pending);
        pending = window.setTimeout(() => void this.refresh(), 250);
      });
    };
    if (window.pywebview?.api?.state) init();
    else window.addEventListener("pywebviewready", init, { once: true });
  }

  get api(): AppApi | null {
    const api = window.pywebview?.api;
    return api?.state ? (api as AppApi) : null;
  }

  async refresh(): Promise<void> {
    const api = this.api;
    if (!api) return;
    this.inApp = true;
    this.state = await api.state();
  }

  minimize = () => void this.api?.minimize();
  /** Frameless: an edge of the page was pressed; Windows resizes the window from it. */
  startResize = (edge: string) => void this.api?.start_resize?.(edge);
  hide = () => void this.api?.hide();
  async toggleMaximize(): Promise<void> {
    if (this.api) this.state = await this.api.toggle_maximize();
  }
  async setOnTop(on: boolean): Promise<void> {
    if (this.api) this.state = await this.api.set_on_top(on);
  }
  /** Opens a new window (Windows can't add or remove a title bar on an open one). */
  async setFrameless(on: boolean): Promise<void> {
    if (this.api) this.state = await this.api.set_frameless(on);
  }
  async setAutostart(on: boolean): Promise<void> {
    if (this.api) this.state = await this.api.set_autostart(on);
  }
}

export const appWindow = new AppWindow();
