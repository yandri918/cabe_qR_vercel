"""
FastAPI Backend for QR Product Data Sync
Serves product data from SQLite database to Vercel website
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
import json
from datetime import datetime

app = FastAPI(
    title="QR Product API",
    description="API for QR product traceability data",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database path
DB_PATH = "../budidaya_cabe_streamlit/data/budidaya_cabe.db"

# Pydantic Models
class TimelineEvent(BaseModel):
    date: str
    event: str
    desc: str
    icon: str

class ProductResponse(BaseModel):
    productId: str
    harvestDate: str
    farmLocation: str
    farmerName: str
    grade: str
    weight: str
    batchNumber: str
    certifications: List[str]
    timeline: List[TimelineEvent]

# Helper Functions
def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_product_timeline(product_id: str, farmer_name: str):
    """Get product timeline from growth and journal data"""
    conn = get_db_connection()
    timeline = []
    
    # Get growth records
    growth_records = conn.execute(
        "SELECT * FROM growth_records WHERE farmer_name = ? ORDER BY hst",
        (farmer_name,)
    ).fetchall()
    
    for record in growth_records:
        timeline.append({
            'date': record['created_at'][:10] if record['created_at'] else '',
            'event': f"Monitoring HST {record['hst']}",
            'desc': f"Tinggi: {record['height_cm']}cm, Daun: {record['leaf_count']} helai",
            'icon': '📏'
        })
    
    # Get journal entries
    journal_entries = conn.execute(
        "SELECT * FROM journal_entries WHERE farmer_name = ? ORDER BY date",
        (farmer_name,)
    ).fetchall()
    
    for entry in journal_entries:
        timeline.append({
            'date': entry['date'],
            'event': entry['activity_type'],
            'desc': entry['description'],
            'icon': '📝'
        })
    
    conn.close()
    
    # Sort by date
    timeline.sort(key=lambda x: x['date'])
    
    return timeline

# API Endpoints
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "QR Product API is running",
        "version": "1.0.0"
    }

@app.get("/api/product/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str):
    """Get product by ID"""
    conn = get_db_connection()
    
    # Get product from qr_products table
    product = conn.execute(
        "SELECT * FROM qr_products WHERE product_id = ?",
        (product_id,)
    ).fetchone()
    
    conn.close()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Parse certifications
    certifications = json.loads(product['certifications']) if product['certifications'] else []
    
    # Get timeline
    timeline = get_product_timeline(product_id, product['farmer_name'])
    
    # Format response
    response = {
        'productId': product['product_id'],
        'harvestDate': product['harvest_date'],
        'farmLocation': product['farm_location'] or 'Garut, Jawa Barat',
        'farmerName': product['farmer_name'] or 'Petani Demo',
        'grade': product['grade'] or 'Grade A',
        'weight': f"{product['weight_kg']} kg" if product['weight_kg'] else '10 kg',
        'batchNumber': product['batch_number'] or 'B001',
        'certifications': certifications,
        'timeline': timeline
    }
    
    return response

@app.get("/api/products")
async def get_all_products():
    """Get all products"""
    conn = get_db_connection()
    
    products = conn.execute(
        "SELECT * FROM qr_products ORDER BY created_at DESC"
    ).fetchall()
    
    conn.close()
    
    result = []
    for product in products:
        certifications = json.loads(product['certifications']) if product['certifications'] else []
        result.append({
            'productId': product['product_id'],
            'harvestDate': product['harvest_date'],
            'farmLocation': product['farm_location'],
            'farmerName': product['farmer_name'],
            'grade': product['grade'],
            'weight': f"{product['weight_kg']} kg",
            'batchNumber': product['batch_number'],
            'certifications': certifications
        })
    
    return result

@app.post("/api/product")
async def create_product(product_data: dict):
    """Create new product (called from Streamlit)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Convert certifications to JSON
    certs_json = json.dumps(product_data.get('certifications', []))
    
    cursor.execute('''
        INSERT OR REPLACE INTO qr_products (
            product_id, harvest_id, batch_number, harvest_date,
            farm_location, farmer_name, grade, weight_kg, certifications
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        product_data['product_id'],
        product_data.get('harvest_id', ''),
        product_data.get('batch_number', ''),
        product_data['harvest_date'],
        product_data.get('farm_location', ''),
        product_data.get('farmer_name', ''),
        product_data.get('grade', ''),
        product_data.get('weight_kg', 0),
        certs_json
    ))
    
    conn.commit()
    conn.close()
    
    return {"status": "success", "product_id": product_data['product_id']}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
