import pandas as pd
import subprocess
import asyncio 
import re 
import numpy as np 
from sklearn.neighbors import NearestNeighbors

OLLAMA_PATH = "/usr/local/bin/ollama"

# -------------------------------
# Load CSV Data Once at Startup
# -------------------------------
def load_farmer_data():
    try:
        return pd.read_csv("data/farmer_advisor_dataset.csv")
    except FileNotFoundError:
        print("Error: data/farmer_advisor_dataset.csv not found.")
        return pd.DataFrame() # Return empty dataframe

def load_market_data():
    try:
        return pd.read_csv("data/market_researcher_dataset.csv")
    except FileNotFoundError:
        print("Error: data/market_researcher_dataset.csv not found.")
        return pd.DataFrame() # Return empty dataframe

FARMER_KB = []
MARKET_KB = []

def build_farmer_kb():
    df = load_farmer_data()
    if df.empty:
        return []
    kb = []
    for _, row in df.iterrows():
        entry_parts = []
        if 'Crop_Type' in row and pd.notna(row['Crop_Type']): entry_parts.append(f"Crop: {row['Crop_Type']}.")
        if 'Soil_pH' in row and pd.notna(row['Soil_pH']): entry_parts.append(f"Soil pH: {row['Soil_pH']},")
        if 'Soil_Moisture' in row and pd.notna(row['Soil_Moisture']): entry_parts.append(f"Moisture: {row['Soil_Moisture']}%,")
        if 'Temperature_C' in row and pd.notna(row['Temperature_C']): entry_parts.append(f"Temperature: {row['Temperature_C']}°C,")
        if 'Rainfall_mm' in row and pd.notna(row['Rainfall_mm']): entry_parts.append(f"Rainfall: {row['Rainfall_mm']} mm,")
        if 'Crop_Yield_ton' in row and pd.notna(row['Crop_Yield_ton']): entry_parts.append(f"Yield: {row['Crop_Yield_ton']} tons.")
        kb.append(" ".join(entry_parts))
    print("Farmer KB built successfully.")
    return kb

def build_market_kb():
    df = load_market_data()
    if df.empty:
        return []
    kb = []
    for _, row in df.iterrows():
        entry_parts = []
        if 'Product' in row and pd.notna(row['Product']): entry_parts.append(f"Crop: {row['Product']}.")
        if 'Market_Price_per_ton' in row and pd.notna(row['Market_Price_per_ton']): entry_parts.append(f"Market Price: {row['Market_Price_per_ton']},")
        if 'Demand_Index' in row and pd.notna(row['Demand_Index']): entry_parts.append(f"Demand Index: {row['Demand_Index']},")
        if 'Supply_Index' in row and pd.notna(row['Supply_Index']): entry_parts.append(f"Supply Index: {row['Supply_Index']},")
        if 'Competitor_Price_per_ton' in row and pd.notna(row['Competitor_Price_per_ton']): entry_parts.append(f"Competitor Price: {row['Competitor_Price_per_ton']},")
        if 'Weather_Impact_Score' in row and pd.notna(row['Weather_Impact_Score']): entry_parts.append(f"Weather Impact Score: {row['Weather_Impact_Score']},")
        if 'Seasonal_Factor' in row and pd.notna(row['Seasonal_Factor']): entry_parts.append(f"Seasonal Factor: {row['Seasonal_Factor']}.")
        kb.append(" ".join(entry_parts))

    print("Market KB built success  fully.")
    return kb

# Build KBs at startup
FARMER_KB = build_farmer_kb()
MARKET_KB = build_market_kb()
print("Knowledge Bases Loaded:")
print(f"Farmer KB: {len(FARMER_KB)} entries")
print(f"Market KB: {len(MARKET_KB)} entries")

# -------------------------------
# Simple Retrieval from the KB by Keyword Matching
# -------------------------------
def retrieve_context(query, kb, top_n=3):
    if not kb: 
        return "No knowledge base available."

    query_words = set(filter(None, re.split(r'\W+', query.lower()))) 
    if not query_words:
        return "No valid query words found." 

    scored = []
    for index, entry in enumerate(kb):
        entry_words = set(filter(None, re.split(r'\W+', entry.lower())))
        score = len(query_words.intersection(entry_words))
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)

    context_entries = [entry for score, entry in scored[:top_n]]

    if not context_entries:
        return "No relevant context found in the knowledge base."

    return "\n---\n".join(context_entries) 

try:
    df = pd.read_csv("data/farmer_advisor_dataset.csv") #
    features = ['Soil_pH', 'Soil_Moisture', 'Temperature_C', 'Rainfall_mm']
    nn = NearestNeighbors(n_neighbors=10, algorithm='ball_tree').fit(df[features]) # Use more neighbors (e.g., 10)
except FileNotFoundError:
    df = None
    nn = None
    print("Error: farmer_advisor_dataset.csv not found.")

def find_crop_suggestion_with_guidance(farmer_input_data):
    if df is None or nn is None:
        return {"error": "Dataset not loaded."}

    # --- Step 1: Find Nearest Neighbors ---
    distances, indices = nn.kneighbors([farmer_input_data])
    neighbor_df = df.iloc[indices[0]] 

    # --- Step 2: Find Most Sustainable Among Neighbors ---
    sorted_neighbors = neighbor_df.sort_values(by=['Sustainability_Score', 'Crop_Yield_ton'], ascending=[False, False])
    best_sustainable_match = sorted_neighbors.iloc[0]

    
    is_good_sustainable_match = False 
                                      

    result = {
         "input": dict(zip(features, farmer_input_data)),
         "found_sustainable": False,
         "sustainable_crop": None,
         "found_alternative": False,
         "alternative_yield_crop": None,
         "condition_changes": None
    }

    if is_good_sustainable_match:
         result["found_sustainable"] = True
         result["sustainable_crop"] = best_sustainable_match.to_dict()
    else:
        highest_yield_match = neighbor_df.loc[neighbor_df['Crop_Yield_ton'].idxmax()]

        if highest_yield_match.equals(best_sustainable_match) and not is_good_sustainable_match:
             pass 

        result["found_alternative"] = True
        result["alternative_yield_crop"] = highest_yield_match.to_dict()

        
        changes = {}
        target_conditions = highest_yield_match[features]
        for i, feature in enumerate(features):
            diff = target_conditions.iloc[i] - farmer_input_data[i]
            changes[feature] = round(diff, 2) # Store the difference

        result["condition_changes"] = changes

    return result


# -------------------------------
# Query Ollama with a Constructed Prompt (Non-Streaming Sync version)
# -------------------------------
def query_ollama(prompt):
    print(f"Querying Ollama with prompt (sync): {prompt[:200]}...") 
    try:
        result = subprocess.run(
            [OLLAMA_PATH, "run", "llama2:7b-chat"],
            input=prompt,
            capture_output=True,
            text=True,
            check=True,
            timeout=60 
        )
        response = result.stdout.strip()
        if not response:
            print("Warning: Ollama returned an empty response.")
            return "Error: Model did not return advice."
        print(f"Ollama response received (sync).")
        return response
    except FileNotFoundError:
        print(f"Error: Ollama executable not found at {OLLAMA_PATH}")
        return "Error: Ollama is not configured correctly."
    except subprocess.CalledProcessError as e:
        print(f"Error: Ollama process failed with exit code {e.returncode}")
        print(f"Stderr: {e.stderr}")
        return f"Error: Ollama failed to process the request. {e.stderr}"
    except subprocess.TimeoutExpired:
        print("Error: Ollama query timed out.")
        return "Error: The request to the model timed out."
    except Exception as e:
        print(f"An unexpected error occurred during Ollama query: {e}")
        return "Error: An unexpected error occurred while getting advice."