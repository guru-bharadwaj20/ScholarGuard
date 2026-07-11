"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import { FileSearch, FlaskConical, Home, Microscope, Upload } from "lucide-react";

/**
 * Cmd+K / Ctrl+K command palette — navigation plus quick access to the two
 * bundled example papers.
 */
export function CommandPalette() {
  const [open, setOpen] = React.useState(false);
  const router = useRouter();

  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", down);
    return () => window.removeEventListener("keydown", down);
  }, []);

  const go = (path: string) => {
    setOpen(false);
    router.push(path);
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[80] flex items-start justify-center bg-black/50 pt-[18vh] backdrop-blur-sm"
      onClick={() => setOpen(false)}
    >
      <div onClick={(e) => e.stopPropagation()} className="w-full max-w-lg">
        <Command
          label="Command palette"
          className="glass overflow-hidden !rounded-xl border-accent/20"
        >
          <Command.Input
            autoFocus
            placeholder="Where to?"
            className="w-full border-b border-ink-line bg-transparent px-4 py-3 font-body text-sm text-slate-100 outline-none placeholder:text-slate-500"
          />
          <Command.List className="max-h-72 overflow-y-auto p-2">
            <Command.Empty className="px-3 py-6 text-center type-meta">
              Nothing matches.
            </Command.Empty>
            <Command.Group
              heading="Navigate"
              className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:type-mono-label"
            >
              <PaletteItem onSelect={() => go("/")} icon={<Home size={15} />}>
                Home
              </PaletteItem>
              <PaletteItem onSelect={() => go("/analyze")} icon={<Upload size={15} />}>
                Analyze a paper
              </PaletteItem>
              <PaletteItem
                onSelect={() => go("/methodology")}
                icon={<Microscope size={15} />}
              >
                Methodology — the Stage 1–7 story
              </PaletteItem>
            </Command.Group>
            <Command.Group
              heading="Example papers"
              className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:type-mono-label"
            >
              <PaletteItem
                onSelect={() => go("/analyze?example=fraud-retracted")}
                icon={<FileSearch size={15} />}
              >
                Run the retracted-paper example
              </PaletteItem>
              <PaletteItem
                onSelect={() => go("/analyze?example=clean-moderate")}
                icon={<FlaskConical size={15} />}
              >
                Run the clean-paper example
              </PaletteItem>
            </Command.Group>
          </Command.List>
        </Command>
      </div>
    </div>
  );
}

function PaletteItem({
  children,
  icon,
  onSelect,
}: {
  children: React.ReactNode;
  icon: React.ReactNode;
  onSelect: () => void;
}) {
  return (
    <Command.Item
      onSelect={onSelect}
      className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 font-body text-sm text-slate-300 aria-selected:bg-accent/15 aria-selected:text-white"
    >
      <span className="text-accent">{icon}</span>
      {children}
    </Command.Item>
  );
}
