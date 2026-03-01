# test.py
import streamlit as st
import sqlite3
import hashlib
from datetime import datetime
from io import BytesIO

DB_PATH = "armario_cher.db"

# -------------------------
# DB helpers
# -------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            mime TEXT NOT NULL,
            content BLOB NOT NULL,
            sha256 TEXT NOT NULL UNIQUE,
            uploaded_at TEXT NOT NULL
        );
    """)
    conn.commit()
    return conn

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def insert_image(conn, filename: str, mime: str, content: bytes):
    digest = sha256_bytes(content)
    conn.execute(
        "INSERT INTO images (filename, mime, content, sha256, uploaded_at) VALUES (?, ?, ?, ?, ?)",
        (filename, mime, content, digest, datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()

def fetch_images(conn, query: str = ""):
    if query.strip():
        q = f"%{query.strip().lower()}%"
        cur = conn.execute(
            "SELECT id, filename, mime, content, uploaded_at FROM images "
            "WHERE LOWER(filename) LIKE ? ORDER BY id DESC",
            (q,)
        )
    else:
        cur = conn.execute(
            "SELECT id, filename, mime, content, uploaded_at FROM images ORDER BY id DESC"
        )

    rows = cur.fetchall()

    fixed = []
    for (image_id, filename, mime, content, uploaded_at) in rows:
        # SQLite pode devolver BLOB como memoryview
        if isinstance(content, memoryview):
            content = content.tobytes()
        elif isinstance(content, bytearray):
            content = bytes(content)
        elif not isinstance(content, (bytes,)):
            # fallback defensivo
            content = bytes(content)

        fixed.append((image_id, filename, mime, content, uploaded_at))
    return fixed

def delete_image(conn, image_id: int):
    conn.execute("DELETE FROM images WHERE id = ?", (image_id,))
    conn.commit()

# -------------------------
# Image rendering (robusto)
# -------------------------
def render_image(content: bytes, caption: str):
    """
    Render robusto para Streamlit Cloud/Py3.13:
    1) Tenta st.image(BytesIO(...)) (bem compatível)
    2) Se falhar, tenta Pillow (se instalado)
    3) Se falhar, mostra aviso
    """
    try:
        st.image(BytesIO(content), caption=caption, use_container_width=True)
        return
    except Exception:
        pass

    # fallback com Pillow (se existir)
    try:
        from PIL import Image  # pillow opcional
        img = Image.open(BytesIO(content))
        st.image(img, caption=caption, use_container_width=True)
        return
    except Exception:
        st.warning("Não foi possível renderizar esta imagem (arquivo pode estar corrompido ou formato inesperado).")

# -------------------------
# UI pages
# -------------------------
def page_upload(conn):
    st.header("📤 Upload de imagens (peças)")
    st.caption("As imagens são salvas no SQLite como BLOB. Duplicatas são evitadas via hash (sha256).")

    files = st.file_uploader(
        "Selecione uma ou mais imagens",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True
    )

    if files and st.button("Salvar no banco", type="primary"):
        saved, skipped, failed = 0, 0, 0

        for f in files:
            try:
                content = f.getvalue()
                if not content:
                    failed += 1
                    continue

                mime = f.type or "application/octet-stream"

                try:
                    insert_image(conn, f.name, mime, content)
                    saved += 1
                except sqlite3.IntegrityError:
                    skipped += 1

            except Exception:
                failed += 1

        st.success(f"✅ Salvas: {saved} | ⚠️ Duplicadas ignoradas: {skipped} | ❌ Falhas: {failed}")

def page_gallery(conn):
    st.header("🖼️ Galeria (todas as imagens)")
    st.caption("Busca por nome do arquivo e visualização direta.")

    query = st.text_input("Buscar por nome do arquivo", placeholder="ex: camisa, vestido, jaqueta...")

    rows = fetch_images(conn, query=query)
    st.write(f"Total encontrado: **{len(rows)}**")

    if not rows:
        st.info("Nenhuma imagem encontrada. Vá na página de Upload e adicione algumas.")
        return

    cols_per_row = 3
    for i in range(0, len(rows), cols_per_row):
        cols = st.columns(cols_per_row)
        for col, row in zip(cols, rows[i:i + cols_per_row]):
            image_id, filename, mime, content, uploaded_at = row
            with col:
                render_image(content, caption=filename)
                st.caption(f"ID: {image_id} • {uploaded_at}")

                with st.expander("Opções", expanded=False):
                    st.download_button(
                        "⬇️ Baixar arquivo",
                        data=content,
                        file_name=filename,
                        mime=mime,
                        key=f"dl_{image_id}"
                    )

                    if st.button(f"🗑️ Excluir (ID {image_id})", key=f"del_{image_id}"):
                        delete_image(conn, image_id)
                        st.rerun()

# -------------------------
# App
# -------------------------
def main():
    st.set_page_config(page_title="Armário da Cher (MVP)", page_icon="👗", layout="wide")
    conn = get_conn()

    st.sidebar.title("👗 Armário da Cher (MVP)")
    page = st.sidebar.radio("Navegação", ["Upload", "Galeria"], index=0)

    if page == "Upload":
        page_upload(conn)
    else:
        page_gallery(conn)

if __name__ == "__main__":
    main()
