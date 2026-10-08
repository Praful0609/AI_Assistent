"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { projectsApi, Project } from "@/lib/api";
import { UploadModal } from "@/components/upload/UploadModal";
import { ProjectCard } from "@/components/projects/ProjectCard";
import { Code2, Plus, Zap } from "lucide-react";

export default function HomePage() {
  const [showUpload, setShowUpload] = useState(false);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["projects"],
    queryFn: () => projectsApi.list().then((r) => r.data),
  });

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center">
              <Code2 className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-white">Code Intelligence</h1>
              <p className="text-xs text-gray-400">AI-powered codebase understanding</p>
            </div>
          </div>
          <button
            onClick={() => setShowUpload(true)}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500
                       text-white text-sm font-medium rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Project
          </button>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-6 py-16 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 bg-indigo-950 border border-indigo-800
                        rounded-full text-indigo-300 text-xs font-medium mb-6">
          <Zap className="w-3 h-3" />
          Powered by Gemini + GraphRAG
        </div>
        <h2 className="text-4xl font-bold text-white mb-4">
          Understand Any Codebase Instantly
        </h2>
        <p className="text-gray-400 text-lg max-w-2xl mx-auto mb-8">
          Upload a Git repo or ZIP. Get an interactive knowledge graph,
          auto-generated docs, UML diagrams, and an AI that answers questions
          about your code.
        </p>
        <button
          onClick={() => setShowUpload(true)}
          className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-medium
                     rounded-xl transition-colors text-base"
        >
          Upload a Project
        </button>
      </section>

      {/* Projects grid */}
      <section className="max-w-7xl mx-auto px-6 pb-16">
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-40 bg-gray-900 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : data?.projects.length ? (
          <>
            <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
              Recent Projects
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {data.projects.map((project: Project) => (
                <ProjectCard key={project.id} project={project} />
              ))}
            </div>
          </>
        ) : (
          <div className="text-center py-16 text-gray-500">
            <Code2 className="w-12 h-12 mx-auto mb-4 opacity-30" />
            <p>No projects yet. Upload your first repository to get started.</p>
          </div>
        )}
      </section>

      {/* Upload modal */}
      {showUpload && (
        <UploadModal
          onClose={() => setShowUpload(false)}
          onSuccess={() => { setShowUpload(false); refetch(); }}
        />
      )}
    </div>
  );
}
