import type {
  APIError,
  FeedbackResponse,
  FeedbackSubmit,
  GenerateQuestionRequest,
  GenerateQuestionResponse,
  RecommendationsResponse,
  SessionAnswersResponse,
  SessionAnswersSubmit,
  SessionResponse,
  SessionStatusResponse,
} from "@/types/api";

// Use nextjs proxy routes with same domain
const API_BASE_URL =
  process.env.NODE_ENV === "production" ? "" : "http://localhost:8000";

class APIClient {
  private baseURL: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      const errorData: APIError = await response.json().catch(() => ({
        detail: "An unexpected error occurred",
        status: response.status,
      }));

      // Transform backend errors to user-friendly messages
      const userMessage = this.getUserFriendlyError(
        errorData.detail,
        response.status,
      );

      throw new Error(userMessage);
    }

    return response.json();
  }

  private getUserFriendlyError(detail: string, status: number): string {
    // Map backend errors to specific but non-technical messages
    if (status === 404) {
      if (detail.toLowerCase().includes("session")) {
        return "Your session expired. Let's start fresh.";
      }
      if (detail.toLowerCase().includes("recommendation")) {
        return "We couldn't find that recommendation.";
      }
      return "We couldn't find what you're looking for.";
    }

    if (status === 400) {
      if (detail.toLowerCase().includes("csv")) {
        return "We couldn't read this file. Make sure it's exported from Goodreads.";
      }
      if (detail.toLowerCase().includes("trace")) {
        return "We couldn't submit your feedback right now.";
      }
      return detail; // Return the specific validation error
    }

    if (status === 500) {
      return "Something went wrong on our end. Please try again.";
    }

    // Default fallback
    return detail || "An unexpected error occurred. Please try again.";
  }

  // ========================================================================
  // Session Endpoints
  // ========================================================================

  async createSession(
    initialQuery: string,
    csvFile?: File,
  ): Promise<SessionResponse> {
    const formData = new FormData();
    formData.append("initial_query", initialQuery);

    if (csvFile) {
      formData.append("csv_file", csvFile);
    }

    const response = await fetch(`${this.baseURL}/api/sessions/create`, {
      method: "POST",
      body: formData,
    });

    return this.handleResponse<SessionResponse>(response);
  }

  async getSessionStatus(sessionId: string): Promise<SessionStatusResponse> {
    const response = await fetch(
      `${this.baseURL}/api/sessions/${sessionId}/status`,
    );

    return this.handleResponse<SessionStatusResponse>(response);
  }

  async submitAnswers(
    sessionId: string,
    answers: SessionAnswersSubmit,
  ): Promise<SessionAnswersResponse> {
    const response = await fetch(
      `${this.baseURL}/api/sessions/${sessionId}/answers`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(answers),
      },
    );

    return this.handleResponse<SessionAnswersResponse>(response);
  }

  async resetSession(sessionId: string): Promise<{ success: boolean }> {
    const response = await fetch(
      `${this.baseURL}/api/sessions/${sessionId}/reset`,
      {
        method: "POST",
      },
    );

    return this.handleResponse<{ success: boolean }>(response);
  }

  async updateQuery(
    sessionId: string,
    initialQuery: string,
  ): Promise<{ success: boolean }> {
    const formData = new FormData();
    formData.append("initial_query", initialQuery);

    const response = await fetch(
      `${this.baseURL}/api/sessions/${sessionId}/query`,
      {
        method: "PUT",
        body: formData,
      },
    );

    return this.handleResponse<{ success: boolean }>(response);
  }

  // ========================================================================
  // Question Generation Endpoint (To be implemented in backend)
  // ========================================================================

  async generateQuestion(
    sessionId: string,
    request: GenerateQuestionRequest,
  ): Promise<GenerateQuestionResponse> {
    const response = await fetch(
      `${this.baseURL}/api/sessions/${sessionId}/generate-question`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
      },
    );

    return this.handleResponse<GenerateQuestionResponse>(response);
  }

  // ========================================================================
  // Recommendations Endpoint
  // ========================================================================

  async getRecommendations(
    sessionId: string,
  ): Promise<RecommendationsResponse> {
    const response = await fetch(
      `${this.baseURL}/api/sessions/${sessionId}/recommendations`,
    );

    return this.handleResponse<RecommendationsResponse>(response);
  }

  // ========================================================================
  // Feedback Endpoint
  // ========================================================================

  async submitFeedback(
    recommendationId: number,
    rank: number,
    feedback: FeedbackSubmit,
  ): Promise<FeedbackResponse> {
    const response = await fetch(
      `${this.baseURL}/api/recommendations/${recommendationId}/feedback`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ...feedback, rank }),
      },
    );

    return this.handleResponse<FeedbackResponse>(response);
  }

  // ========================================================================
  // Health Check
  // ========================================================================

  async healthCheck(): Promise<{ status: string }> {
    const response = await fetch(`${this.baseURL}/health`);
    return this.handleResponse<{ status: string }>(response);
  }
}

// Export singleton instance
export const apiClient = new APIClient(API_BASE_URL);
