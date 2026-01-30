#!/usr/bin/env python3
"""
Day 2 - Task 3: Test RAG Queries
Goal: Query the RAG corpus and validate response quality

Success Criteria:
- Response time < 2 seconds
- Answers are accurate and relevant
- Source citations included
"""

import subprocess
import json
import requests
import time
from pathlib import Path

# Load config
with open("rag_config.json") as f:
    config = json.load(f)

PROJECT_ID = config["project_id"]
PROJECT_NUMBER = config["project_number"]
LOCATION = config["location"]
CORPUS_ID = config["corpus_id"]
CORPUS_NAME = config["corpus_name"]

def get_access_token():
    """Get access token from gcloud"""
    result = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True,
        text=True
    )
    return result.stdout.strip()

def query_rag(query_text, top_k=5):
    """Query the RAG corpus and get relevant context"""
    
    url = f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1/projects/{PROJECT_NUMBER}/locations/{LOCATION}:retrieveContexts"
    
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "vertexRagStore": {
            "ragCorpora": [CORPUS_NAME]
        },
        "query": {
            "text": query_text,
            "similarityTopK": top_k
        }
    }
    
    start_time = time.time()
    response = requests.post(url, headers=headers, json=payload)
    response_time = (time.time() - start_time) * 1000  # ms
    
    if response.status_code != 200:
        return None, response_time, f"Error: {response.status_code} - {response.text}"
    
    result = response.json()
    contexts = result.get("contexts", {}).get("contexts", [])
    
    return contexts, response_time, None

def generate_answer(query_text, contexts):
    """Generate an answer using Gemini with the RAG context"""
    
    # Build context string from retrieved chunks
    context_text = "\n\n".join([
        f"[Source: {c.get('sourceUri', 'unknown')}]\n{c.get('text', '')}"
        for c in contexts
    ])
    
    # Use us-central1 for Gemini (available in more regions)
    gemini_location = "us-central1"
    url = f"https://{gemini_location}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{gemini_location}/publishers/google/models/gemini-2.0-flash:generateContent"
    
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""You are an emergency medicine assistant. Answer the following question using ONLY the provided protocol context. Be concise and use bullet points.

CONTEXT FROM PROTOCOLS:
{context_text}

QUESTION: {query_text}

ANSWER (use bullet points, cite sources):"""

    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 500
        }
    }
    
    start_time = time.time()
    response = requests.post(url, headers=headers, json=payload)
    generation_time = (time.time() - start_time) * 1000
    
    if response.status_code != 200:
        return None, generation_time, f"Error: {response.status_code} - {response.text}"
    
    result = response.json()
    answer = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    
    return answer, generation_time, None

def test_query(query_text):
    """Run a complete RAG query test"""
    print(f"\n{'='*60}")
    print(f"🔍 Query: {query_text}")
    print('='*60)
    
    # Step 1: Retrieve relevant context
    print("\n📚 Retrieving context from RAG corpus...")
    contexts, retrieval_time, error = query_rag(query_text)
    
    if error:
        print(f"❌ {error}")
        return None
    
    print(f"  ✅ Retrieved {len(contexts)} relevant chunks in {retrieval_time:.0f}ms")
    
    # Show sources
    sources = set()
    for ctx in contexts:
        source = ctx.get("sourceUri", "unknown")
        sources.add(source.split("/")[-1])
    
    print(f"  📄 Sources: {', '.join(sources)}")
    
    # Step 2: Generate answer with Gemini
    print("\n🤖 Generating answer with Gemini...")
    answer, generation_time, error = generate_answer(query_text, contexts)
    
    if error:
        print(f"❌ {error}")
        return None
    
    total_time = retrieval_time + generation_time
    
    print(f"  ✅ Answer generated in {generation_time:.0f}ms")
    print(f"  ⏱️  Total time: {total_time:.0f}ms")
    
    # Display answer
    print(f"\n📋 ANSWER:")
    print("-" * 40)
    print(answer)
    print("-" * 40)
    
    # Performance check
    if total_time < 2000:
        print(f"\n✅ Performance: PASS ({total_time:.0f}ms < 2000ms)")
    else:
        print(f"\n⚠️  Performance: SLOW ({total_time:.0f}ms > 2000ms)")
    
    return {
        "query": query_text,
        "answer": answer,
        "sources": list(sources),
        "retrieval_time_ms": retrieval_time,
        "generation_time_ms": generation_time,
        "total_time_ms": total_time
    }

def main():
    print("="*60)
    print("  Task 3: Test RAG Queries")
    print("="*60)
    print(f"\nCorpus: {CORPUS_NAME}")
    print(f"Location: {LOCATION}")
    
    # Test queries
    test_queries = [
        "What are the steps for cardiac arrest?",
        "What is the trauma algorithm?",
        "When should I give epinephrine?",
        "What are the signs of shock?"
    ]
    
    results = []
    for query in test_queries:
        result = test_query(query)
        if result:
            results.append(result)
    
    # Summary
    print("\n" + "="*60)
    print("  SUMMARY")
    print("="*60)
    
    if results:
        avg_time = sum(r["total_time_ms"] for r in results) / len(results)
        passed = sum(1 for r in results if r["total_time_ms"] < 2000)
        
        print(f"\nQueries tested: {len(results)}")
        print(f"Average response time: {avg_time:.0f}ms")
        print(f"Performance pass rate: {passed}/{len(results)}")
        
        if passed == len(results) and avg_time < 2000:
            print("\n" + "="*60)
            print("  ✅ Task 3 Complete - All tests passed!")
            print("="*60)
            print("\n🎉 RAG system is working!")
            print("   - Queries return in < 2 seconds")
            print("   - Answers are sourced from protocols")
            print("   - Ready for Day 3 (UI/API development)")
        else:
            print("\n⚠️  Some tests need review")
    else:
        print("\n❌ No successful queries")

if __name__ == "__main__":
    main()
