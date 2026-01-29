"use client";

import {
  BookOpen,
  CheckCircle,
  ExternalLink,
  Library,
  Loader2,
  SkipForward,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useSession } from "@/contexts/SessionContext";
import { apiClient } from "@/lib/api-client";
import type { Recommendation } from "@/types/api";
import { Footer } from "../components/Footer";
import { Header } from "../components/Header";

const AMAZON_TAG = "leaf07-21";

type PagePhase =
  | "loading_recommendations"
  | "waiting_for_csv"
  | "csv_ready"
  | "csv_failed"
  | "done";

export default function RecommendationsPage() {
  const router = useRouter();
  const session = useSession();

  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Record<number, "like" | "dislike">>(
    {},
  );
  const [feedbackSuccess, setFeedbackSuccess] = useState<number | null>(null);
  const [phase, setPhase] = useState<PagePhase>("loading_recommendations");
  const [booksProcessed, setBooksProcessed] = useState<number | null>(null);
  const [booksTotal, setBooksTotal] = useState<number | null>(null);

  // Track if recommendations have been loaded to prevent duplicate calls
  const hasLoadedRef = useRef(false);
  const currentSessionRef = useRef<string | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const loadRecommendations = useCallback(async () => {
    if (!session.session_id) return;

    setPhase("loading_recommendations");
    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.getRecommendations(session.session_id);
      setRecommendations(response.recommendations);
      setPhase("done");
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "We couldn't generate recommendations. Please try again.",
      );
      setPhase("done");
    } finally {
      setIsLoading(false);
    }
  }, [session.session_id]);

  const startPolling = useCallback(() => {
    if (!session.session_id) return;

    const poll = async () => {
      try {
        const status = await apiClient.getSessionStatus(session.session_id!);
        setBooksProcessed(status.books_processed);
        setBooksTotal(status.books_total);

        if (status.csv_status === "completed") {
          stopPolling();
          session.setCsvStatus("completed");
          setPhase("csv_ready");
        } else if (status.csv_status === "failed") {
          stopPolling();
          session.setCsvStatus("failed");
          setPhase("csv_failed");
        }
      } catch {
        // Silently continue polling on error
      }
    };

    // Poll immediately, then every 2 seconds
    poll();
    pollingRef.current = setInterval(poll, 2000);
  }, [session.session_id, session.setCsvStatus, stopPolling]);

  // Clean up polling on unmount
  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  // Redirect if no session; determine initial phase
  useEffect(() => {
    if (!session.session_id) {
      router.push("/");
      return;
    }

    // Reset ref if session changed
    if (currentSessionRef.current !== session.session_id) {
      hasLoadedRef.current = false;
      currentSessionRef.current = session.session_id;
    }

    if (hasLoadedRef.current) return;
    hasLoadedRef.current = true;

    const csvStatus = session.csv_status;
    const csvUploaded = session.csv_uploaded;

    if (
      !csvUploaded ||
      csvStatus === "none" ||
      csvStatus === "completed"
    ) {
      loadRecommendations();
    } else if (csvStatus === "processing" || csvStatus === "pending") {
      setPhase("waiting_for_csv");
      startPolling();
    } else if (csvStatus === "failed") {
      setPhase("csv_failed");
    }
  }, [session.session_id, session.csv_status, session.csv_uploaded, router, loadRecommendations, startPolling]);

  const handleSkipUpload = () => {
    stopPolling();
    session.setCsvUploaded(false);
    loadRecommendations();
  };

  const handleGetRecommendations = () => {
    loadRecommendations();
  };

  const handleContinueWithoutCsv = () => {
    session.setCsvUploaded(false);
    loadRecommendations();
  };

  const handleFeedback = async (
    recommendationId: number,
    type: "like" | "dislike",
    rank: 1 | 2 | 3
  ) => {
    // Optimistic update
    setFeedback((prev) => ({ ...prev, [recommendationId]: type }));

    try {
      await apiClient.submitFeedback(recommendationId, rank, {
        feedback_type: type,
        rank: rank,
      });

      // Show success message
      setFeedbackSuccess(recommendationId);
      setTimeout(() => setFeedbackSuccess(null), 3000);
    } catch (error) {
      console.error("Failed to submit feedback:", error);
      // Silent fail - don't interrupt user experience
    }
  };

  const handleStartOver = () => {
    // Reset session but keep CSV data
    session.resetSession();
    router.push("/");
  };

  const getAmazonLink = (isbn: string) => {
    return `https://www.amazon.com/dp/${isbn}/?tag=${AMAZON_TAG}`;
  };

  const getConfidenceColor = (score: number) => {
    if (score >= 80) return "bg-success/10 text-success border-success/30";
    if (score >= 60)
      return "bg-secondary/10 text-secondary border-secondary/30";
    return "bg-accent/20 text-primary border-accent/40";
  };

  // Sort and reorder for podium effect: 2nd, 1st, 3rd (left to right)
  const sorted = [...recommendations].sort((a, b) => a.rank - b.rank);
  const podiumOrder =
    sorted.length >= 3 ? [sorted[1], sorted[0], sorted[2]] : sorted;

  if (!session.session_id) {
    return null; // Will redirect via useEffect
  }

  if (phase === "waiting_for_csv") {
    return (
      <div className="min-h-screen flex flex-col bg-background">
        <Header />
        <main className="flex-1 flex items-center justify-center px-4">
          <div className="text-center space-y-6 opacity-0 animate-fade-in max-w-md">
            <Library
              className="w-16 h-16 text-accent mx-auto opacity-80 animate-pulse"
              strokeWidth={1.5}
            />
            <div className="space-y-2">
              <Loader2 className="w-10 h-10 animate-spin text-primary mx-auto" />
              <p className="text-2xl text-primary font-heading font-bold">
                Processing Your Reading Library
              </p>
              <p className="text-lg text-muted">
                We're analyzing your Goodreads export to personalize your recommendations...
              </p>
              {booksTotal !== null && booksProcessed !== null && (
                <p className="text-sm text-muted font-medium">
                  {booksProcessed} / {booksTotal} books processed
                </p>
              )}
            </div>
            <Button
              onClick={handleSkipUpload}
              variant="outline"
              className="border-primary/30 text-primary hover:bg-primary/5 font-semibold"
            >
              <SkipForward className="w-4 h-4 mr-2" />
              Skip Upload
            </Button>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  if (phase === "csv_ready") {
    return (
      <div className="min-h-screen flex flex-col bg-background">
        <Header />
        <main className="flex-1 flex items-center justify-center px-4">
          <div className="text-center space-y-6 opacity-0 animate-fade-in max-w-md">
            <CheckCircle
              className="w-16 h-16 text-success mx-auto opacity-80"
              strokeWidth={1.5}
            />
            <div className="space-y-2">
              <p className="text-2xl text-primary font-heading font-bold">
                Library Ready!
              </p>
              <p className="text-lg text-muted">
                Your reading history has been processed. Ready to find your next great read.
              </p>
            </div>
            <Button
              onClick={handleGetRecommendations}
              className="bg-primary hover:bg-primary/90 text-cream font-bold btn-hover-lift"
            >
              <BookOpen className="w-4 h-4 mr-2" />
              Get Recommendations
            </Button>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  if (phase === "csv_failed") {
    return (
      <div className="min-h-screen flex flex-col bg-background">
        <Header />
        <main className="flex-1 flex items-center justify-center px-4">
          <div className="max-w-md text-center space-y-6 paper-card p-8 rounded-card opacity-0 animate-fade-in-up">
            <BookOpen
              className="w-16 h-16 text-muted mx-auto opacity-50"
              strokeWidth={1.5}
            />
            <h2 className="text-h2 text-primary">
              CSV Processing Failed
            </h2>
            <p className="text-muted">
              We couldn't process your Goodreads export. You can still get recommendations based on your preferences.
            </p>
            <Button
              onClick={handleContinueWithoutCsv}
              className="bg-primary hover:bg-primary/90 text-cream font-bold btn-hover-lift"
            >
              Continue Without CSV
            </Button>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex flex-col bg-background">
        <Header />
        <main className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-5 opacity-0 animate-fade-in">
            <BookOpen
              className="w-16 h-16 text-accent mx-auto opacity-80 animate-pulse"
              strokeWidth={1.5}
            />
            <div className="space-y-2">
              <Loader2 className="w-10 h-10 animate-spin text-primary mx-auto" />
              <p className="text-2xl text-primary font-heading font-bold">
                Curating Your Selections
              </p>
              <p className="text-lg text-muted">
                Finding the perfect books just for you...
              </p>
            </div>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex flex-col bg-background">
        <Header />
        <main className="flex-1 flex items-center justify-center px-4">
          <div className="max-w-md text-center space-y-6 paper-card p-8 rounded-card opacity-0 animate-fade-in-up">
            <BookOpen
              className="w-16 h-16 text-muted mx-auto opacity-50"
              strokeWidth={1.5}
            />
            <h2 className="text-h2 text-primary">
              We couldn't find perfect matches
            </h2>
            <p className="text-muted">{error}</p>
            <Button
              onClick={loadRecommendations}
              className="bg-primary hover:bg-primary/90 text-cream font-bold btn-hover-lift"
            >
              Try Again
            </Button>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  if (recommendations.length === 0) {
    return (
      <div className="min-h-screen flex flex-col bg-background">
        <Header />
        <main className="flex-1 flex items-center justify-center px-4">
          <div className="max-w-md text-center space-y-6 paper-card p-8 rounded-card opacity-0 animate-fade-in-up">
            <BookOpen
              className="w-16 h-16 text-muted mx-auto opacity-50"
              strokeWidth={1.5}
            />
            <h2 className="text-h2 text-primary">No matches found</h2>
            <p className="text-muted">
              Try adjusting your preferences or adding more details.
            </p>
            <Button
              onClick={handleStartOver}
              className="bg-primary hover:bg-primary/90 text-cream font-bold btn-hover-lift"
            >
              Start Over
            </Button>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <Header />

      <main className="flex-1 px-4 py-12">
        <div className="max-w-7xl mx-auto space-y-10">
          {/* Page Header */}
          <div className="text-center space-y-4 opacity-0 animate-fade-in-up">
            <BookOpen
              className="w-12 h-12 text-accent mx-auto opacity-80"
              strokeWidth={1.5}
            />
            <h1 className="text-hero text-primary font-heading">
              Your Personal Library
            </h1>
            <p className="text-xl text-muted font-light max-w-2xl mx-auto">
              Three exceptional books selected just for you
              {session.csv_uploaded && ", based on your unique reading history"}
            </p>
            <div className="flex items-center justify-center gap-3">
              <div className="h-px w-16 bg-primary/20" />
              <BookOpen className="w-5 h-5 text-accent/60" strokeWidth={1.5} />
              <div className="h-px w-16 bg-primary/20" />
            </div>
          </div>

          {/* Recommendations Grid - Podium Layout */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8">
            {podiumOrder.map((rec, index) => {
              const isCenter = rec.rank === 1;
              const userFeedback = feedback[rec.id];
              const showSuccess = feedbackSuccess === rec.id;
              const animationDelay =
                index === 0
                  ? "delay-200"
                  : index === 1
                    ? "delay-300"
                    : "delay-400";

              return (
                <Card
                  key={rec.id}
                  className={`relative paper-card p-0 overflow-hidden card-hover opacity-0 animate-fade-in-up ${animationDelay} ${
                    isCenter
                      ? "md:scale-105 border-2 border-accent/40 shadow-xl"
                      : "border border-primary/10"
                  }`}
                >
                  {/* Rank Badge */}
                  <div
                    className={`absolute top-4 left-4 w-12 h-12 rounded-full flex items-center justify-center font-bold text-xl shadow-xl z-10 ${
                      rec.rank === 1
                        ? "bg-accent text-primary ring-2 ring-accent/20"
                        : rec.rank === 2
                          ? "bg-secondary text-cream ring-2 ring-secondary/20"
                          : "bg-primary/80 text-cream ring-2 ring-primary/20"
                    }`}
                  >
                    {rec.rank}
                  </div>

                  {/* Confidence Badge */}
                  <Badge
                    className={`absolute top-4 right-4 font-semibold z-10 shadow-md ${getConfidenceColor(
                      rec.confidence_score,
                    )}`}
                  >
                    {Math.round(rec.confidence_score)}% Match
                  </Badge>

                  {/* Book Cover */}
                  <div className="flex justify-center pt-8 pb-4">
                    {rec.book.cover_url ? (
                      <Image
                        src={rec.book.cover_url}
                        alt={`${rec.book.title} cover`}
                        width={150}
                        height={224}
                        className="h-56 w-auto object-contain rounded-sm shadow-lg transition-transform hover:scale-105 duration-300"
                        unoptimized
                      />
                    ) : (
                      <div className="h-56 w-36 bg-gradient-to-br from-cream-dark to-primary/10 rounded-sm flex flex-col items-center justify-center border border-primary/20 shadow-md">
                        <BookOpen
                          className="w-16 h-16 text-primary/30 mb-2"
                          strokeWidth={1.5}
                        />
                        <p className="text-xs text-muted text-center px-2 italic">
                          Cover unavailable
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Book Information */}
                  <div className="space-y-3 px-6 pb-4">
                    <a
                      href={getAmazonLink(rec.book.isbn)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="group block"
                    >
                      <h3 className="text-xl font-bold text-primary group-hover:text-secondary transition-colors font-heading leading-tight line-clamp-2 mb-1">
                        {rec.book.title}
                      </h3>
                      <span className="text-xs text-secondary group-hover:underline inline-flex items-center gap-1">
                        View on Amazon
                        <ExternalLink className="w-3 h-3" />
                      </span>
                    </a>

                    <p className="text-text font-medium text-base">
                      by {rec.book.author}
                    </p>

                    {rec.book.publication_year && (
                      <p className="text-xs text-muted italic">
                        {rec.book.publication_year}
                      </p>
                    )}

                    {rec.book.categories && rec.book.categories.length > 0 && (
                      <div className="flex flex-wrap gap-2 pt-1">
                        {rec.book.categories.slice(0, 3).map((category) => (
                          <Badge
                            key={category}
                            variant="secondary"
                            className="text-xs bg-secondary/10 text-secondary border border-secondary/20 font-medium"
                          >
                            {category}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Explanation */}
                  <div className="mx-6 mb-4 bg-cream-dark/50 rounded-component p-4 space-y-2 border border-primary/10">
                    <p className="text-xs font-bold text-primary uppercase tracking-wider">
                      Why We Recommend This
                    </p>
                    <p className="text-sm text-text leading-relaxed">
                      {rec.explanation}
                    </p>
                  </div>

                  {/* Feedback Buttons */}
                  <div className="flex items-center gap-3 px-6 pb-6 pt-2">
                    <Button
                      onClick={() => handleFeedback(rec.id, "like", rec.rank)}
                      disabled={userFeedback !== undefined}
                      variant={userFeedback === "like" ? "default" : "outline"}
                      size="sm"
                      className={`flex-1 transition-all font-semibold ${
                        userFeedback === "like"
                          ? "bg-success hover:bg-success/90 text-cream border-success shadow-md"
                          : "border-primary/30 text-primary hover:bg-primary/5"
                      }`}
                    >
                      <ThumbsUp
                        className={`w-4 h-4 mr-2 ${
                          userFeedback === "like" ? "fill-current" : ""
                        }`}
                      />
                      Perfect Match
                    </Button>

                    <Button
                      onClick={() => handleFeedback(rec.id, "dislike", rec.rank)}
                      disabled={userFeedback !== undefined}
                      variant={
                        userFeedback === "dislike" ? "default" : "outline"
                      }
                      size="sm"
                      className={`flex-1 transition-all font-semibold ${
                        userFeedback === "dislike"
                          ? "bg-error hover:bg-error/90 text-cream border-error shadow-md"
                          : "border-primary/30 text-primary hover:bg-primary/5"
                      }`}
                    >
                      <ThumbsDown
                        className={`w-4 h-4 mr-2 ${
                          userFeedback === "dislike" ? "fill-current" : ""
                        }`}
                      />
                      Not For Me
                    </Button>
                  </div>

                  {/* Success Message */}
                  {showSuccess && (
                    <div className="mx-6 mb-4 bg-success/10 backdrop-blur-sm border border-success/30 rounded-component px-4 py-2.5 text-sm text-success text-center font-semibold animate-in fade-in slide-in-from-bottom-2 flex items-center justify-center gap-2">
                      <CheckCircle className="w-4 h-4" />
                      Thank you for your feedback!
                    </div>
                  )}
                </Card>
              );
            })}
          </div>

          {/* Bottom Section */}
          <div className="text-center space-y-6 pt-10 opacity-0 animate-fade-in delay-500">
            <p className="text-lg text-muted font-light">
              Ready to explore more?
            </p>
            <Button
              onClick={handleStartOver}
              variant="outline"
              className="hover:bg-secondary hover:text-cream border-secondary/50 hover:border-secondary text-secondary font-semibold btn-hover-lift"
            >
              Start a New Search
            </Button>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
