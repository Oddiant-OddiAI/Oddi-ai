'use client';

import React from 'react';
import type { MemoryItem } from './MemoryManagement';
import {
  Edit3,
  Trash2,
  Brain,
  CheckSquare,
  Square,
} from 'lucide-react';

interface MemoryCardGridProps {
  memories: MemoryItem[];
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
  onToggleSelectAll: () => void;
  onEdit: (memory: MemoryItem) => void;
  onDelete: (id: string) => void;
  searchQuery: string;
  memoryEnabled: boolean;
}

const CONFIDENCE_CONFIG = {
  high: {
    label: 'High confidence',
    color: 'rgb(34 197 94)',
    background: 'rgb(34 197 94 / 0.10)',
  },
  medium: {
    label: 'Medium confidence',
    color: 'rgb(245 158 11)',
    background: 'rgb(245 158 11 / 0.10)',
  },
  low: {
    label: 'Low confidence',
    color: 'var(--muted-foreground)',
    background: 'var(--muted)',
  },
} as const;

const CATEGORY_ICONS: Record<string, string> = {
  name: '👤',
  preferences: '⚙️',
  goals: '🎯',
  education: '🎓',
  work: '💼',
  projects: '🚀',
  interests: '✨',
  people: '👥',
  communication: '💬',
  other: '📌',
};

function highlightMatch(
  text: string,
  query: string
): React.ReactNode {
  if (!query.trim()) {
    return text;
  }

  const escapedQuery = query.replace(
    /[.*+?^${}()|[\]\\]/g,
    '\\$&'
  );

  const parts = text.split(
    new RegExp(`(${escapedQuery})`, 'gi')
  );

  return parts.map((part, index) => {
    const isMatch =
      part.toLowerCase() === query.toLowerCase();

    if (!isMatch) {
      return part;
    }

    return (
      <mark
        key={`highlight-${index}`}
        style={{
          background: 'var(--foreground)',
          color: 'var(--background)',
          borderRadius: '3px',
          padding: '0 2px',
        }}
      >
        {part}
      </mark>
    );
  });
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);

  if (Number.isNaN(date.getTime())) {
    return 'Unknown date';
  }

  const now = new Date();

  const diffDays = Math.floor(
    (now.getTime() - date.getTime()) /
      (1000 * 60 * 60 * 24)
  );

  if (diffDays === 0) {
    return 'Today';
  }

  if (diffDays === 1) {
    return 'Yesterday';
  }

  if (diffDays > 1 && diffDays < 7) {
    return `${diffDays} days ago`;
  }

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
}

export default function MemoryCardGrid({
  memories,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
  onEdit,
  onDelete,
  searchQuery,
  memoryEnabled,
}: MemoryCardGridProps) {
  const allSelected =
    memories.length > 0 &&
    selectedIds.size === memories.length;

  if (memories.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-4 py-16 text-center">
        <div
          className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border"
          style={{
            background: 'var(--card)',
            borderColor: 'var(--border)',
          }}
        >
          <Brain
            size={28}
            style={{
              color: 'var(--muted-foreground)',
            }}
          />
        </div>

        <h3
          className="mb-2 text-base font-semibold"
          style={{
            color: 'var(--foreground)',
          }}
        >
          {searchQuery
            ? 'No memories match your search'
            : 'No memories yet'}
        </h3>

        <p
          className="max-w-xs text-sm leading-relaxed"
          style={{
            color: 'var(--muted-foreground)',
          }}
        >
          {searchQuery
            ? 'Try a different search term or clear the filter.'
            : 'Start a conversation with ODDI and tell it something about yourself. It will remember it here.'}
        </p>
      </div>
    );
  }

  return (
    <div className="px-4 py-4">
      {/* Select all */}
      <div
        className="mb-3 flex items-center gap-3 border-b pb-3"
        style={{
          borderColor: 'var(--border)',
        }}
      >
        <button
          type="button"
          onClick={onToggleSelectAll}
          className="flex items-center gap-2 text-xs transition-opacity hover:opacity-70"
          style={{
            color: 'var(--muted-foreground)',
          }}
        >
          {allSelected ? (
            <CheckSquare
              size={14}
              style={{
                color: 'var(--foreground)',
              }}
            />
          ) : (
            <Square size={14} />
          )}

          <span>
            {allSelected ? 'Deselect all' : 'Select all'}
          </span>
        </button>

        <span
          className="text-xs"
          style={{
            color: 'var(--muted-foreground)',
          }}
        >
          {memories.length}{' '}
          {memories.length === 1 ? 'memory' : 'memories'}

          {selectedIds.size > 0 &&
            ` · ${selectedIds.size} selected`}
        </span>
      </div>

      {/* Memory grid */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        {memories.map((memory) => {
          const isSelected = selectedIds.has(memory.id);

          const confidence =
            CONFIDENCE_CONFIG[memory.confidence] ??
            CONFIDENCE_CONFIG.low;

          const categoryIcon =
            CATEGORY_ICONS[memory.category.toLowerCase()] ??
            CATEGORY_ICONS.other;

          return (
            <div
              key={memory.id}
              className="group relative flex flex-col gap-3 rounded-xl border p-4 transition-all duration-150"
              style={{
                background: isSelected
                  ? 'var(--muted)'
                  : 'var(--card)',
                borderColor: isSelected
                  ? 'var(--foreground)'
                  : 'var(--border)',
                opacity: memoryEnabled ? 1 : 0.5,
              }}
            >
              {/* Header */}
              <div className="flex items-start justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                  {/* Selection */}
                  <button
                    type="button"
                    onClick={() =>
                      onToggleSelect(memory.id)
                    }
                    className="flex-shrink-0 transition-opacity hover:opacity-70"
                    aria-label={
                      isSelected
                        ? 'Deselect memory'
                        : 'Select memory'
                    }
                  >
                    {isSelected ? (
                      <CheckSquare
                        size={15}
                        style={{
                          color: 'var(--foreground)',
                        }}
                      />
                    ) : (
                      <Square
                        size={15}
                        className="opacity-0 transition-opacity group-hover:opacity-100"
                        style={{
                          color: 'var(--muted-foreground)',
                        }}
                      />
                    )}
                  </button>

                  <span className="text-base">
                    {categoryIcon}
                  </span>

                  <span
                    className="truncate text-xs font-medium capitalize"
                    style={{
                      color: 'var(--muted-foreground)',
                    }}
                  >
                    {memory.category}
                  </span>
                </div>

                {/* Actions */}
                <div className="flex flex-shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                  <button
                    type="button"
                    onClick={() => onEdit(memory)}
                    className="flex h-7 w-7 items-center justify-center rounded-lg transition-opacity hover:opacity-60"
                    style={{
                      color: 'var(--muted-foreground)',
                    }}
                    title="Edit memory"
                    aria-label="Edit memory"
                  >
                    <Edit3 size={13} />
                  </button>

                  <button
                    type="button"
                    onClick={() => onDelete(memory.id)}
                    className="flex h-7 w-7 items-center justify-center rounded-lg transition-opacity hover:opacity-60"
                    style={{
                      color: 'var(--muted-foreground)',
                    }}
                    title="Delete memory"
                    aria-label="Delete memory"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>

              {/* Content */}
              <p
                className="flex-1 text-sm leading-relaxed"
                style={{
                  color: 'var(--foreground)',
                }}
              >
                {highlightMatch(
                  memory.content,
                  searchQuery
                )}
              </p>

              {/* Footer */}
              <div className="flex items-end justify-between gap-2">
                <span
                  className="rounded-full px-1.5 py-0.5 text-xs font-medium"
                  style={{
                    background: confidence.background,
                    color: confidence.color,
                  }}
                >
                  {confidence.label}
                </span>

                <div className="min-w-0 text-right">
                  <p
                    className="text-xs"
                    style={{
                      color: 'var(--muted-foreground)',
                    }}
                  >
                    {formatDate(memory.savedAt)}
                  </p>

                  <p
                    className="max-w-[100px] truncate text-xs"
                    style={{
                      color: 'var(--muted-foreground)',
                      opacity: 0.6,
                    }}
                    title={memory.source}
                  >
                    {memory.source}
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}