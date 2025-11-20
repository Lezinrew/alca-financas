#!/usr/bin/env python3
import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '../backend/.env'))
load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))

def make_admin(email):
    mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/alca_financas')
    mongo_db = os.getenv('MONGO_DB', 'alca_financas')
    
    print(f"Connecting to MongoDB: {mongo_uri}")
    client = MongoClient(mongo_uri)
    db = client[mongo_db]
    users = db.users
    
    user = users.find_one({'email': email})
    
    if not user:
        print(f"❌ User not found: {email}")
        return False
        
    if user.get('is_admin'):
        print(f"ℹ️  User {email} is already an admin.")
        return True
        
    result = users.update_one({'email': email}, {'$set': {'is_admin': True}})
    
    if result.modified_count > 0:
        print(f"✅ User {email} promoted to admin successfully!")
        return True
    else:
        print(f"❌ Failed to update user {email}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python make_admin.py <email>")
        sys.exit(1)
        
    email = sys.argv[1]
    make_admin(email)
