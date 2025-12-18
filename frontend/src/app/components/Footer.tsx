"use client";

import { Github, Coffee } from "lucide-react";

export function Footer() {
	return (
		<footer className="w-full bg-cream-dark/50 backdrop-blur-sm border-t border-primary/10 mt-auto relative z-10">
			<div className="container mx-auto px-4 py-8">
				<div className="flex flex-col md:flex-row items-center justify-between gap-4">
					<p className="text-sm text-muted font-light">
						Crafted with care for book lovers
					</p>

					<div className="flex items-center gap-6">
						<a
							href="https://github.com/OwnerOfJK/leaf"
							target="_blank"
							rel="noopener noreferrer"
							className="text-sm text-muted hover:text-secondary transition-colors flex items-center gap-2 font-medium"
						>
							<Github className="w-4 h-4" />
							GitHub
						</a>

						<a
							href="https://buymeacoffee.com/ownerofjk"
							target="_blank"
							rel="noopener noreferrer"
							className="text-sm text-muted hover:text-accent transition-colors flex items-center gap-2 font-medium group"
							aria-label="Buy me a coffee"
						>
							<Coffee className="w-4 h-4 group-hover:scale-110 transition-transform" />
							<span className="hidden sm:inline">Support</span>
						</a>
					</div>
				</div>
			</div>
		</footer>
	);
}
