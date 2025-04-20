# ai_sqlite_miner/main.py

import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
import os

# Check if Ollama is installed and running locally
try:
    from llama_index.llms.ollama import Ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    print("Ollama integration not available. Using OpenAI instead.")
    print("To use Ollama, install with: pip install llama-index-llms-ollama")

# Import required llama-index components
try:
    from llama_index.core import SQLDatabase, Settings
    from llama_index.core.query_engine import NLSQLTableQueryEngine
    from llama_index.core.llms import OpenAI
except ImportError:
    print("Error: Required llama-index packages not found.")
    print("Please install with: pip install llama-index")
    exit(1)

# === Config ===
DB_PATH = "cognitive_analysis.db"
MODEL_NAME = "mistral"  # or llama3, etc.

# === Step 1: Setup AI query engine ===
def create_query_engine(db_path, model_name):
    """Create a natural language SQL query engine."""
    # Check if database exists
    if not os.path.exists(db_path):
        print(f"Error: Database file '{db_path}' not found.")
        exit(1)
        
    # Connect to the database
    try:
        db = SQLDatabase.from_uri(f"sqlite:///{db_path}")
    except Exception as e:
        print(f"Error connecting to database: {e}")
        exit(1)
    
    # Set up the language model
    if OLLAMA_AVAILABLE:
        try:
            llm = Ollama(model=model_name)
            Settings.llm = llm
            print(f"Using Ollama with model: {model_name}")
        except Exception as e:
            print(f"Error initializing Ollama: {e}")
            print("Falling back to OpenAI...")
            llm = OpenAI(model="gpt-3.5-turbo")
            Settings.llm = llm
    else:
        # Fallback to OpenAI
        try:
            llm = OpenAI(model="gpt-3.5-turbo")
            Settings.llm = llm
            print("Using OpenAI model: gpt-3.5-turbo")
        except Exception as e:
            print(f"Error initializing OpenAI: {e}")
            exit(1)
    
    # Create the query engine
    try:
        engine = NLSQLTableQueryEngine(sql_database=db)
        return engine, llm
    except Exception as e:
        print(f"Error creating query engine: {e}")
        exit(1)

# === Step 2: Run query ===
def run_query(engine, query):
    """Run a natural language query against the database."""
    try:
        response = engine.query(query)
        print("\nAI Response:")
        print(response)
        
        # Try to extract SQL if available
        sql = None
        if hasattr(response, 'metadata') and response.metadata:
            if 'sql_query' in response.metadata:
                sql = response.metadata['sql_query']
            elif 'native_query' in response.metadata:
                sql = response.metadata['native_query']
        
        if sql:
            print("\nSQL Query:")
            print(sql)
            return sql
        return None
    except Exception as e:
        print(f"\nError running query: {e}")
        return None

# === Step 3: Suggest chart SQL ===
def suggest_chart_sql(llm, user_question):
    """Generate SQL for creating a chart based on the user question."""
    try:
        prompt = f"""
        Based on this question: "{user_question}"
        
        Generate a SQL query that would produce data suitable for a chart or visualization.
        The query should return exactly two columns: one for the x-axis (categories) and one for the y-axis (values).
        
        Return ONLY the SQL query, nothing else.
        """
        
        if hasattr(llm, 'complete'):
            response = llm.complete(prompt)
            sql = str(response).strip()
        else:
            # Fallback for different LLM interfaces
            response = llm.predict(prompt)
            sql = str(response).strip()
            
        print("\nSuggested Chart SQL:")
        print(sql)
        return sql
    except Exception as e:
        print(f"\nError suggesting chart SQL: {e}")
        return None

# === Step 4: Optional chart from SQL ===
def plot_from_sql(query, db_path):
    """Create a plot from SQL query results."""
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            print("\n[No data to plot]")
            return

        # Check if we have at least two columns for plotting
        if len(df.columns) < 2:
            print("\n[Need at least two columns to plot]")
            return
            
        # Create the plot
        plt.figure(figsize=(10, 6))
        df.plot(kind="bar", x=df.columns[0], y=df.columns[1], legend=False)
        plt.title("AI-generated chart")
        plt.xlabel(df.columns[0])
        plt.ylabel(df.columns[1])
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()
    except Exception as e:
        print(f"\n[Plot error: {e}]")

if __name__ == "__main__":
    print("=== AI SQLite Miner ===")
    print(f"Database: {DB_PATH}")
    
    try:
        engine, llm = create_query_engine(DB_PATH, MODEL_NAME)
        
        while True:
            q = input("\nAsk a question about your data (or 'exit', 'chart'): ")
            
            if q.lower() in ("exit", "quit"):
                break
                
            if q.lower() == "chart":
                chart_q = input("What would you like to visualize? ")
                sql = suggest_chart_sql(llm, chart_q)
                if sql:
                    plot_from_sql(sql, DB_PATH)
            else:
                sql = run_query(engine, q)
                if sql and input("\nGenerate chart from this data? (y/n): ").lower() == 'y':
                    plot_from_sql(sql, DB_PATH)
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
