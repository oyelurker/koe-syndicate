import pandas as pd
import json
import os
import argparse

# NOTE: This script is designed to be accelerated by NVIDIA RAPIDS cuDF.
# To run with GPU acceleration: 
# python -m cudf.pandas analytics_acceleration.py

def analyze_sales_data(data_file):
    print(f"[*] Loading sales telemetry data from {data_file}...")
    
    if not os.path.exists(data_file):
        print("[-] No local data found. Run the Lead Finder agent first to generate telemetry.")
        return

    # Load data using standard pandas (will be automatically GPU-accelerated by cuDF if run with -m cudf.pandas)
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)
            
        if not data:
            print("[-] Data file is empty.")
            return
            
        df = pd.DataFrame(data)
        
        print("\n=== KOE SYNDICATE: RAPIDS DATA ANALYTICS ===")
        print(f"Total Leads Processed: {len(df)}")
        
        # Check if we have the expected columns from the lead finder
        if 'city' in df.columns and 'name' in df.columns:
            # Group by city using pandas (Accelerated by NVIDIA cuDF)
            city_counts = df.groupby('city')['name'].count().reset_index()
            city_counts.columns = ['City', 'Lead Count']
            city_counts = city_counts.sort_values(by='Lead Count', ascending=False)
            
            print("\n--- Leads by Region ---")
            print(city_counts.to_string(index=False))
            
        if 'rating' in df.columns:
            # Convert rating to numeric, coercing errors to NaN, then fill with 0
            df['rating'] = pd.to_numeric(df['rating'], errors='coerce').fillna(0)
            avg_rating = df['rating'].mean()
            print(f"\n--- Average Lead Rating: {avg_rating:.2f} ---")
            
        print("\n[*] Analysis complete. (If run with cudf.pandas, operations were executed on NVIDIA GPU)")
        
    except Exception as e:
        print(f"[-] Error analyzing data: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NVIDIA cuDF Accelerated Sales Analytics")
    parser.add_argument('--file', type=str, default='demo_leads.json', help='Path to telemetry JSON file')
    args = parser.parse_args()
    
    analyze_sales_data(args.file)
