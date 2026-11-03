import os
import json

def run_collection():
    print("=== FoodOK Global Data Collection Started ===")
    
    data = {
        "status": "success",
        "message": "Global data updated automatically."
    }
    
    os.makedirs("data", exist_ok=True)
    with open("data/latest.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print("=== FoodOK Global Data Collection Finished ===")

if __name__ == "__main__":
    run_collection()
