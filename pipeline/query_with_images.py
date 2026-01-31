#!/usr/bin/env python3
"""
Query Demo with Images
Shows answers, citations, AND relevant images
"""

import json
import subprocess
import requests
import time
import sys
sys.path.insert(0, '.')

from protocol_store import ProtocolStore, get_images_from_rag_response

# Load config
with open('../poc/rag_config.json', 'r') as f:
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
    
    prompt = f"""You are an emergency medicine assistant. Answer concisely using bullet points.
Cite your sources.

PROTOCOL CONTEXT:
{context_text}

QUESTION: {query}

ANSWER:"""

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 500
        }
    }
    
    start = time.time()
    resp = requests.post(url, headers=headers, json=payload)
    elapsed = (time.time() - start) * 1000
    
    if resp.status_code != 200:
        return f"Error: {resp.status_code}", elapsed
    
    answer = resp.json()['candidates'][0]['content']['parts'][0]['text']
    return answer, elapsed


def demo_query(query):
    """Run a complete query with images"""
    print(f"\n{'='*70}")
    print(f"🔍 QUERY: {query}")
    print('='*70)
    
    # Step 1: Retrieve context
    print("\n📚 RETRIEVING FROM RAG...")
    contexts, rag_time = query_rag(query)
    print(f"   Retrieved {len(contexts)} chunks in {rag_time:.0f}ms")
    
    if not contexts:
        print("   No relevant context found.")
        return
    
    # Step 2: Get associated images
    images = get_images_from_rag_response(contexts, signed_urls=False)
    
    # Step 3: Show sources
    print("\n📄 SOURCES:")
    sources = set()
    for ctx in contexts:
        source = ctx['sourceUri'].split('/')[-1]
        sources.add(source)
    for s in sources:
        print(f"   • {s}")
    
    # Step 4: Show images
    if images:
        print(f"\n🖼️  RELEVANT IMAGES ({len(images)}):")
        for img in images:
            print(f"   • Page {img['page']} from {img['source']}")
            print(f"     {img['url']}")
    else:
        print("\n🖼️  No images found for these protocols")
    
    # Step 5: Generate answer
    print("\n🤖 ANSWER:")
    print("-"*70)
    answer, gen_time = generate_answer(query, contexts)
    print(answer)
    print("-"*70)
    
    # Step 6: Performance
    total = rag_time + gen_time
    status = "✅" if total < 2000 else "⚠️"
    print(f"\n⏱️  Total: {total:.0f}ms {status}")
    
    return {
        "query": query,
        "answer": answer,
        "sources": list(sources),
        "images": images,
        "time_ms": total
    }


def main():
    print("="*70)
    print("  EM Protocol Query Demo (with Images)")
    print("="*70)
    
    queries = [
        "What are the steps for cardiac arrest?",
        "What is the trauma algorithm?",
        "When should I give epinephrine?",
    ]
    
    results = []
    for q in queries:
        result = demo_query(q)
        if result:
            results.append(result)
    
    # Summary
    print(f"\n\n{'='*70}")
    print("  SUMMARY")
    print('='*70)
    print(f"Queries: {len(results)}")
    avg_time = sum(r['time_ms'] for r in results) / len(results) if results else 0
    print(f"Average time: {avg_time:.0f}ms")
    total_images = sum(len(r['images']) for r in results)
    print(f"Total images returned: {total_images}")


if __name__ == "__main__":
    main()
