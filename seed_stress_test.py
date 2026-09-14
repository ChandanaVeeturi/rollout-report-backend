"""
Bulk-seed ~80 real Product Hunt launches as reviews, purely to stress-test
the app at volume (pagination, sorting, filters, category/tag pages).

Bodies are clearly-labeled placeholder text, not real PM opinions — this is
throwaway load-test data, not editorial content.

Idempotent: safe to call on every app startup (via app.main._seed_initial_data)
or run standalone with `python seed_stress_test.py` from backend/.
"""
import uuid, random, unicodedata, re
from datetime import datetime, timedelta, timezone

from app.models.review import Review, Category, Tag, ReviewTag


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = text.lower().strip()
    text = re.sub(r"[^\w\s.-]", "", text)
    text = re.sub(r"[.\s_-]+", "-", text)
    return text.strip("-")


# (title, tagline, category_slug) — sourced from producthunt.com homepage + topic
# pages (today/yesterday/week/month leaderboards, Productivity/AI/Design/Marketing/
# Web3/Health/No-code topics), fetched live. Entries already covered by
# seed_ph_reviews.py (Resurf, Perplexity Hybrid Compute, Cognition SWE-2,
# ScreenCursor, Visiby) and generic mega-incumbents (Apple/Google/Twitter/
# Reddit/Gmail/Product Hunt itself) are excluded.
PRODUCTS = [
    ("LLMagnet", "Make your WordPress site visible to AI", "marketing-sales"),
    ("OzBrain", "Your knowledge shared with every AI agent & any teammate", "productivity"),
    ("Marqly 6.0", "Ask your bookmarks. Bring them to your AI.", "productivity"),
    ("Elva", "Goodbye, Postman. Your APIs have new consumers", "engineering-development"),
    ("Web Search Agents by Nimble", "Self-learning agents automate web research + retrieval", "engineering-development"),
    ("TryCase", "Open a PR and get a video walkthrough of your changes", "engineering-development"),
    ("Naoma AI Demo Agent V2", "Turns website traffic into booked, qualified meetings", "marketing-sales"),
    ("Hello Inbox", "Get more marketing emails into the inbox", "marketing-sales"),
    ("Aside", "AI browser that actually gets work done for you", "productivity"),
    ("Deplo", "A ridiculously good alternative to the cloud", "productivity"),
    ("MemoryPet 2.0", "Turn your browsers toolbar into an animated usage monitor", "platforms"),
    ("Slashy Assistant", "The AI assistant that does email for you", "productivity"),
    ("AppZapper 3000", "The uninstaller Apple forgot", "productivity"),
    ("Oats", "Free, open-source, and on device meeting notetaker", "productivity"),
    ("Image to ASCII", "Make ASCII art for READMEs, Discord & creative visuals", "design-creative"),
    ("OVO", "Play music from files, iCloud & streams across Apple devices", "lifestyle"),
    ("Juggler", "A visual AI coding harness", "engineering-development"),
    ("appdesigns", "Design amazing appstore screenshots for free", "design-creative"),
    ("Afterglow", "Run classic After Dark screen savers on modern macOS", "lifestyle"),
    ("Mastra Factory", "From issue to production, run by agents", "engineering-development"),
    ("Switch", "Bring any AI agent into Slack, Teams & Discord", "engineering-development"),
    ("Anysite.io", "Build and enrich B2B lists by chatting to your agent", "marketing-sales"),
    ("Widgo", "AI Sales rep for your website visitors", "marketing-sales"),
    ("Harden", "A security layer for AI coding agents", "engineering-development"),
    ("Clipto MCP", "Let agents source clips from terabytes of local video", "productivity"),
    ("Hey Noah", "A proactive AI executive assistant for founders", "productivity"),
    ("AdAnt AI", "Claude for viral, high-converting social ads", "marketing-sales"),
    ("Dograh", "The open source VAPI alternative", "engineering-development"),
    ("SODAX SDK", "Digital asset flows you can build and deploy with AI", "finance"),
    ("Figma", "The collaborative interface design tool", "design-creative"),
    ("Vercel", "The frontend cloud. Creators of Next.js.", "engineering-development"),
    ("Claude by Anthropic", "A family of foundational AI models", "llms"),
    ("Cursor", "AI coding agent", "engineering-development"),
    ("Notion", "The all-in-one workspace", "productivity"),
    ("Supabase", "The open source Firebase alternative", "engineering-development"),
    ("OpenAI", "APIs and tools for building AI products", "llms"),
    ("Claude Code", "Anthropic's deep-context AI coder", "engineering-development"),
    ("Slack", "Team communication and collaboration platform", "social-community"),
    ("GitHub", "How people build software", "engineering-development"),
    ("ChatGPT by OpenAI", "Get answers. Find inspiration. Be more productive.", "llms"),
    ("Stripe", "Financial infrastructure for the internet", "finance"),
    ("Linear", "The product development system for teams and agents.", "engineering-development"),
    ("GPT-4o", "Fast, intelligent, flexible GPT model", "llms"),
    ("AWS", "Reliable, scalable, and inexpensive cloud computing", "engineering-development"),
    ("Next.js", "Create web applications with the power of React", "engineering-development"),
    ("Klariqo AI Voice Assistants", "AI Voice assistant in 3 minutes. Built for non-developers", "voice-ai-tools"),
    ("Raydian", "The next frontier of AI product builders", "ai-agents"),
    ("AI Browser", "Automate anything online with a single prompt", "engineering-development"),
    ("Tines", "The single, secure environment for agents, apps, and automations", "engineering-development"),
    ("Canva", "Amazingly simple graphic design", "design-creative"),
    ("Firebase", "An app development platform backed by Google", "engineering-development"),
    ("Tailwind CSS", "A utility-first CSS framework for rapid UI development", "engineering-development"),
    ("Cloudflare", "The web performance & security company", "engineering-development"),
    ("shadcn/ui", "Beautifully designed components", "design-creative"),
    ("Resend", "Email for developers", "engineering-development"),
    ("Spotify", "Stream music and podcasts", "lifestyle"),
    ("ElevenLabs", "Create natural AI voices instantly in any language", "voice-ai-tools"),
    ("Screen Studio", "Beautiful screen recordings in minutes", "design-creative"),
    ("RevenueCat", "Build, analyze, and grow your subscription or app service", "marketing-sales"),
    ("Expo", "Mobile AI Infrastructure for ideas that matter", "engineering-development"),
    ("Railway", "Instant Deployments, Effortless Scale", "engineering-development"),
    ("Perplexity", "Where Knowledge Begins", "llms"),
    ("Cal.com", "Scheduling infrastructure for absolutely everyone", "productivity"),
    ("Bubble", "Build and launch web and mobile apps without writing code", "no-code-platforms"),
    ("Replit", "Idea to app, fast", "engineering-development"),
    ("Plaid", "The safer way for your users to link financial accounts", "finance"),
    ("Xcode", "Develop, test, and distribute apps for all Apple platforms", "engineering-development"),
    ("Hugging Face", "The AI community building the future", "llms"),
    ("Lemon Squeezy", "Sell digital products the easy-peasy way", "ecommerce"),
    ("Miro", "The visual collaboration platform for every team", "productivity"),
    ("Trello", "Visual collaboration with a shared perspective on projects", "productivity"),
    ("Midjourney", "Create AI generated images from a text prompt", "design-creative"),
    ("Framer", "The AI design agent for every step from idea to launch", "design-creative"),
    ("Lovable", "The world's first AI Fullstack Engineer", "engineering-development"),
    ("Webflow", "Where creativity drives performance", "no-code-platforms"),
    ("Netlify", "The AI native full-stack platform for shipping web apps fast", "engineering-development"),
    ("JetBrains", "A suite of intelligent development tools", "engineering-development"),
    ("Zapier", "Connect your apps and automate workflows", "no-code-platforms"),
    ("Bento", "A link in bio, but rich and beautiful", "social-community"),
    ("Tally", "The simplest way to create forms", "no-code-platforms"),
    ("n8n", "Workflow automation for technical people", "no-code-platforms"),
]


def seed_stress_test_products(db) -> tuple[int, int]:
    """Insert PRODUCTS as published reviews. Returns (created, skipped)."""
    random.seed(42)

    def get_cat(slug):
        return db.query(Category).filter(Category.slug == slug).first()

    def make_tag(name):
        slug = slugify(name)
        t = db.query(Tag).filter(Tag.slug == slug).first()
        if not t:
            t = Tag(id=str(uuid.uuid4()), name=name, slug=slug)
            db.add(t)
            db.flush()
        return t

    VERDICTS = ["recommended"] * 5 + ["worth_watching"] * 3 + ["skip_it"] * 2
    today = datetime.now(timezone.utc)
    created, skipped = 0, 0

    for i, (title, tagline, cat_slug) in enumerate(PRODUCTS):
        base_slug = slugify(title)
        if db.query(Review).filter(Review.product_slug == base_slug, Review.title == title).first():
            skipped += 1
            continue

        slug, n = base_slug, 1
        while db.query(Review).filter(Review.slug == slug).first():
            n += 1
            slug = f"{base_slug}-{n}"

        cat = get_cat(cat_slug)
        verdict = VERDICTS[i % len(VERDICTS)]
        release_date = (today - timedelta(days=random.randint(0, 45))).date()

        body = (
            f"**What it is:** {tagline}\n\n"
            f"**First take:** Fits squarely into {cat.name if cat else 'its'} space — "
            f"worth a look if that's in your stack right now.\n\n"
            f"_Stress-test seed entry — placeholder body, not a real review._"
        )

        review = Review(
            id=str(uuid.uuid4()),
            title=title,
            slug=slug,
            product_slug=base_slug,
            tagline=tagline[:160],
            body=body,
            verdict=verdict,
            status="published",
            category_id=cat.id if cat else None,
            platforms=None,
            external_url="https://www.producthunt.com/",
            release_date=release_date,
            published_at=datetime.combine(release_date, datetime.min.time(), tzinfo=timezone.utc),
            upvote_count=random.randint(0, 400),
            comment_count=random.randint(0, 30),
            is_pinned=False,
        )
        db.add(review)
        db.flush()

        tag = make_tag(cat.name if cat else "General")
        db.add(ReviewTag(review_id=review.id, tag_id=tag.id))

        created += 1

    return created, skipped


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from app.database import SessionLocal, Base, engine

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        created, skipped = seed_stress_test_products(db)
        db.commit()
        total = db.query(Review).count()
        print(f"created {created}, skipped {skipped} (already existed) — {total} reviews total in DB")
    finally:
        db.close()
