"use client";

import React, { useState, useEffect, useRef } from "react";
import { UploadCloud, FileText, CheckCircle2, AlertCircle, Loader2, KeyRound } from "lucide-react";
import toast from "react-hot-toast";

interface ActionItem {
  title: string;
  description: string;
  assignee: string | null;
  priority: string;
  confidence: number;
}

interface ApiResponse {
  message: string;
  summary: string;
  processed_meeting_id: number;
  jira_tickets_created: number;
  pending_slack_approvals: number;
  action_items_extracted: number;
}

export default function Dashboard() {
  const [apiKey, setApiKey] = useState("");
  const [transcriptText, setTranscriptText] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<ApiResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load API Key from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem("pipeline_api_key");
    if (saved) setApiKey(saved);
  }, []);

  const handleApiKeyChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setApiKey(val);
    localStorage.setItem("pipeline_api_key", val);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = (file: File) => {
    if (file.type !== "text/plain") {
      toast.error("Please upload a .txt file.");
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      setTranscriptText(text);
      toast.success("Transcript loaded successfully!");
    };
    reader.readAsText(file);
  };

  const handleSubmit = async () => {
    if (!apiKey.trim()) {
      toast.error("Please enter your Pipeline API Key first.");
      return;
    }
    if (!transcriptText.trim()) {
      toast.error("Please provide a meeting transcript.");
      return;
    }

    setIsLoading(true);
    setResult(null);

    try {
      const res = await fetch("http://localhost:8000/process-meeting", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey,
        },
        body: JSON.stringify({ transcript_text: transcriptText }),
      });

      if (!res.ok) {
        let errorMsg = "An error occurred";
        try {
          const errData = await res.json();
          errorMsg = errData.detail || errorMsg;
        } catch {
          errorMsg = res.statusText;
        }
        throw new Error(errorMsg);
      }

      const data: ApiResponse = await res.json();
      setResult(data);
      toast.success("Meeting processed successfully!");
    } catch (err: any) {
      toast.error(`Pipeline Error: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      {/* Header */}
      <header className="bg-slate-900 text-white border-b border-slate-800 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-md bg-blue-500 flex items-center justify-center">
              <FileText className="w-5 h-5 text-white" />
            </div>
            <h1 className="text-xl font-semibold tracking-tight">Origin Medical</h1>
            <span className="text-slate-400 text-sm hidden sm:inline ml-2">| Meeting Intelligence Pipeline</span>
          </div>

          <div className="flex items-center gap-3">
            <KeyRound className="w-4 h-4 text-slate-400" />
            <input
              type="password"
              placeholder="Pipeline API Key"
              value={apiKey}
              onChange={handleApiKeyChange}
              className="bg-slate-800 border border-slate-700 text-sm rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 w-48 transition-all"
            />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          
          {/* Left Column: Ingestion Zone */}
          <div className="flex flex-col gap-6">
            <div>
              <h2 className="text-2xl font-semibold text-slate-900 mb-1">Upload Transcript</h2>
              <p className="text-slate-500 text-sm">Provide the raw text of your medical meeting to extract insights.</p>
            </div>

            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center gap-3 cursor-pointer transition-colors ${
                isDragging ? "border-blue-500 bg-blue-50" : "border-slate-300 bg-white hover:bg-slate-50 hover:border-slate-400"
              }`}
            >
              <input 
                type="file" 
                ref={fileInputRef} 
                onChange={handleFileSelect} 
                className="hidden" 
                accept=".txt" 
              />
              <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center text-slate-500">
                <UploadCloud className="w-6 h-6" />
              </div>
              <div className="text-center">
                <p className="font-medium text-slate-700">Click to upload or drag and drop</p>
                <p className="text-xs text-slate-500 mt-1">.txt files only</p>
              </div>
            </div>

            <div className="relative">
              <div className="absolute inset-0 flex items-center" aria-hidden="true">
                <div className="w-full border-t border-slate-200"></div>
              </div>
              <div className="relative flex justify-center">
                <span className="bg-slate-50 px-3 text-sm text-slate-500">OR PASTE TEXT</span>
              </div>
            </div>

            <textarea
              className="w-full h-64 p-4 border border-slate-200 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white resize-none text-sm font-mono text-slate-700"
              placeholder="Alice: We need to update the model weights by tomorrow...&#10;Bob: I can handle that."
              value={transcriptText}
              onChange={(e) => setTranscriptText(e.target.value)}
            />

            <button
              onClick={handleSubmit}
              disabled={isLoading || !transcriptText.trim()}
              className="w-full bg-slate-900 hover:bg-slate-800 text-white font-medium py-3 px-4 rounded-xl shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Analyzing Transcript...
                </>
              ) : (
                "Process Meeting"
              )}
            </button>
          </div>

          {/* Right Column: Results Dashboard */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 flex flex-col min-h-[500px]">
            {isLoading ? (
              <div className="flex-1 flex flex-col items-center justify-center text-center animate-pulse">
                <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mb-4">
                  <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
                </div>
                <h3 className="text-lg font-semibold text-slate-900">Processing Meeting</h3>
                <p className="text-sm text-slate-500 max-w-xs mt-2">
                  Gemini is analyzing the transcript, syncing with Jira, and requesting Slack approvals...
                </p>
                
                {/* Skeleton UI */}
                <div className="w-full mt-10 space-y-4">
                  <div className="h-4 bg-slate-100 rounded w-3/4 mx-auto"></div>
                  <div className="h-4 bg-slate-100 rounded w-5/6 mx-auto"></div>
                  <div className="h-4 bg-slate-100 rounded w-1/2 mx-auto"></div>
                </div>
              </div>
            ) : result ? (
              <div className="flex flex-col gap-6 animate-in fade-in duration-500">
                <div className="flex items-center gap-2 text-green-600 mb-2">
                  <CheckCircle2 className="w-6 h-6" />
                  <h3 className="text-xl font-semibold text-slate-900">Analysis Complete</h3>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 rounded-xl border border-slate-100 bg-slate-50 flex flex-col gap-1">
                    <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Auto-Created</span>
                    <div className="flex items-center gap-2">
                      <span className="text-3xl font-bold text-slate-900">{result.jira_tickets_created}</span>
                      <span className="bg-green-100 text-green-800 text-xs px-2 py-0.5 rounded-full font-medium">
                        Jira Tickets
                      </span>
                    </div>
                  </div>
                  
                  <div className="p-4 rounded-xl border border-slate-100 bg-slate-50 flex flex-col gap-1">
                    <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Pending Review</span>
                    <div className="flex items-center gap-2">
                      <span className="text-3xl font-bold text-slate-900">{result.pending_slack_approvals}</span>
                      <span className="bg-amber-100 text-amber-800 text-xs px-2 py-0.5 rounded-full font-medium">
                        Sent to Slack
                      </span>
                    </div>
                  </div>
                </div>

                <div className="mt-4">
                  <h4 className="text-sm font-semibold text-slate-900 mb-3 uppercase tracking-wide">Executive Summary</h4>
                  <div className="p-5 rounded-xl bg-slate-900 text-slate-100 leading-relaxed shadow-inner">
                    {result.summary}
                  </div>
                </div>
                
                <div className="mt-auto pt-6 border-t border-slate-100 flex items-start gap-2 text-sm text-slate-500">
                  <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                  <p>
                    All extracted action items ({result.action_items_extracted}) have been processed. Ambiguous tasks are awaiting your approval in the Slack channel.
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-slate-400">
                <FileText className="w-16 h-16 mb-4 opacity-20" />
                <p className="text-center max-w-sm">
                  Upload or paste a meeting transcript on the left to see the AI-generated summary and task breakdown here.
                </p>
              </div>
            )}
          </div>

        </div>
      </main>
    </div>
  );
}
