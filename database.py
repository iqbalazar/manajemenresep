# database.py
import streamlit as st
import psycopg2
import hashlib
import pandas as pd

# --- KONEKSI & SECURITY ---

def init_connection():
    return psycopg2.connect(st.secrets["DATABASE_URL"])

def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    if make_hashes(password) == hashed_text:
        return True
    return False

def init_db():
    try:
        conn = init_connection()
        c = conn.cursor()
        
        # Tabel-tabel
        c.execute('''CREATE TABLE IF NOT EXISTS recipes 
                     (id SERIAL PRIMARY KEY, name TEXT, source_link TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS ingredients 
                     (id SERIAL PRIMARY KEY, recipe_id INTEGER REFERENCES recipes(id), 
                      ingredient_name TEXT, quantity REAL, unit TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (username TEXT PRIMARY KEY, password TEXT, role TEXT)''')
        conn.commit()
        
        # Seed Admin
        c.execute("SELECT count(*) FROM users")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO users VALUES (%s, %s, %s)", ('admin', make_hashes('admin123'), 'admin'))
            c.execute("INSERT INTO users VALUES (%s, %s, %s)", ('user', make_hashes('user123'), 'user'))
            
            # Seed Resep Dummy
            c.execute("INSERT INTO recipes (name, source_link) VALUES (%s, %s) RETURNING id", 
                      ('Nasi Goreng Spesial', 'https://www.youtube.com/watch?v=kY4tWz5vWwc'))
            ns_id = c.fetchone()[0]
            ingredients = [(ns_id, 'Nasi Putih', 200, 'gram'), (ns_id, 'Telur', 1, 'butir'), 
                           (ns_id, 'Kecap Manis', 10, 'ml'), (ns_id, 'Bawang Merah', 3, 'siung')]
            for ing in ingredients:
                c.execute("INSERT INTO ingredients (recipe_id, ingredient_name, quantity, unit) VALUES (%s, %s, %s, %s)", ing)
            conn.commit()
        
        c.close(); conn.close()
    except Exception as e:
        st.error(f"DB Error: {e}")

# --- FUNGSI CRUD (HELPER) ---

def run_query(query, params=None, fetch_data=False):
    conn = init_connection()
    c = conn.cursor()
    data = None
    try:
        if params: c.execute(query, params)
        else: c.execute(query)
        
        if fetch_data:
            colnames = [desc[0] for desc in c.description]
            data = pd.DataFrame(c.fetchall(), columns=colnames)
        else:
            conn.commit()
    except Exception as e:
        st.error(f"Error: {e}")
    finally:
        c.close(); conn.close()
    return data

# --- FUNGSI USER ---
def login_user(username, password):
    conn = init_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username = %s', (username,))
    data = c.fetchone()
    conn.close()
    if data and check_hashes(password, data[1]): return data
    return None

def create_user(u, p, r): return run_query("INSERT INTO users VALUES (%s, %s, %s)", (u, make_hashes(p), r))
def update_user(u, p, r):
    if p: run_query("UPDATE users SET password=%s, role=%s WHERE username=%s", (make_hashes(p), r, u))
    else: run_query("UPDATE users SET role=%s WHERE username=%s", (r, u))
def delete_user_data(u): run_query("DELETE FROM users WHERE username=%s", (u,))
def get_all_users(): return run_query("SELECT username, role FROM users", fetch_data=True)

# --- FUNGSI RESEP ---
def get_all_recipes(): return run_query("SELECT * FROM recipes ORDER BY id", fetch_data=True)
def add_recipe_to_db(n, l): run_query("INSERT INTO recipes (name, source_link) VALUES (%s, %s)", (n, l))
def update_recipe_data(id, n, l): run_query("UPDATE recipes SET name=%s, source_link=%s WHERE id=%s", (n, l, id))
def delete_recipe_from_db(id):
    run_query("DELETE FROM ingredients WHERE recipe_id=%s", (id,))
    run_query("DELETE FROM recipes WHERE id=%s", (id,))

# --- FUNGSI BAHAN ---
def get_ingredients_by_recipe(id): return run_query("SELECT id, ingredient_name, quantity, unit FROM ingredients WHERE recipe_id=%s ORDER BY id", (int(id),), fetch_data=True)
def add_ingredient_to_db(id, n, q, u): run_query("INSERT INTO ingredients (recipe_id, ingredient_name, quantity, unit) VALUES (%s, %s, %s, %s)", (id, n, q, u))
def update_ingredient_data(id, n, q, u): run_query("UPDATE ingredients SET ingredient_name=%s, quantity=%s, unit=%s WHERE id=%s", (n, q, u, id))
def delete_ingredient_data(id): run_query("DELETE FROM ingredients WHERE id=%s", (id,))

# --- FUNGSI SEARCH ---
def get_all_unique_ingredients():
    df = run_query("SELECT DISTINCT ingredient_name FROM ingredients ORDER BY ingredient_name", fetch_data=True)
    return df['ingredient_name'].tolist() if df is not None else []

def find_matching_recipes(user_ingredients):
    recipes = get_all_recipes()
    all_ings = run_query("SELECT recipe_id, ingredient_name FROM ingredients", fetch_data=True)
    results = []
    user_set = set([x.lower() for x in user_ingredients])
    
    if recipes is not None:
        for _, r in recipes.iterrows():
            r_ings = all_ings[all_ings['recipe_id'] == r['id']]['ingredient_name'].tolist()
            r_set = set([x.lower() for x in r_ings])
            if not r_set: continue
            
            common = user_set.intersection(r_set)
            score = len(common) / len(r_set) * 100
            if score > 0:
                results.append({
                    'id': r['id'], 'name': r['name'], 'source_link': r['source_link'],
                    'match_score': score, 'missing_count': len(r_set - user_set),
                    'missing_ingredients': list(r_set - user_set)
                })
        results.sort(key=lambda x: x['match_score'], reverse=True)
    return results
