#!/usr/bin/env python3
"""
Demo: RAG Query Results with Full Output
Shows answers, citations, and sources
"""

import json
import subprocess
import requests
import time

# Load config
with open('rag_config.json', 'r') as f:
    config = json.load(f)

PROJECT_ID = config['project_id']
PROJECT_NUMBER = config['project_number']
LOCATION = config['location']
CORPUS_NAME = config['corpus_name']

def get_token():
    return subprocess.check_output(['gcloud', 'auth', 'application-default', 'print-access-token']).decode().strip()

def query_rag(query):
    """Query the RAG corpus for relevant chunks"""
    url = f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1/projects/{PROJECT_NUMBER}/locations/{LOCATION}:retrieveContexts"
    headers = {
        "Authorization": f"Bearer {get_token()}",
        "Content-Type": "application/json"
    }
    payload = {
        "query": {"text": query},
        "vertex_rag_store": {
            "rag_corpora": [CORPUS_NAME]
        }
    }
    
    start = time.time()
    resp = requests.post(url, headers=headers, json=payload)
    elapsed = (time.time() - start) * 1000
    
    if resp.status_code != 200:
        print(f"  ❌ RAG Error: {resp.status_code}")
        print(f"  {resp.text[:500]}")
        return [], elapsed
    
    result = resp.json()
    contexts = []
    
    if 'contexts' in result:
        for ctx in result['contexts'].get('contexts', []):
            contexts.append({
                'text': ctx.get('text', ''),
                'sourceUri': ctx.get('sourceUri', 'unknown'),
                'score': ctx.get('score', 0)
            })
    
    return contexts, elapsed

def generate_answer(query, contexts):
    """Generate answer using Gemini with RAG context"""
    context_text = "\n\n---\n".join([
        f"[Source: {c.get('sourceUri', 'unknown').split('/')[-1]}]\n{c.get('text', '')}"
        for c in contexts
    ])
    
    url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/us-central1/publishers/google/models/gemini-2.0-flash:generateContent"
    headers = {
        "Authorization": f"Bearer {get_token()}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""You are an emergency medicine assistant helping doctors quickly find protocol information.

Answer the question using ONLY the protocol context below. Be concise and actionable.
- Use bullet points for steps
- Include dosages when available
- Cite your sources in parentheses

PROTOCOL CONTEXT:
{context_text}

QUESTION: {query}

ANSWER:"""

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 800
        }
    }
    
    start = time.time()
    resp = requests.post(url, headers=headers, json=payload)
    elapsed = (time.time() - start) * 1000
    
    if resp.status_code != 200:
        return f"Error: {resp.status_code} - {resp.text[:200]}", elapsed
    
    answer = resp.json()['candidates'][0]['content']['parts'][0]['text']
    return answer, elapsed

def demo_query(query):
    """Run a complete demo query"""
    print(f"\n{'='*70}")
    print(f"🔍 QUERY: {query}")
    print('='*70)
    
    # Step 1: Retrieve context
    print("\n📚 RETRIEVING FROM RAG CORPUS...")
    contexts, rag_time = query_rag(query)
    print(f"   Retrieved {len(contexts)} chunks in {rag_time:.0f}ms")
    
    if not contexts:
        print("   No relevant context found.")
        return
    
    # Step 2: Show sources
    print("\n📄 SOURCES & CITATIONS:")
    print("-"*70)
    for i, c in enumerate(contexts, 1):
        source = c['sourceUri'].split('/')[-1]
        score = c.get('score', 0)
        text_preview = c['text'][:300].replace('\n', ' ').strip()
        print(f"\n  [{i}] {source}")
        print(f"      Relevance Score: {score:.3f}")
        print(f"      Content: \"{text_preview}...\"")
    
    # Step 3: Generate answer
    print("\n\n🤖 GEMINI ANSWER:")
    print("-"*70)
    answer, gen_time = generate_answer(query, contexts)
    print(answer)
    print("-"*70)
    
    # Step 4: Performance
    total = rag_time + gen_time
    print(f"\n⏱️  PERFORMANCE:")
    print(f"   RAG Retrieval: {rag_time:.0f}ms")
    print(f"   Gemini Generation: {gen_time:.0f}ms")
    print(f"   Total: {total:.0f}ms {'✅' if total < 2000 else '⚠️'}")

def main():
    print("="*70)
    print("  EM Protocol RAG Demo - Query Results")
    print("="*70)
    print(f"\nCorpus: {CORPUS_NAME}")
    print(f"Model: gemini-2.0-flash")
    
    # Demo queries
    queries = [
        "What are the steps for cardiac arrest?",
        "What is the trauma algorithm?",
        "When should I give epinephrine?",
        "What are the H's and T's?",
    ]
    
    for q in queries:
        demo_query(q)
        print("\n")

if __name__ == "__main__":
    main()
