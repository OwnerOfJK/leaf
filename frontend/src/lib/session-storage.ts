// Session storage utilities for localStorage management

import type { SessionState } from "@/types/api";

const SESSION_KEY = "leaf_session";

export const sessionStorage = {
  // Save session ID to localStorage
  saveSessionId(sessionId: string): void {
    if (typeof window === "undefined") return;
    localStorage.setItem(SESSION_KEY, sessionId);
  },

  // Get session ID from localStorage
  getSessionId(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(SESSION_KEY);
  },

  // Clear session ID from localStorage
  clearSessionId(): void {
    if (typeof window === "undefined") return;
    localStorage.removeItem(SESSION_KEY);
  },

  // Check if session exists
  hasSession(): boolean {
    return this.getSessionId() !== null;
  },

  // Save full session state (for back navigation)
  saveSessionState(state: Partial<SessionState>): void {
    if (typeof window === "undefined") return;
    const existing = this.getSessionState();
    const updated = { ...existing, ...state };
    localStorage.setItem(`${SESSION_KEY}_state`, JSON.stringify(updated));
  },

  // Get full session state (with automatic expiration check)
  getSessionState(): Partial<SessionState> {
    if (typeof window === "undefined") return {};
    const stored = localStorage.getItem(`${SESSION_KEY}_state`);
    if (!stored) return {};

    try {
      const state = JSON.parse(stored) as Partial<SessionState>;

      // Client-side expiration check: if expires_at is in the past, auto-clear
      if (state.expires_at && Date.now() > state.expires_at) {
        console.log(
          "Session expired (client-side check), clearing localStorage...",
        );
        this.clearAll();
        return {};
      }

      return state;
    } catch {
      return {};
    }
  },

  // Clear session state
  clearSessionState(): void {
    if (typeof window === "undefined") return;
    localStorage.removeItem(`${SESSION_KEY}_state`);
  },

  // Clear everything
  clearAll(): void {
    this.clearSessionId();
    this.clearSessionState();
  },
};
