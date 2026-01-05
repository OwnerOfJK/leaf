"use client";

import { BookOpen, CheckCircle2, Shield } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useSession } from "@/contexts/SessionContext";
import { apiClient } from "@/lib/api-client";
import { CSVUpload } from "./components/CSVUpload";
import { Footer } from "./components/Footer";
import { Header } from "./components/Header";

export default function Home() {
  const router = useRouter();
  const session = useSession();

  const [query, setQuery] = useState("");
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvUploadStatus, setCsvUploadStatus] = useState<
    "idle" | "uploading" | "success" | "error"
  >("idle");
  const [csvProgress, setCsvProgress] = useState(0);
  const [csvError, setCsvError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [generalError, setGeneralError] = useState<string | null>(null);

  // Load saved query from session on mount
  useEffect(() => {
    if (session.initial_query) {
      setQuery(session.initial_query);
    }
  }, [session.initial_query]);

  const pollCsvStatus = async (sessionId: string) => {
		const maxAttempts = 120; // 2 minutes max (120 * 1 second)
		let attempts = 0;
 
		const poll = setInterval(async () => {
			attempts++;
 
			try {
				const status = await apiClient.getSessionStatus(sessionId);
 
				if (status.csv_status === "completed") {
					clearInterval(poll);
					setCsvUploadStatus("success");
					session.setCsvStatus("completed");
					session.setCsvUploaded(true);
 
					// Update progress to 100%
					if (status.books_processed && status.books_total) {
						setCsvProgress(
							Math.round((status.books_processed / status.books_total) * 100),
						);
					}
				} else if (status.csv_status === "failed") {
					clearInterval(poll);
					setCsvUploadStatus("error");
					setCsvError("CSV processing failed. Please try again.");
					session.setCsvStatus("failed");
				} else if (status.csv_status === "processing") {
					// Update progress
					if (status.books_processed && status.books_total) {
						setCsvProgress(
							Math.round((status.books_processed / status.books_total) * 100),
						);
					}
					session.setCsvStatus("processing");
				}
 
				// Timeout after max attempts
				if (attempts >= maxAttempts) {
					clearInterval(poll);
					setCsvUploadStatus("error");
					setCsvError("Processing timed out. Please try again.");
				}
			} catch (error) {
				clearInterval(poll);
				setCsvUploadStatus("error");
				setCsvError(
					error instanceof Error
						? error.message
						: "Failed to check CSV status.",
				);
			}
		}, 1000); // Poll every second
	};

  // Check if user has existing session with CSV data and resume polling if needed
  useEffect(() => {
    if (session.csv_status === "completed") {
      setCsvUploadStatus("success");
    } else if (session.csv_status === "processing" && session.session_id) {
      // CSV is still processing - resume polling
      setCsvUploadStatus("uploading");
      pollCsvStatus(session.session_id);
    } else if (session.csv_status === "failed") {
      setCsvUploadStatus("error");
      setCsvError("CSV processing failed. Please try again.");
    }
  }, [session.csv_status, session.session_id, pollCsvStatus]);

  const handleFileSelect = async (file: File) => {
    setCsvFile(file);
    setCsvUploadStatus("uploading");
    setCsvError(null);
    setCsvProgress(0);

    try {
      // Create session with CSV immediately (use placeholder query if none entered)
      const response = await apiClient.createSession(
        query.trim() || "Help me find my next book",
        file,
      );

      // Save session info (including expiration)
      session.setSessionId(response.session_id);
      session.setExpiresAt(response.expires_at);
      if (query.trim()) {
        session.setInitialQuery(query.trim());
      }

      // Start polling for CSV processing
      session.setCsvStatus("processing");
      await pollCsvStatus(response.session_id);
    } catch (error) {
      setCsvUploadStatus("error");
      setCsvError(
        error instanceof Error
          ? error.message
          : "Failed to upload CSV. Please try again.",
      );
    }
  };

  const handleClearFile = () => {
    setCsvFile(null);
    setCsvUploadStatus("idle");
    setCsvError(null);
    session.clearCsvData();
  };

  const handleSubmit = async () => {
    if (!query.trim()) {
      return; // Button should be disabled, but double check
    }

    setIsSubmitting(true);
    setGeneralError(null);

    try {
      let sessionId = session.session_id;

      // If no session exists yet (no CSV uploaded), create new session
      if (!sessionId) {
        const response = await apiClient.createSession(
          query.trim(),
          csvFile || undefined,
        );

        sessionId = response.session_id;
        session.setSessionId(sessionId);
        session.setExpiresAt(response.expires_at);
        session.setInitialQuery(query.trim());

        // If CSV was just uploaded now, wait for processing
        if (csvFile || response.status === "processing_csv") {
          setCsvUploadStatus("uploading");
          setCsvProgress(0);
          session.setCsvStatus("processing");
          await pollCsvStatus(sessionId);
        }
      } else {
        // Session already exists (CSV was uploaded earlier), update query
        session.setInitialQuery(query.trim());

        // Update query in backend Redis session
        await apiClient.updateQuery(sessionId, query.trim());
      }

      // Validate question generation before navigating
      // Try to load the first question to ensure backend is working
      try {
        const questionResponse = await apiClient.generateQuestion(sessionId, {
          question_number: 1,
        });
        session.setQuestion(1, questionResponse.question);

        // Question generation successful, navigate to questions page
        router.push("/questions");
      } catch (questionError) {
        // Question generation failed - show error on main page
        setIsSubmitting(false);
        setGeneralError(
          questionError instanceof Error
            ? questionError.message
            : "We couldn't generate questions. Please try again.",
        );
      }
    } catch (error) {
      setIsSubmitting(false);
      setGeneralError(
        error instanceof Error
          ? error.message
          : "Failed to create session. Please try again.",
      );
    }
  };

  const canSubmit = query.trim().length > 0 && !isSubmitting;

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <Header />

      <main className="flex-1 flex items-center justify-center px-4 py-8 md:py-12">
        <div className="max-w-4xl w-full space-y-10">
          {/* Hero Section */}
          <div className="text-center space-y-4 opacity-0 animate-fade-in-up">
            <div className="flex justify-center mb-3">
              <BookOpen
                className="w-16 h-16 text-accent opacity-80"
                strokeWidth={1.5}
              />
            </div>
            <h1 className="text-hero text-primary font-heading">
              Discover Your Next
              <span className="block mt-1 text-accent italic">Great Read</span>
            </h1>
            <p className="text-xl text-muted max-w-2xl mx-auto font-light">
              Personalized book recommendations powered by your taste
            </p>
          </div>

          {/* Main Input Section - The Focal Point */}
          <div className="relative paper-card rounded-card p-8 md:p-10 space-y-6 overflow-hidden opacity-0 animate-fade-in-up delay-200">
            <label
              htmlFor="query"
              className="block text-h2 text-primary text-center relative z-10"
            >
              What kind of book are you looking for?
            </label>

            <Textarea
              id="query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="I'm looking for a character-driven novel with complex relationships, similar to The Remains of the Day but set in a contemporary setting..."
              className="relative z-10 min-h-[160px] text-lg resize-none border border-primary/20 focus:border-primary focus:ring-2 focus:ring-accent/20 rounded-component bg-white/50 backdrop-blur-sm"
              disabled={isSubmitting}
            />

            {/* Optional CSV Upload - De-emphasized */}
            <div className="space-y-3">
              <CSVUpload
                onFileSelect={handleFileSelect}
                onClearFile={handleClearFile}
                uploadStatus={csvUploadStatus}
                uploadProgress={csvProgress}
                fileName={csvFile?.name}
                errorMessage={csvError || undefined}
                alreadyUploaded={session.csv_uploaded}
              />
            </div>

            {/* CTA Button */}
            <div className="flex justify-center pt-4">
              <Button
                onClick={handleSubmit}
                disabled={!canSubmit}
                size="lg"
                className="bg-primary hover:bg-primary/90 text-cream font-bold px-12 py-7 text-xl rounded-component btn-hover-lift disabled:opacity-50 disabled:cursor-not-allowed shadow-lg relative overflow-hidden group"
              >
                <span className="relative z-10">
                  {isSubmitting ? "Processing..." : "Find My Next Book"}
                </span>
                <div className="absolute inset-0 bg-accent opacity-0 group-hover:opacity-10 transition-opacity duration-300" />
              </Button>
            </div>

            {/* Error Message */}
            {generalError && (
              <div className="bg-error/5 border border-error/30 rounded-component p-4 text-center backdrop-blur-sm">
                <p className="text-error font-medium">{generalError}</p>
              </div>
            )}
          </div>

          {/* Trust Indicators */}
          <div className="pt-4 flex flex-wrap items-center justify-center gap-6 md:gap-8 text-sm text-muted opacity-0 animate-fade-in delay-400">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-secondary" />
              <span>Open source</span>
            </div>
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-secondary" />
              <span>Privacy-friendly</span>
            </div>
            <div className="flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-secondary" />
              <span>No data stored</span>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
