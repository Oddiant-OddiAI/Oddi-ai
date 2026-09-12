'use client';

import React, { useEffect, useState } from 'react';
import {
  Loader2,
  X,
} from 'lucide-react';

interface MemoryItem {
  id: string;
  category: string;
  content: string;
  source: string;
  savedAt: string;
  confidence: 'high' | 'medium' | 'low';
}

interface MemoryEditModalProps {
  memory: MemoryItem;
  onSave: (id: string, content: string) => void | Promise<void>;
  onClose: () => void;
}

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

function formatSavedDate(dateStr: string): string {
  const date = new Date(dateStr);

  if (Number.isNaN(date.getTime())) {
    return dateStr;
  }

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export default function MemoryEditModal({
  memory,
  onSave,
  onClose,
}: MemoryEditModalProps) {
  const [content, setContent] = useState(memory.content);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setContent(memory.content);
    setIsSaving(false);
  }, [memory.id, memory.content]);

  const trimmedContent = content.trim();
  const isDirty = content !== memory.content;

  const error =
    trimmedContent.length === 0
      ? 'Memory content cannot be empty'
      : trimmedContent.length < 3
        ? 'Memory must be at least 3 characters'
        : trimmedContent.length > 500
          ? 'Memory must be under 500 characters'
          : '';

  const handleSubmit = async (
    event: React.FormEvent<HTMLFormElement>
  ) => {
    event.preventDefault();

    if (
      !isDirty ||
      !trimmedContent ||
      error ||
      isSaving
    ) {
      return;
    }

    try {
      setIsSaving(true);
      await onSave(memory.id, trimmedContent);
    } finally {
      setIsSaving(false);
    }
  };

  const categoryIcon =
    CATEGORY_ICONS[memory.category.toLowerCase()] ??
    CATEGORY_ICONS.other;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="edit-memory-title"
      style={{
        background: 'rgb(0 0 0 / 0.55)',
        backdropFilter: 'blur(4px)',
      }}
      onMouseDown={(event) => {
        if (
          event.target === event.currentTarget &&
          !isSaving
        ) {
          onClose();
        }
      }}
    >
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-lg overflow-hidden rounded-2xl border shadow-2xl"
        style={{
          background: 'var(--card)',
          color: 'var(--foreground)',
          borderColor: 'var(--border)',
        }}
        onMouseDown={(event) =>
          event.stopPropagation()
        }
      >
        {/* Header */}
        <div
          className="flex items-center justify-between border-b px-5 py-4"
          style={{
            borderColor: 'var(--border)',
          }}
        >
          <h2
            id="edit-memory-title"
            className="text-base font-semibold"
            style={{
              color: 'var(--foreground)',
            }}
          >
            Edit Memory
          </h2>

          <button
            type="button"
            onClick={onClose}
            disabled={isSaving}
            className="flex h-8 w-8 items-center justify-center rounded-lg transition-opacity hover:opacity-60 disabled:cursor-not-allowed disabled:opacity-40"
            style={{
              color: 'var(--muted-foreground)',
            }}
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="flex flex-col gap-4 px-5 py-5">
          {/* Memory metadata */}
          <div
            className="flex items-center gap-3 rounded-xl border p-3"
            style={{
              background: 'var(--muted)',
              borderColor: 'var(--border)',
            }}
          >
            <span className="text-xl">
              {categoryIcon}
            </span>

            <div className="min-w-0">
              <p
                className="text-xs font-semibold capitalize"
                style={{
                  color: 'var(--foreground)',
                }}
              >
                {memory.category}
              </p>

              <p
                className="text-xs"
                style={{
                  color: 'var(--muted-foreground)',
                }}
              >
                Saved {formatSavedDate(memory.savedAt)} ·{' '}
                {memory.source}
              </p>
            </div>
          </div>

          {/* Content field */}
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="memory-content"
              className="text-sm font-medium"
              style={{
                color: 'var(--foreground)',
              }}
            >
              Memory content
            </label>

            <p
              className="text-xs"
              style={{
                color: 'var(--muted-foreground)',
              }}
            >
              Edit what ODDI remembers. Be clear and
              specific for best results.
            </p>

            <textarea
              id="memory-content"
              rows={5}
              autoFocus
              maxLength={500}
              value={content}
              disabled={isSaving}
              onChange={(event) =>
                setContent(event.target.value)
              }
              className="w-full resize-none rounded-xl border px-4 py-3 text-sm outline-none transition-all disabled:cursor-not-allowed disabled:opacity-60"
              style={{
                background: 'var(--input)',
                color: 'var(--foreground)',
                borderColor: error
                  ? 'rgb(239 68 68)'
                  : 'var(--border)',
              }}
              aria-invalid={Boolean(error)}
              aria-describedby="memory-content-help"
            />

            <div className="flex items-start justify-between gap-3">
              <div
                id="memory-content-help"
                className="min-h-[18px]"
              >
                {error && (
                  <p
                    className="text-xs"
                    style={{
                      color: 'rgb(248 113 113)',
                    }}
                  >
                    {error}
                  </p>
                )}
              </div>

              <p
                className="flex-shrink-0 font-mono text-xs"
                style={{
                  color: 'var(--muted-foreground)',
                }}
              >
                {content.length}/500
              </p>
            </div>
          </div>

          {/* Info */}
          <div
            className="rounded-lg border px-3 py-2 text-xs leading-relaxed"
            style={{
              background: 'var(--muted)',
              borderColor: 'var(--border)',
              color: 'var(--muted-foreground)',
            }}
          >
            💡 Editing a memory updates it in ODDI's
            context for future conversations.
          </div>
        </div>

        {/* Footer */}
        <div
          className="flex items-center justify-between gap-3 border-t px-5 py-4"
          style={{
            borderColor: 'var(--border)',
          }}
        >
          <button
            type="button"
            onClick={onClose}
            disabled={isSaving}
            className="rounded-lg border px-4 py-2 text-sm font-medium transition-opacity hover:opacity-70 disabled:cursor-not-allowed disabled:opacity-50"
            style={{
              color: 'var(--muted-foreground)',
              borderColor: 'var(--border)',
              background: 'transparent',
            }}
          >
            Cancel
          </button>

          <button
            type="submit"
            disabled={
              isSaving ||
              !isDirty ||
              Boolean(error)
            }
            className="flex min-w-[120px] items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-50"
            style={{
              background: 'var(--foreground)',
              color: 'var(--background)',
            }}
          >
            {isSaving ? (
              <>
                <Loader2
                  size={13}
                  className="animate-spin"
                />
                Saving...
              </>
            ) : (
              'Save Memory'
            )}
          </button>
        </div>
      </form>
    </div>
  );
}