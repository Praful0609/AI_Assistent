"use client";

import Link from "next/link";
import { Project } from "@/lib/api";
import { CheckCircle, Clock, AlertCircle, Loader2, FileCode, GitBranch } from "lucide-react";

const STATUS_CONFIG = {
  pending:   { icon: Clock,        color: "text-yellow-400", label: "Pending" },
  parsing:   { icon: Loader2,      color: "text-blue-400",   label: "Parsing" },
  analyzing: { icon: Loader2,      color: "text-blue-400",   label: "Analyzing" },
  indexing:  { icon: Loader2,      color: "text-blue-400",   label: "Indexing" },
  complete:  { icon: CheckCircle,  color: "text-green-400",  label: "Complete" },
  failed:    { icon: AlertCircle,  color: "text-red-400",    label: "Failed" },
};

export function ProjectCard({ project }: { project: Project }) {
  const config = STATUS_CONFIG[project.status] || STATUS_CONFIG.pending;
  const StatusIcon = config.icon;
  const isLoading = ["parsing", "analyzing", "indexing"].includes(project.status);

  return (
    <Link
      href={`/projects/${project.id}`}
      className="block bg-gray-900 border border-gray-800 rounded-xl p-5 hover:border-indigo-700
                 transition-colors group"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          {project.source_type === "git_url" ? (
            <GitBranch className="w-4 h-4 text-gray-400" />
          ) : (
            <FileCode className="w-4 h-4 text-gray-400" />
          )}
          <h3 className="font-medium text-white group-hover:text-indigo-300 transition-colors truncate max-w-40">
            {project.name}
          </h3>
        </div>
        <div className={`flex items-center gap-1.5 text-xs font-medium ${config.color}`}>
          <StatusIcon className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
          {config.label}
        </div>
      </div>

      {project.description && (
        <p className="text-sm text-gray-400 mb-3 line-clamp-2">{project.description}</p>
      )}

      <div className="flex items-center gap-4 text-xs text-gray-500">
        <span>{project.total_files} files</span>
        <span>{project.total_lines.toLocaleString()} lines</span>
        <span>{new Date(project.created_at).toLocaleDateString()}</span>
      </div>
    </Link>
  );
}
