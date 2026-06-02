"use client";
import { BookOpen, Eye, ThumbsUp, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useState } from "react";

const articles = [
  { id: 1, title: "How do I reset my password?", category: "Account & Billing", status: "published", views: 1234, helpful: 89, updated: "2 days ago" },
  { id: 2, title: "What is your return policy?", category: "Orders & Shipping", status: "published", views: 987, helpful: 76, updated: "3 days ago" },
  { id: 3, title: "How do I track my order?", category: "Orders & Shipping", status: "published", views: 876, helpful: 65, updated: "1 week ago" },
  { id: 4, title: "Payment methods accepted", category: "Account & Billing", status: "published", views: 654, helpful: 43, updated: "1 week ago" },
  { id: 5, title: "Two-factor authentication setup", category: "Technical Support", status: "published", views: 432, helpful: 38, updated: "2 weeks ago" },
  { id: 6, title: "Subscription upgrade guide", category: "Account & Billing", status: "draft", views: 0, helpful: 0, updated: "1 day ago" },
  { id: 7, title: "API rate limiting explained", category: "Technical Support", status: "review", views: 0, helpful: 0, updated: "3 hours ago" },
];

export default function KnowledgePage() {
  const [search, setSearch] = useState("");
  const filtered = articles.filter((a) => !search || a.title.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Knowledge Base</h1>
          <p className="text-[var(--foreground-muted)] text-sm mt-1">{articles.length} articles • Powers AI agent responses via RAG</p>
        </div>
        <Button><BookOpen className="w-4 h-4 mr-1" /> New Article</Button>
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted)]" />
        <input type="text" placeholder="Search articles..." value={search} onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2 rounded-xl bg-[var(--input-bg)] border border-[var(--border)] text-sm focus:outline-none focus:border-[var(--primary)] transition-all-200" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((a) => (
          <div key={a.id} className="glass glass-hover transition-all-200 p-5 cursor-pointer group">
            <div className="flex items-start justify-between mb-3">
              <Badge variant={a.status === "published" ? "success" : a.status === "draft" ? "default" : "warning"}>{a.status}</Badge>
              <Badge variant="default">{a.category}</Badge>
            </div>
            <h3 className="text-sm font-semibold mb-3 group-hover:text-[var(--primary)] transition-colors">{a.title}</h3>
            <div className="flex items-center gap-4 text-xs text-[var(--foreground-muted)]">
              <span className="flex items-center gap-1"><Eye className="w-3 h-3" /> {a.views}</span>
              <span className="flex items-center gap-1"><ThumbsUp className="w-3 h-3" /> {a.helpful}</span>
              <span>{a.updated}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
