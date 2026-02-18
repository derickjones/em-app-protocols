# RAG System Test - Quick Start Guide

## Overview
This test compares your RAG system with Gemini on 5 emergency medicine queries to identify strengths and areas for improvement.

## Setup Steps

### 1. Start the Backend API
```bash
cd api
uvicorn main:app --reload --port 8000
```

Leave this running in a terminal.

### 2. Run the Test Script
In a new terminal:
```bash
cd /Users/derickjones/Documents/VS-Code/em-app/em-app-protocols
python3 test_rag_queries.py
```

This will:
- Query your RAG system with 5 emergency medicine questions
- Save results to `docs/RAG_TEST_RESULTS.md`
- Show response times, citations, and images

### 3. Test the Same Queries in Gemini

Go to [Google AI Studio](https://aistudio.google.com/) or Gemini and use this system prompt:

```
You are a clinical decision support tool for emergency medicine physicians meant to give them useful advice at the bedside.
```

Then test each of these 5 queries:

1. **What are the contraindications and dosing for tPA in acute ischemic stroke?**

2. **How do I manage undifferentiated shock in a hypotensive patient?**

3. **What's the management for suspected hyperkalemia with EKG changes?**

4. **When can I safely discharge a patient with chest pain after negative troponin?**

5. **What are the steps for RSI in a suspected difficult airway?**

### 4. Compare Results

Open `docs/GEMINI_VS_RAG_COMPARISON.md` and fill in:
- Paste your RAG responses (from `RAG_TEST_RESULTS.md`)
- Paste Gemini responses
- Compare on these dimensions:
  - **Accuracy**: Is the medical information correct?
  - **Relevance**: Does it answer the specific question?
  - **Citations**: Does it provide sources? (Your RAG should win here!)
  - **Actionability**: Can an ED physician act on this immediately?
  - **Bedside Utility**: Is it concise enough for the bedside?
  - **Format**: How is the information structured?

### 5. Identify Improvements

Based on the comparison, note:
- What Gemini does better (format, brevity, etc.)
- What your RAG does better (citations, specific sources, images)
- How to enhance your RAG's response format

## Expected Advantages of Your RAG System

✅ **Evidence-based citations** from WikEM, LITFL, PMC  
✅ **Images and diagrams** (especially from LITFL)  
✅ **Traceable sources** for liability protection  
✅ **Consistent information** from curated medical databases  
✅ **Copyright compliance** with proper attribution  

## Potential Areas for Improvement

🔧 **Response format** - May need better structure  
🔧 **Conciseness** - Balance detail vs brevity for bedside use  
🔧 **Action emphasis** - Highlight critical steps first  
🔧 **Clinical context** - Tailor to emergency medicine workflow  

## Troubleshooting

### API not starting?
```bash
cd api
# Check if required packages are installed
pip install -r requirements.txt

# Set environment variables if needed
export PROJECT_NUMBER="930035889332"
export RAG_LOCATION="us-west4"
export CORPUS_ID="2305843009213693952"
```

### Test script failing?
```bash
# Install requests if needed
pip3 install requests

# Run with more verbose output
python3 test_rag_queries.py
```

### No citations appearing?
The LITFL corpus is still indexing. Once complete, you'll need to:
1. Add `LITFL_CORPUS_ID="7991637538768945152"` to `api/.env`
2. Restart the API
3. Update the test queries to include `"litfl"` in sources

## Next Steps After Testing

1. Document findings in comparison doc
2. Prioritize RAG improvements based on Gemini comparison
3. Implement format/structure enhancements
4. Re-test to validate improvements
5. Consider A/B testing with actual ED physicians
