"use client";

import { Github, Coffee } from "lucide-react";

export function Footer() {
	return (
		<footer className="w-full bg-background-darker border-t border-gray-200 mt-auto">
			<div className="container mx-auto px-4 py-6">
				<div className="flex flex-col md:flex-row items-center justify-between gap-4">
					<p className="text-sm text-gray-600">
						Made with ❤️ for readers
					</p>

					<div className="flex items-center gap-6">
						<a
							href="https://github.com/OwnerOfJK/leaf"
							target="_blank"
							rel="noopener noreferrer"
							className="text-sm text-gray-600 hover:text-secondary transition-colors flex items-center gap-1"
						>
							<Github className="w-4 h-4" />
							GitHub
						</a>

						<a
							href="https://buymeacoffee.com/ownerofjk"
							target="_blank"
							rel="noopener noreferrer"
							className="text-sm text-gray-600 hover:text-accent transition-colors flex items-center gap-1"
							aria-label="Buy me a coffee"
						>
							<Coffee className="w-4 h-4" />
							<span className="hidden sm:inline">Support</span>
						</a>
					</div>
				</div>
			</div>
		</footer>
	);
}
