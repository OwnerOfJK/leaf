// API Types matching backend Pydantic schemas

// ============================================================================
// Session Types
// ============================================================================

export type CSVStatus = "pending" | "processing" | "completed" | "failed" | "none";

export interface SessionResponse {
	session_id: string;
	status: "ready" | "processing_csv";
	follow_up_questions: never[]; // Always empty - frontend handles UI
}

export interface SessionAnswersSubmit {
	answers: {
		question_1: string | null;
		question_2: string | null;
		question_3: string | null;
	};
}

export interface SessionAnswersResponse {
	session_id: string;
	status: "ready";
	csv_books_count: number | null;
}

export interface SessionStatusResponse {
	session_id: string;
	csv_status: CSVStatus;
	books_processed: number | null;
	books_total: number | null;
	new_books_added: number | null;
}

// ============================================================================
// Question Generation Types (Backend endpoint to be implemented)
// ============================================================================

export interface GenerateQuestionRequest {
	question_number: 1 | 2 | 3;
}

export interface GenerateQuestionResponse {
	question: string;
	question_number: 1 | 2 | 3;
}

// ============================================================================
// Book Types
// ============================================================================

export interface Book {
	isbn: string;
	title: string;
	author: string;
	description: string | null;
	categories: string[] | null;
	cover_url: string | null;
	isbn13: string | null;
	page_count: number | null;
	publisher: string | null;
	publication_year: number | null;
	language: string | null;
	average_rating: number | null;
	ratings_count: number | null;
}

// ============================================================================
// Recommendation Types
// ============================================================================

export interface Recommendation {
	id: number;
	book: Book;
	confidence_score: number; // 0-100
	explanation: string;
	rank: 1 | 2 | 3;
}

export interface RecommendationsResponse {
	session_id: string;
	recommendations: Recommendation[];
	trace_id: string | null;
	trace_url: string | null;
}

// ============================================================================
// Feedback Types
// ============================================================================

export type FeedbackType = "like" | "dislike";

export interface FeedbackSubmit {
	feedback_type: FeedbackType;
}

export interface FeedbackResponse {
	success: boolean;
	langfuse_score_id: string | null;
}

// ============================================================================
// Error Types
// ============================================================================

export interface APIError {
	detail: string;
	status?: number;
}

// ============================================================================
// Local State Types (Frontend only)
// ============================================================================

export interface SessionState {
	session_id: string | null;
	initial_query: string;
	csv_uploaded: boolean;
	csv_status: CSVStatus;
	current_step: "main" | "questions" | "recommendations";
	answers: {
		question_1: string | null;
		question_2: string | null;
		question_3: string | null;
	};
	questions: {
		question_1: string | null;
		question_2: string | null;
		question_3: string | null;
	};
}
