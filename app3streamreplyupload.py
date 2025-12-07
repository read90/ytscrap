import streamlit as st
import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="YouTube Scraper Pro", page_icon="🎥", layout="wide")

# --- JUDUL & DESKRIPSI ---
st.title("🎥 YouTube Comment, Like & View Scraper")
st.markdown("""
Aplikasi untuk mengambil **Views**, **Likes**, dan **Komentar** YouTube.
*Catatan: Jumlah Dislike tidak dapat diambil karena kebijakan privasi YouTube (Hidden).*
""")

# --- SIDEBAR (INPUT USER) ---
with st.sidebar:
    st.header("⚙️ Konfigurasi")
    video_url = st.text_input("Link Video YouTube", placeholder="Paste link di sini...")
    
    col1, col2 = st.columns(2)
    with col1:
        max_scrolls = st.number_input("Max Scroll", min_value=1, value=20)
    with col2:
        target_comments = st.number_input("Target Komentar", min_value=10, value=100)
    
    include_replies = st.checkbox("Ambil Balasan (Replies)?", value=False)
    
    start_btn = st.button("🚀 Mulai Scraping", type="primary")

# --- FUNGSI UTAMA SCRAPING ---
def scrape_youtube(url, scrolls, target, get_replies):
    data_collected = []
    video_likes = "0"
    video_views = "0"
    
    # --- SETUP CHROME UNTUK STREAMLIT CLOUD ---
    options = webdriver.ChromeOptions()
    options.add_argument("--headless") # WAJIB: Tidak ada UI di Cloud
    options.add_argument("--no-sandbox") # WAJIB: Keamanan Linux
    options.add_argument("--disable-dev-shm-usage") # WAJIB: Mengatasi limit memori
    options.add_argument("--disable-gpu")
    
    # Paksa ukuran layar virtual agar elemen tidak sembunyi
    options.add_argument("--window-size=1920,1080") 
    
    # Konfigurasi Service agar otomatis mencari Chromium yang diinstall packages.txt
    try:
        service = Service(ChromeDriverManager(driver_version="latest").install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        # Fallback jika webdriver manager gagal di cloud
        # Kadang path chromium di cloud ada di lokasi spesifik
        options.binary_location = "/usr/bin/chromium"
        service = Service("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=options)
        wait = WebDriverWait(driver, 20)
    
    # ... (Lanjutkan dengan kode try driver.get(url) dan seterusnya sama seperti sebelumnya)
    
    try:
        driver.get(url)
        st.toast("Sedang membuka video...", icon="⏳")
        
        # 2. Tunggu Video & Ambil METADATA (Likes & Views)
        try:
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "ytd-comments")))
            time.sleep(3) 

            # --- A. AMBIL LIKES ---
            try:
                like_element = driver.find_element(By.XPATH, '//like-button-view-model//button//div[contains(@class,"yt-spec-button-shape-next__button-text-content")]')
                video_likes = like_element.text
            except:
                video_likes = "N/A"

            # --- B. AMBIL VIEWS (UPDATE BARU) ---
            try:
                # Selector ini mencari teks di area deskripsi/judul yang mengandung angka views
                # Menggunakan Javascript agar lebih akurat mengambil raw text dari metadata
                view_element = driver.find_element(By.XPATH, '//*[@id="info-container"]//span[contains(@class, "view-count")]')
                video_views = view_element.text
            except:
                # Fallback selector (jika layout beda)
                try:
                    view_element = driver.find_element(By.XPATH, '//ytd-watch-metadata//span[contains(text(), "views") or contains(text(), "ditonton")]')
                    video_views = view_element.text
                except:
                    video_views = "N/A"
            # -----------------------------
            
        except:
            st.warning("⚠️ Gagal mengambil metadata (Likes/Views).")
        
        # Setup Progress Bar
        progress_text = "Fase 1: Scrolling halaman utama..."
        my_bar = st.progress(0, text=progress_text)
        status_area = st.empty()

        last_height = driver.execute_script("return document.documentElement.scrollHeight")
        stuck_counter = 0

        # 3. LOOP SCROLLING
        for i in range(scrolls):
            progress_percent = int((i / scrolls) * 50)
            my_bar.progress(progress_percent, text=f"Scrolling halaman ke-{i+1} dari {scrolls}...")
            
            driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.END)
            time.sleep(3)
            
            new_height = driver.execute_script("return document.documentElement.scrollHeight")
            
            if new_height == last_height:
                stuck_counter += 1
                if stuck_counter >= 3:
                    break
            else:
                stuck_counter = 0
                last_height = new_height
            
            if not get_replies:
                current_count = len(driver.find_elements(By.ID, "author-text"))
                if current_count >= target:
                    break
        
        # 4. FASE BUKA REPLIES
        if get_replies:
            my_bar.progress(60, text="Fase 2: Mencari tombol replies...")
            time.sleep(2)
            reply_buttons = driver.find_elements(By.XPATH, '//ytd-button-renderer[@id="more-replies"]')
            
            for idx, btn in enumerate(reply_buttons):
                try:
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
                except:
                    continue

        # 5. FASE EKSTRAKSI DATA
        my_bar.progress(95, text="Fase 3: Mengambil teks komentar...")
        
        author_elems = driver.find_elements(By.ID, "author-text")
        content_elems = driver.find_elements(By.ID, "content-text")
        
        limit = min(len(author_elems), len(content_elems))
        if limit > target: limit = target

        for i in range(limit):
            try:
                u = author_elems[i].text.strip()
                c = content_elems[i].text.strip().replace('\n', ' ')
                data_collected.append({"username": u, "comment": c})
            except:
                continue
            
        my_bar.progress(100, text="Selesai!")
        time.sleep(1)
        my_bar.empty()
        
    except Exception as e:
        st.error(f"Terjadi Kesalahan: {e}")
    finally:
        driver.quit()
        
    # Return 3 Data: Komentar, Likes, Views
    return data_collected, video_likes, video_views

# --- LOGIKA APLIKASI ---
if start_btn:
    if not video_url:
        st.warning("⚠️ Harap masukkan Link Video terlebih dahulu!")
    else:
        # Clear session
        for key in ['df_result', 'video_likes', 'video_views']:
            if key in st.session_state:
                del st.session_state[key]

        with st.spinner('Sedang memproses...'):
            result_data, result_likes, result_views = scrape_youtube(video_url, max_scrolls, target_comments, include_replies)
            
            if result_data:
                st.session_state['df_result'] = pd.DataFrame(result_data)
                st.session_state['video_likes'] = result_likes
                st.session_state['video_views'] = result_views # Simpan Views
                st.success(f"✅ Berhasil mengambil {len(result_data)} komentar!")
            else:
                st.error("❌ Data kosong.")

# --- TAMPILKAN HASIL ---
if 'df_result' in st.session_state:
    df = st.session_state['df_result']
    likes = st.session_state['video_likes']
    views = st.session_state['video_views']
    
    st.divider()
    
    # Menampilkan 3 Metric Utama
    st.markdown("### 📈 Statistik Video")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Views 👁️", views) # Metric Baru
    with c2:
        st.metric("Total Likes 👍", likes)
    with c3:
        st.metric("Total Komentar 💬", len(df))

    st.divider()
    
    # Bagian Download
    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.subheader("📊 Tabel Data")
    with col_b:
        # Masukkan metadata ke CSV
        #df['video_likes'] = likes
        #df['video_views'] = views
        
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Download CSV", data=csv, file_name='youtube_data_complete.csv', mime='text/csv')
    
    st.dataframe(df, use_container_width=True)