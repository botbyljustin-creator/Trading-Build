"use client";

import clsx from "clsx";
import { useState, type ReactNode } from "react";

export interface TabItem {
  key: string;
  label: string;
  content: ReactNode;
}

export function Tabs({ items, defaultKey }: { items: TabItem[]; defaultKey?: string }) {
  const [active, setActive] = useState(defaultKey ?? items[0]?.key);
  const activeItem = items.find((i) => i.key === active) ?? items[0];

  return (
    <div>
      <div className="mb-4 flex gap-1 overflow-x-auto border-b border-base-700">
        {items.map((item) => (
          <button
            key={item.key}
            onClick={() => setActive(item.key)}
            className={clsx(
              "whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors",
              active === item.key
                ? "border-accent-info text-slate-100"
                : "border-transparent text-slate-500 hover:text-slate-300",
            )}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div>{activeItem?.content}</div>
    </div>
  );
}
