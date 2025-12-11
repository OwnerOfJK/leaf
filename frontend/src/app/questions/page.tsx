"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Header } from "../components/Header";
import { Footer } from "../components/Footer";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ChevronLeft, ChevronRight, Loader2, CheckCircle2 } from "lucide-react";
import { useSession } from "@/contexts/SessionContext";
import { apiClient } from "@/lib/api-client";

export default function QuestionsPage() {
	const router = useRouter();
	const session = useSession();

	const [currentQuestion, setCurrentQuestion] = useState<1 | 2 | 3>(1);
	const [currentAnswer, setCurrentAnswer] = useState("");
	const [isLoadingQuestion, setIsLoadingQuestion] = useState(false);
	const [isSubmitting, setIsSubmitting] = useState(false);

	// Redirect if no session
	useEffect(() => {
		if (!session.session_id) {
			router.push("/");
		}
	}, [session.session_id, router]);

	// Load question when component mounts or question number changes
	useEffect(() => {
		loadQuestion(currentQuestion);
	}, [currentQuestion]);

	// Load answer for current question if it exists
	useEffect(() => {
		const existingAnswer =
			session.answers[`question_${currentQuestion}` as keyof typeof session.answers];
		setCurrentAnswer(existingAnswer || "");
	}, [currentQuestion, session.answers]);

	const loadQuestion = async (questionNum: 1 | 2 | 3) => {
		// Check if we already have this question loaded
		const existingQuestion =
			session.questions[`question_${questionNum}` as keyof typeof session.questions];

		if (existingQuestion) {
			return; // Already loaded
		}

		setIsLoadingQuestion(true);

		try {
	  if (!session.session_id) return;
      const response = await apiClient.generateQuestion(session.session_id, {
        question_number: questionNum,
      });
			session.setQuestion(questionNum, response.question);
		} catch (error) {
			console.error("Failed to load question:", error);

			// If session expired, clear and redirect to home
			if (error instanceof Error && (error.message.includes("expired") || error.message.includes("not found"))) {
				console.log("Session expired, redirecting to home...");
				session.clearSession();
				router.push("/");
				return;
			}

			// Fallback to default question if generation fails
			const fallbackQuestions = {
				1: "What themes or subjects are you most drawn to in books?",
				2: "How do you prefer books to make you feel - challenged and thought-provoking, or comforted and entertained?",
				3: "Are there any specific writing styles, pacing, or narrative structures you particularly enjoy or want to avoid?",
			};
			session.setQuestion(questionNum, fallbackQuestions[questionNum]);
		} finally {
			setIsLoadingQuestion(false);
		}
	};

	const handleBack = async () => {
		// Save current answer before going back (syncs to backend automatically)
		await session.setAnswer(currentQuestion, currentAnswer || null);

		if (currentQuestion > 1) {
			setCurrentQuestion((prev) => (prev - 1) as 1 | 2 | 3);
		} else {
			// On question 1, go back to main page
			router.push("/");
		}
	};

	const handleNext = async () => {
		// Save current answer (syncs to backend automatically)
		await session.setAnswer(currentQuestion, currentAnswer || null);

		if (currentQuestion < 3) {
			// Move to next question (backend now has answer for context)
			setCurrentQuestion((prev) => (prev + 1) as 1 | 2 | 3);
		} else {
			// Final question - navigate to recommendations
			await handleSubmit();
		}
	};

	const handleSkip = async () => {
		// Save as null (skipped) - syncs to backend automatically
		await session.setAnswer(currentQuestion, null);

		if (currentQuestion < 3) {
			setCurrentQuestion((prev) => (prev + 1) as 1 | 2 | 3);
		} else {
			// On last question, skip means submit with all current answers
			handleSubmit();
		}
	};

	const handleSubmit = async () => {
		if (!session.session_id) return;

		setIsSubmitting(true);

		// Answers already synced via setAnswer() - just navigate
		router.push("/recommendations");
	};

	const currentQuestionText =
		session.questions[`question_${currentQuestion}` as keyof typeof session.questions];

	const progressPercentage = (currentQuestion / 3) * 100;

	if (!session.session_id) {
		return null; // Will redirect via useEffect
	}

	return (
		<div className="min-h-screen flex flex-col bg-background">
			<Header />

			{/* CSV Status Indicator - Always visible if CSV uploaded */}
			{session.csv_uploaded && (
				<div className="fixed top-20 right-4 z-50">
					{(session.csv_status === "processing" || session.csv_status === "pending") && (
						<div className="bg-icy-blue-light rounded-lg shadow-lg px-4 py-3 flex items-center gap-2 border border-secondary">
							<Loader2 className="w-4 h-4 animate-spin text-secondary" />
							<span className="text-sm text-gray-700">Processing library...</span>
						</div>
					)}
					{session.csv_status === "completed" && (
						<div className="bg-green-50 rounded-lg shadow-lg px-4 py-3 flex items-center gap-2 border border-green-200">
							<CheckCircle2 className="w-4 h-4 text-green-600" />
							<span className="text-sm text-green-700">Library ready!</span>
						</div>
					)}
				</div>
			)}

			<main className="flex-1 flex items-center justify-center px-4 py-12">
				<div className="max-w-2xl w-full space-y-8">
					{/* Progress Indicator */}
					<div className="flex items-center justify-between mb-8">
						{[1, 2, 3].map((step) => (
							<div key={step} className="flex items-center flex-1">
								<div className="flex flex-col items-center flex-1">
									<div
										className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold transition-all ${
											step <= currentQuestion
												? "bg-secondary text-white scale-110 shadow-lg shadow-secondary/30"
												: "bg-gray-200 text-gray-500"
										}`}
									>
										{step}
									</div>
									<p className="text-xs mt-2 text-gray-600">
										Question {step}
									</p>
								</div>

								{step < 3 && (
									<div
										className={`h-1 flex-1 mx-2 transition-all ${
											step < currentQuestion
												? "bg-secondary"
												: "bg-gray-200"
										}`}
									/>
								)}
							</div>
						))}
					</div>

					{/* Question Card */}
					<div className="bg-white rounded-card shadow-md p-8 space-y-6">
						<div className="space-y-4">
							<Badge variant="outline" className="text-xs">
								{currentQuestion} of 3
							</Badge>

							{isLoadingQuestion ? (
								<div className="flex items-center gap-3 py-4">
									<Loader2 className="w-5 h-5 animate-spin text-secondary" />
									<p className="text-lg text-gray-600">
										Generating question...
									</p>
								</div>
							) : (
								<h2 className="text-h2 text-gray-900">
									{currentQuestionText ||
										"Loading question..."}
								</h2>
							)}

							{session.csv_uploaded && (
								<p className="text-sm text-gray-500 italic">
									Based on your library and previous answers
								</p>
							)}
						</div>

						<Textarea
							value={currentAnswer}
							onChange={(e) => setCurrentAnswer(e.target.value)}
							placeholder="Share your thoughts..."
							className="min-h-[150px] text-base resize-none"
							disabled={isLoadingQuestion || isSubmitting}
						/>

						<button
							onClick={handleSkip}
							className="text-sm text-gray-500 hover:text-secondary hover:underline transition-colors"
							disabled={isLoadingQuestion || isSubmitting}
						>
							Skip this question
						</button>
					</div>

					{/* Navigation Buttons */}
					<div className="flex items-center justify-between gap-4">
						<Button
							onClick={handleBack}
							variant="outline"
							size="lg"
							disabled={isSubmitting}
							className="flex items-center gap-2"
						>
							<ChevronLeft className="w-4 h-4" />
							Back
						</Button>

						<Button
							onClick={handleNext}
							size="lg"
							disabled={isLoadingQuestion || isSubmitting}
							className="bg-accent hover:bg-accent-dark text-white font-semibold px-8 flex items-center gap-2 btn-hover-lift"
						>
							{isSubmitting ? (
								<>
									<Loader2 className="w-4 h-4 animate-spin" />
									Processing...
								</>
							) : currentQuestion === 3 ? (
								"Get My Recommendations"
							) : (
								<>
									Next
									<ChevronRight className="w-4 h-4" />
								</>
							)}
						</Button>
					</div>
				</div>
			</main>

			<Footer />
		</div>
	);
}
