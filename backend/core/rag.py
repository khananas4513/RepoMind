import os
import logging
from functools import lru_cache
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from backend.core.personalize import STYLES, structure_notes

load_dotenv()
log = logging.getLogger(__name__)

# Google-maintained aliases that always point to a current model.
PREFERRED = ["gemini-flash-latest", "gemini-flash-lite-latest"]
SKIP = ("image", "tts", "audio", "live", "embedding", "robotics", "computer-use", "preview")


def _available_models():
    """Ask Google which models this key can use. None if the lookup fails."""
    try:
        from google import genai
        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        return [
            m.name.removeprefix("models/")
            for m in client.models.list()
            if "generateContent" in (m.supported_actions or [])
        ]
    except Exception as e:
        log.warning("Could not list Gemini models (%s).", e)
        return None


@lru_cache(maxsize=1)
def get_llm():
    """The ONLY place that knows which LLM provider we use.
    Builds a chain of models; if one is overloaded, missing or retired,
    the next one answers."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    env = os.getenv("LLM_MODELS")
    chosen = [m.strip() for m in env.split(",") if m.strip()] if env else list(PREFERRED)

    # Add extra Flash models from Google's live list as additional fallbacks.
    available = _available_models()
    if available:
        extras = sorted(
            (m for m in available
             if "flash" in m and not any(s in m for s in SKIP) and m not in chosen),
            reverse=True,
        )[:2]
        chosen += extras

    print(f"[RepoMind] LLM chain: {chosen}")
    models = [
        ChatGoogleGenerativeAI(model=m, temperature=0.2, max_retries=3, timeout=45)
        for m in chosen
    ]
    return models[0].with_fallbacks(models[1:]) if len(models) > 1 else models[0]


PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are RepoMind, an assistant that answers questions about a codebase.\n"
     "Rules:\n"
     "1. Use ONLY the information provided below. Do not use outside knowledge about the project.\n"
     "2. Cite code claims as [path:start-end] using the REAL line numbers shown at the "
     "start of each code line (for example '  42: code' means line 42).\n"
     "3. If the information does not contain the answer, say so plainly instead of guessing.\n"
     "4. Use the dependency notes to explain how files relate when it helps.\n"
     "5. For questions about the whole repository (where to start, architecture, what matters most), "
     "build the answer from the repository overview and say it comes from the dependency graph, "
     "not from documentation. Write file paths in `backticks`.\n\n"
     "Explanation style for this user (level: {level}):\n{style}"),
    ("human",
     "Repository overview (computed from the dependency graph):\n{overview}\n\n"
     "Dependency notes (how the retrieved files relate):\n{structure}\n\n"
     "Code context:\n{context}\n\n"
     "Question: {question}"),
])


def format_context(results) -> str:
    blocks = []
    for score, c in results:
        numbered = "\n".join(f"{c.start + i:>5}: {line}"
                             for i, line in enumerate(c.text.splitlines()))
        blocks.append(f"### {c.path} ({c.kind} {c.symbol})\n{numbered}")
    return "\n\n".join(blocks)


def answer(index, question: str, k: int = 5, profile=None, G=None, overview: str = ""):
    level = "intermediate"
    if profile is not None:
        profile.observe(question)
        level = profile.level

    results = index.search(question, k)
    chain = PROMPT | get_llm() | StrOutputParser()
    text = chain.invoke({
        "level": level,
        "style": STYLES[level],
        "overview": overview or "(not available)",
        "structure": structure_notes(G, results) if G is not None else "(not available)",
        "context": format_context(results),
        "question": question,
    })
    sources = [f"{c.path}:{c.start}-{c.end} (score {s:.2f})" for s, c in results]
    return text, sources