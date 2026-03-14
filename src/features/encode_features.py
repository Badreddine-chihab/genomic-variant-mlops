import pandas as pd
import numpy as np
import os
from sklearn.preprocessing import StandardScaler

def encode_genetic_features(input_path, output_path):
    print(f"🧬 Processing dataset safely...")
    
    # Use chunking or downcasting to save RAM
    # We load columns with smaller types (float32 instead of float64)
    df = pd.read_csv(input_path)
    
    # 1. DROP TEXT COLUMNS EARLY to free memory
    # We keep only what we need for the math
    refs = df['REF'].astype(str)
    alts = df['ALT'].astype(str)
    target = df['Target'].astype('int8') # 1 byte instead of 8
    
    # 2. FEATURE ENGINEERING
    df['Delta_Length'] = (alts.str.len() - refs.str.len()).astype('int16')
    df['Impact_Score'] = ((df['Is_Frameshift'] * df['Delta_Length'].abs()) / 
                          (df['ALT_FREQ'] + 1e-6)).astype('float32')
    
    # 3. SELECTIVE SCALING (Memory Efficient)
    to_scale = ['ALT_FREQ', 'Delta_Length', 'Impact_Score']
    scaler = StandardScaler()
    df[to_scale] = scaler.fit_transform(df[to_scale].astype('float32'))
    
    # 4. ONE-HOT ENCODING (Last step to avoid column explosion)
    # Only keep the first base to limit new columns
    df['REF_Base'] = refs.str[0].str.upper()
    df['ALT_Base'] = alts.str[0].str.upper()
    
    # Convert to dummies but cast to int8 immediately
    df = pd.get_dummies(df, columns=['REF_Base', 'ALT_Base'], dtype='int8')

    # 5. FINAL CLEANUP
    # Keep only numeric columns, drop the strings
    df_final = df.select_dtypes(include=[np.number])
    
    # Save using a smaller float format
    df_final.to_csv(output_path, index=False, float_format='%.4f')
    print(f"✅ Success! Matrix saved without crashing VS Code.")

if __name__ == "__main__":
    encode_genetic_features("data/processed/final_training_dataset.csv", 
                            "data/processed/encoded_training_dataset.csv")