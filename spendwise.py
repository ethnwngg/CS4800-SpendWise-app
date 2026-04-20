from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import date, datetime
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pymongo import MongoClient
import bcrypt

# -----------------------------
# MongoDB Connection
# -----------------------------
MONGODB_URI = "mongodb+srv://ethanwong_db_user:2V5CtI30FxL5DF5C@finance-db.hjw6tbv.mongodb.net/finance-db?retryWrites=true&w=majority&tls=true"
client = MongoClient(MONGODB_URI)
db = client["spend-wise"]

users = db["users"]
transactions = db["transactions"]

# -----------------------------
# FastAPI App
# -----------------------------
app = FastAPI(title="SpendWise API")

# -----------------------------
# Data Models
# -----------------------------
class UserRegister(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class Transaction(BaseModel):
    amount: float
    category: str
    description: str
    date: date
    type: str  # "income" or "expense"

# -----------------------------
# CORS
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Register User
# -----------------------------
@app.post("/register")
def register(user: UserRegister):
    if users.find_one({"username": user.username}):
        raise HTTPException(status_code=400, detail="Username already exists")

    hashed_pw = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt())

    users.insert_one({
        "username": user.username,
        "password": hashed_pw
    })

    return {"message": "Account created successfully"}

# -----------------------------
# Login User
# -----------------------------
@app.post("/login")
def login(user: UserLogin):
    db_user = users.find_one({"username": user.username})

    if not db_user:
        return {"success": False}

    if not bcrypt.checkpw(user.password.encode("utf-8"), db_user["password"]):
        return {"success": False}

    return {"success": True}

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
        "date": t.date.isoformat()
    }

    transactions.insert_one(transaction_data)
    return {"message": "Transaction added"}

# -----------------------------
# Get All Transactions
# -----------------------------
@app.get("/transactions/{username}")
def get_transactions(username: str):
    return list(transactions.find({"username": username}, {"_id": 0}))

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
    if not users.find_one({"username": username}):
        raise HTTPException(status_code=404, detail="User not found")

    income = 0
    expenses = 0

    for t in transactions.find({"username": username}):
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
# Delete All Transactions
# -----------------------------
@app.delete("/transactions/{username}")
def delete_transaction(username: str):
    result = transactions.delete_many({"username": username})
    return {"deleted": result.deleted_count}

# -----------------------------
# Serve index.html
# -----------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    with open("index.html") as f:
        return f.read()
