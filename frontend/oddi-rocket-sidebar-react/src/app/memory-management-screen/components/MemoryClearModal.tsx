'use client';

import React, { useState } from 'react';
import {
  Trash2,
  Loader2,
  AlertTriangle,
  X,
} from 'lucide-react';

interface MemoryClearModalProps {
  categoryLabel: string;
  onConfirm: () => void | Promise<void>;
  onClose: () => void;
}

export default function MemoryClearModal({
  categoryLabel,
  onConfirm,
  onClose,
}: MemoryClearModalProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  const [confirmed, setConfirmed] = useState(false);

  const handleConfirm = async () => {
    if (!confirmed || isDeleting) {
      return;
    }

    try {
      setIsDeleting(true);
      await onConfirm();
    } finally {
      setIsDeleting(false);
    }
  };

  const dangerColor = 'rgb(239 68 68)';
  const dangerBackground = 'rgb(239 68 68 / 0.10)';
  const dangerBorder = 'rgb(239 68 68 / 0.25)';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="clear-memory-title"
      style={{
        background: 'rgb(0 0 0 / 0.55)',
        backdropFilter: 'blur(4px)',
      }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !isDeleting) {
          onClose();
        }
      }}
    >
      <div
        className="w-full max-w-md overflow-hidden rounded-2xl border shadow-2xl"
        style={{
          background: 'var(--card)',
          color: 'var(--foreground)',
          borderColor: 'var(--border)',
        }}
        onMouseDown={(event) => event.stopPropagation()}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between border-b px-5 py-4"
          style={{
            borderColor: 'var(--border)',
          }}
        >
          <h2
            id="clear-memory-title"
            className="text-base font-semibold"
            style={{
              color: 'var(--foreground)',
            }}
          >
            Clear memories
          </h2>

          <button
            type="button"
            onClick={onClose}
            disabled={isDeleting}
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
          {/* Warning header */}
          <div className="flex items-center gap-3">
            <div
              className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl border"
              style={{
                background: dangerBackground,
                borderColor: dangerBorder,
              }}
            >
              <AlertTriangle
                size={18}
                style={{
                  color: dangerColor,
                }}
              />
            </div>

            <div className="min-w-0">
              <h3
                className="text-base font-semibold"
                style={{
                  color: 'var(--foreground)',
                }}
              >
                Clear {categoryLabel}?
              </h3>

              <p
                className="mt-0.5 text-xs"
                style={{
                  color: 'var(--muted-foreground)',
                }}
              >
                This action cannot be undone.
              </p>
            </div>
          </div>

          {/* Description */}
          <p
            className="text-sm leading-relaxed"
            style={{
              color: 'var(--muted-foreground)',
            }}
          >
            ODDI will permanently forget all memories in{' '}
            <strong
              style={{
                color: 'var(--foreground)',
              }}
            >
              {categoryLabel}
            </strong>
            . Future conversations won't have access to
            this context.
          </p>

          {/* Confirmation */}
          <label
            className="flex cursor-pointer items-start gap-2.5 rounded-xl border p-3 transition-opacity hover:opacity-80"
            style={{
              background: 'var(--muted)',
              borderColor: 'var(--border)',
            }}
          >
            <input
              type="checkbox"
              checked={confirmed}
              disabled={isDeleting}
              onChange={(event) =>
                setConfirmed(event.target.checked)
              }
              className="mt-0.5 h-4 w-4 flex-shrink-0 cursor-pointer accent-current disabled:cursor-not-allowed"
            />

            <span
              className="text-sm leading-relaxed"
              style={{
                color: 'var(--foreground)',
              }}
            >
              I understand this will permanently delete{' '}
              <strong>{categoryLabel}</strong> from ODDI's
              memory.
            </span>
          </label>
        </div>

        {/* Footer */}
        <div
          className="flex items-center gap-3 border-t px-5 py-4"
          style={{
            borderColor: 'var(--border)',
          }}
        >
          <button
            type="button"
            onClick={onClose}
            disabled={isDeleting}
            className="flex-1 rounded-lg border px-4 py-2 text-sm font-medium transition-opacity hover:opacity-70 disabled:cursor-not-allowed disabled:opacity-50"
            style={{
              color: 'var(--muted-foreground)',
              borderColor: 'var(--border)',
              background: 'transparent',
            }}
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={handleConfirm}
            disabled={isDeleting || !confirmed}
            className="flex flex-1 items-center justify-center gap-2 rounded-lg border px-4 py-2 text-sm font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-50"
            style={{
              background: confirmed
                ? dangerBackground
                : 'var(--muted)',
              color: confirmed
                ? dangerColor
                : 'var(--muted-foreground)',
              borderColor: confirmed
                ? dangerBorder
                : 'var(--border)',
            }}
          >
            {isDeleting ? (
              <>
                <Loader2
                  size={13}
                  className="animate-spin"
                />
                Clearing...
              </>
            ) : (
              <>
                <Trash2 size={13} />
                Clear memories
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}