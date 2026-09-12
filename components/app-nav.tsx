"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Generar" },
  { href: "/historial", label: "Historial" },
  { href: "/skills", label: "Skills" },
] as const;

export function AppNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Principal">
      <ul className="flex flex-wrap items-center gap-1">
        {LINKS.map((link) => {
          const current =
            link.href === "/"
              ? pathname === "/"
              : pathname === link.href || pathname.startsWith(`${link.href}/`);
          return (
            <li key={link.href}>
              <Link
                href={link.href}
                aria-current={current ? "page" : undefined}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
                  current
                    ? "bg-zinc-900 text-white"
                    : "text-zinc-800 hover:bg-zinc-100"
                }`}
              >
                {link.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
