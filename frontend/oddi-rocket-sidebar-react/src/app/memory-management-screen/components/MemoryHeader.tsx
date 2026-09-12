'use client';

import React from 'react';
import {
  Search,
  Trash2,
  RotateCcw,
  Brain,
  ChevronDown,
} from 'lucide-react';

interface MemoryCategory {
  id: string;
  label: string;
  icon: string;
  count: number;
}

interface MemoryHeaderProps {
  searchQuery: string;
  onSearchChange: (q: string) => void;
  memoryEnabled: boolean;
  onToggleMemory: (enabled: boolean) => void;
  onClearAll: () => void;
  selectedCount: number;
  onDeleteSelected: () => void;
  totalCount: number;
  selectedCategory: string;
  categories: MemoryCategory[];
  onCategoryChange: (id: string) => void;
}

interface MemoryToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
}

function MemoryToggle({
  checked,
  onChange,
  label,
}: MemoryToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className="relative h-5 w-9 flex-shrink-0 rounded-full transition-all duration-200"
      style={{
        background: checked
          ? 'var(--foreground)'
          : 'var(--muted)',
        border: '1px solid var(--border)',
      }}
    >
      <span
        className="absolute top-1/2 h-3.5 w-3.5 -translate-y-1/2 rounded-full transition-all duration-200"
        style={{
          left: checked ? '17px' : '3px',
          background: checked
            ? 'var(--background)'
            : 'var(--muted-foreground)',
        }}
      />
    </button>
  );
}

export default function MemoryHeader({
  searchQuery,
  onSearchChange,
  memoryEnabled,
  onToggleMemory,
  onClearAll,
  selectedCount,
  onDeleteSelected,
  totalCount,
  selectedCategory,
  categories,
  onCategoryChange,
}: MemoryHeaderProps) {
  const currentCategory = categories.find(
    (category) => category.id === selectedCategory
  );

  const clearLabel =
    selectedCategory === 'all'
      ? 'Clear all'
      : `Clear ${currentCategory?.label ?? 'category'}`;

  return (
    <header
      className="flex-shrink-0 border-b px-4 py-4"
      style={{
        background: 'var(--secondary)',
        borderColor: 'var(--border)',
      }}
    >
      {/* Title row */}
      <div className="mb-4 flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          {/* Brain icon */}
          <div
            className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl border"
            style={{
              background: 'var(--muted)',
              borderColor: 'var(--border)',
            }}
          >
            <Brain
              size={18}
              style={{
                color: 'var(--foreground)',
              }}
            />
          </div>

          {/* Title */}
          <div className="min-w-0">
            <h1
              className="text-lg font-semibold"
              style={{
                color: 'var(--foreground)',
              }}
            >
              Your Memory
            </h1>

            <p
              className="text-xs"
              style={{
                color: 'var(--muted-foreground)',
              }}
            >
              {totalCount}{' '}
              {totalCount === 1
                ? 'memory'
                : 'memories'}

              {selectedCategory !== 'all' &&
              currentCategory
                ? ` in ${currentCategory.label}`
                : ' total'}
            </p>
          </div>
        </div>

        {/* Memory toggle */}
        <div className="flex flex-shrink-0 items-center gap-2">
          <span
            className="hidden text-xs sm:block"
            style={{
              color: 'var(--muted-foreground)',
            }}
          >
            {memoryEnabled
              ? 'Memory on'
              : 'Memory off'}
          </span>

          <MemoryToggle
            checked={memoryEnabled}
            onChange={onToggleMemory}
            label="Toggle memory"
          />
        </div>
      </div>

      {/* Mobile category selector */}
      <div className="mb-3 md:hidden">
        <div className="relative">
          <select
            value={selectedCategory}
            onChange={(event) =>
              onCategoryChange(event.target.value)
            }
            className="w-full appearance-none rounded-lg border py-2 pl-3 pr-8 text-sm outline-none"
            style={{
              background: 'var(--input)',
              color: 'var(--foreground)',
              borderColor: 'var(--border)',
            }}
            aria-label="Memory category"
          >
            {categories.map((category) => (
              <option
                key={`mobile-category-${category.id}`}
                value={category.id}
              >
                {category.icon} {category.label} (
                {category.count})
              </option>
            ))}
          </select>

          <ChevronDown
            size={14}
            className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2"
            style={{
              color: 'var(--muted-foreground)',
            }}
          />
        </div>
      </div>

      {/* Search + actions */}
      <div className="flex items-center gap-2">
        {/* Search */}
        <div className="relative min-w-0 flex-1">
          <Search
            size={14}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2"
            style={{
              color: 'var(--muted-foreground)',
            }}
          />

          <input
            type="search"
            placeholder="Search memories..."
            value={searchQuery}
            onChange={(event) =>
              onSearchChange(event.target.value)
            }
            className="w-full rounded-lg border py-2 pl-9 pr-4 text-sm outline-none transition-all"
            style={{
              background: 'var(--input)',
              color: 'var(--foreground)',
              borderColor: 'var(--border)',
            }}
            aria-label="Search memories"
          />
        </div>

        {/* Delete selected */}
        {selectedCount > 0 ? (
          <button
            type="button"
            onClick={onDeleteSelected}
            className="flex flex-shrink-0 items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium transition-all active:scale-95 hover:opacity-75"
            style={{
              background: 'rgb(239 68 68 / 0.10)',
              color: 'rgb(239 68 68)',
              borderColor: 'rgb(239 68 68 / 0.20)',
            }}
            aria-label={`Delete ${selectedCount} selected memories`}
          >
            <Trash2 size={14} />

            <span className="hidden sm:inline">
              Delete {selectedCount}
            </span>
          </button>
        ) : (
          /* Clear */
          <button
            type="button"
            onClick={onClearAll}
            disabled={totalCount === 0}
            className="flex flex-shrink-0 items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium transition-all active:scale-95 hover:opacity-75 disabled:cursor-not-allowed disabled:opacity-40"
            style={{
              color: 'var(--muted-foreground)',
              borderColor: 'var(--border)',
              background: 'transparent',
            }}
            aria-label={clearLabel}
          >
            <RotateCcw size={14} />

            <span className="hidden sm:inline">
              {clearLabel}
            </span>
          </button>
        )}
      </div>

      {/* Memory disabled warning */}
      {!memoryEnabled && (
        <div
          className="mt-3 flex items-center gap-2 rounded-lg border px-3 py-2 text-xs"
          style={{
            background: 'rgb(245 158 11 / 0.08)',
            borderColor: 'rgb(245 158 11 / 0.20)',
            color: 'rgb(245 158 11)',
          }}
        >
          <span aria-hidden="true">⚠️</span>

          <span>
            Memory is paused — ODDI won't save new
            information until you re-enable it.
          </span>
        </div>
      )}
    </header>
  );
}