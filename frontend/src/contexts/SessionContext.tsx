"use client";

import type React from "react";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { sessionStorage } from "@/lib/session-storage";
import type { CSVStatus, SessionState } from "@/types/api";

interface SessionContextValue extends SessionState {
  setSessionId: (id: string) => void;
  setExpiresAt: (expiresAt: number) => void;
  setInitialQuery: (query: string) => void;
  setCsvUploaded: (uploaded: boolean) => void;
  setCsvStatus: (status: CSVStatus) => void;
  setCurrentStep: (step: SessionState["current_step"]) => void;
  setAnswer: (questionNum: 1 | 2 | 3, answer: string | null) => Promise<void>;
  setQuestion: (questionNum: 1 | 2 | 3, question: string | null) => void;
  resetSession: () => Promise<void>;
  clearCsvData: () => void;
  clearSession: () => void;
}

const defaultState: SessionState = {
  session_id: null,
  expires_at: null,
  initial_query: "",
  csv_uploaded: false,
  csv_status: "none",
  current_step: "main",
  answers: {
    question_1: null,
    question_2: null,
    question_3: null,
  },
  questions: {
    question_1: null,
    question_2: null,
    question_3: null,
  },
};

const SessionContext = createContext<SessionContextValue | undefined>(
  undefined,
);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<SessionState>(defaultState);

  // Helper function to clear session (defined early for use in useEffect)
  const clearSession = useCallback(() => {
    setState(defaultState);
    sessionStorage.clearAll();
  }, []);

  // Load session from localStorage on mount (with automatic expiration check)
  useEffect(() => {
    const sessionId = sessionStorage.getSessionId();
    const storedState = sessionStorage.getSessionState(); // Auto-validates expiration

    if (sessionId || Object.keys(storedState).length > 0) {
      setState((prev) => ({
        ...prev,
        session_id: sessionId,
        ...storedState,
      }));

      // Server-side validation: check if session still exists in Redis
      if (sessionId) {
        apiClient.getSessionStatus(sessionId).catch((error) => {
          // If session not found on server, clear everything
          if (
            error.message.includes("expired") ||
            error.message.includes("not found")
          ) {
            console.log("Session not found on server, clearing...");
            clearSession();
          }
        });
      }
    }
  }, [clearSession]);

  // Save to localStorage whenever state changes
  useEffect(() => {
    if (state.session_id) {
      sessionStorage.saveSessionId(state.session_id);
      sessionStorage.saveSessionState(state);
    }
  }, [state]);

  const setSessionId = useCallback((id: string) => {
    setState((prev) => ({ ...prev, session_id: id }));
  }, []);

  const setExpiresAt = useCallback((expiresAt: number) => {
    setState((prev) => ({ ...prev, expires_at: expiresAt }));
  }, []);

  const setInitialQuery = useCallback((query: string) => {
    setState((prev) => ({ ...prev, initial_query: query }));
  }, []);

  const setCsvUploaded = useCallback((uploaded: boolean) => {
    setState((prev) => ({ ...prev, csv_uploaded: uploaded }));
  }, []);

  const setCsvStatus = useCallback((status: CSVStatus) => {
    setState((prev) => ({ ...prev, csv_status: status }));
  }, []);

  const setCurrentStep = useCallback((step: SessionState["current_step"]) => {
    setState((prev) => ({ ...prev, current_step: step }));
  }, []);

  const setAnswer = useCallback(async (questionNum: 1 | 2 | 3, answer: string | null) => {
    // Update local state first (optimistic update)
    setState((prev) => ({
      ...prev,
      answers: {
        ...prev.answers,
        [`question_${questionNum}`]: answer,
      },
    }));

    // Sync to backend Redis session
    if (state.session_id) {
      try {
        await apiClient.submitAnswers(state.session_id, {
          answers: {
            ...state.answers,
            [`question_${questionNum}`]: answer,
          },
        });
      } catch (error) {
        console.error("Failed to sync answer to backend:", error);
        // Continue anyway - local state is updated
        // Backend will get answers on next sync or final submit
      }
    }
  }, [state.session_id, state.answers]);

  const setQuestion = useCallback((questionNum: 1 | 2 | 3, question: string | null) => {
    setState((prev) => ({
      ...prev,
      questions: {
        ...prev.questions,
        [`question_${questionNum}`]: question,
      },
    }));
  }, []);

  const resetSession = useCallback(async () => {
    // Reset both frontend state and backend Redis session
    const currentSessionId = state.session_id;

    // Reset frontend state (keep session_id, and csv data)
    setState((prev) => {
      const resetState = {
        ...defaultState,
        session_id: prev.session_id,
        csv_uploaded: prev.csv_uploaded,
        csv_status: prev.csv_status,
      };

      // Save to localStorage
      sessionStorage.saveSessionState(resetState);

      return resetState;
    });

    // Reset backend Redis session (clear questions/answers)
    if (currentSessionId) {
      try {
        await apiClient.resetSession(currentSessionId);
        console.log("Backend session reset successfully");
      } catch (error) {
        console.error("Failed to reset backend session:", error);
        // Continue anyway - frontend is reset
      }
    }
  }, [state.session_id]);

  const clearCsvData = useCallback(() => {
    setState((prev) => ({
      ...prev,
      csv_uploaded: false,
      csv_status: "none",
    }));
  }, []);

  const value: SessionContextValue = useMemo(() => ({
    ...state,
    setSessionId,
    setExpiresAt,
    setInitialQuery,
    setCsvUploaded,
    setCsvStatus,
    setCurrentStep,
    setAnswer,
    setQuestion,
    resetSession,
    clearCsvData,
    clearSession,
  }), [
    state,
    setSessionId,
    setExpiresAt,
    setInitialQuery,
    setCsvUploaded,
    setCsvStatus,
    setCurrentStep,
    setAnswer,
    setQuestion,
    resetSession,
    clearCsvData,
    clearSession,
  ]);

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession() {
  const context = useContext(SessionContext);
  if (context === undefined) {
    throw new Error("useSession must be used within a SessionProvider");
  }
  return context;
}
