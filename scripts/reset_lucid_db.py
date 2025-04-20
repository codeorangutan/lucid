"""
reset_lucid_db.py

Drops and recreates the LUCID database with the latest schema.
Use this before running nose-to-tail tests or after schema changes.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from sqlalchemy import create_engine
from db import Base

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'lucid_data.db')

if os.path.exists(DB_PATH):
    print(f"Removing existing database at {DB_PATH}")
    os.remove(DB_PATH)
else:
    print(f"No existing database found at {DB_PATH}")

engine = create_engine(f'sqlite:///{DB_PATH}')
Base.metadata.create_all(engine)
print("Database reset and ready with latest schema.")
