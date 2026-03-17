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
CONTACT_EMAIL = "bharatyadav@gmail.com"
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


def build_similarity_score(left_text, right_text):
    if not left_text.strip() or not right_text.strip():
        return 0.0

    matrix = TfidfVectorizer(stop_words="english").fit_transform([left_text, right_text])
    return float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])


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


def search_serpapi(query):
    if HTTP is None or not SERPAPI_API_KEY:
        return None

    try:
        response = HTTP.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google",
                "q": query,
                "api_key": SERPAPI_API_KEY,
                "num": 8,
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


def search_newsapi(query):
    if HTTP is None or not NEWSAPI_KEY:
        return None

    try:
        response = HTTP.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "language": "en",
                "pageSize": 8,
                "sortBy": "publishedAt",
                "apiKey": NEWSAPI_KEY,
            },
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


def search_duckduckgo_html(query):
    if HTTP is None or BeautifulSoup is None:
        return {"provider": "DuckDuckGo HTML", "error": "Missing requests/bs4", "items": []}

    try:
        response = HTTP.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
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


def fetch_search_results(query):
    providers = []

    if SEARCH_PROVIDER in ("auto", "serpapi"):
        providers.append(search_serpapi(query))
    if SEARCH_PROVIDER in ("auto", "newsapi"):
        providers.append(search_newsapi(query))
    if SEARCH_PROVIDER in ("auto", "duckduckgo", "ddg"):
        providers.append(search_duckduckgo_html(query))

    for result in providers:
        if result and result.get("items"):
            return result

    for result in providers:
        if result and result.get("error"):
            return result

    return {
        "provider": "No provider configured",
        "error": (
            "Set SERPAPI_API_KEY or NEWSAPI_KEY for reliable live search. "
            "HTML scraping is only a fallback."
        ),
        "items": [],
    }


def score_search_results(claim, items, provider_name, max_results=6):
    results = []

    for item in items:
        url = item.get("url", "")
        title = item.get("title", "Untitled result")
        snippet = item.get("snippet", "")
        page_summary = fetch_page_summary(url)
        evidence_text = " ".join(part for part in [title, snippet, page_summary] if part)
        similarity = build_similarity_score(claim, evidence_text)

        claim_numbers = extract_numbers(claim)
        source_numbers = extract_numbers(evidence_text)
        matching_numbers = sorted(claim_numbers & source_numbers)
        contradicts_numbers = bool(claim_numbers and source_numbers and not matching_numbers)

        if similarity >= 0.33 and (not claim_numbers or matching_numbers):
            status = "Supports claim"
        elif contradicts_numbers and similarity >= 0.18:
            status = "Possible contradiction"
        elif similarity >= 0.18:
            status = "Related coverage"
        else:
            status = "Weak match"

        results.append(
            {
                "title": title,
                "url": url,
                "domain": item.get("domain", get_domain(url)),
                "snippet": snippet or page_summary or "No snippet available.",
                "status": status,
                "trusted": is_trusted_source(url),
                "similarity": round(similarity, 3),
                "matching_numbers": matching_numbers,
                "provider": provider_name,
            }
        )

    results.sort(key=lambda item: (item["trusted"], item["similarity"]), reverse=True)
    top_results = results[:max_results]

    support_count = sum(1 for item in top_results if item["status"] == "Supports claim")
    contradiction_count = sum(1 for item in top_results if item["status"] == "Possible contradiction")
    trusted_count = sum(1 for item in top_results if item["trusted"])

    if not top_results:
        verdict = "No live sources found"
        summary = f"{provider_name} did not return usable live sources for this claim."
    elif support_count >= 2 and trusted_count >= 1:
        verdict = "Likely supported by live sources"
        summary = f"Multiple {provider_name} results look consistent with the claim."
    elif contradiction_count >= 2 and support_count == 0:
        verdict = "Potentially contradicted by live sources"
        summary = f"{provider_name} results show mismatching details or numbers."
    else:
        verdict = "Needs manual verification"
        summary = f"{provider_name} found related coverage, but the evidence is not strong enough to auto-verify."

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

    query = claim.strip()
    if not query:
        return {
            "available": False,
            "provider": "Unavailable",
            "verdict": "Live lookup unavailable",
            "summary": "No claim text was provided.",
            "sources": [],
        }

    search_result = fetch_search_results(query)
    provider_name = search_result.get("provider", "Unknown")

    if search_result.get("items"):
        return score_search_results(query, search_result["items"], provider_name, max_results=max_results)

    summary = search_result.get("error") or (
        "No usable live search results were returned. "
        "For production, configure SERPAPI_API_KEY or NEWSAPI_KEY."
    )
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
            live_available=live_check["available"],
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
