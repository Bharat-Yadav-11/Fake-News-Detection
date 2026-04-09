from flask import Flask, render_template, request
import math
import os
import pickle
import re
from html import unescape
from urllib.parse import parse_qs, unquote, urlparse

import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


if load_dotenv is not None:
    load_dotenv()


app = Flask(__name__, template_folder="./templates", static_folder="./static")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}
SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "auto").lower()
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "").strip()
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "").strip()
CONTACT_EMAIL = "bharatyadav2724@gmail.com"
CONTACT_NAME = "bharat"

TRUSTED_DOMAINS = (
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "npr.org",
    "cnbc.com",
    "wsj.com",
    "nytimes.com",
    "thehindu.com",
    "indianexpress.com",
    "hindustantimes.com",
    "livemint.com",
    "economictimes.indiatimes.com",
    "moneycontrol.com",
)

TRUSTED_DOMAIN_ALIASES = {
    "reuters.com": ("reuters", "reuters news"),
    "apnews.com": ("associated press", "ap news", "apnews"),
    "bbc.com": ("bbc", "bbc news"),
    "npr.org": ("npr", "national public radio"),
    "cnbc.com": ("cnbc",),
    "wsj.com": ("wsj", "wall street journal"),
    "nytimes.com": ("nyt", "new york times", "nytimes"),
    "thehindu.com": ("the hindu",),
    "indianexpress.com": ("indian express", "the indian express"),
    "hindustantimes.com": ("hindustan times",),
    "livemint.com": ("livemint",),
    "economictimes.indiatimes.com": ("economic times", "et markets", "economictimes"),
    "moneycontrol.com": ("moneycontrol",),
}

HTTP = requests.Session() if requests is not None else None


def ensure_nltk_resource(resource_path, download_name):
    try:
        nltk.data.find(resource_path)
    except LookupError:
        nltk.download(download_name, quiet=True)


loaded_model = pickle.load(open("model.pkl", "rb"))
vector = pickle.load(open("vector.pkl", "rb"))

ensure_nltk_resource("corpora/stopwords", "stopwords")
ensure_nltk_resource("tokenizers/punkt", "punkt")
ensure_nltk_resource("corpora/wordnet", "wordnet")
ensure_nltk_resource("corpora/omw-1.4", "omw-1.4")

lemmatizer = WordNetLemmatizer()
stpwrds = set(stopwords.words("english"))


def preprocess_text(news):
    cleaned = re.sub(r"[^a-zA-Z\s]", " ", news)
    cleaned = cleaned.lower()
    tokens = nltk.word_tokenize(cleaned)

    processed_tokens = []
    for token in tokens:
        if token and token not in stpwrds:
            processed_tokens.append(lemmatizer.lemmatize(token))

    return " ".join(processed_tokens)


def fake_news_det(news):
    cleaned_text = preprocess_text(news)
    vectorized_input_data = vector.transform([cleaned_text])
    prediction = int(loaded_model.predict(vectorized_input_data)[0])
    decision_score = float(loaded_model.decision_function(vectorized_input_data)[0])

    return {
        "prediction": prediction,
        "decision_score": decision_score,
        "cleaned_text": cleaned_text,
    }


def extract_numbers(text):
    return {match.replace(",", "") for match in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


def tokenize_for_match(text):
    cleaned = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return {
        token
        for token in cleaned.split()
        if len(token) > 2 and token not in stpwrds
    }


def build_similarity_score(left_text, right_text):
    if not left_text.strip() or not right_text.strip():
        return 0.0

    matrix = TfidfVectorizer(stop_words="english").fit_transform([left_text, right_text])
    return float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])


def build_overlap_score(left_text, right_text):
    left_tokens = tokenize_for_match(left_text)
    right_tokens = tokenize_for_match(right_text)
    if not left_tokens or not right_tokens:
        return 0.0

    overlap = left_tokens & right_tokens
    return len(overlap) / max(len(left_tokens), 1)


def get_lead_excerpt(text, max_words=28):
    words = text.split()
    return " ".join(words[:max_words])


def build_search_query(text, max_words=16, max_chars=140):
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return ""

    sentence_parts = re.split(r"(?<=[.!?])\s+", normalized)
    preferred = sentence_parts[0] if sentence_parts else normalized
    excerpt = get_lead_excerpt(preferred, max_words=max_words)
    excerpt = excerpt[:max_chars].strip(" ,.-")
    return excerpt or normalized[:max_chars].strip(" ,.-")


def build_search_queries(text):
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []

    queries = []
    for candidate in (
        build_search_query(normalized, max_words=18, max_chars=160),
        build_search_query(normalized, max_words=12, max_chars=110),
        build_search_query(normalized, max_words=28, max_chars=220),
    ):
        if candidate and candidate not in queries:
            queries.append(candidate)

    return queries


def normalize_url(url):
    if not url:
        return ""

    if url.startswith("//"):
        url = f"https:{url}"

    parsed = urlparse(url)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            return unquote(target)

    return url


def get_domain(url):
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def is_trusted_source(url):
    domain = get_domain(url)
    return any(domain == trusted or domain.endswith(f".{trusted}") for trusted in TRUSTED_DOMAINS)


def detect_preferred_domains(text):
    lowered = text.lower()
    matched_domains = set()

    for domain, aliases in TRUSTED_DOMAIN_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            matched_domains.add(domain)

    return matched_domains


def filter_trusted_items(items):
    filtered_items = []
    seen_urls = set()

    for item in items:
        url = normalize_url(item.get("url", ""))
        if not url or url in seen_urls or not is_trusted_source(url):
            continue

        seen_urls.add(url)
        filtered_items.append(
            {
                **item,
                "url": url,
                "domain": get_domain(url),
            }
        )

    return filtered_items


def fetch_page_summary(url):
    if HTTP is None or BeautifulSoup is None or not url:
        return ""

    try:
        response = HTTP.get(url, headers=HEADERS, timeout=6)
        response.raise_for_status()
    except Exception:
        return ""

    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    description_tag = soup.find("meta", attrs={"name": "description"})
    og_description_tag = soup.find("meta", attrs={"property": "og:description"})
    description = ""

    if description_tag and description_tag.get("content"):
        description = description_tag["content"].strip()
    elif og_description_tag and og_description_tag.get("content"):
        description = og_description_tag["content"].strip()

    return unescape(" ".join(part for part in [title, description] if part))


def search_serpapi(query, domain=None):
    if HTTP is None or not SERPAPI_API_KEY:
        return None

    search_query = f"{query} site:{domain}" if domain else query

    try:
        response = HTTP.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google",
                "q": search_query,
                "api_key": SERPAPI_API_KEY,
                "num": 12,
            },
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return {"provider": "SerpAPI", "error": str(exc), "items": []}

    items = []
    for item in payload.get("organic_results", []):
        url = item.get("link", "")
        items.append(
            {
                "title": item.get("title", "Untitled result"),
                "url": url,
                "snippet": item.get("snippet", ""),
                "domain": get_domain(url),
            }
        )

    return {"provider": "SerpAPI", "error": "", "items": items}


def search_newsapi(query, domain=None):
    if HTTP is None or not NEWSAPI_KEY:
        return None

    params = {
        "q": query,
        "language": "en",
        "pageSize": 12,
        "sortBy": "publishedAt",
        "apiKey": NEWSAPI_KEY,
    }
    if domain:
        params["domains"] = domain

    try:
        response = HTTP.get(
            "https://newsapi.org/v2/everything",
            params=params,
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return {"provider": "NewsAPI", "error": str(exc), "items": []}

    items = []
    for item in payload.get("articles", []):
        url = item.get("url", "")
        snippet = " ".join(
            part for part in [item.get("description", ""), item.get("content", "")] if part
        )
        items.append(
            {
                "title": item.get("title", "Untitled result"),
                "url": url,
                "snippet": snippet,
                "domain": get_domain(url),
            }
        )

    return {"provider": "NewsAPI", "error": "", "items": items}


def search_duckduckgo_html(query, domain=None):
    if HTTP is None or BeautifulSoup is None:
        return {"provider": "DuckDuckGo HTML", "error": "Missing requests/bs4", "items": []}

    search_query = f"{query} site:{domain}" if domain else query

    try:
        response = HTTP.get(
            "https://html.duckduckgo.com/html/",
            params={"q": search_query},
            headers=HEADERS,
            timeout=10,
        )
        response.raise_for_status()
    except Exception as exc:
        return {"provider": "DuckDuckGo HTML", "error": str(exc), "items": []}

    soup = BeautifulSoup(response.text, "html.parser")
    items = []

    for result in soup.select(".result"):
        link = result.select_one(".result__title a")
        snippet_node = result.select_one(".result__snippet")
        if not link:
            continue

        url = normalize_url(link.get("href", ""))
        items.append(
            {
                "title": unescape(link.get_text(" ", strip=True)),
                "url": url,
                "snippet": unescape(snippet_node.get_text(" ", strip=True)) if snippet_node else "",
                "domain": get_domain(url),
            }
        )

    return {"provider": "DuckDuckGo HTML", "error": "", "items": items}


def run_provider_searches(query, domain=None):
    provider_runs = []

    if SEARCH_PROVIDER in ("auto", "serpapi"):
        provider_runs.append(search_serpapi(query, domain=domain))
    if SEARCH_PROVIDER in ("auto", "newsapi"):
        provider_runs.append(search_newsapi(query, domain=domain))
    if SEARCH_PROVIDER in ("auto", "duckduckgo", "ddg"):
        provider_runs.append(search_duckduckgo_html(query, domain=domain))

    return [result for result in provider_runs if result]


def merge_trusted_items(results_bucket, seen_urls, provider_names, items, provider_name, max_items):
    added = 0
    filtered_items = filter_trusted_items(items)

    for item in filtered_items:
        url = item.get("url", "")
        if not url or url in seen_urls:
            continue
        if len(results_bucket) >= max_items:
            break

        seen_urls.add(url)
        provider_names.add(provider_name)
        results_bucket.append(
            {
                **item,
                "provider": provider_name,
            }
        )
        added += 1

    return added


def fetch_search_results(claim, max_results=6):
    query_variants = build_search_queries(claim)
    preferred_domains = list(detect_preferred_domains(claim))
    fallback_domains = [domain for domain in TRUSTED_DOMAINS if domain not in preferred_domains]
    priority_domains = preferred_domains + fallback_domains

    trusted_items = []
    seen_urls = set()
    provider_names = set()
    errors = []
    target_pool_size = max(max_results * 3, 12)

    for query in query_variants:
        for result in run_provider_searches(query):
            merge_trusted_items(
                trusted_items,
                seen_urls,
                provider_names,
                result.get("items", []),
                result.get("provider", "Unknown"),
                target_pool_size,
            )
            if result.get("error"):
                errors.append({"provider": result.get("provider", "Unknown"), "error": result["error"]})
        if len(trusted_items) >= target_pool_size:
            break

    if len(trusted_items) < max_results:
        for domain in priority_domains:
            for query in query_variants[:2]:
                for result in run_provider_searches(query, domain=domain):
                    merge_trusted_items(
                        trusted_items,
                        seen_urls,
                        provider_names,
                        result.get("items", []),
                        result.get("provider", "Unknown"),
                        target_pool_size,
                    )
                    if result.get("error"):
                        errors.append({"provider": result.get("provider", "Unknown"), "error": result["error"]})
                if len(trusted_items) >= target_pool_size:
                    break
            if len(trusted_items) >= target_pool_size:
                break

    if trusted_items:
        provider_label = ", ".join(sorted(provider_names)) if provider_names else "Trusted sources"
        return {
            "provider": provider_label,
            "error": "",
            "items": trusted_items,
        }

    if errors:
        return {
            "provider": errors[0]["provider"],
            "error": errors[0]["error"],
            "items": [],
        }

    return {
        "provider": "No provider configured",
        "error": (
            "No trusted live sources were returned. Set SERPAPI_API_KEY or "
            "NEWSAPI_KEY for stronger trusted-source retrieval. HTML scraping "
            "is only a fallback."
        ),
        "items": [],
    }


def build_live_lookup_error(search_result):
    provider_name = search_result.get("provider", "Live provider")
    if provider_name == "NewsAPI":
        return (
            "NewsAPI could not process this full article as a search query. "
            "Try a shorter claim or headline, or configure another provider "
            "for broader live lookup."
        )

    if provider_name == "SerpAPI":
        return (
            "SerpAPI did not return usable trusted-source results for this claim."
        )

    if provider_name == "DuckDuckGo HTML":
        return (
            "DuckDuckGo fallback did not return usable trusted-source results for this claim."
        )

    return (
        "Live lookup is temporarily unavailable or no trusted-source matches were found."
    )


def score_search_results(claim, items, provider_name, max_results=6):
    results = []
    preferred_domains = detect_preferred_domains(claim)
    query_variants = build_search_queries(claim)
    lead_excerpt = query_variants[0] if query_variants else get_lead_excerpt(claim)

    for item in items:
        url = item.get("url", "")
        title = item.get("title", "Untitled result")
        snippet = item.get("snippet", "")
        domain = item.get("domain", get_domain(url))
        page_summary = fetch_page_summary(url)
        evidence_text = " ".join(part for part in [title, snippet, page_summary] if part)
        full_similarity = build_similarity_score(claim, evidence_text)
        query_similarity = max(
            [build_similarity_score(query, evidence_text) for query in query_variants] or [0.0]
        )
        overlap = max(
            [build_overlap_score(claim, evidence_text)]
            + [build_overlap_score(query, evidence_text) for query in query_variants]
        )
        title_similarity = max(
            [build_similarity_score(claim, title)]
            + [build_similarity_score(query, title) for query in query_variants]
        )
        lead_similarity = build_similarity_score(lead_excerpt, title or evidence_text)

        claim_numbers = extract_numbers(claim)
        source_numbers = extract_numbers(evidence_text)
        matching_numbers = sorted(claim_numbers & source_numbers)
        preferred_domain_match = domain in preferred_domains

        has_number_alignment = not claim_numbers or bool(matching_numbers)
        similarity = min(
            0.999,
            (
                max(full_similarity * 0.9, query_similarity) * 0.62
                + overlap * 0.16
                + title_similarity * 0.14
                + lead_similarity * 0.08
                + (0.05 if matching_numbers else 0.0)
                + (0.08 if preferred_domain_match else 0.0)
            ),
        )

        if similarity >= 0.56 and (overlap >= 0.16 or title_similarity >= 0.26) and has_number_alignment:
            status = "Strong match"
        elif similarity >= 0.3 or overlap >= 0.1 or title_similarity >= 0.16:
            status = "Related coverage"
        else:
            status = "Weak match"

        results.append(
            {
                "title": title,
                "url": url,
                "domain": domain,
                "snippet": snippet or page_summary or "No snippet available.",
                "status": status,
                "trusted": is_trusted_source(url),
                "similarity": round(similarity, 3),
                "full_similarity": round(full_similarity, 3),
                "query_similarity": round(query_similarity, 3),
                "overlap": round(overlap, 3),
                "title_similarity": round(title_similarity, 3),
                "lead_similarity": round(lead_similarity, 3),
                "preferred_domain_match": preferred_domain_match,
                "matching_numbers": matching_numbers,
                "provider": item.get("provider", provider_name),
            }
        )

    results.sort(
        key=lambda item: (
            item["similarity"],
            item["preferred_domain_match"],
            item["status"] == "Strong match",
            item["status"] == "Related coverage",
            item["query_similarity"],
            item["overlap"],
            item["title_similarity"],
            len(item["matching_numbers"]),
        ),
        reverse=True,
    )
    top_results = results[:max_results]

    support_count = sum(1 for item in top_results if item["status"] == "Strong match")
    related_count = sum(1 for item in top_results if item["status"] == "Related coverage")
    trusted_count = sum(1 for item in top_results if item["trusted"])

    if not top_results:
        verdict = "No live sources found"
        summary = f"{provider_name} did not return usable live sources for this claim."
    elif support_count >= 2 and trusted_count >= 1:
        verdict = "Likely supported by live sources"
        summary = f"Multiple {provider_name} results look consistent with the claim."
    elif support_count >= 1 or related_count >= 2:
        verdict = "Needs manual verification"
        summary = f"{provider_name} found relevant trusted-source coverage for this claim."
    else:
        verdict = "Needs manual verification"
        summary = f"{provider_name} found weak trusted-source matches for this claim."

    return {
        "available": True,
        "provider": provider_name,
        "verdict": verdict,
        "summary": summary,
        "sources": top_results,
    }


def search_live_sources(claim, max_results=6):
    if HTTP is None:
        return {
            "available": False,
            "provider": "Unavailable",
            "verdict": "Live lookup unavailable",
            "summary": "Install requests to enable live lookup.",
            "sources": [],
        }

    query = build_search_query(claim)
    if not query:
        return {
            "available": False,
            "provider": "Unavailable",
            "verdict": "Live lookup unavailable",
            "summary": "No claim text was provided.",
            "sources": [],
        }

    search_result = fetch_search_results(claim, max_results=max_results)
    provider_name = search_result.get("provider", "Unknown")

    if search_result.get("items"):
        return score_search_results(claim, search_result["items"], provider_name, max_results=max_results)

    summary = build_live_lookup_error(search_result)
    return {
        "available": False,
        "provider": provider_name,
        "verdict": "Live lookup unavailable",
        "summary": summary,
        "sources": [],
    }

def build_model_confidence(score):
    return round((1 / (1 + math.exp(-abs(score)))) * 100, 1)


def build_prediction_detail():
    return (
        "This local classifier was trained on the repository dataset and can misclassify "
        "modern finance, local-price, or out-of-domain claims. Retraining is recommended "
        "if you want stronger real-world accuracy."
    )


@app.route("/")
def home():
    return render_template(
        "index.html",
        contact_email=CONTACT_EMAIL,
        contact_name=CONTACT_NAME,
    )


@app.route("/predict", methods=["GET", "POST"])
def predict():
    if request.method == "POST":
        message = request.form.get("news", "").strip()

        if not message:
            return render_template(
                "prediction.html",
                error_message="Paste a claim, headline, or article before submitting.",
                submitted_text="",
                contact_email=CONTACT_EMAIL,
                contact_name=CONTACT_NAME,
            )

        model_result = fake_news_det(message)
        live_check = search_live_sources(message)
        is_fake = model_result["prediction"] == 1

        return render_template(
            "prediction.html",
            prediction_text="Likely Fake" if is_fake else "Likely Real",
            prediction_detail=build_prediction_detail(),
            score_label="Model confidence",
            score_value=f'{build_model_confidence(model_result["decision_score"])}%',
            submitted_text=message,
            cleaned_text=model_result["cleaned_text"],
            live_verdict=live_check["verdict"],
            live_summary=live_check["summary"],
            live_sources=live_check["sources"],
            live_available=live_check["available"] and bool(live_check["sources"]),
            live_provider=live_check["provider"],
            contact_email=CONTACT_EMAIL,
            contact_name=CONTACT_NAME,
        )

    return render_template(
        "prediction.html",
        submitted_text="",
        live_sources=[],
        contact_email=CONTACT_EMAIL,
        contact_name=CONTACT_NAME,
    )


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
