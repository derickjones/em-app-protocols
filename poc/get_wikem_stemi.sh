#!/bin/bash
# Download STEMI protocol from WikEM as PDF

echo "📄 To get the STEMI protocol from WikEM:"
echo ""
echo "Option 1 - Chrome Headless (if Chrome installed):"
echo "  /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \\"
echo "    --headless --disable-gpu \\"
echo "    --print-to-pdf=sample_pdfs/WikEM_STEMI_Protocol.pdf \\"
echo "    'https://wikem.org/wiki/ST-segment_elevation_myocardial_infarction'"
echo ""
echo "Option 2 - Manual (recommended):"
echo "  1. Open: https://wikem.org/wiki/ST-segment_elevation_myocardial_infarction"
echo "  2. Press Cmd+P (Print)"
echo "  3. Save as PDF to: sample_pdfs/WikEM_STEMI_Protocol.pdf"
echo ""
echo "Option 3 - Use a public STEMI protocol instead:"
echo "  curl -L -o sample_pdfs/STEMI_Protocol.pdf <URL_TO_PDF>"

# Try Chrome headless if available
if [ -f "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]; then
    echo ""
    echo "⚡ Chrome detected! Attempting automatic download..."
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
        --headless --disable-gpu \
        --print-to-pdf=sample_pdfs/WikEM_STEMI_Protocol.pdf \
        'https://wikem.org/wiki/ST-segment_elevation_myocardial_infarction' \
        2>/dev/null && echo "✅ PDF saved!" || echo "❌ Failed - try manual option"
fi
