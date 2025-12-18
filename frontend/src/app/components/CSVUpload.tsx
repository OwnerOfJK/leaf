"use client";

import { CheckCircle, Library, Upload, X, XCircle } from "lucide-react";
import { useRef, useState } from "react";
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
    if (files?.[0]) {
      handleFile(files[0]);
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files?.[0]) {
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
        <div className="border border-success/30 rounded-component p-5 bg-success/5 backdrop-blur-sm flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CheckCircle className="w-6 h-6 text-success" strokeWidth={2} />
            <div>
              <p className="font-semibold text-primary">
                {fileName || "Goodreads library uploaded"}
              </p>
              <p className="text-sm text-muted">
                Your reading history is ready
              </p>
            </div>
          </div>
          <Button
            onClick={onClearFile}
            variant="ghost"
            size="sm"
            className="text-muted hover:text-error hover:bg-error/5"
          >
            <X className="w-4 h-4 mr-1" />
            Remove
          </Button>
        </div>
      </div>
    );
  }

  // If uploading, show progress
  if (uploadStatus === "uploading") {
    return (
      <div className="w-full">
        <div className="border border-secondary/30 rounded-component p-5 bg-secondary/5 backdrop-blur-sm">
          <div className="flex items-center gap-3 mb-3">
            <Library
              className="w-6 h-6 text-secondary animate-pulse"
              strokeWidth={2}
            />
            <div className="flex-1">
              <p className="font-semibold text-primary">{fileName}</p>
              <p className="text-sm text-muted">
                Building your reading profile...
              </p>
            </div>
          </div>
          <Progress value={uploadProgress} className="h-2 bg-cream-dark" />
          <p className="text-xs text-muted mt-2 text-right font-medium">
            {uploadProgress}% complete
          </p>
        </div>
      </div>
    );
  }

  // If error, show error state
  if (uploadStatus === "error") {
    return (
      <div className="w-full">
        <div className="border border-error/30 rounded-component p-5 bg-error/5 backdrop-blur-sm flex items-center justify-between">
          <div className="flex items-center gap-3">
            <XCircle className="w-6 h-6 text-error" strokeWidth={2} />
            <div>
              <p className="font-semibold text-primary">Upload failed</p>
              <p className="text-sm text-error">
                {errorMessage ||
                  "Please ensure you're using a valid Goodreads export file."}
              </p>
            </div>
          </div>
          <Button
            onClick={handleClick}
            variant="outline"
            size="sm"
            className="border-error/30 text-error hover:bg-error hover:text-cream font-semibold"
          >
            Retry
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
          cursor-pointer transition-all duration-300
          ${
            dragActive
              ? "border-secondary bg-secondary/10 scale-[1.01] shadow-md"
              : "border-primary/20 hover:border-secondary hover:bg-secondary/5"
          }
        `}
      >
        <div className="flex flex-col items-center text-center gap-4">
          <div className="relative">
            <Library
              className="w-12 h-12 text-accent opacity-70"
              strokeWidth={1.5}
            />
            <Upload
              className="w-5 h-5 text-secondary absolute -bottom-1 -right-1"
              strokeWidth={2.5}
            />
          </div>

          <div className="flex items-center gap-2 flex-wrap justify-center">
            <p className="text-lg font-bold text-primary">
              Upload Your Goodreads Library
            </p>
            <a
              href="https://www.goodreads.com/review/import"
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-sm text-secondary hover:underline font-medium"
            >
              (Export Guide)
            </a>
          </div>

          <p className="text-sm text-muted max-w-md font-light">
            Help us personalize your recommendations by sharing your reading
            history
            <span className="block mt-1 text-xs italic">
              (Optional, but highly recommended)
            </span>
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
