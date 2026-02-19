#!/usr/bin/env python3
"""Quick test script to inspect REBEL EM post structures."""
import sys
from bs4 import BeautifulSoup, Tag
from pathlib import Path

raw_dir = Path(__file__).parent / "output" / "raw"

def inspect_post(slug):
    html_path = raw_dir / f"{slug}.html"
    if not html_path.exists():
        print(f"No raw HTML for {slug}")
        return
    
    html = html_path.read_text()
    soup = BeautifulSoup(html, "lxml")
    
    ec = soup.find("div", class_="elementor-widget-theme-post-content")
    if not ec:
        print("No Elementor post content widget found")
        # Try article > entry-content
        article = soup.find("article")
        if article:
            ec = article.find("div", class_="entry-content")
            if ec:
                print("Found entry-content in article instead")
            else:
                print("No entry-content either")
                return
        else:
            print("No article tag either")
            return
    
    container = ec.find("div", class_="elementor-widget-container")
    if not container:
        container = ec
        print("Using ec directly (no widget-container found)")
    
    print(f"\n=== Structure of {slug} ===\n")
    
    for child in container.children:
        if isinstance(child, Tag):
            text = child.get_text(strip=True)[:100]
            if child.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                print(f"  HEADING <{child.name}> {text}")
            elif child.name == "p":
                strongs = child.find_all("strong")
                imgs = child.find_all("img")
                if imgs:
                    for img in imgs:
                        src = img.get("src", "")[:80]
                        print(f"  IMAGE in <p>: {src}")
                elif strongs and len(text) < 80 and len(strongs) == 1 and strongs[0].get_text(strip=True) == text:
                    print(f"  BOLD-HEADING <p><strong> {text}")
                else:
                    print(f"  <p> {text[:80]}")
            elif child.name == "ul":
                items = child.find_all("li")
                print(f"  <ul> ({len(items)} items)")
            elif child.name == "ol":
                items = child.find_all("li")
                print(f"  <ol> ({len(items)} items)")
            elif child.name == "figure":
                img = child.find("img")
                if img:
                    src = img.get("src", "")[:80]
                    print(f"  FIGURE/IMAGE: {src}")
                else:
                    print(f"  <figure> {text[:60]}")
            elif child.name == "div":
                classes = " ".join(child.get("class", []))
                inner_imgs = child.find_all("img")
                if inner_imgs:
                    print(f"  <div class='{classes}'> ({len(inner_imgs)} images)")
                else:
                    print(f"  <div class='{classes}'> {text[:60]}")
            elif child.name == "table":
                rows = child.find_all("tr")
                print(f"  TABLE ({len(rows)} rows)")
            else:
                print(f"  <{child.name}> {text[:60]}")

if __name__ == "__main__":
    slugs = sys.argv[1:] if len(sys.argv) > 1 else ["rebel-core-cast-89-0-spontaneous-bacterial-peritonitis"]
    for slug in slugs:
        inspect_post(slug)
        print()
