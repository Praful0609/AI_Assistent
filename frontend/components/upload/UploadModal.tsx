"use client";

import { useState } from "react";
import { projectsApi } from "@/lib/api";
import { toast } from "sonner";
import { X, Github, FileArchive, Loader2 } from "lucide-react";

interface Props {
  onClose: () => void;
  onSuccess: () => void;
}

export function UploadModal({ onClose, onSuccess }: Props) {
  const [tab, setTab] = useState<"git" | "zip">("git");
  const [name, setName] = useState("");
  const [gitUrl, setGitUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { toast.error("Project name is required"); return; }

    setLoading(true);
    try {
      if (tab === "git") {
        if (!gitUrl.trim()) { toast.error("Git URL is required"); return; }
        await projectsApi.uploadGit(name, gitUrl);
      } else {
        if (!file) { toast.error("Please select a ZIP file"); return; }
        await projectsApi.uploadZip(name, file);
      }
      toast.success("Project queued for analysis!");
      onSuccess();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Upload failed";
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-md">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <h2 className="text-lg font-semibold text-white">Upload Project</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex px-6 pt-4 gap-2">
          {[{ key: "git", label: "Git URL", icon: Github }, { key: "zip", label: "ZIP File", icon: FileArchive }].map(
            ({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setTab(key as "git" | "zip")}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  tab === key
                    ? "bg-indigo-600 text-white"
                    : "text-gray-400 hover:text-white hover:bg-gray-800"
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </button>
            )
          )}
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4">
          <div>
            <label className="block text-sm text-gray-300 mb-1">Project Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Awesome Project"
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg
                         text-white placeholder-gray-500 text-sm focus:outline-none
                         focus:border-indigo-500 transition-colors"
            />
          </div>

          {tab === "git" ? (
            <div>
              <label className="block text-sm text-gray-300 mb-1">Git Repository URL</label>
              <input
                type="url"
                value={gitUrl}
                onChange={(e) => setGitUrl(e.target.value)}
                placeholder="https://github.com/owner/repo"
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg
                           text-white placeholder-gray-500 text-sm focus:outline-none
                           focus:border-indigo-500 transition-colors"
              />
            </div>
          ) : (
            <div>
              <label className="block text-sm text-gray-300 mb-1">ZIP File (max 500 MB)</label>
              <div
                className="border-2 border-dashed border-gray-700 rounded-lg p-6 text-center
                           hover:border-indigo-500 transition-colors cursor-pointer"
                onDrop={(e) => {
                  e.preventDefault();
                  const dropped = e.dataTransfer.files[0];
                  if (dropped?.name.endsWith(".zip")) setFile(dropped);
                  else toast.error("Only .zip files are supported");
                }}
                onDragOver={(e) => e.preventDefault()}
              >
                <FileArchive className="w-8 h-8 mx-auto text-gray-500 mb-2" />
                {file ? (
                  <p className="text-sm text-indigo-400">{file.name}</p>
                ) : (
                  <p className="text-sm text-gray-500">Drag & drop or click to select</p>
                )}
                <input
                  type="file"
                  accept=".zip"
                  className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  id="zip-input"
                />
                <label htmlFor="zip-input" className="mt-2 inline-block text-xs text-indigo-400 cursor-pointer">
                  Browse files
                </label>
              </div>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50
                       text-white font-medium rounded-lg text-sm transition-colors flex items-center justify-center gap-2"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            {loading ? "Uploading…" : "Start Analysis"}
          </button>
        </form>
      </div>
    </div>
  );
}
