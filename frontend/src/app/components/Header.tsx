"use client";

import { Github, Leaf } from "lucide-react";
import { useRouter } from "next/navigation";
import { useSession } from "@/contexts/SessionContext";

export function Header() {
  const router = useRouter();
  const session = useSession();

  const handleLogoClick = async () => {
    // Reset session (keep CSV data but clear query/answers/questions)
    await session.resetSession();
    router.push("/");
  };

  return (
    <header className="w-full bg-cream/80 backdrop-blur-md border-b border-primary/10 shadow-sm relative z-10">
      <div className="container mx-auto px-4 py-5 flex items-center justify-between">
        <button
          onClick={handleLogoClick}
          className="flex items-center gap-2.5 text-primary hover:opacity-70 transition-all cursor-pointer bg-transparent border-none p-0 group"
          type="button"
        >
          <Leaf
            className="w-7 h-7 text-secondary group-hover:rotate-12 transition-transform duration-300"
            strokeWidth={2}
          />
          <span className="text-3xl font-bold font-heading tracking-tight">
            Leaf
          </span>
        </button>

        <a
          href="https://github.com/OwnerOfJK/leaf"
          target="_blank"
          rel="noopener noreferrer"
          className="text-muted hover:text-secondary transition-colors p-2 rounded-lg hover:bg-secondary/5"
          aria-label="View on GitHub"
        >
          <Github className="w-5 h-5" />
        </a>
      </div>
    </header>
  );
}
