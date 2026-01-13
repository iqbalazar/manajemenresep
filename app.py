import streamlit as st
import pandas as pd
import hashlib
import psycopg2
from io import BytesIO

# --- 1. Database Connection & Security ---

def init_connection():
    # Mengambil rahasia koneksi dari st.secrets
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
        
        # Tabel Resep (PostgreSQL syntax: SERIAL untuk auto increment)
        c.execute('''CREATE TABLE IF NOT EXISTS recipes 
                     (id SERIAL PRIMARY KEY, 
                      name TEXT, 
                      source_link TEXT)''')
        
        # Tabel Bahan
        c.execute('''CREATE TABLE IF NOT EXISTS ingredients 
                     (id SERIAL PRIMARY KEY, 
                      recipe_id INTEGER REFERENCES recipes(id), 
                      ingredient_name TEXT, 
                      quantity REAL, 
                      unit TEXT)''')
        
        # Tabel User
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (username TEXT PRIMARY KEY, 
                      password TEXT, 
                      role TEXT)''')
        
        conn.commit()
        
        # Seed Data Awal (Cek apakah user admin sudah ada)
        c.execute("SELECT count(*) FROM users")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", 
                      ('admin', make_hashes('admin123'), 'admin'))
            c.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", 
                      ('user', make_hashes('user123'), 'user'))
            
            # Data Dummy
            c.execute("INSERT INTO recipes (name, source_link) VALUES (%s, %s) RETURNING id", 
                      ('Nasi Goreng Spesial', 'https://www.youtube.com/watch?v=kY4tWz5vWwc'))
            ns_id = c.fetchone()[0]
            
            # Insert bahan (Executemany di postgres agak beda, kita loop manual biar aman bagi pemula)
            ingredients_data = [
                (ns_id, 'Nasi Putih', 200, 'gram'),
                (ns_id, 'Telur', 1, 'butir'),
                (ns_id, 'Kecap Manis', 10, 'ml'),
                (ns_id, 'Bawang Merah', 3, 'siung')
            ]
            for ing in ingredients_data:
                c.execute("INSERT INTO ingredients (recipe_id, ingredient_name, quantity, unit) VALUES (%s, %s, %s, %s)", ing)
                
            conn.commit()
            
        c.close()
        conn.close()
    except Exception as e:
        st.error(f"Gagal inisialisasi Database: {e}")

# --- 2. CRUD Functions (Updated for PostgreSQL) ---

def run_query(query, params=None, fetch_data=False):
    """Fungsi helper agar tidak berulang nulis connect/close"""
    conn = init_connection()
    c = conn.cursor()
    data = None
    try:
        if params:
            c.execute(query, params)
        else:
            c.execute(query)
        
        if fetch_data:
            # Ambil nama kolom
            colnames = [desc[0] for desc in c.description]
            rows = c.fetchall()
            data = pd.DataFrame(rows, columns=colnames)
        else:
            conn.commit()
    except Exception as e:
        st.error(f"Error Query: {e}")
    finally:
        c.close()
        conn.close()
    return data

def create_user(username, password, role):
    try:
        run_query("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", 
                  (username, make_hashes(password), role))
        return True
    except:
        return False

def update_user(username, new_password, new_role):
    if new_password:
        run_query("UPDATE users SET password=%s, role=%s WHERE username=%s", 
                  (make_hashes(new_password), new_role, username))
    else:
        run_query("UPDATE users SET role=%s WHERE username=%s", 
                  (new_role, username))

def delete_user_data(username):
    run_query("DELETE FROM users WHERE username=%s", (username,))

def get_all_users():
    return run_query("SELECT username, role FROM users", fetch_data=True)

def login_user(username, password):
    conn = init_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username = %s', (username,))
    data = c.fetchone()
    conn.close()
    if data:
        if check_hashes(password, data[1]):
            return data
    return None

def add_recipe_to_db(name, link):
    run_query("INSERT INTO recipes (name, source_link) VALUES (%s, %s)", (name, link))

def update_recipe_data(id, new_name, new_link):
    run_query("UPDATE recipes SET name=%s, source_link=%s WHERE id=%s", (new_name, new_link, id))

def delete_recipe_from_db(recipe_id):
    run_query("DELETE FROM ingredients WHERE recipe_id=%s", (recipe_id,))
    run_query("DELETE FROM recipes WHERE id=%s", (recipe_id,))

def get_all_recipes():
    return run_query("SELECT * FROM recipes ORDER BY id", fetch_data=True)

def add_ingredient_to_db(recipe_id, name, qty, unit):
    run_query("INSERT INTO ingredients (recipe_id, ingredient_name, quantity, unit) VALUES (%s, %s, %s, %s)", 
              (recipe_id, name, qty, unit))

def update_ingredient_data(ing_id, name, qty, unit):
    run_query("UPDATE ingredients SET ingredient_name=%s, quantity=%s, unit=%s WHERE id=%s", 
              (name, qty, unit, ing_id))

def delete_ingredient_data(ing_id):
    run_query("DELETE FROM ingredients WHERE id=%s", (ing_id,))

def get_ingredients_by_recipe(recipe_id):
    # Konversi ID ke int standar python agar tidak error di adapter postgres
    return run_query("SELECT id, ingredient_name, quantity, unit FROM ingredients WHERE recipe_id = %s ORDER BY id", 
                     (int(recipe_id),), fetch_data=True)

def get_all_unique_ingredients():
    df = run_query("SELECT DISTINCT ingredient_name FROM ingredients ORDER BY ingredient_name", fetch_data=True)
    if df is not None and not df.empty:
        return df['ingredient_name'].tolist()
    return []

def find_matching_recipes(user_ingredients):
    recipes_df = get_all_recipes()
    all_ing_df = run_query("SELECT recipe_id, ingredient_name FROM ingredients", fetch_data=True)
    
    results = []
    user_ing_set = set([x.lower() for x in user_ingredients])
    
    if recipes_df is not None:
        for index, recipe in recipes_df.iterrows():
            recipe_ings = all_ing_df[all_ing_df['recipe_id'] == recipe['id']]['ingredient_name'].tolist()
            recipe_ing_set = set([x.lower() for x in recipe_ings])
            
            if not recipe_ing_set: continue
            
            common = user_ing_set.intersection(recipe_ing_set)
            missing = recipe_ing_set - user_ing_set
            match_percentage = len(common) / len(recipe_ing_set) * 100
            
            if match_percentage > 0:
                results.append({
                    'id': recipe['id'],
                    'name': recipe['name'],
                    'source_link': recipe['source_link'],
                    'match_score': match_percentage,
                    'missing_count': len(missing),
                    'missing_ingredients': list(missing)
                })
        results.sort(key=lambda x: x['match_score'], reverse=True)
    return results

# --- 3. Logic Utils & Excel (Sama seperti sebelumnya) ---

def normalize_units(df):
    conversion_rules = {
        'kg': ('gram', 1000), 'kilo': ('gram', 1000), 'kilogram': ('gram', 1000),
        'gr': ('gram', 1), 'gram': ('gram', 1), 'ons': ('gram', 100),
        'l': ('ml', 1000), 'liter': ('ml', 1000), 'ml': ('ml', 1),
        'milliliter': ('ml', 1), 'cc': ('ml', 1),
        'sdm': ('sdm', 1), 'sdt': ('sdt', 1),
        'butir': ('butir', 1), 'pcs': ('pcs', 1), 'buah': ('buah', 1)
    }
    def convert_row(row):
        u = str(row['unit']).lower().strip()
        q = row['total_quantity']
        if u in conversion_rules:
            new_unit, factor = conversion_rules[u]
            return pd.Series([q * factor, new_unit])
        return pd.Series([q, row['unit']])
    
    if not df.empty:
        df[['total_quantity', 'unit']] = df.apply(convert_row, axis=1)
    return df

def format_indo(number):
    s = f"{number:,.2f}"
    s = s.translate(str.maketrans({',': '.', '.': ','}))
    if ',' in s: s = s.rstrip('0').rstrip(',')
    return s

def format_output(val, unit):
    final_val = val
    final_unit = unit
    if unit == 'gram' and val >= 1000:
        final_val = val / 1000; final_unit = 'kg'
    elif unit == 'ml' and val >= 1000:
        final_val = val / 1000; final_unit = 'liter'
    return f"{format_indo(final_val)} {final_unit}"

def generate_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df_to_save = df[['ingredient_name', 'Estimasi Belanja']]
    df_to_save.columns = ['Nama Bahan', 'Harus Dibeli'] 
    df_to_save.to_excel(writer, index=False, sheet_name='Daftar Belanja')
    workbook = writer.book
    worksheet = writer.sheets['Daftar Belanja']
    header_format = workbook.add_format({'bold': True, 'text_wrap': True, 'valign': 'top', 'fg_color': '#4CAF50', 'font_color': 'white', 'border': 1})
    body_format = workbook.add_format({'border': 1, 'valign': 'vcenter'})
    for col_num, value in enumerate(df_to_save.columns.values):
        worksheet.write(0, col_num, value, header_format)
    worksheet.set_column('A:A', 30, body_format)
    worksheet.set_column('B:B', 20, body_format)
    writer.close()
    return output.getvalue()

# --- 4. UI Pages ---

def login_page():
    st.title("🔐 Login Sistem")
    col1, col2 = st.columns([1,2])
    with col1:
        username = st.text_input("Username")
        password = st.text_input("Password", type='password')
        if st.button("Login"):
            result = login_user(username, password)
            if result:
                st.session_state['logged_in'] = True
                st.session_state['username'] = result[0]
                st.session_state['role'] = result[2]
                st.rerun()
            else: st.error("Gagal Login")

def calculator_page():
    st.title("🍳 Aplikasi Masak Cerdas")
    tab_belanja, tab_resep_stok = st.tabs(["🛒 Kalkulator Belanja & Stok", "🔍 Cari Resep dari Stok"])
    
    with tab_belanja:
        if 'menu_list' not in st.session_state: st.session_state.menu_list = []
        recipes_df = get_all_recipes()
        if recipes_df is None or recipes_df.empty: st.warning("Belum ada resep."); return

        r_dict = dict(zip(recipes_df['id'], recipes_df['name']))
        link_dict = dict(zip(recipes_df['id'], recipes_df['source_link']))
        
        col1, col2 = st.columns([1.2, 2])
        with col1:
            st.info("Langkah 1: Pilih Menu")
            with st.form("calc"):
                s_id = st.selectbox("Resep", list(r_dict.keys()), format_func=lambda x: r_dict[x])
                portions = st.number_input("Porsi", min_value=1, value=1)
                if st.form_submit_button("Tambah Ke Daftar"):
                    st.session_state.menu_list.append({'id': s_id, 'name': r_dict[s_id], 'portions': portions, 'link': link_dict.get(s_id)})
                    st.success("Ditambahkan")
            
            if st.session_state.menu_list:
                if st.button("Reset Daftar"): st.session_state.menu_list = []; st.rerun()
                st.divider()
                st.write("📖 **Panduan Masak:**")
                for item in st.session_state.menu_list:
                    with st.expander(f"{item['name']}"):
                        link = item['link']
                        if link and len(link) > 5:
                            if "youtube.com" in link or "youtu.be" in link: st.video(link)
                            else: st.link_button("Buka Link", link)
                        else: st.write("Tanpa Link")

        with col2:
            st.info("Langkah 2: Cek Stok")
            if st.session_state.menu_list:
                all_ing = []
                for item in st.session_state.menu_list:
                    df = get_ingredients_by_recipe(item['id'])
                    df['total_quantity'] = df['quantity'] * item['portions']
                    all_ing.append(df)
                
                if all_ing:
                    full_df = pd.concat(all_ing)
                    full_df = normalize_units(full_df)
                    final = full_df.groupby(['ingredient_name', 'unit'])['total_quantity'].sum().reset_index()
                    
                    if 'stok_input' not in st.session_state: final['Stok di Rumah'] = 0.0
                    else: final['Stok di Rumah'] = 0.0

                    st.write("👇 **Edit 'Stok di Rumah':**")
                    edited_df = st.data_editor(
                        final,
                        column_config={
                            "ingredient_name": "Nama Bahan",
                            "total_quantity": st.column_config.NumberColumn("Total Butuh", disabled=True, format="%.2f"),
                            "unit": st.column_config.TextColumn("Satuan", disabled=True),
                            "Stok di Rumah": st.column_config.NumberColumn("Stok di Rumah", min_value=0, step=1)
                        },
                        disabled=["ingredient_name", "total_quantity", "unit"],
                        hide_index=True,
                        key="editor_stok"
                    )
                    
                    edited_df['Harus Beli'] = edited_df['total_quantity'] - edited_df['Stok di Rumah']
                    edited_df['Harus Beli'] = edited_df['Harus Beli'].apply(lambda x: x if x > 0 else 0)
                    edited_df['Estimasi Belanja'] = edited_df.apply(lambda x: format_output(x['Harus Beli'], x['unit']), axis=1)
                    
                    st.divider()
                    st.subheader("📋 Final Daftar Belanja")
                    st.dataframe(edited_df[['ingredient_name', 'Estimasi Belanja']], use_container_width=True)
                    excel_data = generate_excel(edited_df)
                    st.download_button(label="📥 Download Excel", data=excel_data, file_name='Daftar_Belanja_Final.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    with tab_resep_stok:
        st.subheader("🔍 Punya bahan apa di kulkas?")
        all_ingredients_list = get_all_unique_ingredients()
        if all_ingredients_list:
            selected_ingredients = st.multiselect("Pilih Bahan Tersedia:", all_ingredients_list)
            if st.button("Cari Resep Cocok"):
                if selected_ingredients:
                    matches = find_matching_recipes(selected_ingredients)
                    if matches:
                        st.write(f"Ditemukan **{len(matches)}** resep relevan:")
                        for m in matches:
                            score = m['match_score']
                            color = "green" if score == 100 else "orange" if score >= 50 else "red"
                            with st.expander(f"🥘 {m['name']} (Kecocokan: :{color}[{score:.0f}%])"):
                                if m['missing_count'] > 0: st.warning(f"⚠️ Kurang: {', '.join(m['missing_ingredients'])}")
                                else: st.success("✅ Bahan Lengkap!")
                                st.divider()
                                st.write("📝 **Rincian Bahan:**")
                                ing_detail = get_ingredients_by_recipe(m['id'])
                                ing_detail['Jumlah'] = ing_detail.apply(lambda x: format_indo(x['quantity']), axis=1)
                                st.table(ing_detail[['ingredient_name', 'Jumlah', 'unit']])
                                if m['source_link'] and len(m['source_link']) > 5:
                                    st.write("---")
                                    st.link_button(f"📺 Tonton / Lihat Sumber {m['name']}", m['source_link'])
                    else: st.warning("Tidak ditemukan.")
                else: st.error("Pilih minimal satu.")
        else: st.warning("Database kosong.")

def manage_recipes_page():
    st.title("🍽️ Kelola Resep")
    tab1, tab2, tab3 = st.tabs(["Tambah Baru", "Edit Resep & Bahan", "Hapus Resep"])
    
    with tab1:
        st.subheader("Buat Resep Baru")
        n = st.text_input("Nama Resep")
        l = st.text_input("Link Sumber")
        if st.button("Simpan Resep"):
            if n:
                add_recipe_to_db(n, l)
                st.success(f"Resep '{n}' dibuat!")
            else: st.error("Nama wajib diisi")

    with tab2:
        recipes_df = get_all_recipes()
        if recipes_df is not None and not recipes_df.empty:
            r_dict = dict(zip(recipes_df['id'], recipes_df['name']))
            col_sel, col_act = st.columns([2,1])
            with col_sel:
                sid = st.selectbox("Pilih Resep untuk Diedit", list(r_dict.keys()), format_func=lambda x: r_dict[x])
            
            curr_data = recipes_df[recipes_df['id'] == sid].iloc[0]
            with st.expander("✏️ Edit Nama & Link Resep", expanded=False):
                with st.form("edit_recipe_info"):
                    new_n = st.text_input("Nama Resep", value=curr_data['name'])
                    new_l = st.text_input("Link Sumber", value=curr_data['source_link'] if curr_data['source_link'] else "")
                    if st.form_submit_button("Update Info"):
                        update_recipe_data(sid, new_n, new_l)
                        st.success("Updated!"); st.rerun()

            st.divider()
            st.subheader("Daftar Bahan")
            curr_ing = get_ingredients_by_recipe(sid)
            if curr_ing is not None and not curr_ing.empty:
                display_ing = curr_ing.copy()
                display_ing['formatted_qty'] = display_ing.apply(lambda x: format_indo(x['quantity']), axis=1)
                st.table(display_ing[['ingredient_name', 'formatted_qty', 'unit']])
                
                with st.expander("✏️ Edit / Hapus Bahan Tertentu"):
                    ing_dict = dict(zip(curr_ing['id'], curr_ing['ingredient_name'] + " (" + curr_ing['quantity'].astype(str) + " " + curr_ing['unit'] + ")"))
                    selected_ing_id = st.selectbox("Pilih Bahan", options=list(ing_dict.keys()), format_func=lambda x: ing_dict[x])
                    selected_data = curr_ing[curr_ing['id'] == selected_ing_id].iloc[0]
                    c1, c2, c3 = st.columns(3)
                    with c1: e_name = st.text_input("Nama", value=selected_data['ingredient_name'])
                    with c2: e_qty = st.number_input("Jumlah", min_value=0.01, value=float(selected_data['quantity']), step=0.1)
                    with c3: e_unit = st.text_input("Satuan", value=selected_data['unit'])
                    
                    col_update, col_delete = st.columns(2)
                    with col_update:
                        if st.button("Update Bahan"):
                            update_ingredient_data(selected_ing_id, e_name, e_qty, e_unit)
                            st.success("Updated!"); st.rerun()
                    with col_delete:
                        if st.button("Hapus Bahan Ini", type="primary"):
                            delete_ingredient_data(selected_ing_id)
                            st.warning("Deleted."); st.rerun()
            else: st.info("Belum ada bahan.")

            st.divider()
            st.write("**Tambah Bahan Baru ke Resep Ini:**")
            with st.form("add_ing_form"):
                c1, c2, c3 = st.columns(3)
                n_new = c1.text_input("Nama Bahan")
                q_new = c2.number_input("Jumlah", min_value=0.1, step=0.1)
                u_new = c3.text_input("Satuan")
                if st.form_submit_button("Tambah Bahan"):
                    add_ingredient_to_db(sid, n_new, q_new, u_new)
                    st.rerun()

    with tab3:
        recipes_df = get_all_recipes()
        if recipes_df is not None and not recipes_df.empty:
            d = dict(zip(recipes_df['id'], recipes_df['name']))
            did = st.selectbox("Hapus Resep", list(d.keys()), format_func=lambda x: d[x], key='del_res')
            if st.button("Hapus Permanen", type='primary'):
                delete_recipe_from_db(did)
                st.rerun()

def manage_users_page():
    st.title("👥 Kelola User")
    with st.expander("Buat User Baru", expanded=True):
        c1, c2, c3 = st.columns([2,2,1])
        u = c1.text_input("User Baru")
        p = c2.text_input("Pass Baru", type='password')
        r = c3.selectbox("Role", ["user", "admin"])
        if st.button("Buat User"):
            if create_user(u,p,r): st.success("Sukses"); st.rerun()
            else: st.error("Gagal/User ada")
    st.divider()
    st.subheader("Daftar & Edit User")
    udf = get_all_users()
    col_list, col_edit = st.columns([1, 1])
    with col_list: 
        if udf is not None: st.dataframe(udf, use_container_width=True)
    with col_edit:
        st.write("🔧 **Edit User / Reset Password**")
        if udf is not None and not udf.empty:
            target_user = st.selectbox("Pilih User", udf['username'])
            with st.form("edit_user"):
                new_pass = st.text_input("Password Baru (Biarkan kosong jika tetap)", type='password')
                current_role = udf[udf['username'] == target_user]['role'].values[0]
                new_role = st.selectbox("Role", ["user", "admin"], index=0 if current_role == 'user' else 1)
                if st.form_submit_button("Update User"):
                    update_user(target_user, new_pass, new_role)
                    st.success("Updated."); st.rerun()
            st.write("🗑️ **Hapus User**")
            if st.button("Hapus User Terpilih", type="primary"):
                if target_user != st.session_state['username']:
                    delete_user_data(target_user)
                    st.rerun()
                else: st.error("Tidak bisa hapus akun sendiri.")

def main():
    st.set_page_config("Resep App", layout="wide")
    init_db() # Ini akan otomatis membuat tabel di Supabase saat pertama kali jalan
    
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False; st.session_state['role'] = None
    if not st.session_state['logged_in']: login_page()
    else:
        st.sidebar.title(f"Halo, {st.session_state['username']}")
        if st.sidebar.button("Logout"):
            st.session_state['logged_in'] = False; st.session_state['role'] = None; st.session_state['menu_list'] = []; st.rerun()
        st.sidebar.divider()
        if st.session_state['role'] == 'admin':
            m = st.sidebar.radio("Menu Admin", ["Kalkulator", "Kelola Resep", "Kelola User"])
            if m == "Kalkulator": calculator_page()
            elif m == "Kelola Resep": manage_recipes_page()
            elif m == "Kelola User": manage_users_page()
        else: calculator_page()

if __name__ == '__main__':
    main()
