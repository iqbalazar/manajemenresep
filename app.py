import streamlit as st
import pandas as pd
import time # Import time untuk delay sedikit agar toast terbaca

# Import modul buatan sendiri
import database as db
import utils

# --- CONFIG & INIT ---
st.set_page_config(page_title="Resep App", layout="wide")

# Init DB saat pertama kali load
if 'db_initialized' not in st.session_state:
    db.init_db()
    st.session_state['db_initialized'] = True

# --- FUNGSI HELPER UI (TOAST) ---
def show_success_toast(message):
    st.toast(message, icon='✅')
    time.sleep(0.8) # Beri waktu sedikit agar mata sempat melihat sebelum refresh

def show_warning_toast(message):
    st.toast(message, icon='🗑️')
    time.sleep(0.8)

# --- FUNGSI INISIALISASI SESI ---
def init_session():
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
    if 'role' not in st.session_state:
        st.session_state['role'] = None
    if 'username' not in st.session_state:
        st.session_state['username'] = None
    if 'menu_list' not in st.session_state:
        st.session_state['menu_list'] = []

    # Logika Auto-Login dari URL
    if not st.session_state['logged_in'] and 'user' in st.query_params:
        username_url = st.query_params['user']
        try:
            user_data = db.get_user_by_username(username_url)
            if user_data:
                st.session_state['logged_in'] = True
                st.session_state['username'] = user_data[0]
                st.session_state['role'] = user_data[2]
            else:
                st.query_params.clear()
        except Exception:
            pass

# --- MAIN ROUTER ---
def main():
    init_session()
    
    if not st.session_state['logged_in']:
        page_login()
    else:
        st.sidebar.title(f"👨‍🍳 Halo, {st.session_state['username']}")
        
        if st.sidebar.button("Logout", type="primary"):
            st.session_state['logged_in'] = False
            st.session_state['role'] = None
            st.session_state['menu_list'] = []
            st.query_params.clear()
            st.rerun()
            
        st.sidebar.divider()
        
        if st.session_state['role'] == 'admin':
            st.sidebar.caption("Menu Administrator")
            options = ["Kalkulator", "Resep", "User"]
            default_index = 0
            if "page" in st.query_params:
                current_page_param = st.query_params["page"]
                if current_page_param in options:
                    default_index = options.index(current_page_param)
            
            selected_menu = st.sidebar.radio("Navigasi", options, index=default_index)
            
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
    st.markdown("<h1 style='text-align: center;'>🔐 Login Sistem Resep</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        with st.container(border=True):
            st.markdown("Silakan masukkan kredensial Anda.")
            u = st.text_input("Username")
            p = st.text_input("Password", type='password')
            if st.button("Masuk Sistem", type="primary", use_container_width=True):
                user = db.login_user(u, p)
                if user:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = user[0]
                    st.session_state['role'] = user[2]
                    st.query_params['user'] = user[0]
                    show_success_toast(f"Selamat datang, {user[0]}!")
                    st.rerun()
                else:
                    st.toast("Username atau Password salah!", icon='❌')

def page_calculator():
    st.title("🍳 Aplikasi Masak Cerdas")
    st.caption("Kelola rencana masak Anda, hitung kebutuhan belanja, atau cari inspirasi dari stok di kulkas.")
    
    tab1, tab2 = st.tabs(["🛒 Hitung Belanja", "🔍 Cari Resep dari Stok"])
    
    # --- TAB 1: KALKULATOR ---
    with tab1:
        if 'menu_list' not in st.session_state: st.session_state.menu_list = []
        
        recipes = db.get_all_recipes()
        if recipes is None or recipes.empty: 
            st.warning("Belum ada data resep. Hubungi Admin.")
            return
        
        r_dict = dict(zip(recipes['id'], recipes['name']))
        l_dict = dict(zip(recipes['id'], recipes['source_link']))
        
        c1, c2 = st.columns([1.2, 2])
        with c1:
            st.markdown("### 1️⃣ Pilih Menu")
            st.info("Pilih masakan yang ingin dibuat dan tentukan porsinya.")
            
            with st.container(border=True):
                with st.form("add_menu"):
                    sid = st.selectbox("Daftar Resep", list(r_dict.keys()), format_func=lambda x: r_dict[x])
                    portion = st.number_input("Jumlah Porsi", min_value=1, value=1)
                    if st.form_submit_button("Tambah ke Daftar", type="primary"):
                        st.session_state.menu_list.append({
                            'id': sid, 'name': r_dict[sid], 'portions': portion, 'link': l_dict.get(sid)
                        })
                        show_success_toast("Menu berhasil ditambahkan!")
                        st.rerun()
            
            if st.session_state.menu_list:
                if st.button("Reset Daftar Belanja"): 
                    st.session_state.menu_list = []
                    show_warning_toast("Daftar belanja dikosongkan.")
                    st.rerun()
                
                st.markdown("#### 📖 Panduan Masak")
                for i in st.session_state.menu_list:
                    with st.expander(f"👨‍🍳 Cara Masak: {i['name']}"):
                        link = i['link']
                        if link and len(link) > 5:
                            if "youtube.com" in link or "youtu.be" in link:
                                st.video(link)
                            else:
                                st.link_button("🔗 Buka Artikel Resep", link)
                        else:
                            st.caption("Tidak ada link sumber tersedia.")
        
        with c2:
            st.markdown("### 2️⃣ Cek Stok & Belanja")
            if st.session_state.menu_list:
                st.success("Di bawah ini adalah total bahan yang dibutuhkan. Silakan isi kolom **'Stok di Rumah'** untuk mengurangi belanjaan.")
                
                all_dfs = []
                for i in st.session_state.menu_list:
                    d = db.get_ingredients_by_recipe(i['id'])
                    d['total_quantity'] = d['quantity'] * i['portions']
                    all_dfs.append(d)
                
                if all_dfs:
                    full = pd.concat(all_dfs)
                    full = utils.normalize_units(full)
                    final = full.groupby(['ingredient_name', 'unit'])['total_quantity'].sum().reset_index()
                    final['Stok di Rumah'] = 0.0 # Default value
                    
                    edited = st.data_editor(
                        final, 
                        hide_index=True, 
                        disabled=['ingredient_name','unit','total_quantity'],
                        column_config={
                            "ingredient_name": "Nama Bahan",
                            "total_quantity": st.column_config.NumberColumn("Total Butuh", format="%.2f"),
                            "Stok di Rumah": st.column_config.NumberColumn("Punya Stok Brp?", min_value=0, help="Isi jika sudah punya bahannya")
                        }
                    )
                    
                    edited['Harus Beli'] = (edited['total_quantity'] - edited['Stok di Rumah']).apply(lambda x: x if x>0 else 0)
                    edited['Estimasi'] = edited.apply(lambda x: utils.format_output(x['Harus Beli'], x['unit']), axis=1)
                    
                    st.divider()
                    st.markdown("#### 🧾 Final Daftar Belanja")
                    st.dataframe(edited[['ingredient_name', 'Estimasi']], use_container_width=True)
                    
                    st.download_button(
                        label="📥 Download Excel",
                        data=utils.generate_excel(edited),
                        file_name="Daftar_Belanja.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary"
                    )
            else:
                st.info("👈 Belum ada menu dipilih. Silakan pilih menu di panel sebelah kiri.")

    # --- TAB 2: CARI RESEP ---
    with tab2:
        st.subheader("🔍 Punya bahan apa di kulkas?")
        st.caption("Bingung mau masak apa? Centang bahan yang Anda miliki, kami akan carikan resepnya.")
        
        all_ings = db.get_all_unique_ingredients()
        sel = st.multiselect("Pilih Bahan Tersedia:", all_ings, placeholder="Misal: Telur, Bawang, Ayam...")
        
        if st.button("Cari Inspirasi Resep", type="primary"):
            if sel:
                matches = db.find_matching_recipes(sel)
                if matches:
                    st.success(f"Hore! Ditemukan {len(matches)} resep yang relevan.")
                    for m in matches:
                        color = "green" if m['match_score']==100 else "orange"
                        with st.expander(f"🥘 {m['name']} (Kecocokan: :{color}[{m['match_score']:.0f}%])"):
                            if m['missing_count'] > 0: 
                                st.warning(f"⚠️ **Bahan Kurang:** {', '.join(m['missing_ingredients'])}")
                            else: 
                                st.success("✅ Bahan Lengkap! Siap masak.")
                            
                            st.markdown("**Rincian Bahan:**")
                            det = db.get_ingredients_by_recipe(m['id'])
                            det['Jml'] = det.apply(lambda x: utils.format_indo(x['quantity']), axis=1)
                            st.table(det[['ingredient_name', 'Jml', 'unit']])
                            
                            link = m['source_link']
                            if link and len(link) > 5:
                                st.markdown("---")
                                if "youtube.com" in link or "youtu.be" in link:
                                    st.video(link)
                                else:
                                    st.link_button("🔗 Lihat Sumber Resep", link)
                else: 
                    st.error("Belum ada resep yang cocok dengan kombinasi bahan tersebut.")
            else: 
                st.toast("Pilih minimal satu bahan dulu ya!", icon='⚠️')

def page_manage_recipes():
    st.title("🛠️ Kelola Database Resep")
    st.caption("Admin Area: Tambah, Edit, atau Hapus resep dan bahan masakan.")
    
    t1, t2, t3 = st.tabs(["➕ Tambah Resep", "✏️ Edit Resep & Bahan", "🗑️ Hapus Resep"])
    
    # TAB 1: TAMBAH
    with t1:
        st.markdown("### Buat Resep Baru")
        with st.container(border=True):
            n = st.text_input("Nama Masakan")
            l = st.text_input("Link Sumber (YouTube/Blog)")
            if st.button("Simpan Resep Baru", type="primary"):
                if n:
                    db.add_recipe_to_db(n, l)
                    show_success_toast(f"Resep '{n}' berhasil dibuat!")
                    st.rerun()
                else:
                    st.toast("Nama resep wajib diisi!", icon='⚠️')
    
    # TAB 2: EDIT
    with t2:
        st.markdown("### Update Data Resep")
        df = db.get_all_recipes()
        if df is not None and not df.empty:
            rd = dict(zip(df['id'], df['name']))
            sid = st.selectbox("Pilih Resep untuk Diedit", list(rd.keys()), format_func=lambda x: rd[x])
            cur = df[df['id']==sid].iloc[0]
            
            with st.expander("📝 Edit Informasi Utama (Nama & Link)", expanded=False):
                with st.form("edit_info"):
                    nn = st.text_input("Nama Resep", cur['name'])
                    nl = st.text_input("Link Sumber", cur['source_link'])
                    if st.form_submit_button("Simpan Perubahan Info"):
                        db.update_recipe_data(sid, nn, nl)
                        show_success_toast("Informasi resep diperbarui!")
                        st.rerun()
            
            st.markdown("#### Daftar Bahan Masakan")
            cur_ing = db.get_ingredients_by_recipe(sid)
            
            if not cur_ing.empty:
                cur_ing['disp'] = cur_ing.apply(lambda x: utils.format_indo(x['quantity']), axis=1)
                st.table(cur_ing[['ingredient_name','disp','unit']])
                
                with st.expander("✏️ Edit atau Hapus Bahan Tertentu"):
                    id_ing = st.selectbox("Pilih Bahan", cur_ing['id'], format_func=lambda x: cur_ing[cur_ing['id']==x]['ingredient_name'].values[0])
                    row = cur_ing[cur_ing['id']==id_ing].iloc[0]
                    
                    c1,c2,c3 = st.columns(3)
                    en = c1.text_input("Nama Bahan", row['ingredient_name'])
                    eq = c2.number_input("Jumlah", value=float(row['quantity']), step=0.1)
                    eu = c3.text_input("Satuan", row['unit'])
                    
                    c_btn1, c_btn2 = st.columns(2)
                    with c_btn1:
                        if st.button("Simpan Perubahan Bahan"):
                            db.update_ingredient_data(id_ing, en, eq, eu)
                            show_success_toast("Data bahan diperbarui!")
                            st.rerun()
                    with c_btn2:
                        if st.button("Hapus Bahan Ini", type="primary"):
                            db.delete_ingredient_data(id_ing)
                            show_warning_toast("Bahan dihapus.")
                            st.rerun()
            else:
                st.info("Resep ini belum memiliki bahan.")
            
            st.divider()
            st.markdown("#### ➕ Tambah Bahan Baru")
            with st.container(border=True):
                with st.form("new_ing"):
                    c1,c2,c3 = st.columns(3)
                    n = c1.text_input("Nama Bahan Baru")
                    q = c2.number_input("Jumlah", step=0.1, min_value=0.0)
                    u = c3.text_input("Satuan")
                    if st.form_submit_button("Tambahkan Bahan"):
                        if n:
                            db.add_ingredient_to_db(sid, n, q, u)
                            show_success_toast("Bahan berhasil ditambahkan!")
                            st.rerun()
                        else:
                            st.toast("Nama bahan tidak boleh kosong", icon='⚠️')
    
    # TAB 3: HAPUS
    with t3:
        st.markdown("### Hapus Resep Permanen")
        st.warning("Hati-hati! Menghapus resep akan menghapus semua bahan di dalamnya juga.")
        df = db.get_all_recipes()
        if df is not None and not df.empty:
            rd = dict(zip(df['id'], df['name']))
            did = st.selectbox("Pilih Resep yang akan dihapus", list(rd.keys()), format_func=lambda x: rd[x], key='del_res')
            
            if st.button("Ya, Hapus Resep Ini", type="primary"):
                db.delete_recipe_from_db(did)
                show_warning_toast("Resep telah dihapus permanen.")
                st.rerun()

def page_manage_users():
    st.title("👥 Kelola Pengguna")
    st.caption("Admin Area: Tambah user baru atau reset password.")
    
    col_l, col_r = st.columns([1, 1.5])
    
    with col_l:
        with st.container(border=True):
            st.markdown("### Buat User Baru")
            u = st.text_input("Username Baru")
            p = st.text_input("Password Awal", type='password')
            r = st.selectbox("Role", ['user','admin'])
            if st.button("Buat User", type="primary"):
                if u and p:
                    if db.create_user(u,p,r): 
                        show_success_toast(f"User {u} berhasil dibuat!")
                        st.rerun()
                    else: 
                        st.toast("Gagal! Username mungkin sudah ada.", icon='❌')
                else:
                    st.toast("Data tidak boleh kosong", icon='⚠️')
    
    with col_r:
        st.markdown("### Daftar User")
        udf = db.get_all_users()
        if udf is not None: 
            st.dataframe(udf, use_container_width=True)
        
        if udf is not None and not udf.empty:
            st.divider()
            st.markdown("#### Edit / Hapus User")
            us = st.selectbox("Pilih User", udf['username'])
            
            with st.form("eu"):
                np = st.text_input("Password Baru (Kosongkan jika tidak ubah)", type='password')
                nr = st.selectbox("Role", ['user','admin'])
                
                c_up, c_del = st.columns(2)
                with c_up:
                    if st.form_submit_button("Update User"):
                        db.update_user(us, np, nr)
                        show_success_toast(f"Data user {us} diperbarui!")
                        st.rerun()
            
            if st.button("Hapus User Terpilih", type="primary"): 
                if us != st.session_state['username']: 
                    db.delete_user_data(us)
                    show_warning_toast(f"User {us} dihapus.")
                    st.rerun()
                else: 
                    st.toast("Tidak bisa menghapus akun sendiri!", icon='⛔')

if __name__ == '__main__':
    main()
