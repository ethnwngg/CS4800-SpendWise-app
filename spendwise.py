from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import date, datetime
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pymongo import MongoClient


## MongoDB connection
MONGODB_URI = "mongodb+srv://ethanwong_db_user:crngf1cp7rK0tmak@finance-db.hjw6tbv.mongodb.net/?appName=finance-db"
client = MongoClient(MONGODB_URI)
db = client["spend-wise"]

users = db["users"]
transactions = db["transactions"]


app = FastAPI(title="SpendWise API")


# -----------------------------
# Data Models
# -----------------------------
class User(BaseModel):
    username: str

class Transaction(BaseModel):
    amount: float
    category: str
    description: str
    date: date
    type: str  # "income" or "expense"

# -----------------------------
# User Registration
# -----------------------------
@app.post("/users")

def create_user(user: User):
    if users.find_one({"username": user.username}):
        raise HTTPException(status_code=400, detail="User already exists")
    
    users.insert_one({"username": user.username})
    return {"message": "User created successfully"}


# -----------------------------
# Add Transaction
# -----------------------------
@app.post("/transactions/{username}")
def add_transaction(username: str, t: Transaction):
    if not users.find_one({"username": username}):
        raise HTTPException(status_code=404, detail="User not found")
    
    transaction_data = {
        "username": username,
        "amount": t.amount,
        "type": t.type,
        "category": t.category,
        "description": t.description,
        "date": t.date.isoformat()  # store date as string
    }
    
    transactions.insert_one(transaction_data)

    return {"message": "Transaction added"}

# -----------------------------
# Get All Transactions
# -----------------------------
@app.get("/transactions/{username}")
def get_transactions(username: str):
    
    user_transactions = list(transactions.find({"username": username}, {"_id":0}))

    return user_transactions

# -----------------------------
# Monthly Summary
# -----------------------------
@app.get("/summary/monthly/{username}/{year}/{month}")
def monthly_summary(username: str, year: int, month: int):

    user_transactions = transactions.find({"username": username})

    income = 0
    expenses = 0

    for t in user_transactions:
        t_date = datetime.fromisoformat(t["date"]).date()

        if t_date.year == year and t_date.month == month:
            if t["type"] == "income":
                income += t["amount"]
            else:
                expenses += t["amount"]

    return {
        "income": income,
        "expenses": expenses,
        "net": income - expenses
    }

# -----------------------------
# Yearly Summary
# -----------------------------
@app.get("/summary/yearly/{username}/{year}")
def yearly_summary(username: str, year: int):

    # Check if user exists
    if not users.find_one({"username": username}):
        raise HTTPException(status_code=404, detail="User not found")

    income = 0
    expenses = 0

    user_transactions = transactions.find({"username": username})

    for t in user_transactions:
        t_date = datetime.fromisoformat(t["date"]).date()

        if t_date.year == year:
            if t["type"] == "income":
                income += t["amount"]
            else:
                expenses += t["amount"]

    return {
        "year": year,
        "income": income,
        "expenses": expenses,
        "net": income - expenses
    }

# -----------------------------
# Delete Transaction
# -----------------------------
@app.delete("/transactions/{username}")
def delete_transaction(username: str):

    result = transactions.delete_many({"username": username})

    return {"deleted": result.deleted_count}


# index.html
@app.get("/", response_class=HTMLResponse)
def home():
    with open("index.html") as f:
        return f.read()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)