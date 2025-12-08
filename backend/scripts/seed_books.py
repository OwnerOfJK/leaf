"""Seed sample books for development and testing.

Adds a curated set of books with embeddings to test the recommendation system.
Safe to run multiple times - skips books that already exist.

Usage:
    python scripts/seed_books.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SessionLocal
from app.core.embeddings import create_embedding, format_book_text
from app.services.book_service import create_book, get_book_by_isbn

# Sample books for testing
SAMPLE_BOOKS = [
    {
        "isbn": "9780451524935",
        "title": "1984",
        "author": "George Orwell",
        "description": "A dystopian social science fiction novel and cautionary tale about the dangers of totalitarianism.",
        "categories": ["Fiction", "Dystopian", "Science Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780451524935-L.jpg",
    },
    {
        "isbn": "9780061120084",
        "title": "To Kill a Mockingbird",
        "author": "Harper Lee",
        "description": "A novel about racial injustice and childhood innocence in the American South.",
        "categories": ["Fiction", "Classic", "Historical"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780061120084-L.jpg",
    },
    {
        "isbn": "9780547928227",
        "title": "The Hobbit",
        "author": "J.R.R. Tolkien",
        "description": "A fantasy novel about a hobbit's unexpected adventure to reclaim a treasure guarded by a dragon.",
        "categories": ["Fantasy", "Adventure", "Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780547928227-L.jpg",
    },
    {
        "isbn": "9780316769488",
        "title": "The Catcher in the Rye",
        "author": "J.D. Salinger",
        "description": "A story about teenage rebellion and alienation narrated by Holden Caulfield.",
        "categories": ["Fiction", "Classic", "Coming of Age"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780316769488-L.jpg",
    },
    {
        "isbn": "9780142437239",
        "title": "Pride and Prejudice",
        "author": "Jane Austen",
        "description": "A romantic novel about manners, marriage, and morality in Georgian England.",
        "categories": ["Romance", "Classic", "Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780142437239-L.jpg",
    },
    {
        "isbn": "9780553418026",
        "title": "A Brief History of Time",
        "author": "Stephen Hawking",
        "description": "A landmark volume in science writing that explores cosmology and the universe.",
        "categories": ["Science", "Physics", "Non-Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780553418026-L.jpg",
    },
    {
        "isbn": "9780062316097",
        "title": "Sapiens: A Brief History of Humankind",
        "author": "Yuval Noah Harari",
        "description": "An exploration of the history of the human species from the Stone Age to the modern age.",
        "categories": ["History", "Non-Fiction", "Anthropology"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780062316097-L.jpg",
    },
    {
        "isbn": "9780062073488",
        "title": "The Alchemist",
        "author": "Paulo Coelho",
        "description": "A philosophical novel about a shepherd's journey to find treasure and discover his destiny.",
        "categories": ["Fiction", "Philosophy", "Adventure"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780062073488-L.jpg",
    },
    {
        "isbn": "9780441172719",
        "title": "Dune",
        "author": "Frank Herbert",
        "description": "A science fiction epic about politics, religion, and ecology on the desert planet Arrakis.",
        "categories": ["Science Fiction", "Fantasy", "Epic"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780441172719-L.jpg",
    },
    {
        "isbn": "9780345391803",
        "title": "The Hitchhiker's Guide to the Galaxy",
        "author": "Douglas Adams",
        "description": "A comedic science fiction series following Arthur Dent's intergalactic adventures.",
        "categories": ["Science Fiction", "Comedy", "Adventure"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780345391803-L.jpg",
    },
    # Science Fiction & Fantasy
    {
        "isbn": "9780553293357",
        "title": "Foundation",
        "author": "Isaac Asimov",
        "description": "The first novel in Asimov's Foundation series about the fall and rise of galactic civilizations.",
        "categories": ["Science Fiction", "Space Opera", "Classic"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780553293357-L.jpg",
    },
    {
        "isbn": "9780316769174",
        "title": "The Name of the Wind",
        "author": "Patrick Rothfuss",
        "description": "The first book in the Kingkiller Chronicle, following the legend of Kvothe.",
        "categories": ["Fantasy", "Epic Fantasy", "Adventure"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780316769174-L.jpg",
    },
    {
        "isbn": "9780765326355",
        "title": "The Way of Kings",
        "author": "Brandon Sanderson",
        "description": "Epic fantasy about honor, war, and magic in a world of storms.",
        "categories": ["Fantasy", "Epic Fantasy", "High Fantasy"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780765326355-L.jpg",
    },
    {
        "isbn": "9780441569595",
        "title": "Neuromancer",
        "author": "William Gibson",
        "description": "A cyberpunk novel about a washed-up computer hacker hired for one last job.",
        "categories": ["Science Fiction", "Cyberpunk", "Thriller"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780441569595-L.jpg",
    },
    {
        "isbn": "9780765348784",
        "title": "Ender's Game",
        "author": "Orson Scott Card",
        "description": "A military science fiction novel about a child genius trained to fight an alien invasion.",
        "categories": ["Science Fiction", "Military SF", "Young Adult"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780765348784-L.jpg",
    },
    {
        "isbn": "9780441007318",
        "title": "The Left Hand of Darkness",
        "author": "Ursula K. Le Guin",
        "description": "A science fiction novel exploring gender and society on an alien world.",
        "categories": ["Science Fiction", "Anthropological SF", "Classic"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780441007318-L.jpg",
    },
    {
        "isbn": "9780345342966",
        "title": "A Game of Thrones",
        "author": "George R.R. Martin",
        "description": "The first book in A Song of Ice and Fire series, a tale of power, betrayal, and dragons.",
        "categories": ["Fantasy", "Epic Fantasy", "Dark Fantasy"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780345342966-L.jpg",
    },
    {
        "isbn": "9780060850524",
        "title": "Brave New World",
        "author": "Aldous Huxley",
        "description": "A dystopian novel about a technologically advanced society without freedom.",
        "categories": ["Science Fiction", "Dystopian", "Classic"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780060850524-L.jpg",
    },
    {
        "isbn": "9780441013593",
        "title": "Do Androids Dream of Electric Sheep?",
        "author": "Philip K. Dick",
        "description": "A science fiction novel exploring what it means to be human in a post-apocalyptic world.",
        "categories": ["Science Fiction", "Dystopian", "Philosophical"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780441013593-L.jpg",
    },
    {
        "isbn": "9780553381689",
        "title": "The Handmaid's Tale",
        "author": "Margaret Atwood",
        "description": "A dystopian novel about a totalitarian theocracy and the oppression of women.",
        "categories": ["Dystopian", "Science Fiction", "Feminist"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780553381689-L.jpg",
    },
    # Mystery & Thriller
    {
        "isbn": "9780307949486",
        "title": "The Girl with the Dragon Tattoo",
        "author": "Stieg Larsson",
        "description": "A gripping mystery thriller about a journalist and a hacker investigating a decades-old disappearance.",
        "categories": ["Mystery", "Thriller", "Crime"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780307949486-L.jpg",
    },
    {
        "isbn": "9780062073556",
        "title": "Gone Girl",
        "author": "Gillian Flynn",
        "description": "A psychological thriller about a marriage gone terribly wrong.",
        "categories": ["Thriller", "Mystery", "Psychological"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780062073556-L.jpg",
    },
    {
        "isbn": "9780062024039",
        "title": "And Then There Were None",
        "author": "Agatha Christie",
        "description": "Ten strangers are lured to an island where they're accused of murder and killed one by one.",
        "categories": ["Mystery", "Classic", "Thriller"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780062024039-L.jpg",
    },
    {
        "isbn": "9780307387899",
        "title": "The Da Vinci Code",
        "author": "Dan Brown",
        "description": "A mystery thriller following symbologist Robert Langdon as he investigates a murder.",
        "categories": ["Thriller", "Mystery", "Adventure"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780307387899-L.jpg",
    },
    {
        "isbn": "9780743273565",
        "title": "The Great Gatsby",
        "author": "F. Scott Fitzgerald",
        "description": "A classic American novel about wealth, love, and the American Dream in the 1920s.",
        "categories": ["Classic", "Literary Fiction", "Romance"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780743273565-L.jpg",
    },
    # Literary Fiction
    {
        "isbn": "9780679783268",
        "title": "One Hundred Years of Solitude",
        "author": "Gabriel García Márquez",
        "description": "A landmark of magical realism chronicling the Buendía family over seven generations.",
        "categories": ["Literary Fiction", "Magical Realism", "Classic"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780679783268-L.jpg",
    },
    {
        "isbn": "9780140449136",
        "title": "Crime and Punishment",
        "author": "Fyodor Dostoevsky",
        "description": "A psychological drama about a man who commits murder and grapples with guilt.",
        "categories": ["Classic", "Psychological", "Literary Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780140449136-L.jpg",
    },
    {
        "isbn": "9780679732242",
        "title": "The Remains of the Day",
        "author": "Kazuo Ishiguro",
        "description": "A meditation on dignity, regret, and missed opportunities through an English butler's memoir.",
        "categories": ["Literary Fiction", "Historical", "Drama"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780679732242-L.jpg",
    },
    {
        "isbn": "9780375507250",
        "title": "The Road",
        "author": "Cormac McCarthy",
        "description": "A post-apocalyptic tale of a father and son's journey through a devastated America.",
        "categories": ["Literary Fiction", "Post-Apocalyptic", "Drama"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780375507250-L.jpg",
    },
    {
        "isbn": "9780143039433",
        "title": "The Kite Runner",
        "author": "Khaled Hosseini",
        "description": "A powerful story of friendship, betrayal, and redemption set in Afghanistan.",
        "categories": ["Literary Fiction", "Historical", "Drama"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780143039433-L.jpg",
    },
    # Non-Fiction: Science & History
    {
        "isbn": "9780385537858",
        "title": "Thinking, Fast and Slow",
        "author": "Daniel Kahneman",
        "description": "A groundbreaking tour of the mind exploring the two systems that drive human thinking.",
        "categories": ["Psychology", "Non-Fiction", "Science"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780385537858-L.jpg",
    },
    {
        "isbn": "9780393347777",
        "title": "Guns, Germs, and Steel",
        "author": "Jared Diamond",
        "description": "An exploration of why some societies prospered while others did not.",
        "categories": ["History", "Anthropology", "Non-Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780393347777-L.jpg",
    },
    {
        "isbn": "9780374533557",
        "title": "Thinking in Bets",
        "author": "Annie Duke",
        "description": "A former poker champion's guide to making smarter decisions when stakes are high.",
        "categories": ["Business", "Psychology", "Non-Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780374533557-L.jpg",
    },
    {
        "isbn": "9780804139298",
        "title": "The Power of Habit",
        "author": "Charles Duhigg",
        "description": "An exploration of the science behind why we do what we do in life and business.",
        "categories": ["Psychology", "Self-Help", "Non-Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780804139298-L.jpg",
    },
    {
        "isbn": "9780385504201",
        "title": "The God Delusion",
        "author": "Richard Dawkins",
        "description": "A critique of religion and argument for atheism from an evolutionary biologist.",
        "categories": ["Philosophy", "Science", "Non-Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780385504201-L.jpg",
    },
    {
        "isbn": "9780143127796",
        "title": "Educated",
        "author": "Tara Westover",
        "description": "A memoir about growing up in a survivalist family and pursuing education.",
        "categories": ["Memoir", "Biography", "Non-Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780143127796-L.jpg",
    },
    {
        "isbn": "9780307887894",
        "title": "The Immortal Life of Henrietta Lacks",
        "author": "Rebecca Skloot",
        "description": "The story of Henrietta Lacks and the immortal cell line that revolutionized medicine.",
        "categories": ["Biography", "Science", "Non-Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780307887894-L.jpg",
    },
    # Business & Self-Help
    {
        "isbn": "9780062301239",
        "title": "Atomic Habits",
        "author": "James Clear",
        "description": "A practical guide to building good habits and breaking bad ones.",
        "categories": ["Self-Help", "Business", "Non-Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780062301239-L.jpg",
    },
    {
        "isbn": "9781501111105",
        "title": "The 7 Habits of Highly Effective People",
        "author": "Stephen R. Covey",
        "description": "A classic guide to personal and professional effectiveness.",
        "categories": ["Self-Help", "Business", "Non-Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9781501111105-L.jpg",
    },
    {
        "isbn": "9780735211292",
        "title": "Atomic Habits",
        "author": "James Clear",
        "description": "Practical strategies for building good habits and achieving remarkable results.",
        "categories": ["Self-Help", "Productivity", "Non-Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780735211292-L.jpg",
    },
    {
        "isbn": "9780812981605",
        "title": "Thinking in Systems",
        "author": "Donella H. Meadows",
        "description": "A primer on how to understand and work with complex systems.",
        "categories": ["Science", "Business", "Non-Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780812981605-L.jpg",
    },
    # Horror & Dark Fiction
    {
        "isbn": "9780385121675",
        "title": "The Shining",
        "author": "Stephen King",
        "description": "A horror novel about a family isolated in a haunted hotel during winter.",
        "categories": ["Horror", "Thriller", "Supernatural"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780385121675-L.jpg",
    },
    {
        "isbn": "9780140186390",
        "title": "Frankenstein",
        "author": "Mary Shelley",
        "description": "The classic tale of a scientist who creates a monster with tragic consequences.",
        "categories": ["Horror", "Gothic", "Classic"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780140186390-L.jpg",
    },
    {
        "isbn": "9780143107545",
        "title": "Dracula",
        "author": "Bram Stoker",
        "description": "The quintessential vampire novel about Count Dracula's attempt to move from Transylvania to England.",
        "categories": ["Horror", "Gothic", "Classic"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780143107545-L.jpg",
    },
    # Young Adult
    {
        "isbn": "9780439023481",
        "title": "The Hunger Games",
        "author": "Suzanne Collins",
        "description": "A dystopian novel about a televised fight to the death in a post-apocalyptic nation.",
        "categories": ["Young Adult", "Dystopian", "Science Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780439023481-L.jpg",
    },
    {
        "isbn": "9780439064873",
        "title": "Harry Potter and the Sorcerer's Stone",
        "author": "J.K. Rowling",
        "description": "The first book in the Harry Potter series about a young wizard discovering his magical heritage.",
        "categories": ["Fantasy", "Young Adult", "Adventure"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780439064873-L.jpg",
    },
    {
        "isbn": "9780062237507",
        "title": "Divergent",
        "author": "Veronica Roth",
        "description": "A dystopian novel about a society divided into factions based on virtues.",
        "categories": ["Young Adult", "Dystopian", "Science Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780062237507-L.jpg",
    },
    {
        "isbn": "9780141346137",
        "title": "The Fault in Our Stars",
        "author": "John Green",
        "description": "A heart-wrenching story about two teenagers who meet in a cancer support group.",
        "categories": ["Young Adult", "Romance", "Contemporary"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780141346137-L.jpg",
    },
    # Historical Fiction
    {
        "isbn": "9780385490818",
        "title": "All the Light We Cannot See",
        "author": "Anthony Doerr",
        "description": "A WWII novel about a blind French girl and a German boy whose paths collide.",
        "categories": ["Historical Fiction", "War", "Literary Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780385490818-L.jpg",
    },
    {
        "isbn": "9780385333849",
        "title": "The Book Thief",
        "author": "Markus Zusak",
        "description": "A story about a young girl living in Nazi Germany who steals books and shares them.",
        "categories": ["Historical Fiction", "Young Adult", "War"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780385333849-L.jpg",
    },
    {
        "isbn": "9780307947727",
        "title": "The Nightingale",
        "author": "Kristin Hannah",
        "description": "A tale of two sisters in France during World War II and their fight for survival.",
        "categories": ["Historical Fiction", "War", "Drama"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780307947727-L.jpg",
    },
    {
        "isbn": "9780143125761",
        "title": "The Underground Railroad",
        "author": "Colson Whitehead",
        "description": "A reimagining of the Underground Railroad as an actual railroad beneath the Southern soil.",
        "categories": ["Historical Fiction", "Literary Fiction", "Alternate History"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780143125761-L.jpg",
    },
    # Contemporary Fiction
    {
        "isbn": "9780374292799",
        "title": "Normal People",
        "author": "Sally Rooney",
        "description": "A story about the complex relationship between two Irish teenagers.",
        "categories": ["Contemporary", "Literary Fiction", "Romance"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780374292799-L.jpg",
    },
    {
        "isbn": "9780316769488",
        "title": "Where the Crawdads Sing",
        "author": "Delia Owens",
        "description": "A mystery about a marsh girl raised in isolation who becomes a suspect in a murder.",
        "categories": ["Mystery", "Contemporary", "Literary Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780316769488-L.jpg",
    },
    {
        "isbn": "9780812968255",
        "title": "Project Hail Mary",
        "author": "Andy Weir",
        "description": "A lone astronaut must save humanity after waking up with amnesia on a spaceship.",
        "categories": ["Science Fiction", "Space Opera", "Thriller"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780812968255-L.jpg",
    },
    {
        "isbn": "9780316015844",
        "title": "Twilight",
        "author": "Stephenie Meyer",
        "description": "A romance between a teenage girl and a vampire in the Pacific Northwest.",
        "categories": ["Young Adult", "Romance", "Paranormal"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780316015844-L.jpg",
    },
    # Philosophy & Classics
    {
        "isbn": "9780486280615",
        "title": "Meditations",
        "author": "Marcus Aurelius",
        "description": "The personal writings of the Roman Emperor, a foundational text in Stoic philosophy.",
        "categories": ["Philosophy", "Classic", "Non-Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780486280615-L.jpg",
    },
    {
        "isbn": "9780679720201",
        "title": "The Stranger",
        "author": "Albert Camus",
        "description": "A philosophical novel about absurdism following a man who commits murder.",
        "categories": ["Philosophy", "Classic", "Literary Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780679720201-L.jpg",
    },
    {
        "isbn": "9780143105428",
        "title": "Siddhartha",
        "author": "Hermann Hesse",
        "description": "A spiritual journey of self-discovery set in ancient India.",
        "categories": ["Philosophy", "Spiritual", "Classic"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780143105428-L.jpg",
    },
    {
        "isbn": "9780679783268",
        "title": "The Brothers Karamazov",
        "author": "Fyodor Dostoevsky",
        "description": "A philosophical novel exploring faith, doubt, and morality through a family drama.",
        "categories": ["Classic", "Philosophy", "Literary Fiction"],
        "cover_url": "https://covers.openlibrary.org/b/isbn/9780679783268-L.jpg",
    },
]


def seed_books():
    """Seed sample books into the database."""
    db = SessionLocal()
    books_added = 0
    books_skipped = 0

    try:
        print("=" * 70)
        print("SEEDING SAMPLE BOOKS")
        print("=" * 70)
        print(f"\nProcessing {len(SAMPLE_BOOKS)} books...\n")

        for i, book_data in enumerate(SAMPLE_BOOKS, 1):
            # Check if book already exists
            existing = get_book_by_isbn(db, book_data["isbn"])
            if existing:
                print(f"[{i}/{len(SAMPLE_BOOKS)}] ⏭️  {book_data['title']} (already exists)")
                books_skipped += 1
                continue

            # Create embedding from book text
            book_text = format_book_text(
                title=book_data["title"],
                author=book_data["author"],
                description=book_data["description"],
            )
            embedding = create_embedding(book_text)

            # Create book
            create_book(
                db=db,
                isbn=book_data["isbn"],
                title=book_data["title"],
                author=book_data["author"],
                description=book_data["description"],
                categories=book_data["categories"],
                cover_url=book_data["cover_url"],
                embedding=embedding,
            )

            print(f"[{i}/{len(SAMPLE_BOOKS)}] ✅ {book_data['title']} by {book_data['author']}")
            books_added += 1

        db.commit()

        print("\n" + "=" * 70)
        print("SEEDING COMPLETE")
        print("=" * 70)
        print(f"✅ Added: {books_added} books")
        print(f"⏭️  Skipped: {books_skipped} books (already exist)")
        print(f"📚 Total: {books_added + books_skipped} books in database")
        print("=" * 70)

        return books_added

    except Exception as e:
        db.rollback()
        print(f"\n❌ Error during seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_books()
