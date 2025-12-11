"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Header } from "../components/Header";
import { Footer } from "../components/Footer";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
	ThumbsUp,
	ThumbsDown,
	Loader2,
	BookOpen,
	ExternalLink,
} from "lucide-react";
import { useSession } from "@/contexts/SessionContext";
import { apiClient } from "@/lib/api-client";
import type { Recommendation } from "@/types/api";

const AMAZON_TAG = "leaf07-21"

export default function RecommendationsPage() {
	const router = useRouter();
	const session = useSession();

	const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [feedback, setFeedback] = useState<Record<number, "like" | "dislike">>(
		{},
	);
	const [feedbackSuccess, setFeedbackSuccess] = useState<number | null>(null);

	// Track if recommendations have been loaded to prevent duplicate calls
	const hasLoadedRef = useRef(false);
	const currentSessionRef = useRef<string | null>(null);

	// Redirect if no session and load recommendations
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

		// Only load once per session_id
		if (!hasLoadedRef.current) {
			hasLoadedRef.current = true;
			loadRecommendations();
		}
	}, [session.session_id, router]);

	const loadRecommendations = async () => {
		if (!session.session_id) return;

		setIsLoading(true);
		setError(null);

		try {
			const response = await apiClient.getRecommendations(session.session_id);
			setRecommendations(response.recommendations);
		} catch (error) {
			setError(
				error instanceof Error
					? error.message
					: "We couldn't generate recommendations. Please try again.",
			);
		} finally {
			setIsLoading(false);
		}
	};

	const handleFeedback = async (
		recommendationId: number,
		type: "like" | "dislike",
	) => {
		// Optimistic update
		setFeedback((prev) => ({ ...prev, [recommendationId]: type }));

		try {
			await apiClient.submitFeedback(recommendationId, {
				feedback_type: type,
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
		if (score >= 80) return "bg-green-100 text-green-800 border-green-200";
		if (score >= 60) return "bg-blue-100 text-blue-800 border-blue-200";
		return "bg-yellow-100 text-yellow-800 border-yellow-200";
	};

	// Sort and reorder for podium effect: 2nd, 1st, 3rd (left to right)
	const sorted = [...recommendations].sort((a, b) => a.rank - b.rank);
	const podiumOrder = [sorted[1], sorted[0], sorted[2]];

	if (!session.session_id) {
		return null; // Will redirect via useEffect
	}

	if (isLoading) {
		return (
			<div className="min-h-screen flex flex-col bg-background">
				<Header />
				<main className="flex-1 flex items-center justify-center">
					<div className="text-center space-y-4">
						<Loader2 className="w-12 h-12 animate-spin text-secondary mx-auto" />
						<p className="text-xl text-gray-600">
							Curating your perfect recommendations...
						</p>
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
					<div className="max-w-md text-center space-y-6">
						<BookOpen className="w-16 h-16 text-gray-400 mx-auto" />
						<h2 className="text-h2 text-gray-900">
							Hmm, we couldn't find great matches
						</h2>
						<p className="text-gray-600">{error}</p>
						<Button
							onClick={loadRecommendations}
							className="bg-accent hover:bg-accent-dark text-white"
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
					<div className="max-w-md text-center space-y-6">
						<BookOpen className="w-16 h-16 text-gray-400 mx-auto" />
						<h2 className="text-h2 text-gray-900">
							Hmm, we couldn't find great matches
						</h2>
						<p className="text-gray-600">
							Try adjusting your preferences or adding more details.
						</p>
						<Button
							onClick={handleStartOver}
							className="bg-accent hover:bg-accent-dark text-white"
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
				<div className="max-w-7xl mx-auto space-y-8">
					{/* Page Header */}
					<div className="text-center space-y-3">
						<h1 className="text-h1 text-primary font-heading">
							Your Personalized Recommendations
						</h1>
						<p className="text-lg text-gray-600">
							Based on your preferences
							{session.csv_uploaded && " and reading history"}
						</p>
					</div>

					{/* Recommendations Grid - Podium Layout */}
					<div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8">
						{podiumOrder.map((rec, index) => {
							const isCenter = rec.rank === 1;
							const userFeedback = feedback[rec.id];
							const showSuccess = feedbackSuccess === rec.id;

							return (
								<Card
									key={rec.id}
									className={`relative p-6 space-y-4 transition-all duration-300 card-hover ${
										isCenter
											? "md:scale-105 md:shadow-xl border-2 border-secondary/40"
											: "border border-gray-200"
									}`}
								>
									{/* Rank Badge */}
									<div
										className={`absolute top-4 left-4 w-10 h-10 rounded-full flex items-center justify-center font-bold text-lg shadow-lg ${
											rec.rank === 1
												? "bg-accent text-white"
												: rec.rank === 2
												? "bg-gray-400 text-white"
												: "bg-orange-400 text-white"
										}`}
									>
										#{rec.rank}
									</div>

									{/* Confidence Badge */}
									<Badge
										className={`absolute top-4 right-4 ${getConfidenceColor(
											rec.confidence_score,
										)}`}
									>
										{Math.round(rec.confidence_score)}% Match
									</Badge>

									{/* Book Cover */}
									<div className="flex justify-center pt-4">
										{rec.book.cover_url ? (
											<img
												src={rec.book.cover_url}
												alt={`${rec.book.title} cover`}
												className="h-48 w-auto object-contain rounded shadow-md"
											/>
										) : (
											<div className="h-48 w-32 bg-gray-200 rounded flex items-center justify-center">
												<BookOpen className="w-12 h-12 text-gray-400" />
											</div>
										)}
									</div>

									{/* Book Information */}
									<div className="space-y-2">
										<a
											href={getAmazonLink(rec.book.isbn)}
											target="_blank"
											rel="noopener noreferrer"
											className="text-xl font-bold text-gray-900 hover:text-secondary hover:underline transition-colors flex items-center gap-1"
										>
											{rec.book.title}
											<ExternalLink className="w-4 h-4" />
										</a>

										<p className="text-gray-700 font-medium">
											{rec.book.author}
										</p>

										{rec.book.publication_year && (
											<p className="text-sm text-gray-500">
												{rec.book.publication_year}
											</p>
										)}

										{rec.book.categories &&
											rec.book.categories.length > 0 && (
												<div className="flex flex-wrap gap-2 pt-2">
													{rec.book.categories
														.slice(0, 3)
														.map((category) => (
															<Badge
																key={category}
																variant="secondary"
																className="text-xs text-white"
															>
																{category}
															</Badge>
														))}
												</div>
											)}
									</div>

									{/* Explanation */}
									<div className="bg-gray-50 rounded-component p-4 space-y-2">
										<p className="text-sm font-semibold text-gray-700">
											Why we recommend this
										</p>
										<p className="text-sm text-gray-600">
											{rec.explanation}
										</p>
									</div>

									{/* Feedback Buttons */}
									<div className="flex items-center gap-3 pt-2">
										<Button
											onClick={() => handleFeedback(rec.id, "like")}
											disabled={userFeedback !== undefined}
											variant={
												userFeedback === "like"
													? "default"
													: "outline"
											}
											size="sm"
											className={`flex-1 ${
												userFeedback === "like"
													? "bg-green-600 hover:bg-green-700 text-white"
													: ""
											}`}
										>
											<ThumbsUp
												className={`w-4 h-4 mr-2 ${
													userFeedback === "like"
														? "fill-current"
														: ""
												}`}
											/>
											Like
										</Button>

										<Button
											onClick={() => handleFeedback(rec.id, "dislike")}
											disabled={userFeedback !== undefined}
											variant={
												userFeedback === "dislike"
													? "default"
													: "outline"
											}
											size="sm"
											className={`flex-1 ${
												userFeedback === "dislike"
													? "bg-red-600 hover:bg-red-700 text-white"
													: ""
											}`}
										>
											<ThumbsDown
												className={`w-4 h-4 mr-2 ${
													userFeedback === "dislike"
														? "fill-current"
														: ""
												}`}
											/>
											Dislike
										</Button>
									</div>

									{/* Success Message */}
									{showSuccess && (
										<div className="absolute bottom-4 left-4 right-4 bg-green-100 border border-green-200 rounded px-2 py-2 text-sm text-green-800 text-center animate-in fade-in slide-in-from-bottom-2">
											Thanks for your feedback!
										</div>
									)}
								</Card>
							);
						})}
					</div>

					{/* Bottom Section */}
					<div className="text-center space-y-4 pt-8">
						<p className="text-gray-600">
							Want more recommendations? Start a new search
						</p>
						<Button
							onClick={handleStartOver}
							variant="outline"
							className="hover:bg-secondary hover:text-white border-secondary/50 hover:border-secondary"
						>
							New Search
						</Button>
					</div>
				</div>
			</main>

			<Footer />
		</div>
	);
}
