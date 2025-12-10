"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import type { SessionState, CSVStatus } from "@/types/api";
import { sessionStorage } from "@/lib/session-storage";
import { apiClient } from "@/lib/api-client";

interface SessionContextValue extends SessionState {
	setSessionId: (id: string) => void;
	setInitialQuery: (query: string) => void;
	setCsvUploaded: (uploaded: boolean) => void;
	setCsvStatus: (status: CSVStatus) => void;
	setCurrentStep: (step: SessionState["current_step"]) => void;
	setAnswer: (
		questionNum: 1 | 2 | 3,
		answer: string | null,
	) => Promise<void>;
	setQuestion: (questionNum: 1 | 2 | 3, question: string | null) => void;
	resetSession: () => void;
	clearCsvData: () => void;
}

const defaultState: SessionState = {
	session_id: null,
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

	// Load session from localStorage on mount
	useEffect(() => {
		const sessionId = sessionStorage.getSessionId();
		const storedState = sessionStorage.getSessionState();

		if (sessionId || Object.keys(storedState).length > 0) {
			setState((prev) => ({
				...prev,
				session_id: sessionId,
				...storedState,
			}));
		}
	}, []);

	// Save to localStorage whenever state changes
	useEffect(() => {
		if (state.session_id) {
			sessionStorage.saveSessionId(state.session_id);
			sessionStorage.saveSessionState(state);
		}
	}, [state]);

	const setSessionId = (id: string) => {
		setState((prev) => ({ ...prev, session_id: id }));
	};

	const setInitialQuery = (query: string) => {
		setState((prev) => ({ ...prev, initial_query: query }));
	};

	const setCsvUploaded = (uploaded: boolean) => {
		setState((prev) => ({ ...prev, csv_uploaded: uploaded }));
	};

	const setCsvStatus = (status: CSVStatus) => {
		setState((prev) => ({ ...prev, csv_status: status }));
	};

	const setCurrentStep = (step: SessionState["current_step"]) => {
		setState((prev) => ({ ...prev, current_step: step }));
	};

	const setAnswer = async (
		questionNum: 1 | 2 | 3,
		answer: string | null,
	) => {
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
	};

	const setQuestion = (questionNum: 1 | 2 | 3, question: string | null) => {
		setState((prev) => ({
			...prev,
			questions: {
				...prev.questions,
				[`question_${questionNum}`]: question,
			},
		}));
	};

	const resetSession = () => {
		// Keep session_id and csv data, reset everything else (query, answers, questions, step)
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
	};

	const clearCsvData = () => {
		setState((prev) => ({
			...prev,
			csv_uploaded: false,
			csv_status: "none",
		}));
	};

	const value: SessionContextValue = {
		...state,
		setSessionId,
		setInitialQuery,
		setCsvUploaded,
		setCsvStatus,
		setCurrentStep,
		setAnswer,
		setQuestion,
		resetSession,
		clearCsvData,
	};

	return (
		<SessionContext.Provider value={value}>
			{children}
		</SessionContext.Provider>
	);
}

export function useSession() {
	const context = useContext(SessionContext);
	if (context === undefined) {
		throw new Error("useSession must be used within a SessionProvider");
	}
	return context;
}
