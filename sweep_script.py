import json
import os
import time
import statistics
from typing import Dict, List, Optional
import google.auth
import google.auth.transport.requests
import requests

PROJECT_ID = "clinical-assistant-457902"
LOCATION = "us-central1"

PROMPTS = [
    "What is the dose of alteplase for acute ischemic stroke?",
    "How do I manage suspected hyperkalemia with ECG changes?",
    "What is the first-line treatment for status epilepticus in adults?",
    "What are the indications and dose for intralipid in local anesthetic systemic toxicity?",
    "What is the adult treatment for anaphylaxis in the emergency department?",
    "How should I risk stratify chest pain with a HEART score in the ED?"
]

LONG_EM_PROMPT = """You are an emergency medicine clinical assistant for bedside use.
Answer the user's question directly and concisely.
RESPONSE RULES:
- Start with **Bottom Line:** in 1-2 sentences.
- Use markdown tables for medication dosing, contraindications, scoring systems, and comparisons when useful.
- Medication dosing must use standard form: Drug | Dose | Route | Frequency or rate | Max dose | Key cautions.
- Prefer society guidelines and PubMed or PubMed Central sources when available.
- FOAM or blog sources may be used only when clearly relevant and attributed with a URL.
- Never invent citations, URLs, journal names, article titles, authors, DOIs, or PMIDs.
- Include a PMID only when it is explicitly present in the grounded source.
- If a point cannot be supported by grounded sources, say so plainly.
- Be practical and concise for bedside use.
QUESTION: {query}"""

CONCISE_EM_PROMPT = """You are an EM bedside assistant. Give a high-yield, concise answer.
Rules:
- Start with a 1-sentence **Bottom Line**.
- Use tables for dosing or scores.
- Be extremely brief. Focus on immediate actions.
- Use grounded info only.
QUESTION: {query}"""

CONFIGS = [
    {"name": "A", "model": "gemini-1.5-flash", "temp": 0.7, "max_tokens": 2000, "prompt": LONG_EM_PROMPT},
    {"name": "B", "model": "gemini-1.5-flash", "temp": 0.5, "max_tokens": 1200, "prompt": CONCISE_EM_PROMPT},
    {"name": "C", "model": "gemini-1.5-flash", "temp": 0.3, "max_tokens": 900, "prompt": CONCISE_EM_PROMPT},
    {"name": "D", "model": "gemini-1.5-flash", "temp": 0.5, "max_tokens": 1200, "prompt": CONCISE_EM_PROMPT},
]

def get_access_token():
    credentials, _ = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token

def run_query(config, query):
    url = f"https://{LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/publishers/google/models/{config['model']}:streamGenerateContent?alt=sse"
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
    }
    payload = {
        "contents": [{"role": "user", "parts": [{"text": config['prompt'].format(query=query)}]}],
        "tools": [{"googleSearchRetrieval": {"dynamicRetrievalConfig": {"mode": "MODE_DYNAMIC", "dynamicThreshold": 0.3}}}],
        "generationConfig": {
            "temperature": config['temp'],
            "maxOutputTokens": config['max_tokens'],
        },
    }
    
    start_time = time.time()
    ttfc = None
    full_text = ""
    latest_metadata = None
    
    try:
        response = requests.post(url, headers=headers, json=payload, stream=True, timeout=60)
        if response.status_code != 200:
            return {"error": f"Status {response.status_code}: {response.text}"}
            
        for line in response.iter_lines():
            if not line: continue
            line_str = line.decode('utf-8')
            if not line_str.startswith("data: "): continue
            json_str = line_str[6:]
            if json_str == "[DONE]": break
            
            chunk_data = json.loads(json_str)
            if ttfc is None:
                ttfc = int((time.time() - start_time) * 1000)
            
            candidates = chunk_data.get("candidates", [])
            for cand in candidates:
                parts = cand.get("content", {}).get("parts", [])
                for p in parts:
                    if "text" in p:
                        full_text += p["text"]
                
                meta = cand.get("groundingMetadata") or cand.get("grounding_metadata")
                if meta:
                    latest_metadata = meta
                    
        total_time = int((time.time() - start_time) * 1000)
        
        citations = []
        if latest_metadata:
            seen = set()
            for chunk in latest_metadata.get("groundingChunks", []):
                web = chunk.get("web") or {}
                uri = web.get("uri") or web.get("url")
                if uri and uri not in seen:
                    citations.append(uri)
                    seen.add(uri)
        
        return {
            "ttfc": ttfc,
            "total_ms": total_time,
            "grounded": bool(latest_metadata),
            "citation_count": len(citations),
            "has_search_html": bool(latest_metadata.get("searchEntryPoint") if latest_metadata else None),
            "answer_excerpt": full_text[:500].replace("\n", " "),
            "citations": citations
        }
    except Exception as e:
        return {"error": str(e)}

results = {}
for config in CONFIGS:
    print(f"Running config {config['name']} ({config['model']})...")
    config_results = []
    for q in PROMPTS:
        res = run_query(config, q)
        res['prompt'] = q
        config_results.append(res)
    results[config['name']] = config_results

for name, res_list in results.items():
    valid = [r for r in res_list if "error" not in r]
    errors = len(res_list) - len(valid)
    
    print(f"\n--- Config {name} Summary ---")
    if not valid:
        print(f"All requests failed. Errors: {errors}")
        for r in res_list:
            if "error" in r:
                print(f"Error for '{r['prompt'][:30]}...': {r['error']}")
        continue
        
    ttfc_list = [r['ttfc'] for r in valid if r['ttfc'] is not None]
    total_list = [r['total_ms'] for r in valid]
    cit_list = [r['citation_count'] for r in valid]
    zero_cit = len([r for r in valid if r['citation_count'] == 0])

    print(f"Avg TTFC: {statistics.mean(ttfc_list):.1f}ms, Median TTFC: {statistics.median(ttfc_list):.1f}ms")
    print(f"Avg Total: {statistics.mean(total_list):.1f}ms, Median Total: {statistics.median(total_list):.1f}ms")
    print(f"Avg Citations: {statistics.mean(cit_list):.2f}, Zero-citation prompts: {zero_cit}")
    print(f"Error count: {errors}")

    print("\nPer-prompt results:")
    for r in res_list:
        if "error" in r:
            print(f"Q: {r['prompt']} | ERROR: {r['error']}")
        else:
            print(f"Q: {r['prompt']}\n   TTFC: {r['ttfc']}ms | Total: {r['total_ms']}ms | Grounded: {r['grounded']} | Citations: {r['citation_count']}\n   Excerpt: {r['answer_excerpt']}...")

    print("\nQualitative Assessment:")
    avg_total = statistics.mean(total_list)
    avg_cit = statistics.mean(cit_list)
    speed = "Fast" if avg_total < 4000 else "Moderate" if avg_total < 8000 else "Slow"
    qual = "Well-referenced" if avg_cit > 3 else "Adequately referenced" if avg_cit > 1 else "Poorly referenced"
    print(f"Config {name}: {speed} speed. {qual}. Excerpts show {'good' if 'Bottom Line' in valid[0]['answer_excerpt'] else 'potential'} structure.")
