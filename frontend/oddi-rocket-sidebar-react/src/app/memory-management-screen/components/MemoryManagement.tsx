'use client';

import React, { useCallback, useMemo, useState } from 'react';
import MemoryCategoryList from './MemoryCategoryList';
import MemoryCardGrid from './MemoryCardGrid';
import MemoryHeader from './MemoryHeader';
import MemoryEditModal from './MemoryEditModal';
import MemoryClearModal from '../components/MemoryClearModal';

export interface MemoryItem {
  id: string;
  category: string;
  content: string;
  source: string;
  savedAt: string;
  confidence: 'high' | 'medium' | 'low';
}

export interface MemoryCategory {
  id: string;
  label: string;
  icon: string;
  count: number;
}

/*
 * Temporary Rocket demo data.
 *
 * This will be replaced by the real ODDI memory API later.
 * Keeping it here for now lets us fully test the UI before
 * connecting Neon/Groq.
 */
export const INITIAL_MEMORIES: MemoryItem[] = [
  // Name
  {
    id: 'mem-001',
    category: 'name',
    content: 'Full name is Vedanssh Kumar',
    source: 'Direct input',
    savedAt: '2026-09-10',
    confidence: 'high',
  },
  {
    id: 'mem-002',
    category: 'name',
    content: 'Prefers to be called Vedanssh',
    source: 'Conversation',
    savedAt: '2026-09-10',
    confidence: 'high',
  },

  // Preferences
  {
    id: 'mem-003',
    category: 'preferences',
    content:
      'Prefers detailed technical explanations with code examples',
    source: 'Explicit request',
    savedAt: '2026-09-11',
    confidence: 'high',
  },
  {
    id: 'mem-004',
    category: 'preferences',
    content: 'Likes dark mode interfaces',
    source: 'App usage',
    savedAt: '2026-09-09',
    confidence: 'medium',
  },
  {
    id: 'mem-005',
    category: 'preferences',
    content: 'Prefers Rust and Python for backend systems',
    source: 'Conversation',
    savedAt: '2026-09-08',
    confidence: 'high',
  },

  // Goals
  {
    id: 'mem-006',
    category: 'goals',
    content:
      'Building a personal AI assistant as a side project',
    source: 'Conversation',
    savedAt: '2026-09-07',
    confidence: 'high',
  },
  {
    id: 'mem-007',
    category: 'goals',
    content:
      'Wants to land a senior software engineering role by 2027',
    source: 'Career planning chat',
    savedAt: '2026-09-05',
    confidence: 'high',
  },
  {
    id: 'mem-008',
    category: 'goals',
    content:
      'Learning systems programming and low-level optimization',
    source: 'Conversation',
    savedAt: '2026-09-03',
    confidence: 'medium',
  },

  // Education
  {
    id: 'mem-009',
    category: 'education',
    content:
      'Studying Electronics and Computer Engineering (ECE)',
    source: 'Direct input',
    savedAt: '2026-09-01',
    confidence: 'high',
  },
  {
    id: 'mem-010',
    category: 'education',
    content:
      'Currently in 3rd year of undergraduate studies',
    source: 'Conversation',
    savedAt: '2026-09-01',
    confidence: 'high',
  },
  {
    id: 'mem-011',
    category: 'education',
    content:
      'Strong in calculus, data structures, and circuit analysis',
    source: 'Study session',
    savedAt: '2026-09-02',
    confidence: 'medium',
  },

  // Work
  {
    id: 'mem-012',
    category: 'work',
    content:
      'Working on a Python/Flask backend for ODDI AI',
    source: 'Project discussion',
    savedAt: '2026-09-11',
    confidence: 'high',
  },
  {
    id: 'mem-013',
    category: 'work',
    content:
      'Has experience with React, Next.js, and TypeScript',
    source: 'Conversation',
    savedAt: '2026-09-06',
    confidence: 'high',
  },

  // Projects
  {
    id: 'mem-014',
    category: 'projects',
    content:
      'ODDI AI — personal AI assistant with persistent memory',
    source: 'Direct input',
    savedAt: '2026-09-07',
    confidence: 'high',
  },
  {
    id: 'mem-015',
    category: 'projects',
    content:
      'Building a modular vector store abstraction layer',
    source: 'Architecture discussion',
    savedAt: '2026-09-12',
    confidence: 'high',
  },
  {
    id: 'mem-016',
    category: 'projects',
    content:
      'Exploring Rust for high-performance embedding service',
    source: 'Conversation',
    savedAt: '2026-09-10',
    confidence: 'medium',
  },

  // Interests
  {
    id: 'mem-017',
    category: 'interests',
    content:
      'Deeply interested in AI/ML and language models',
    source: 'Conversation',
    savedAt: '2026-09-04',
    confidence: 'high',
  },
  {
    id: 'mem-018',
    category: 'interests',
    content:
      'Enjoys competitive programming and algorithm challenges',
    source: 'Conversation',
    savedAt: '2026-09-02',
    confidence: 'medium',
  },

  // People
  {
    id: 'mem-019',
    category: 'people',
    content:
      'Works closely with a friend named Aryan on the AI project',
    source: 'Conversation',
    savedAt: '2026-09-08',
    confidence: 'medium',
  },

  // Communication
  {
    id: 'mem-020',
    category: 'communication',
    content:
      'Prefers structured responses with numbered steps for complex topics',
    source: 'Feedback',
    savedAt: '2026-09-09',
    confidence: 'high',
  },
  {
    id: 'mem-021',
    category: 'communication',
    content:
      'Appreciates when ODDI asks clarifying questions before long answers',
    source: 'Feedback',
    savedAt: '2026-09-09',
    confidence: 'medium',
  },

  // Other
  {
    id: 'mem-022',
    category: 'other',
    content: 'Timezone: IST (UTC+5:30)',
    source: 'System',
    savedAt: '2026-09-01',
    confidence: 'high',
  },
  {
    id: 'mem-023',
    category: 'other',
    content:
      'Uses ODDI primarily in the evenings for study and project work',
    source: 'Usage pattern',
    savedAt: '2026-09-05',
    confidence: 'low',
  },
  {
    id: 'mem-024',
    category: 'other',
    content: 'Prefers responses in English',
    source: 'Settings',
    savedAt: '2026-09-01',
    confidence: 'high',
  },
];

export const CATEGORIES: MemoryCategory[] = [
  {
    id: 'all',
    label: 'All Memories',
    icon: '🧠',
    count: 0,
  },
  {
    id: 'name',
    label: 'Name',
    icon: '👤',
    count: 0,
  },
  {
    id: 'preferences',
    label: 'Preferences',
    icon: '⚙️',
    count: 0,
  },
  {
    id: 'goals',
    label: 'Goals',
    icon: '🎯',
    count: 0,
  },
  {
    id: 'education',
    label: 'Education',
    icon: '🎓',
    count: 0,
  },
  {
    id: 'work',
    label: 'Work',
    icon: '💼',
    count: 0,
  },
  {
    id: 'projects',
    label: 'Projects',
    icon: '🚀',
    count: 0,
  },
  {
    id: 'interests',
    label: 'Interests',
    icon: '✨',
    count: 0,
  },
  {
    id: 'people',
    label: 'People',
    icon: '👥',
    count: 0,
  },
  {
    id: 'communication',
    label: 'Communication',
    icon: '💬',
    count: 0,
  },
  {
    id: 'other',
    label: 'Other',
    icon: '📌',
    count: 0,
  },
];

export default function MemoryManagement() {
  const [memories, setMemories] =
    useState<MemoryItem[]>(INITIAL_MEMORIES);

  const [selectedCategory, setSelectedCategory] =
    useState('all');

  const [searchQuery, setSearchQuery] =
    useState('');

  const [memoryEnabled, setMemoryEnabled] =
    useState(true);

  const [editingMemory, setEditingMemory] =
    useState<MemoryItem | null>(null);

  const [showClearModal, setShowClearModal] =
    useState(false);

  const [selectedIds, setSelectedIds] =
    useState<Set<string>>(new Set());

  /*
   * Filter memories by category and search.
   */
  const filteredMemories = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();

    return memories.filter((memory) => {
      const matchesCategory =
        selectedCategory === 'all' ||
        memory.category === selectedCategory;

      if (!query) {
        return matchesCategory;
      }

      const matchesSearch =
        memory.content
          .toLowerCase()
          .includes(query) ||
        memory.source
          .toLowerCase()
          .includes(query) ||
        memory.category
          .toLowerCase()
          .includes(query);

      return matchesCategory && matchesSearch;
    });
  }, [memories, selectedCategory, searchQuery]);

  /*
   * Generate category counts from the current memory state.
   *
   * This is intentionally calculated from `memories` instead
   * of storing separate count state.
   */
  const categoriesWithCounts = useMemo(
    () =>
      CATEGORIES.map((category) => ({
        ...category,
        count:
          category.id === 'all'
            ? memories.length
            : memories.filter(
                (memory) =>
                  memory.category === category.id
              ).length,
      })),
    [memories]
  );

  /*
   * Delete one memory.
   *
   * Later this will call the real ODDI API.
   */
  const handleDelete = useCallback((id: string) => {
    setMemories((previous) =>
      previous.filter((memory) => memory.id !== id)
    );

    setSelectedIds((previous) => {
      const next = new Set(previous);
      next.delete(id);
      return next;
    });

    setEditingMemory((current) =>
      current?.id === id ? null : current
    );
  }, []);

  /*
   * Delete selected memories.
   */
  const handleDeleteSelected = useCallback(() => {
    if (selectedIds.size === 0) {
      return;
    }

    setMemories((previous) =>
      previous.filter(
        (memory) => !selectedIds.has(memory.id)
      )
    );

    setSelectedIds(new Set());
  }, [selectedIds]);

  /*
   * Open edit modal.
   */
  const handleEdit = useCallback(
    (memory: MemoryItem) => {
      setEditingMemory(memory);
    },
    []
  );

  /*
   * Save edited memory.
   *
   * Later this becomes the real PATCH request.
   */
  const handleSaveEdit = useCallback(
    (id: string, newContent: string) => {
      const content = newContent.trim();

      if (!content) {
        return;
      }

      setMemories((previous) =>
        previous.map((memory) =>
          memory.id === id
            ? {
                ...memory,
                content,
              }
            : memory
        )
      );

      setEditingMemory(null);
    },
    []
  );

  /*
   * Clear every memory.
   */
  const handleClearAll = useCallback(() => {
    setMemories([]);
    setSelectedIds(new Set());
    setEditingMemory(null);
    setShowClearModal(false);
  }, []);

  /*
   * Clear the currently selected category.
   */
  const handleClearCategory = useCallback(() => {
    if (selectedCategory === 'all') {
      return;
    }

    setMemories((previous) =>
      previous.filter(
        (memory) =>
          memory.category !== selectedCategory
      )
    );

    setSelectedIds(new Set());
    setEditingMemory(null);
    setShowClearModal(false);
  }, [selectedCategory]);

  /*
   * Toggle one memory selection.
   */
  const toggleSelectId = useCallback((id: string) => {
    setSelectedIds((previous) => {
      const next = new Set(previous);

      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }

      return next;
    });
  }, []);

  /*
   * Select/deselect all currently visible memories.
   */
  const toggleSelectAll = useCallback(() => {
    setSelectedIds((previous) => {
      const visibleIds = filteredMemories.map(
        (memory) => memory.id
      );

      const allVisibleSelected =
        visibleIds.length > 0 &&
        visibleIds.every((id) => previous.has(id));

      const next = new Set(previous);

      if (allVisibleSelected) {
        visibleIds.forEach((id) => next.delete(id));
      } else {
        visibleIds.forEach((id) => next.add(id));
      }

      return next;
    });
  }, [filteredMemories]);

  /*
   * If the user changes category, selections from the
   * previous view should not remain accidentally selected.
   */
  const handleCategoryChange = useCallback(
    (categoryId: string) => {
      setSelectedCategory(categoryId);
      setSelectedIds(new Set());
      setSearchQuery('');
    },
    []
  );

  /*
   * Current category label for the clear confirmation.
   */
  const currentCategory = categoriesWithCounts.find(
    (category) => category.id === selectedCategory
  );

  const clearCategoryLabel =
    selectedCategory === 'all'
      ? 'all memories'
      : currentCategory?.label ??
        selectedCategory;

  return (
    <div
      className="flex h-full overflow-hidden"
      style={{
        background: 'var(--background)',
        color: 'var(--foreground)',
      }}
    >
      {/* Category sidebar */}
      <aside
        className="hidden w-56 flex-shrink-0 flex-col overflow-y-auto border-r md:flex xl:w-64"
        style={{
          background: 'var(--secondary)',
          borderColor: 'var(--border)',
        }}
      >
        <MemoryCategoryList
          categories={categoriesWithCounts}
          selected={selectedCategory}
          onSelect={handleCategoryChange}
        />
      </aside>

      {/* Main content */}
      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <MemoryHeader
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          memoryEnabled={memoryEnabled}
          onToggleMemory={setMemoryEnabled}
          onClearAll={() => setShowClearModal(true)}
          selectedCount={selectedIds.size}
          onDeleteSelected={handleDeleteSelected}
          totalCount={memories.length}
          selectedCategory={selectedCategory}
          categories={categoriesWithCounts}
          onCategoryChange={handleCategoryChange}
        />

        {/* Cards */}
        <div className="min-h-0 flex-1 overflow-y-auto">
          <MemoryCardGrid
            memories={filteredMemories}
            selectedIds={selectedIds}
            onToggleSelect={toggleSelectId}
            onToggleSelectAll={toggleSelectAll}
            onEdit={handleEdit}
            onDelete={handleDelete}
            searchQuery={searchQuery}
            memoryEnabled={memoryEnabled}
          />
        </div>
      </main>

      {/* Edit modal */}
      {editingMemory && (
        <MemoryEditModal
          memory={editingMemory}
          onSave={handleSaveEdit}
          onClose={() => setEditingMemory(null)}
        />
      )}

      {/* Clear modal */}
      {showClearModal && (
        <MemoryClearModal
          categoryLabel={clearCategoryLabel}
          onConfirm={
            selectedCategory === 'all'
              ? handleClearAll
              : handleClearCategory
          }
          onClose={() => setShowClearModal(false)}
        />
      )}
    </div>
  );
}