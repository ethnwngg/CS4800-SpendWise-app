from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import date, datetime
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pymongo import MongoClient
from bson import ObjectId
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
    first: str
    last: str
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class ChangePassword(BaseModel):
    username: str
    old_password: str
    new_password: str


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
# Helpers
# -----------------------------
def serialize_transaction(doc):
    """Convert MongoDB document to JSON‑friendly dict with string _id."""
    return {
        "_id": str(doc["_id"]),
        "username": doc["username"],
        "amount": doc["amount"],
        "type": doc["type"],
        "category": doc.get("category", ""),
        "description": doc.get("description", ""),
        "date": doc["date"],
    }

# -----------------------------
# Register User
# -----------------------------
@app.post("/register")
def register(user: UserRegister):
    if users.find_one({"username": user.username}):
        raise HTTPException(status_code=400, detail="Username already exists")

    hashed_pw = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt())

    users.insert_one({
        "first": user.first,
        "last": user.last,
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

    return {
        "success": True,
        "first": db_user.get("first", ""),
        "last": db_user.get("last", "")
    }


# -----------------------------
# Change Password
# -----------------------------
@app.post("/change-password")
def change_password(data: ChangePassword):
    user = users.find_one({"username": data.username})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not bcrypt.checkpw(data.old_password.encode(), user["password"]):
        raise HTTPException(status_code=401, detail="Old password is incorrect")

    hashed_pw = bcrypt.hashpw(data.new_password.encode(), bcrypt.gensalt())

    users.update_one(
        {"username": data.username},
        {"$set": {"password": hashed_pw}}
    )

    return {"success": True, "message": "Password updated successfully"}


# -----------------------------
# Delete Account
# -----------------------------
@app.delete("/delete-account/{username}")
def delete_account(username: str):
    user = users.find_one({"username": username})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Delete user
    users.delete_one({"username": username})

    # Delete all their transactions
    transactions.delete_many({"username": username})

    return {"success": True, "message": "Account deleted successfully"}



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

    result = transactions.insert_one(transaction_data)
    return {"message": "Transaction added", "id": str(result.inserted_id)}

# -----------------------------
# Get All Transactions (for user)
# -----------------------------
@app.get("/transactions/{username}")
def get_transactions(username: str):
    docs = transactions.find({"username": username})
    return [serialize_transaction(d) for d in docs]

# -----------------------------
# Delete Single Transaction
# -----------------------------
@app.delete("/transactions/{username}/{transaction_id}")
def delete_single_transaction(username: str, transaction_id: str):
    # Ensure user exists (optional but nice)
    if not users.find_one({"username": username}):
        raise HTTPException(status_code=404, detail="User not found")

    try:
        oid = ObjectId(transaction_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid transaction id")

    result = transactions.delete_one({"_id": oid, "username": username})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return {"deleted": True}

# -----------------------------
# Delete All Transactions (for user)
# -----------------------------
@app.delete("/transactions/{username}")
def delete_all_transactions(username: str):
    result = transactions.delete_many({"username": username})
    return {"deleted": result.deleted_count}

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
# Serve index.html
# -----------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    with open("index.html") as f:
        return f.read()
