'use client';

import React from 'react';
import type { MemoryCategory } from './MemoryManagement';

interface MemoryCategoryListProps {
  categories: MemoryCategory[];
  selected: string;
  onSelect: (id: string) => void;
}

export default function MemoryCategoryList({
  categories,
  selected,
  onSelect,
}: MemoryCategoryListProps) {
  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div
        className="flex-shrink-0 border-b px-4 py-4"
        style={{
          borderColor: 'var(--border)',
        }}
      >
        <h2
          className="text-sm font-semibold"
          style={{
            color: 'var(--foreground)',
          }}
        >
          Categories
        </h2>

        <p
          className="mt-0.5 text-xs"
          style={{
            color: 'var(--muted-foreground)',
          }}
        >
          Filter memories by type
        </p>
      </div>

      {/* Categories */}
      <nav className="flex-1 overflow-y-auto px-2 py-2">
        {categories.map((category) => {
          const isSelected = selected === category.id;

          return (
            <button
              key={`category-${category.id}`}
              type="button"
              onClick={() => onSelect(category.id)}
              className="mb-0.5 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-all duration-150"
              style={{
                background: isSelected
                  ? 'var(--muted)'
                  : 'transparent',
                borderLeft: `2px solid ${
                  isSelected
                    ? 'var(--foreground)'
                    : 'transparent'
                }`,
                color: isSelected
                  ? 'var(--foreground)'
                  : 'var(--muted-foreground)',
              }}
              aria-current={
                isSelected ? 'true' : undefined
              }
            >
              {/* Icon */}
              <span className="flex-shrink-0 text-base">
                {category.icon}
              </span>

              {/* Label */}
              <span className="flex-1 truncate text-sm font-medium">
                {category.label}
              </span>

              {/* Count */}
              <span
                className="flex-shrink-0 rounded-full px-1.5 py-0.5 font-mono text-xs font-semibold"
                style={{
                  background: isSelected
                    ? 'var(--foreground)'
                    : 'var(--muted)',
                  color: isSelected
                    ? 'var(--background)'
                    : 'var(--muted-foreground)',
                }}
              >
                {category.count}
              </span>
            </button>
          );
        })}
      </nav>

      {/* Footer */}
      <div
        className="flex-shrink-0 border-t px-4 py-3"
        style={{
          borderColor: 'var(--border)',
        }}
      >
        <p
          className="text-xs leading-relaxed"
          style={{
            color: 'var(--muted-foreground)',
          }}
        >
          ODDI saves memories automatically during
          conversations. You can edit or remove any
          memory at any time.
        </p>
      </div>
    </div>
  );
}