# app.py
from __future__ import annotations

import os
import uuid
import logging
from pathlib import Path
from datetime import datetime, date
from typing import Optional, Literal, Dict, List, Tuple

import streamlit as st
from PIL import Image

from sqlalchemy import (
    create_engine,
    event,
    select,
    func,
    desc,
    asc,
    or_,
    String,
    Integer,
    DateTime,
    Date,
    Text,
    ForeignKey,
    Boolean,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    sessionmaker,
    Mapped,
    mapped_column,
    relationship,
    joinedload,
)

# -----------------------------
# Config / Paths / Logging
# -----------------------------
st.set_page_config(page_title="Armário da Cher (offline)", page_icon="👗", layout="wide")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("armario")

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
IMAGES_DIR = DATA_DIR / "images"
DB_PATH = DATA_DIR / "app.db"
THUMB_SUFFIX = ".thumb.jpg"

def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

ensure_dirs()

# -----------------------------
# Cache buster
# -----------------------------
CACHE_KEY = "cache_buster"
def ensure_cache_buster() -> None:
    if CACHE_KEY not in st.session_state:
        st.session_state[CACHE_KEY] = 0

def bump_cache() -> None:
    ensure_cache_buster()
    st.session_state[CACHE_KEY] += 1

def cache_token() -> int:
    ensure_cache_buster()
    return int(st.session_state[CACHE_KEY])

# -----------------------------
# Image helpers
# -----------------------------
def unique_filename(original_name: str) -> str:
    ext = Path(original_name).suffix.lower() or ".jpg"
    return f"{uuid.uuid4().hex}{ext}"

def save_upload_to_disk(uploaded_file) -> Path:
    fname = unique_filename(uploaded_file.name)
    out_path = IMAGES_DIR / fname
    out_path.write_bytes(uploaded_file.getbuffer())
    return out_path

def thumbnail_path_for(image_path: Path) -> Path:
    return image_path.with_suffix(image_path.suffix + THUMB_SUFFIX)

def make_thumbnail(image_path: Path, max_size: int = 512) -> Optional[Path]:
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            img.thumbnail((max_size, max_size))
            thumb_path = thumbnail_path_for(image_path)
            img.save(thumb_path, format="JPEG", quality=85, optimize=True)
            return thumb_path
    except Exception as e:
        logger.warning("Thumbnail failed for %s: %s", image_path, e)
        return None

def delete_files(paths: List[Path]) -> None:
    for p in paths:
        try:
            if p.exists():
                p.unlink()
        except Exception as e:
            logger.warning("Failed to delete file %s: %s", p, e)

# -----------------------------
# DB / ORM
# -----------------------------
class Base(DeclarativeBase):
    pass

def get_engine():
    url = f"sqlite:///{DB_PATH.as_posix()}"
    engine = create_engine(url, echo=False, future=True)

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    return engine

ENGINE = get_engine()
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False, future=True)

def db_session() -> Session:
    return SessionLocal()

# -----------------------------
# Models
# -----------------------------
Category = Literal["top", "bottom", "footwear", "outerwear", "accessory"]
Season = Literal["summer", "winter", "mid", "all"]
Occasion = Literal["casual", "work", "formal", "gym", "other"]
Status = Literal["available", "laundry", "borrowed"]
Slot = Literal["top", "bottom", "footwear", "outerwear", "accessory"]

CATEGORIES: List[str] = ["top", "bottom", "footwear", "outerwear", "accessory"]
SEASONS: List[str] = ["summer", "winter", "mid", "all"]
OCCASIONS: List[str] = ["casual", "work", "formal", "gym", "other"]
STATUSES: List[str] = ["available", "laundry", "borrowed"]
SLOTS: List[str] = ["top", "bottom", "footwear", "outerwear", "accessory"]

class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    category: Mapped[str] = mapped_column(String(20), nullable=False)
    type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    color_primary: Mapped[str] = mapped_column(String(40), nullable=False)
    color_secondary: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    season: Mapped[str] = mapped_column(String(10), nullable=False)
    occasion: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    images: Mapped[List["ItemImage"]] = relationship(
        "ItemImage",
        back_populates="item",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ItemImage.id.asc()",
    )

    __table_args__ = (
        Index("ix_items_name", "name"),
        Index("ix_items_category", "category"),
        Index("ix_items_color_primary", "color_primary"),
        Index("ix_items_season", "season"),
        Index("ix_items_occasion", "occasion"),
        Index("ix_items_status", "status"),
    )

class ItemImage(Base):
    __tablename__ = "item_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    item: Mapped["Item"] = relationship("Item", back_populates="images")

    __table_args__ = (Index("ix_item_images_item_id", "item_id"),)

class Look(Base):
    __tablename__ = "looks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    season: Mapped[str] = mapped_column(String(10), nullable=False)
    occasion: Mapped[str] = mapped_column(String(10), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    items: Mapped[List["LookItem"]] = relationship(
        "LookItem",
        back_populates="look",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    wear_logs: Mapped[List["WearLog"]] = relationship(
        "WearLog",
        back_populates="look",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (Index("ix_looks_name", "name"),)

class LookItem(Base):
    __tablename__ = "look_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    look_id: Mapped[int] = mapped_column(ForeignKey("looks.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"), nullable=False)
    slot: Mapped[str] = mapped_column(String(15), nullable=False)

    look: Mapped["Look"] = relationship("Look", back_populates="items")
    item: Mapped["Item"] = relationship("Item")

    __table_args__ = (
        UniqueConstraint("look_id", "slot", name="uq_look_slot"),
        Index("ix_look_items_look_id", "look_id"),
        Index("ix_look_items_item_id", "item_id"),
    )

class WearLog(Base):
    __tablename__ = "wear_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    look_id: Mapped[Optional[int]] = mapped_column(ForeignKey("looks.id", ondelete="SET NULL"), nullable=True)

    date: Mapped[date] = mapped_column(Date, nullable=False)
    time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    look: Mapped[Optional["Look"]] = relationship("Look", back_populates="wear_logs")

    __table_args__ = (
        Index("ix_wear_log_date", "date"),
        Index("ix_wear_log_look_id", "look_id"),
    )

def init_db() -> None:
    Base.metadata.create_all(bind=ENGINE)

init_db()

# -----------------------------
# Repos
# -----------------------------
def get_item_primary_path(item: Item) -> Optional[str]:
    if not item.images:
        return None
    primary = next((im for im in item.images if im.is_primary), None) or item.images[0]
    return primary.file_path

def item_tag_line(item: Item) -> str:
    return f"{item.category} • {item.type or '—'} • {item.color_primary} • {item.season} • {item.occasion} • {item.status}"

def repo_list_distinct_types(s: Session) -> List[str]:
    stmt = select(func.distinct(Item.type)).where(Item.type.isnot(None)).order_by(asc(Item.type))
    rows = s.execute(stmt).scalars().all()
    return [r for r in rows if r]

def repo_list_distinct_colors(s: Session) -> List[str]:
    stmt = select(func.distinct(Item.color_primary)).order_by(asc(Item.color_primary))
    rows = s.execute(stmt).scalars().all()
    return [r for r in rows if r]

def repo_get_item(s: Session, item_id: int) -> Optional[Item]:
    stmt = select(Item).where(Item.id == item_id).options(joinedload(Item.images))
    return s.execute(stmt).scalars().first()

def repo_search_items(
    s: Session,
    text: str = "",
    category: Optional[str] = None,
    type_: Optional[str] = None,
    color_primary: Optional[str] = None,
    season: Optional[str] = None,
    occasion: Optional[str] = None,
    status: Optional[str] = None,
    order_by: str = "recent",
    limit: int = 500,
) -> List[Item]:
    stmt = select(Item).options(joinedload(Item.images))

    if text.strip():
        t = f"%{text.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Item.name).like(t),
                func.lower(func.coalesce(Item.type, "")).like(t),
                func.lower(func.coalesce(Item.notes, "")).like(t),
            )
        )

    if category:
        stmt = stmt.where(Item.category == category)
    if type_:
        stmt = stmt.where(Item.type == type_)
    if color_primary:
        stmt = stmt.where(Item.color_primary == color_primary)
    if season:
        stmt = stmt.where(Item.season == season)
    if occasion:
        stmt = stmt.where(Item.occasion == occasion)
    if status:
        stmt = stmt.where(Item.status == status)

    if order_by == "name":
        stmt = stmt.order_by(asc(Item.name))
    else:
        stmt = stmt.order_by(desc(Item.created_at))

    return s.execute(stmt.limit(limit)).scalars().all()

def repo_create_item(s: Session, payload: dict, uploads: list, primary_index: int) -> Item:
    item = Item(**payload)
    s.add(item)
    s.commit()
    s.refresh(item)

    # images
    imgs: List[ItemImage] = []
    for i, uf in enumerate(uploads):
        p = save_upload_to_disk(uf)
        make_thumbnail(p)
        imgs.append(ItemImage(item_id=item.id, file_path=str(p.as_posix()), is_primary=(i == primary_index)))

    for im in imgs:
        item.images.append(im)

    s.add(item)
    s.commit()
    s.refresh(item)
    return item

def repo_update_item(s: Session, item: Item) -> Item:
    s.add(item)
    s.commit()
    s.refresh(item)
    return item

def repo_set_primary_image(s: Session, item_id: int, image_id: int) -> None:
    imgs = s.execute(select(ItemImage).where(ItemImage.item_id == item_id)).scalars().all()
    for img in imgs:
        img.is_primary = (img.id == image_id)
    s.commit()

def repo_remove_image(s: Session, image_id: int) -> Optional[ItemImage]:
    img = s.get(ItemImage, image_id)
    if not img:
        return None
    s.delete(img)
    s.commit()
    return img

def repo_delete_item_and_files(s: Session, item: Item) -> None:
    # Decision: delete files from disk (image + thumb) to avoid accumulating unused files.
    file_paths = [Path(im.file_path) for im in item.images]
    to_delete: List[Path] = []
    for p in file_paths:
        to_delete.append(p)
        to_delete.append(thumbnail_path_for(p))
    delete_files(to_delete)

    s.delete(item)  # cascades to item_images
    s.commit()

def repo_list_looks(s: Session, order_by: str = "recent", limit: int = 500) -> List[Look]:
    stmt = select(Look).options(joinedload(Look.items).joinedload(LookItem.item))
    if order_by == "name":
        stmt = stmt.order_by(asc(Look.name))
    else:
        stmt = stmt.order_by(desc(Look.created_at))
    return s.execute(stmt.limit(limit)).scalars().all()

def repo_get_look(s: Session, look_id: int) -> Optional[Look]:
    stmt = select(Look).where(Look.id == look_id).options(joinedload(Look.items).joinedload(LookItem.item))
    return s.execute(stmt).scalars().first()

def repo_create_look(s: Session, payload: dict) -> Look:
    lk = Look(**payload)
    s.add(lk)
    s.commit()
    s.refresh(lk)
    return lk

def repo_update_look(s: Session, lk: Look) -> Look:
    s.add(lk)
    s.commit()
    s.refresh(lk)
    return lk

def repo_delete_look(s: Session, lk: Look) -> None:
    s.delete(lk)
    s.commit()

def repo_replace_look_slots(s: Session, lk: Look, slots: Dict[str, Optional[int]]) -> None:
    lk.items.clear()
    for slot, item_id in slots.items():
        if item_id:
            lk.items.append(LookItem(look_id=lk.id, item_id=int(item_id), slot=slot))
    s.add(lk)
    s.commit()
    s.refresh(lk)

def repo_log_wear(s: Session, look_id: Optional[int], notes: Optional[str] = None) -> WearLog:
    now = datetime.utcnow()
    wl = WearLog(look_id=look_id, date=now.date(), time=now, notes=notes)
    s.add(wl)
    s.commit()
    s.refresh(wl)
    return wl

def repo_list_wear_logs(s: Session, look_id: Optional[int] = None, limit: int = 500) -> List[WearLog]:
    stmt = select(WearLog).options(joinedload(WearLog.look)).order_by(desc(WearLog.time))
    if look_id:
        stmt = stmt.where(WearLog.look_id == look_id)
    return s.execute(stmt.limit(limit)).scalars().all()

def repo_wear_counts_by_look(s: Session) -> Dict[int, int]:
    stmt = select(WearLog.look_id, func.count(WearLog.id)).where(WearLog.look_id.isnot(None)).group_by(WearLog.look_id)
    rows = s.execute(stmt).all()
    return {int(look_id): int(cnt) for look_id, cnt in rows if look_id is not None}

# -----------------------------
# Validation (lightweight)
# -----------------------------
def validate_required(value: str, field: str) -> Tuple[bool, str]:
    if value is None or str(value).strip() == "":
        return False, f"Campo obrigatório: {field}"
    return True, ""

def validate_item_payload(payload: dict) -> Tuple[bool, str]:
    for f in ["name", "category", "color_primary", "season", "occasion", "status"]:
        ok, msg = validate_required(payload.get(f, ""), f)
        if not ok:
            return False, msg
    if payload["category"] not in CATEGORIES:
        return False, "category inválida"
    if payload["season"] not in SEASONS:
        return False, "season inválida"
    if payload["occasion"] not in OCCASIONS:
        return False, "occasion inválida"
    if payload["status"] not in STATUSES:
        return False, "status inválido"
    return True, ""

def validate_look_payload(payload: dict) -> Tuple[bool, str]:
    for f in ["name", "season", "occasion"]:
        ok, msg = validate_required(payload.get(f, ""), f)
        if not ok:
            return False, msg
    if payload["season"] not in SEASONS:
        return False, "season inválida"
    if payload["occasion"] not in OCCASIONS:
        return False, "occasion inválida"
    return True, ""

def validate_slots(slots: Dict[str, Optional[int]]) -> Tuple[bool, str]:
    # must have top+bottom+footwear
    for req in ["top", "bottom", "footwear"]:
        if not slots.get(req):
            return False, f"Slot obrigatório faltando: {req}"
    return True, ""

# -----------------------------
# UI helpers
# -----------------------------
def slot_label(slot: str) -> str:
    return {"top": "Top", "bottom": "Bottom", "footwear": "Footwear", "outerwear": "Outerwear", "accessory": "Accessory"}.get(slot, slot)

def render_item_card(item: Item, key: str = "") -> None:
    img_path = get_item_primary_path(item)
    c1, c2 = st.columns([1, 2], gap="small")
    with c1:
        if img_path:
            p = Path(img_path)
            thumb = thumbnail_path_for(p)
            if thumb.exists():
                st.image(str(thumb), use_column_width=True)
            elif p.exists():
                st.image(str(p), use_column_width=True)
        else:
            st.info("Sem imagem")
    with c2:
        st.markdown(f"### {item.name}")
        st.caption(item_tag_line(item))
        if st.button("Abrir", key=f"open_{item.id}_{key}"):
            st.query_params["item_id"] = str(item.id)
            st.rerun()

def back_to_normal_route():
    st.query_params.pop("item_id", None)
    st.query_params.pop("look_id", None)

# -----------------------------
# Cached queries
# -----------------------------
@st.cache_data(show_spinner=False)
def cached_totals(_token: int) -> Dict[str, int]:
    with db_session() as s:
        total_items = s.execute(select(func.count(Item.id))).scalar_one()
        total_looks = s.execute(select(func.count(Look.id))).scalar_one()
        return {"items": int(total_items), "looks": int(total_looks)}

@st.cache_data(show_spinner=False)
def cached_top_used(_token: int, top_n: int = 5) -> List[Tuple[int, str, int]]:
    with db_session() as s:
        counts = repo_wear_counts_by_look(s)
        looks = repo_list_looks(s, limit=500)
        rows = [(lk.id, lk.name, counts.get(lk.id, 0)) for lk in looks]
        rows.sort(key=lambda r: r[2], reverse=True)
        return rows[:top_n]

@st.cache_data(show_spinner=False)
def cached_filters(_token: int) -> Tuple[List[str], List[str]]:
    with db_session() as s:
        return repo_list_distinct_types(s), repo_list_distinct_colors(s)

@st.cache_data(show_spinner=False)
def cached_items(_token: int, params: dict) -> List[Item]:
    with db_session() as s:
        return repo_search_items(
            s,
            text=params["text"],
            category=params.get("category") or None,
            type_=params.get("type_") or None,
            color_primary=params.get("color_primary") or None,
            season=params.get("season") or None,
            occasion=params.get("occasion") or None,
            status=params.get("status") or None,
            order_by=params.get("order_by") or "recent",
            limit=500,
        )

@st.cache_data(show_spinner=False)
def cached_looks(_token: int, order_by: str) -> List[Look]:
    with db_session() as s:
        return repo_list_looks(s, order_by=order_by, limit=500)

@st.cache_data(show_spinner=False)
def cached_wear_counts(_token: int) -> Dict[int, int]:
    with db_session() as s:
        return repo_wear_counts_by_look(s)

@st.cache_data(show_spinner=False)
def cached_all_items(_token: int) -> List[Item]:
    with db_session() as s:
        return repo_search_items(s, limit=500)

@st.cache_data(show_spinner=False)
def cached_history(_token: int, look_id: Optional[int]) -> List[WearLog]:
    with db_session() as s:
        return repo_list_wear_logs(s, look_id=look_id, limit=500)

# -----------------------------
# Pages
# -----------------------------
def page_dashboard():
    st.title("Dashboard")
    totals = cached_totals(cache_token())
    c1, c2 = st.columns(2)
    c1.metric("Total de peças", totals["items"])
    c2.metric("Total de looks", totals["looks"])
    st.divider()
    st.subheader("Looks mais usados")
    rows = cached_top_used(cache_token(), 5)
    if not rows:
        st.info("Ainda não há uso registrado.")
        return
    for look_id, name, cnt in rows:
        st.write(f"• **{name}** — {cnt} uso(s)")

def page_closet():
    st.title("Closet (Peças)")
    types, colors = cached_filters(cache_token())

    with st.expander("Busca e filtros", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        text = c1.text_input("Busca (nome/tipo/notas)", value="")
        category = c2.selectbox("Category", [""] + CATEGORIES, index=0)
        type_ = c3.selectbox("Type", [""] + types, index=0)
        color_primary = c4.selectbox("Color (primary)", [""] + colors, index=0)

        c5, c6, c7, c8 = st.columns(4)
        season = c5.selectbox("Season", [""] + SEASONS, index=0)
        occasion = c6.selectbox("Occasion", [""] + OCCASIONS, index=0)
        status = c7.selectbox("Status", [""] + STATUSES, index=0)
        order_by = c8.selectbox("Ordenação", ["recent", "name"], index=0)

    params = dict(
        text=text, category=category, type_=type_, color_primary=color_primary,
        season=season, occasion=occasion, status=status, order_by=order_by
    )
    items = cached_items(cache_token(), params)
    st.caption(f"{len(items)} peça(s) encontrada(s)")

    if not items:
        st.info("Nenhuma peça encontrada com esses filtros.")
        return

    cols = st.columns(3, gap="large")
    for i, item in enumerate(items):
        with cols[i % 3]:
            st.container(border=True)
            render_item_card(item, key=f"grid_{i}")

def page_item_new():
    st.title("Nova Peça")

    with st.form("new_item_form"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Name (apelido)*")
        category = c2.selectbox("Category*", CATEGORIES)
        type_ = c3.text_input("Type (texto livre)")

        c4, c5, c6 = st.columns(3)
        color_primary = c4.text_input("Color primary*")
        color_secondary = c5.text_input("Color secondary (opcional)")
        status = c6.selectbox("Status*", STATUSES)

        c7, c8 = st.columns(2)
        season = c7.selectbox("Season*", SEASONS)
        occasion = c8.selectbox("Occasion*", OCCASIONS)

        notes = st.text_area("Notes (opcional)", height=80)

        uploads = st.file_uploader("Fotos (1+)", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
        primary_index = st.number_input("Índice da foto principal (0..)", min_value=0, value=0, step=1)

        submitted = st.form_submit_button("Salvar peça")

    if not submitted:
        return

    payload = {
        "name": name.strip(),
        "category": category,
        "type": (type_.strip() or None),
        "color_primary": color_primary.strip(),
        "color_secondary": (color_secondary.strip() or None),
        "season": season,
        "occasion": occasion,
        "status": status,
        "notes": (notes.strip() or None),
    }

    ok, msg = validate_item_payload(payload)
    if not ok:
        st.error(f"Erro: {msg}")
        return
    if not uploads or len(uploads) == 0:
        st.error("Envie ao menos 1 foto.")
        return
    if primary_index >= len(uploads):
        st.error("Índice da foto principal inválido.")
        return

    with db_session() as s:
        item = repo_create_item(s, payload, uploads, int(primary_index))

    bump_cache()
    st.success("Peça criada!")
    st.query_params["item_id"] = str(item.id)
    st.rerun()

def page_item_detail():
    st.title("Detalhe da Peça")

    if "item_id" not in st.query_params:
        st.info("Nenhuma peça selecionada.")
        return

    item_id = int(st.query_params["item_id"])

    with db_session() as s:
        item = repo_get_item(s, item_id)
        if not item:
            st.error("Peça não encontrada.")
            if st.button("Voltar"):
                st.query_params.clear()
                st.rerun()
            return

        st.caption(f"ID: {item.id} • Criado: {item.created_at} • Atualizado: {item.updated_at}")

        st.subheader("Fotos")
        if item.images:
            cols = st.columns(min(5, len(item.images)))
            for i, im in enumerate(item.images):
                with cols[i % len(cols)]:
                    p = Path(im.file_path)
                    if p.exists():
                        st.image(str(p), use_column_width=True, caption=("PRIMARY" if im.is_primary else ""))
                    else:
                        st.warning("Arquivo não encontrado")

                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("Primária", key=f"primary_{im.id}"):
                            repo_set_primary_image(s, item.id, im.id)
                            bump_cache()
                            st.success("Imagem primária atualizada.")
                            st.rerun()
                    with b2:
                        if st.button("Remover", key=f"rm_img_{im.id}"):
                            removed = repo_remove_image(s, im.id)
                            if removed:
                                fp = Path(removed.file_path)
                                delete_files([fp, thumbnail_path_for(fp)])
                            bump_cache()
                            st.success("Imagem removida.")
                            st.rerun()
        else:
            st.info("Sem imagens.")

        st.divider()
        st.subheader("Editar dados")
        with st.form("edit_item_form"):
            c1, c2, c3 = st.columns(3)
            name = c1.text_input("Name*", value=item.name)
            category = c2.selectbox("Category*", CATEGORIES, index=CATEGORIES.index(item.category))
            type_ = c3.text_input("Type", value=item.type or "")

            c4, c5, c6 = st.columns(3)
            color_primary = c4.text_input("Color primary*", value=item.color_primary)
            color_secondary = c5.text_input("Color secondary", value=item.color_secondary or "")
            status = c6.selectbox("Status*", STATUSES, index=STATUSES.index(item.status))

            c7, c8 = st.columns(2)
            season = c7.selectbox("Season*", SEASONS, index=SEASONS.index(item.season))
            occasion = c8.selectbox("Occasion*", OCCASIONS, index=OCCASIONS.index(item.occasion))

            notes = st.text_area("Notes", value=item.notes or "", height=80)

            st.markdown("**Adicionar novas fotos (opcional)**")
            uploads = st.file_uploader("Novas fotos", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
            primary_index = st.number_input("Índice da foto principal (novas uploads)", min_value=0, value=0, step=1)

            submit = st.form_submit_button("Salvar alterações")

        st.markdown("### Marcar status rápido")
        qcols = st.columns(3)
        for i, stt in enumerate(STATUSES):
            with qcols[i]:
                if st.button(f"{stt}", key=f"quick_{stt}"):
                    item.status = stt
                    repo_update_item(s, item)
                    bump_cache()
                    st.success(f"Status alterado para {stt}.")
                    st.rerun()

        if submit:
            payload = {
                "name": name.strip(),
                "category": category,
                "type": (type_.strip() or None),
                "color_primary": color_primary.strip(),
                "color_secondary": (color_secondary.strip() or None),
                "season": season,
                "occasion": occasion,
                "status": status,
                "notes": (notes.strip() or None),
            }
            ok, msg = validate_item_payload(payload)
            if not ok:
                st.error(f"Erro: {msg}")
                return

            item.name = payload["name"]
            item.category = payload["category"]
            item.type = payload["type"]
            item.color_primary = payload["color_primary"]
            item.color_secondary = payload["color_secondary"]
            item.season = payload["season"]
            item.occasion = payload["occasion"]
            item.status = payload["status"]
            item.notes = payload["notes"]
            repo_update_item(s, item)

            if uploads and len(uploads) > 0:
                if primary_index >= len(uploads):
                    st.error("Índice da foto principal (novas uploads) inválido.")
                else:
                    for i, uf in enumerate(uploads):
                        p = save_upload_to_disk(uf)
                        make_thumbnail(p)
                        item.images.append(ItemImage(file_path=str(p.as_posix()), is_primary=(i == int(primary_index))))
                    # if new images were added and one is primary, clear older primaries
                    if len(uploads) > 0:
                        # set exactly one primary: prefer the newly uploaded "primary_index"
                        # first clear all primaries
                        for im in item.images:
                            im.is_primary = False
                        # now set the last batch primary
                        last_batch = item.images[-len(uploads):]
                        last_batch[int(primary_index)].is_primary = True
                    repo_update_item(s, item)

            bump_cache()
            st.success("Peça atualizada!")
            st.rerun()

        st.divider()
        st.subheader("Excluir peça")
        confirm = st.checkbox("Confirmo que quero excluir esta peça", value=False)
        if st.button("Excluir definitivamente", disabled=not confirm):
            repo_delete_item_and_files(s, item)
            bump_cache()
            st.success("Peça excluída.")
            st.query_params.clear()
            st.rerun()

        if st.button("Voltar ao Closet"):
            st.query_params.clear()
            st.rerun()

def page_looks():
    st.title("Looks")
    order_by = st.selectbox("Ordenação", ["recent", "name"], index=0)
    looks = cached_looks(cache_token(), order_by)
    counts = cached_wear_counts(cache_token())

    st.divider()
    st.subheader("Criar look (metadados)")
    st.caption("Para escolher peças por slots (top/bottom/footwear), use **Montar Look** no menu.")

    with st.form("create_look_form"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Name*")
        season = c2.selectbox("Season*", SEASONS)
        occasion = c3.selectbox("Occasion*", OCCASIONS)
        notes = st.text_area("Notes", height=60)
        submit = st.form_submit_button("Criar look")

    if submit:
        payload = {"name": name.strip(), "season": season, "occasion": occasion, "notes": (notes.strip() or None)}
        ok, msg = validate_look_payload(payload)
        if not ok:
            st.error(f"Erro: {msg}")
        else:
            with db_session() as s:
                repo_create_look(s, payload)
            bump_cache()
            st.success("Look criado. Vá em **Montar Look** para adicionar peças.")
            st.rerun()

    st.divider()
    st.subheader("Lista de looks")

    if not looks:
        st.info("Nenhum look criado ainda.")
        return

    for lk in looks:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            c1.markdown(f"### {lk.name}")
            c2.caption(f"season: {lk.season}")
            c3.caption(f"occasion: {lk.occasion}")
            c4.metric("Usos", counts.get(lk.id, 0))

            slots = {li.slot: li.item.name for li in lk.items}
            st.caption("Slots: " + (" • ".join([f"{k}:{v}" for k, v in slots.items()]) if slots else "—"))

            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button("Editar/Montar", key=f"edit_{lk.id}"):
                    st.query_params["look_id"] = str(lk.id)
                    st.rerun()
            with b2:
                if st.button("Usei hoje", key=f"use_{lk.id}"):
                    with db_session() as s:
                        repo_log_wear(s, lk.id, None)
                    bump_cache()
                    st.success("Uso registrado.")
                    st.rerun()
            with b3:
                if st.button("Excluir", key=f"del_{lk.id}"):
                    st.session_state["delete_look_id"] = lk.id

    if "delete_look_id" in st.session_state:
        look_id = st.session_state["delete_look_id"]
        st.warning(f"Confirmar exclusão do look ID={look_id}?")
        c1, c2 = st.columns(2)
        if c1.button("Confirmar excluir"):
            with db_session() as s:
                lk = repo_get_look(s, look_id)
                if lk:
                    repo_delete_look(s, lk)
            st.session_state.pop("delete_look_id", None)
            bump_cache()
            st.success("Look excluído.")
            st.rerun()
        if c2.button("Cancelar"):
            st.session_state.pop("delete_look_id", None)
            st.rerun()

def page_look_builder():
    st.title("Montar Look (manual)")

    qp = st.query_params
    look_id = int(qp["look_id"]) if "look_id" in qp else None

    with db_session() as s:
        st.subheader("1) Selecione/crie um look")
        look = repo_get_look(s, look_id) if look_id else None

        if not look:
            st.info("Nenhum look selecionado. Crie um novo abaixo ou escolha um existente em Looks.")
            with st.form("create_look_builder_form"):
                c1, c2, c3 = st.columns(3)
                name = c1.text_input("Name*")
                season = c2.selectbox("Season*", SEASONS)
                occasion = c3.selectbox("Occasion*", OCCASIONS)
                notes = st.text_area("Notes", height=60)
                submit = st.form_submit_button("Criar e montar")
            if submit:
                payload = {"name": name.strip(), "season": season, "occasion": occasion, "notes": (notes.strip() or None)}
                ok, msg = validate_look_payload(payload)
                if not ok:
                    st.error(f"Erro: {msg}")
                    return
                lk = repo_create_look(s, payload)
                bump_cache()
                st.query_params["look_id"] = str(lk.id)
                st.rerun()
            return

        st.success(f"Editando look: {look.name} (ID {look.id})")

        st.divider()
        st.subheader("2) Escolha peças por slot (top/bottom/footwear obrigatórios)")

        items_all = cached_all_items(cache_token())
        colors = sorted({it.color_primary for it in items_all if it.color_primary})

        current = {li.slot: li.item_id for li in look.items}
        selections: Dict[str, Optional[int]] = {}

        # Shared filters for search while selecting
        f1, f2, f3, f4 = st.columns(4)
        qtext = f1.text_input("Filtro texto", value="")
        qcolor = f2.selectbox("Cor primária", [""] + colors, index=0)
        qseason = f3.selectbox("Preferência de season", ["", "summer", "winter", "mid", "all"], index=0)
        qstatus = f4.selectbox("Status", ["", "available", "laundry", "borrowed"], index=0)

        def filter_candidates(slot: str) -> List[Item]:
            cat = slot
            out = [it for it in items_all if it.category == cat]
            if qtext.strip():
                t = qtext.strip().lower()
                out = [it for it in out if (t in it.name.lower()) or (t in (it.type or "").lower()) or (t in (it.notes or "").lower())]
            if qcolor:
                out = [it for it in out if it.color_primary == qcolor]
            if qseason:
                # allow all-season to pass
                if qseason != "all":
                    out = [it for it in out if it.season in (qseason, "all")]
                else:
                    out = [it for it in out if it.season in ("all", "summer", "winter", "mid")]
            if qstatus:
                out = [it for it in out if it.status == qstatus]
            return out

        for slot in SLOTS:
            st.markdown(f"### {slot_label(slot)} {'(obrigatório)' if slot in ('top','bottom','footwear') else '(opcional)'}")
            candidates = filter_candidates(slot)

            options = {f"{it.name} • {it.type or '—'} • {it.color_primary} • {it.status} (ID {it.id})": it.id for it in candidates}
            labels = [""] + list(options.keys())

            current_id = current.get(slot)
            current_label = ""
            if current_id:
                for lbl, iid in options.items():
                    if iid == current_id:
                        current_label = lbl
                        break

            idx = labels.index(current_label) if current_label in labels else 0
            chosen = st.selectbox(f"Selecionar {slot_label(slot)}", labels, index=idx, key=f"slot_{slot}_{look.id}")
            selections[slot] = options.get(chosen) if chosen else None

            if selections[slot]:
                it = next((x for x in candidates if x.id == selections[slot]), None)
                if it:
                    img = get_item_primary_path(it)
                    if img and Path(img).exists():
                        st.image(img, width=220, caption=it.name)

        st.divider()
        st.subheader("Pré-visualização")
        preview_cols = st.columns(5)
        for i, slot in enumerate(SLOTS):
            with preview_cols[i]:
                st.caption(slot_label(slot))
                it_id = selections.get(slot)
                if not it_id:
                    st.write("—")
                    continue
                it = next((x for x in items_all if x.id == it_id), None)
                if not it:
                    st.write("—")
                    continue
                img = get_item_primary_path(it)
                if img and Path(img).exists():
                    st.image(img, use_column_width=True)
                st.write(it.name)

        st.divider()
        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("Salvar slots"):
                ok, msg = validate_slots(selections)
                if not ok:
                    st.error(f"Erro: {msg}")
                else:
                    repo_replace_look_slots(s, look, selections)
                    bump_cache()
                    st.success("Slots salvos.")
                    st.rerun()
        with b2:
            if st.button("Usei hoje"):
                repo_log_wear(s, look.id, None)
                bump_cache()
                st.success("Uso registrado.")
                st.rerun()
        with b3:
            if st.button("Limpar seleção"):
                st.query_params.clear()
                st.rerun()

def page_history():
    st.title("Histórico (wear_log)")
    looks = cached_looks(cache_token(), "recent")
    options = [(0, "— todos —")] + [(lk.id, lk.name) for lk in looks]
    choice = st.selectbox("Filtrar por look", options, format_func=lambda x: x[1])
    look_id = choice[0] or None

    logs = cached_history(cache_token(), look_id)
    if not logs:
        st.info("Sem registros ainda.")
        return

    for wl in logs:
        with st.container(border=True):
            title = wl.look.name if wl.look else "(look removido)"
            st.markdown(f"**{title}**")
            st.caption(f"Data: {wl.date} • Time(UTC): {wl.time}")
            if wl.notes:
                st.write(wl.notes)

# -----------------------------
# Main Router + Sidebar
# -----------------------------
def run_app():
    ensure_cache_buster()

    st.sidebar.title("👗 Armário da Cher")
    menu = st.sidebar.radio(
        "Menu",
        ["Dashboard", "Closet (Peças)", "Nova Peça", "Looks", "Montar Look", "Histórico"],
        index=0,
    )

    # deep-link: item detail has priority
    if "item_id" in st.query_params:
        page_item_detail()
        return

    if menu == "Dashboard":
        page_dashboard()
    elif menu == "Closet (Peças)":
        page_closet()
    elif menu == "Nova Peça":
        page_item_new()
    elif menu == "Looks":
        page_looks()
    elif menu == "Montar Look":
        page_look_builder()
    elif menu == "Histórico":
        page_history()

run_app()
