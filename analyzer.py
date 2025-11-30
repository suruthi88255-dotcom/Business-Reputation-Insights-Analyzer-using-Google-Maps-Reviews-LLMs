import pandas as pd
import os
import time
from langchain_huggingface import ChatHuggingFace
from langchain_huggingface import HuggingFaceEndpoint
from langchain_core.prompts import PromptTemplate

# --- CONFIGURATION ---
INPUT_FILE = "data/reviews_raw.csv"
OUTPUT_FILE = "data/reviews_analyzed.csv"

# ❗ REQUIRED: Hugging Face API Token
HF_API_TOKEN = "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"
REPO_ID = "mistralai/Mistral-7B-Instruct-v0.3"

# Limit number of reviews being analyzed
MAX_REVIEWS = 10   # ← change to None later for full dataset


def analyze_reviews():
    # 1. TOKEN CHECK
    if not HF_API_TOKEN or HF_API_TOKEN.startswith("hf_") is False:
        print("❌ ERROR: Invalid / missing Hugging Face API token.")
        return

    # 2. LOAD CSV
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: {INPUT_FILE} not found. Run the data fetcher first.")
        return
    
    df = pd.read_csv(INPUT_FILE)
    if MAX_REVIEWS:
        df = df.head(MAX_REVIEWS)

    print(f"📂 Loaded {len(df)} reviews (LIMIT = {MAX_REVIEWS}) from {INPUT_FILE}")

    # 3. CONNECT TO HUGGING FACE
    print(f"🧠 Connecting to Hugging Face Cloud ({REPO_ID})...")
    try:
        llm_endpoint = HuggingFaceEndpoint(
            repo_id=REPO_ID,
            huggingfacehub_api_token=HF_API_TOKEN,
            task="conversational"
        )
        llm = ChatHuggingFace(llm=llm_endpoint)
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return

    # 4. PROMPT
    template = """
    You are a business analyst. Analyze this customer review.
    
    Review: "{text}"
    Rating: {rating}/5.0
    
    Output strictly in this format:
    Sentiment: [Positive / Neutral / Negative]
    Summary: [1 sentence summary]
    Recommendation: [1 actionable tip]
    """
    prompt = PromptTemplate(template=template, input_variables=["text", "rating"])
    chain = prompt | llm

    # 5. LOOP THROUGH REVIEWS
    print(f"\n🚀 Starting analysis on {len(df)} reviews...\n")
    analyzed_rows = []

    for index, row in df.iterrows():
        text = str(row.get("text", ""))
        rating = row.get("rating", 0)
        author = row.get("author", "Unknown")

        # Skip blank garbage text
        if len(text) < 5 or "No Text" in text:
            analyzed_rows.append({
                "author": author, "rating": rating, "text": text,
                "sentiment": "Neutral", "summary": "No text provided", "recommendation": "N/A"
            })
            continue

        print(f" ➤ Review #{index + 1}: Analyzing...")

        try:
            response = chain.invoke({"text": text, "rating": rating})
            content = str(response).strip()
            lines = content.split("\n")

            # Helper extractor
            def extract(key):
                for line in lines:
                    if key in line:
                        parts = line.split(":", 1)
                        if len(parts) > 1:
                            return parts[1].strip()
                return "N/A"

            sentiment = extract("Sentiment").title()
            if sentiment not in ["Positive", "Negative", "Neutral"]:
                sentiment = "Neutral"

            analyzed_rows.append({
                "author": author,
                "rating": rating,
                "text": text,
                "sentiment": sentiment,
                "summary": extract("Summary"),
                "recommendation": extract("Recommendation")
            })

            print(f"    ↳ Sentiment = {sentiment}")
            time.sleep(1)  # Avoid rate limits

        except Exception as e:
            print(f"    ⚠️ Error analyzing review: {str(e)}")
            # Use simple sentiment analysis based on rating if API fails
            if rating >= 4:
                sentiment = "Positive"
            elif rating <= 2:
                sentiment = "Negative"
            else:
                sentiment = "Neutral"
            
            analyzed_rows.append({
                "author": author, 
                "rating": rating, 
                "text": text,
                "sentiment": sentiment, 
                "summary": text[:100] if len(text) > 100 else text,
                "recommendation": "Review the feedback for improvements."
            })
            time.sleep(2)
            continue

    # 6. SAVE
    results_df = pd.DataFrame(analyzed_rows)
    results_df.to_csv(OUTPUT_FILE, index=False)

    print("\n" + "=" * 60)
    print(f"✅ FINISHED — Results saved to: {OUTPUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    analyze_reviews()
