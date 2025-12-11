"use client";

import { useState, useRef } from "react";
import { Upload, CheckCircle, XCircle, X, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

interface CSVUploadProps {
	onFileSelect: (file: File) => void;
	onClearFile: () => void;
	uploadStatus: "idle" | "uploading" | "success" | "error";
	uploadProgress?: number;
	fileName?: string;
	errorMessage?: string;
	alreadyUploaded?: boolean;
}

export function CSVUpload({
	onFileSelect,
	onClearFile,
	uploadStatus,
	uploadProgress = 0,
	fileName,
	errorMessage,
	alreadyUploaded = false,
}: CSVUploadProps) {
	const fileInputRef = useRef<HTMLInputElement>(null);
	const [dragActive, setDragActive] = useState(false);

	const handleDrag = (e: React.DragEvent) => {
		e.preventDefault();
		e.stopPropagation();
		if (e.type === "dragenter" || e.type === "dragover") {
			setDragActive(true);
		} else if (e.type === "dragleave") {
			setDragActive(false);
		}
	};

	const handleDrop = (e: React.DragEvent) => {
		e.preventDefault();
		e.stopPropagation();
		setDragActive(false);

		const files = e.dataTransfer.files;
		if (files && files[0]) {
			handleFile(files[0]);
		}
	};

	const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
		const files = e.target.files;
		if (files && files[0]) {
			handleFile(files[0]);
		}
	};

	const handleFile = (file: File) => {
		if (file.type !== "text/csv" && !file.name.endsWith(".csv")) {
			// Could show error here
			return;
		}
		onFileSelect(file);
	};

	const handleClick = () => {
		if (uploadStatus === "success" || alreadyUploaded) {
			onClearFile();
		} else if (uploadStatus === "error") {
			// Clear error state first, then user can upload again
			onClearFile();
		} else {
			fileInputRef.current?.click();
		}
	};

	// If already uploaded or success, show uploaded state
	if (uploadStatus === "success" || alreadyUploaded) {
		return (
			<div className="w-full">
				<div className="border-2 border-success rounded-component p-6 bg-green-50 flex items-center justify-between">
					<div className="flex items-center gap-3">
						<CheckCircle className="w-6 h-6 text-success" />
						<div>
							<p className="font-medium text-gray-900">
								{fileName || "Goodreads library uploaded"}
							</p>
							<p className="text-sm text-gray-600">
								Your reading history is ready
							</p>
						</div>
					</div>
					<Button
						onClick={onClearFile}
						variant="ghost"
						size="sm"
						className="text-gray-600 hover:text-error"
					>
						<X className="w-4 h-4 mr-1" />
						Clear CSV
					</Button>
				</div>
			</div>
		);
	}

	// If uploading, show progress
	if (uploadStatus === "uploading") {
		return (
			<div className="w-full">
				<div className="border-2 border-secondary rounded-component p-6 bg-icy-blue-light">
					<div className="flex items-center gap-3 mb-3">
						<FileText className="w-6 h-6 text-secondary animate-pulse" />
						<div className="flex-1">
							<p className="font-medium text-gray-900">{fileName}</p>
							<p className="text-sm text-gray-600">
								Processing your library...
							</p>
						</div>
					</div>
					<Progress value={uploadProgress} className="h-2" />
					<p className="text-xs text-gray-600 mt-2 text-right">
						{uploadProgress}%
					</p>
				</div>
			</div>
		);
	}

	// If error, show error state
	if (uploadStatus === "error") {
		return (
			<div className="w-full">
				<div className="border-2 border-error rounded-component p-6 bg-red-50 flex items-center justify-between">
					<div className="flex items-center gap-3">
						<XCircle className="w-6 h-6 text-error" />
						<div>
							<p className="font-medium text-gray-900">Upload failed</p>
							<p className="text-sm text-error">
								{errorMessage ||
									"We couldn't read this file. Make sure it's exported from Goodreads."}
							</p>
						</div>
					</div>
					<Button
						onClick={handleClick}
						variant="outline"
						size="sm"
						className="border-error text-error hover:bg-error hover:text-white"
					>
						Try Again
					</Button>
				</div>
			</div>
		);
	}

	// Default: idle state (upload prompt)
	return (
		<div className="w-full">
			<div
				onDragEnter={handleDrag}
				onDragLeave={handleDrag}
				onDragOver={handleDrag}
				onDrop={handleDrop}
				onClick={handleClick}
				className={`
          border-2 border-dashed rounded-component p-8
          cursor-pointer transition-all duration-200
          ${
						dragActive
							? "border-secondary bg-icy-blue-light scale-[1.02]"
							: "border-gray-300 hover:border-secondary hover:bg-icy-blue-light/50"
					}
        `}
			>
				<div className="flex flex-col items-center text-center gap-4">
					<div className="w-8 h-8 rounded-full bg-secondary/10 flex items-center justify-center">
						<Upload className="w-4 h-4 text-secondary" />
					</div>

					<div className="flex items-center gap-2 flex-wrap justify-center">
						<p className="text-lg font-semibold text-gray-900">
							Upload your Goodreads library
						</p>
						<a
							href="https://www.goodreads.com/review/import"
							target="_blank"
							rel="noopener noreferrer"
							onClick={(e) => e.stopPropagation()}
							className="text-sm text-secondary hover:underline"
						>
							(How To)
						</a>
					</div>

					<p className="text-xs text-gray-500 max-w-md">
						Your reading history helps us understand your taste (optional but
						recommended)
					</p>
				</div>

				<input
					ref={fileInputRef}
					type="file"
					accept=".csv"
					onChange={handleFileInput}
					className="hidden"
					aria-label="Upload CSV file"
				/>
			</div>
		</div>
	);
}
