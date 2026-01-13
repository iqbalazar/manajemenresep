import streamlit as st
import pandas as pd

# Import modul buatan sendiri
import database as db
import utils

# --- CONFIG & INIT ---
st.set_page_config(page_title="Resep App", layout="wide")

# Init DB saat pertama kali load
if 'db_initialized' not in st.session_state:
    db.init_db()
    st.session_state['db_initialized'] = True

# --- MAIN ROUTER (Navigasi Persisten) ---
def main():
    if not st.session_state['logged_in']:
        page_login()
    else:
        st.sidebar.title(f"Halo, {st.session_state['username']}")
        
        if st.sidebar.button("Logout"):
            st.session_state['logged_in'] = False
            st.session_state['role'] = None
            st.session_state['menu_list'] = []
            st.query_params.clear()
            st.rerun()
            
        st.sidebar.divider()
        
        if st.session_state['role'] == 'admin':
            options = ["Kalkulator", "Resep", "User"]
            default_index = 0
            if "page" in st.query_params:
                current_page_param = st.query_params["page"]
                if current_page_param in options:
                    default_index = options.index(current_page_param)
            
            selected_menu = st.sidebar.radio("Menu", options, index=default_index)
            
            if st.query_params.get("page") != selected_menu:
                st.query_params["page"] = selected_menu
            
            if selected_menu == "Kalkulator": page_calculator()
            elif selected_menu == "Resep": page_manage_recipes()
            elif selected_menu == "User": page_manage_users()
            
        else:
            if st.query_params.get("page") != "Kalkulator":
                st.query_params["page"] = "Kalkulator"
            page_calculator()

# --- HALAMAN-HALAMAN (VIEWS) ---

def page_login():
    st.title("🔐 Login Sistem")
    c1, c2 = st.columns([1,2])
    with c1:
        u = st.text_input("Username")
        p = st.text_input("Password", type='password')
        if st.button("Login"):
            user = db.login_user(u, p)
            if user:
                st.session_state['logged_in'] = True
                st.session_state['username'] = user[0]
                st.session_state['role'] = user[2]
                st.query_params['user'] = user[0] # Simpan sesi di URL
                st.rerun()
            else:
                st.error("Gagal Login")

def page_calculator():
    st.title("🍳 Aplikasi Masak Cerdas")
    tab1, tab2 = st.tabs(["🛒 Hitung Belanja", "🔍 Cari Resep dari Stok"])
    
    # --- TAB 1: KALKULATOR ---
    with tab1:
        if 'menu_list' not in st.session_state: st.session_state.menu_list = []
        
        recipes = db.get_all_recipes()
        if recipes is None or recipes.empty: st.warning("Belum ada data."); return
        
        r_dict = dict(zip(recipes['id'], recipes['name']))
        l_dict = dict(zip(recipes['id'], recipes['source_link']))
        
        c1, c2 = st.columns([1, 2])
        with c1:
            st.info("Pilih Menu")
            with st.form("add_menu"):
                sid = st.selectbox("Resep", list(r_dict.keys()), format_func=lambda x: r_dict[x])
                portion = st.number_input("Porsi", min_value=1, value=1)
                if st.form_submit_button("Tambah"):
                    st.session_state.menu_list.append({
                        'id': sid, 'name': r_dict[sid], 'portions': portion, 'link': l_dict.get(sid)
                    })
                    st.success("Oke")
            
            if st.session_state.menu_list:
                if st.button("Reset"): st.session_state.menu_list = []; st.rerun()
                st.divider()
                st.write("📖 **Panduan Masak:**")
                for i in st.session_state.menu_list:
                    with st.expander(f"{i['name']} ({i['portions']} Porsi)"):
                        link = i['link']
                        # PERBAIKAN DI SINI (Deteksi YouTube)
                        if link and len(link) > 5:
                            if "youtube.com" in link or "youtu.be" in link:
                                st.video(link) # Tampil Video Player
                            else:
                                st.link_button("Buka Artikel Resep", link) # Tombol biasa
                        else:
                            st.caption("Tidak ada link.")
        
        with c2:
            if st.session_state.menu_list:
                all_dfs = []
                for i in st.session_state.menu_list:
                    d = db.get_ingredients_by_recipe(i['id'])
                    d['total_quantity'] = d['quantity'] * i['portions']
                    all_dfs.append(d)
                
                if all_dfs:
                    full = pd.concat(all_dfs)
                    full = utils.normalize_units(full)
                    final = full.groupby(['ingredient_name', 'unit'])['total_quantity'].sum().reset_index()
                    final['Stok di Rumah'] = 0.0 # Default
                    
                    st.write("👇 **Cek Stok:**")
                    edited = st.data_editor(final, hide_index=True, disabled=['ingredient_name','unit','total_quantity'],
                                            column_config={"Stok di Rumah": st.column_config.NumberColumn(min_value=0)})
                    
                    edited['Harus Beli'] = (edited['total_quantity'] - edited['Stok di Rumah']).apply(lambda x: x if x>0 else 0)
                    edited['Estimasi'] = edited.apply(lambda x: utils.format_output(x['Harus Beli'], x['unit']), axis=1)
                    
                    st.dataframe(edited[['ingredient_name', 'Estimasi']], use_container_width=True)
                    st.download_button("Download Excel", utils.generate_excel(edited), "Belanja.xlsx")

    # --- TAB 2: CARI RESEP ---
    with tab2:
        st.subheader("Cari Resep by Stok")
        all_ings = db.get_all_unique_ingredients()
        sel = st.multiselect("Bahan Tersedia", all_ings)
        if st.button("Cari"):
            if sel:
                matches = db.find_matching_recipes(sel)
                if matches:
                    for m in matches:
                        color = "green" if m['match_score']==100 else "orange"
                        with st.expander(f"{m['name']} (Cocok: :{color}[{m['match_score']:.0f}%])"):
                            if m['missing_count'] > 0: st.warning(f"Kurang: {', '.join(m['missing_ingredients'])}")
                            else: st.success("Bahan Lengkap!")
                            
                            det = db.get_ingredients_by_recipe(m['id'])
                            det['Jml'] = det.apply(lambda x: utils.format_indo(x['quantity']), axis=1)
                            st.table(det[['ingredient_name', 'Jml', 'unit']])
                            
                            # PERBAIKAN DI SINI JUGA
                            link = m['source_link']
                            if link and len(link) > 5:
                                st.write("---")
                                if "youtube.com" in link or "youtu.be" in link:
                                    st.video(link)
                                else:
                                    st.link_button("Lihat Sumber Resep", link)
                else: st.warning("Tidak ada yang cocok.")

def page_manage_recipes():
    st.title("Kelola Resep")
    t1, t2, t3 = st.tabs(["Tambah", "Edit", "Hapus"])
    
    with t1:
        n = st.text_input("Nama"); l = st.text_input("Link")
        if st.button("Simpan"): db.add_recipe_to_db(n, l); st.success("OK")
    
    with t2:
        df = db.get_all_recipes()
        if df is not None and not df.empty:
            rd = dict(zip(df['id'], df['name']))
            sid = st.selectbox("Pilih", list(rd.keys()), format_func=lambda x: rd[x])
            cur = df[df['id']==sid].iloc[0]
            
            with st.expander("Edit Info Resep"):
                nn = st.text_input("Nama", cur['name']); nl = st.text_input("Link", cur['source_link'])
                if st.button("Update Info"): db.update_recipe_data(sid, nn, nl); st.rerun()
            
            st.write("Bahan:"); cur_ing = db.get_ingredients_by_recipe(sid)
            if not cur_ing.empty:
                cur_ing['disp'] = cur_ing.apply(lambda x: utils.format_indo(x['quantity']), axis=1)
                st.table(cur_ing[['ingredient_name','disp','unit']])
                
                with st.expander("Edit Bahan"):
                    id_ing = st.selectbox("Pilih Bahan", cur_ing['id'], format_func=lambda x: cur_ing[cur_ing['id']==x]['ingredient_name'].values[0])
                    row = cur_ing[cur_ing['id']==id_ing].iloc[0]
                    c1,c2,c3 = st.columns(3)
                    en = c1.text_input("Nama", row['ingredient_name'])
                    eq = c2.number_input("Jml", value=float(row['quantity']), step=0.1)
                    eu = c3.text_input("Satuan", row['unit'])
                    if st.button("Update Bahan"): db.update_ingredient_data(id_ing, en, eq, eu); st.rerun()
                    if st.button("Hapus Bahan", type="primary"): db.delete_ingredient_data(id_ing); st.rerun()
            
            with st.form("new_ing"):
                c1,c2,c3 = st.columns(3)
                n = c1.text_input("Nama"); q = c2.number_input("Jml", step=0.1); u = c3.text_input("Satuan")
                if st.form_submit_button("Tambah"): db.add_ingredient_to_db(sid, n, q, u); st.rerun()
    
    with t3:
        df = db.get_all_recipes()
        if df is not None and not df.empty:
            rd = dict(zip(df['id'], df['name']))
            did = st.selectbox("Hapus", list(rd.keys()), format_func=lambda x: rd[x], key='d')
            if st.button("Hapus Permanen", type="primary"): db.delete_recipe_from_db(did); st.rerun()

def page_manage_users():
    st.title("Kelola User")
    with st.expander("Buat User"):
        c1,c2,c3 = st.columns([2,2,1])
        u = c1.text_input("User"); p = c2.text_input("Pass", type='password'); r = c3.selectbox("Role", ['user','admin'])
        if st.button("Buat"): db.create_user(u,p,r); st.success("OK"); st.rerun()
    
    udf = db.get_all_users()
    if udf is not None: st.dataframe(udf)
    if udf is not None and not udf.empty:
        us = st.selectbox("Edit User", udf['username'])
        with st.form("eu"):
            np = st.text_input("Pass Baru (Kosongkan jk tdk ubah)", type='password')
            nr = st.selectbox("Role", ['user','admin'])
            if st.form_submit_button("Update"): db.update_user(us, np, nr); st.rerun()
        if st.button("Hapus User", type="primary"): 
            if us != st.session_state['username']: db.delete_user_data(us); st.rerun()
            else: st.error("Gabisa hapus diri sendiri")

if __name__ == '__main__':
    main()
