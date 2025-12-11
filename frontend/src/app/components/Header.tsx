"use client";

import { useRouter } from "next/navigation";
import { Leaf, Github } from "lucide-react";
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
		<header className="w-full bg-background border-b border-gray-200">
			<div className="container mx-auto px-4 py-4 flex items-center justify-between">
				<button
					onClick={handleLogoClick}
					className="flex items-center gap-2 text-primary hover:opacity-80 transition-opacity cursor-pointer bg-transparent border-none p-0"
					type="button"
				>
					<Leaf className="w-6 h-6" />
					<span className="text-2xl font-bold font-heading">Leaf</span>
				</button>

				<a
					href="https://github.com/OwnerOfJK/leaf"
					target="_blank"
					rel="noopener noreferrer"
					className="text-gray-600 hover:text-secondary transition-colors"
					aria-label="View on GitHub"
				>
					<Github className="w-5 h-5" />
				</a>
			</div>
		</header>
	);
}
