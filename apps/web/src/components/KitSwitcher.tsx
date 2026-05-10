"use client";

import { useState } from "react";
import { useStore } from "@/store";
import { createKit, deleteKit, duplicateKit, updateKit } from "@/lib/api/user-kits";
import { createClient } from "@/lib/supabase/client";

async function getToken(): Promise<string> {
  const supabase = createClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? "";
}

export function KitSwitcher({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { kits, activeKitId, setActiveKit, addKit, removeKit, updateKit: updateKitStore } =
    useStore();

  const [showNewKitForm, setShowNewKitForm] = useState(false);
  const [newKitName, setNewKitName] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");

  if (!open) return null;

  async function handleNewKit(e: React.FormEvent) {
    e.preventDefault();
    if (!newKitName.trim()) return;
    const token = await getToken();
    const kit = await createKit({ name: newKitName.trim(), source_weights: {} }, token);
    addKit(kit);
    setActiveKit(kit.id);
    setNewKitName("");
    setShowNewKitForm(false);
    onClose();
  }

  async function handleDelete(id: string) {
    const token = await getToken();
    await deleteKit(id, token);
    removeKit(id);
  }

  async function handleDuplicate(id: string) {
    const token = await getToken();
    const kit = await duplicateKit(id, token);
    addKit(kit);
  }

  async function handleRename(id: string) {
    if (!editingName.trim()) return;
    const token = await getToken();
    const updated = await updateKit(id, { name: editingName.trim() }, token);
    updateKitStore(id, { name: updated.name });
    setEditingId(null);
    setEditingName("");
  }

  return (
    <>
      {/* Scrim */}
      <div
        className="pl-scrim fixed inset-0 z-40 pl-scrim-enter"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <div className="pl-drawer-enter fixed right-0 top-0 z-50 flex h-full w-80 flex-col bg-bg-elevated shadow-drawer">
        <div className="flex h-14 items-center justify-between border-b border-border-subtle px-4">
          <h2 className="text-sm font-semibold">Draft Kits</h2>
          <button
            aria-label="Close"
            onClick={onClose}
            className="pl-btn-ghost rounded p-1.5"
          >
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto py-2">
          {kits.map((kit) => (
            <div
              key={kit.id}
              className="group flex items-center gap-2 px-3 py-1"
            >
              <button
                role="radio"
                aria-checked={kit.id === activeKitId}
                aria-label={kit.name}
                onClick={() => {
                  setActiveKit(kit.id);
                  onClose();
                }}
                className="flex flex-1 items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-bg-overlay"
              >
                <span
                  className="flex h-4 w-4 items-center justify-center text-accent-blue"
                  aria-hidden="true"
                >
                  {kit.id === activeKitId ? "✓" : ""}
                </span>
                {editingId === kit.id ? (
                  <input
                    autoFocus
                    value={editingName}
                    onChange={(e) => setEditingName(e.target.value)}
                    onBlur={() => handleRename(kit.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleRename(kit.id);
                      if (e.key === "Escape") setEditingId(null);
                    }}
                    className="pl-input flex-1 rounded px-1 py-0.5 text-sm"
                    onClick={(e) => e.stopPropagation()}
                  />
                ) : (
                  <span className="flex-1 truncate">{kit.name}</span>
                )}
              </button>

              <button
                aria-label="Kit options"
                onClick={(e) => {
                  e.stopPropagation();
                  // Dropdown would open here — for now inline actions via context
                  const action = window.prompt(
                    `${kit.name}: type rename, duplicate, or delete`,
                  );
                  if (action === "rename") {
                    setEditingId(kit.id);
                    setEditingName(kit.name);
                  } else if (action === "duplicate") {
                    handleDuplicate(kit.id);
                  } else if (action === "delete") {
                    handleDelete(kit.id);
                  }
                }}
                className="pl-btn-ghost hidden rounded p-1 text-xs group-hover:flex"
              >
                ···
              </button>
            </div>
          ))}
        </div>

        <div className="border-t border-border-subtle p-3">
          {showNewKitForm ? (
            <form onSubmit={handleNewKit} className="flex gap-2">
              <input
                autoFocus
                value={newKitName}
                onChange={(e) => setNewKitName(e.target.value)}
                placeholder="Kit name"
                className="pl-input flex-1 rounded px-2 py-1 text-sm"
              />
              <button
                type="submit"
                className="pl-btn-primary rounded px-3 py-1 text-xs"
              >
                Create
              </button>
            </form>
          ) : (
            <button
              onClick={() => setShowNewKitForm(true)}
              className="pl-btn-secondary flex w-full items-center justify-center gap-1.5 rounded py-2 text-sm"
            >
              + New kit
            </button>
          )}
        </div>
      </div>
    </>
  );
}
