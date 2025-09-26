"""
EPUB Metadata Enricher - v2
Adds structured logging and a retry/backoff strategy for network calls.

Path (first line): /projects/epub_enricher/epub_enricher.py
"""
from __future__ import annotations

import os
import re
import json
import csv
import shutil
import threading
import traceback
import time
import random
import logging
from logging.handlers import RotatingFileHandler
from dataclasses import dataclass
from typing import Optional, List, Dict, Callable
from io import BytesIO

import requests
from ebooklib import epub
from isbnlib import is_isbn10, is_isbn13, canonical
from langdetect import detect
from PIL import Image
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ---------- Configuration ----------
API_TIMEOUT = 10
OPENLIB_SEARCH = "https://openlibrary.org/search.json"
OPENLIB_BOOK = "https://openlibrary.org/api/books"
COVER_CACHE_DIR = ".cover_cache"
BACKUP_DIR = "backups"
LOG_DIR = "logs"
SUPPORTED_EXT = (".epub",)

ISBN_RE = re.compile(r"(?:(?:ISBN(?:-1[03])?:?\s*)?)(97[89][ -]?)?[0-9][0-9 -]{8,}[0-9Xx]")

# Retry/backoff configuration
MAX_RETRIES = 5
INITIAL_BACKOFF = 1.0  # seconds
MAX_BACKOFF = 30.0
JITTER = 0.3  # fraction for jitter

# ---------- Logging setup ----------
os.makedirs(LOG_DIR, exist_ok=True)
logger = logging.getLogger("epub_enricher")
logger.setLevel(logging.DEBUG)
logfile = os.path.join(LOG_DIR, "epub_enricher.log")
handler = RotatingFileHandler(logfile, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
formatter = logging.Formatter("%(asctime)s %(levelname)s [%(threadName)s] %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
# console INFO
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
logger.addHandler(console)


# ---------- Helpers: retry/backoff ----------
def retry_backoff(
    max_retries: int = MAX_RETRIES,
    initial_backoff: float = INITIAL_BACKOFF,
    max_backoff: float = MAX_BACKOFF,
    jitter: float = JITTER,
    allowed_exceptions: tuple = (requests.RequestException,),
):
    """Decorator for retrying functions with exponential backoff + jitter."""

    def deco(func: Callable):
        def wrapper(*args, **kwargs):
            backoff = initial_backoff
            for attempt in range(1, max_retries + 1):
                try:
                    logger.debug("Attempt %d for %s", attempt, func.__name__)
                    return func(*args, **kwargs)
                except allowed_exceptions as e:
                    if attempt == max_retries:
                        logger.exception("Max retries reached for %s", func.__name__)
                        raise
                    sleep_time = backoff * (1 + random.uniform(-jitter, jitter))
                    sleep_time = max(0.0, min(max_backoff, sleep_time))
                    logger.warning(
                        "Error on attempt %d for %s: %s -- backing off %.2fs",
                        attempt,
                        func.__name__,
                        e,
                        sleep_time,
                    )
                    time.sleep(sleep_time)
                    backoff = min(max_backoff, backoff * 2)
                except Exception:
                    logger.exception("Non-retryable exception in %s", func.__name__)
                    raise

        return wrapper

    return deco


# ---------- Data classes ----------
@dataclass
class EpubMeta:
    path: str
    filename: str
    original_title: Optional[str] = None
    original_authors: Optional[List[str]] = None
    original_isbn: Optional[str] = None
    original_language: Optional[str] = None

    suggested_title: Optional[str] = None
    suggested_authors: Optional[List[str]] = None
    suggested_isbn: Optional[str] = None
    suggested_language: Optional[str] = None
    suggested_cover_url: Optional[str] = None

    accepted: bool = False
    processed: bool = False
    note: Optional[str] = None


# ---------- Core functionality ----------


def find_epubs_in_folder(folder: str) -> List[str]:
    files = []
    for root, _, filenames in os.walk(folder):
        for f in filenames:
            if f.lower().endswith(SUPPORTED_EXT):
                files.append(os.path.join(root, f))
    logger.info("Found %d epub(s) in folder %s", len(files), folder)
    return files


def backup_file(path: str) -> str:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    basename = os.path.basename(path)
    ts = time.strftime("%Y%m%d-%H%M%S")
    dst = os.path.join(BACKUP_DIR, f"{ts}-{basename}")
    shutil.copy2(path, dst)
    logger.debug("Backed up %s -> %s", path, dst)
    return dst


def safe_read_epub(epub_path: str):
    try:
        return epub.read_epub(epub_path)
    except Exception as e:
        logger.exception("ebooklib failed to read %s: %s", epub_path, e)
        return None


def extract_metadata(epub_path: str) -> Dict:
    data = {"title": None, "authors": None, "language": None, "identifier": None}
    book = safe_read_epub(epub_path)
    if not book:
        return data

    try:
        title = book.get_metadata("DC", "title")
        if title:
            data["title"] = title[0][0]
    except Exception:
        logger.debug("Title not found in metadata for %s", epub_path)

    try:
        auths = book.get_metadata("DC", "creator")
        authors = []
        for a in auths:
            if isinstance(a, tuple):
                authors.append(a[0])
            else:
                authors.append(str(a))
        data["authors"] = authors if authors else None
    except Exception:
        logger.debug("Authors not found in metadata for %s", epub_path)

    try:
        l = book.get_metadata("DC", "language")
        if l:
            data["language"] = l[0][0]
    except Exception:
        logger.debug("Language not found in metadata for %s", epub_path)

    try:
        ids = book.get_metadata("DC", "identifier")
        for ident in ids:
            candidate = ident[0]
            if isinstance(candidate, str) and ISBN_RE.search(candidate):
                m = ISBN_RE.search(candidate).group(0)
                if is_isbn10(m) or is_isbn13(m):
                    data["identifier"] = canonical(m)
                    break
    except Exception:
        logger.debug("Identifier not found in metadata for %s", epub_path)

    if not data["language"]:
        try:
            docs = list(book.get_items_of_type(epub.ITEM_DOCUMENT))
            if docs:
                text = docs[0].get_content().decode("utf-8", errors="ignore")
                sample = re.sub("<[^<]+?>", "", text)[:3000]
                if sample.strip():
                    data["language"] = detect(sample)
        except Exception:
            logger.debug("Language detection failed for %s", epub_path)

    if not data["identifier"]:
        try:
            for item in book.get_items_of_type(epub.ITEM_DOCUMENT):
                txt = item.get_content().decode("utf-8", errors="ignore")
                m = ISBN_RE.search(txt)
                if m:
                    raw = m.group(0)
                    if is_isbn10(raw) or is_isbn13(raw):
                        data["identifier"] = canonical(raw)
                        break
        except Exception:
            logger.debug("Text ISBN search failed for %s", epub_path)

    logger.info(
        "Extracted metadata for %s: title=%s, authors=%s, isbn=%s, lang=%s",
        epub_path,
        data["title"],
        data["authors"],
        data["identifier"],
        data["language"],
    )
    return data


# ---------- Network functions with retries ----------


@retry_backoff()
def http_get(
    url: str,
    params: Optional[Dict[str, str]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = API_TIMEOUT,
) -> requests.Response:
    logger.debug("HTTP GET %s params=%s", url, params)
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r


@retry_backoff()
def http_download_bytes(url: str, timeout: int = API_TIMEOUT) -> bytes:
    logger.debug("Downloading bytes from %s", url)
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.content


def query_openlibrary_by_isbn(isbn: str) -> Optional[Dict]:
    try:
        params = {"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"}
        r = http_get(OPENLIB_BOOK, params=params)
        js = r.json()
        key = f"ISBN:{isbn}"
        if key in js:
            logger.info("OpenLibrary returned data for ISBN %s", isbn)
            return js[key]
        logger.info("OpenLibrary no data for ISBN %s", isbn)
    except Exception as e:
        logger.warning("query_openlibrary_by_isbn failed for %s: %s", isbn, e)
    return None


def query_openlibrary_search(title: str, author: Optional[str] = None) -> Optional[Dict]:
    try:
        q = title
        if author:
            q += f" {author}"
        params = {"q": q, "title": title}
        r = http_get(OPENLIB_SEARCH, params=params)
        js = r.json()
        docs = js.get("docs")
        if docs:
            logger.info("OpenLibrary search returned %d docs for query %s", len(docs), q)
            return docs[0]
    except Exception as e:
        logger.warning("query_openlibrary_search failed for %s / %s: %s", title, author, e)
    return None


def extract_suggested_from_openlib(
    isbn: Optional[str], title: Optional[str], authors: Optional[List[str]]
) -> Dict:
    out = {}
    if isbn:
        data = query_openlibrary_by_isbn(isbn)
        if data:
            out["title"] = data.get("title")
            out["authors"] = (
                [a.get("name") for a in data.get("authors", [])] if data.get("authors") else None
            )
            out["isbn"] = isbn
            cover = data.get("cover")
            if cover:
                out["cover"] = cover.get("large") or cover.get("medium") or cover.get("small")
            languages = data.get("languages")
            if languages and isinstance(languages, list):
                lang_keys = [l.get("key") for l in languages if isinstance(l, dict)]
                if lang_keys:
                    out["language"] = lang_keys[0].split("/")[-1]
            return out
    if title:
        auth = authors[0] if authors else None
        doc = query_openlibrary_search(title, auth)
        if doc:
            out["title"] = doc.get("title")
            out["authors"] = doc.get("author_name")
            isbns = doc.get("isbn")
            if isbns:
                for candidate in isbns:
                    if is_isbn13(candidate) or is_isbn10(candidate):
                        try:
                            out["isbn"] = canonical(candidate)
                            break
                        except Exception:
                            out["isbn"] = candidate
            cover_id = doc.get("cover_i")
            if cover_id:
                out["cover"] = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
            out["language"] = doc.get("language")[0] if doc.get("language") else None
            return out
    return out


def download_cover(url: str) -> Optional[bytes]:
    try:
        os.makedirs(COVER_CACHE_DIR, exist_ok=True)
        import hashlib

        name = hashlib.sha1(url.encode("utf-8")).hexdigest() + ".jpg"
        cache_name = os.path.join(COVER_CACHE_DIR, name)
        if os.path.exists(cache_name):
            with open(cache_name, "rb") as f:
                logger.debug("Loaded cover from cache %s", cache_name)
                return f.read()
        b = http_download_bytes(url)
        try:
            with open(cache_name, "wb") as f:
                f.write(b)
            logger.debug("Cached cover to %s", cache_name)
        except Exception:
            logger.debug("Failed to cache cover %s", cache_name)
        return b
    except Exception as e:
        logger.warning("download_cover failed for %s: %s", url, e)
        return None


def update_epub_with_metadata(epub_path: str, meta: EpubMeta) -> bool:
    try:
        backup_file(epub_path)
    except Exception as e:
        meta.note = f"Backup failed: {e}"
        logger.exception("Backup failed for %s", epub_path)
        return False

    try:
        book = epub.read_epub(epub_path)
        if meta.suggested_title:
            try:
                book.set_title(meta.suggested_title)
            except Exception:
                logger.exception("Failed to set title for %s", epub_path)
        if meta.suggested_authors:
            try:
                for a in meta.suggested_authors:
                    book.add_author(a)
            except Exception:
                logger.exception("Failed to set authors for %s", epub_path)
        if meta.suggested_isbn:
            try:
                book.set_identifier(meta.suggested_isbn)
            except Exception:
                logger.exception("Failed to set identifier for %s", epub_path)
        if meta.suggested_language:
            try:
                book.set_language(meta.suggested_language)
            except Exception:
                logger.exception("Failed to set language for %s", epub_path)
        if meta.suggested_cover_url:
            content = download_cover(meta.suggested_cover_url)
            if content:
                try:
                    book.set_cover("cover.jpg", content)
                except Exception:
                    logger.exception("Failed to set cover for %s", epub_path)
        epub.write_epub(epub_path, book)
        logger.info("Updated EPUB %s with suggested metadata", epub_path)
        return True
    except Exception as e:
        meta.note = f"Error updating epub: {e}\n{traceback.format_exc()}"
        logger.exception("Error updating epub %s", epub_path)
        return False


# ---------- GUI ----------
class EnricherGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EPUB Metadata Enricher")
        self.geometry("1100x700")
        self.meta_list: List[EpubMeta] = []
        self.cover_photo_cache: Dict[str, "ImageTk.PhotoImage"] = {}

        self.create_widgets()

    def create_widgets(self):
        frm_top = ttk.Frame(self)
        frm_top.pack(fill=tk.X, padx=6, pady=6)

        self.folder_var = tk.StringVar()
        ttk.Entry(frm_top, textvariable=self.folder_var, width=80).pack(side=tk.LEFT, padx=4)
        ttk.Button(frm_top, text="Select folder", command=self.select_folder).pack(side=tk.LEFT)
        ttk.Button(frm_top, text="Scan", command=self.scan_folder).pack(side=tk.LEFT, padx=4)
        ttk.Button(
            frm_top, text="Fetch suggestions", command=self.fetch_suggestions_for_selected
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(frm_top, text="Apply accepted", command=self.apply_accepted).pack(
            side=tk.LEFT, padx=4
        )

        cols = (
            "filename",
            "orig_title",
            "suggested_title",
            "orig_authors",
            "suggested_authors",
            "orig_isbn",
            "suggested_isbn",
            "language",
            "status",
        )
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=18)
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=140, anchor="w")
        self.tree.column("filename", width=220)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=6)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X, padx=6, pady=6)
        left = ttk.Frame(bottom)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = ttk.Frame(bottom)
        right.pack(side=tk.RIGHT, fill=tk.Y)

        self.txt_before = tk.Text(left, height=8)
        self.txt_before.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.txt_after = tk.Text(left, height=8)
        self.txt_after.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.cover_label = ttk.Label(right, text="Cover preview")
        self.cover_label.pack()
        self.cover_canvas = tk.Label(right)
        self.cover_canvas.pack(padx=4, pady=4)

        ttk.Button(right, text="Accept suggestion", command=self.accept_selected).pack(
            fill=tk.X, padx=4, pady=2
        )
        ttk.Button(right, text="Reject suggestion", command=self.reject_selected).pack(
            fill=tk.X, padx=4, pady=2
        )
        ttk.Button(right, text="Save CSV", command=self.export_csv).pack(fill=tk.X, padx=4, pady=8)

    def select_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.folder_var.set(d)

    def scan_folder(self):
        folder = self.folder_var.get()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error", "Select a valid folder first")
            return
        files = find_epubs_in_folder(folder)
        self.meta_list = []
        for p in files:
            res = extract_metadata(p)
            em = EpubMeta(
                path=p,
                filename=os.path.basename(p),
                original_title=res.get("title"),
                original_authors=res.get("authors"),
                original_isbn=res.get("identifier"),
                original_language=res.get("language"),
            )
            self.meta_list.append(em)
        self.refresh_tree()

    def refresh_tree(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for idx, m in enumerate(self.meta_list):
            vals = (
                m.filename,
                m.original_title or "",
                m.suggested_title or "",
                ", ".join(m.original_authors) if m.original_authors else "",
                ", ".join(m.suggested_authors) if m.suggested_authors else "",
                m.original_isbn or "",
                m.suggested_isbn or "",
                m.suggested_language or m.original_language or "",
                "accepted" if m.accepted else ("processed" if m.processed else "idle"),
            )
            self.tree.insert("", "end", iid=str(idx), values=vals)

    def on_select(self, evt):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        meta = self.meta_list[idx]
        before = json.dumps(
            {
                "title": meta.original_title,
                "authors": meta.original_authors,
                "isbn": meta.original_isbn,
                "language": meta.original_language,
            },
            ensure_ascii=False,
            indent=2,
        )
        after = json.dumps(
            {
                "title": meta.suggested_title or meta.original_title,
                "authors": meta.suggested_authors or meta.original_authors,
                "isbn": meta.suggested_isbn or meta.original_isbn,
                "language": meta.suggested_language or meta.original_language,
            },
            ensure_ascii=False,
            indent=2,
        )
        self.txt_before.delete("1.0", tk.END)
        self.txt_before.insert(tk.END, before)
        self.txt_after.delete("1.0", tk.END)
        self.txt_after.insert(tk.END, after)
        if meta.suggested_cover_url:
            img = self.get_cover_image(meta.suggested_cover_url)
            if img:
                self.cover_canvas.configure(image=img)
                self.cover_canvas.image = img
                return
        self.cover_canvas.configure(image="")
        self.cover_canvas.image = None

    def get_cover_image(self, url: str):
        if url in self.cover_photo_cache:
            return self.cover_photo_cache[url]
        try:
            from PIL import ImageTk  # type: ignore
        except Exception:
            return None
        try:
            b = download_cover(url)
            if not b:
                return None
            pil = Image.open(BytesIO(b))
            pil.thumbnail((200, 300))
            tkimg = ImageTk.PhotoImage(pil)
            self.cover_photo_cache[url] = tkimg
            return tkimg
        except Exception:
            logger.exception("Failed to create preview image for %s", url)
            return None

    def fetch_suggestions_for_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Select one or more files in the list")
            return
        threading.Thread(target=self._fetch_thread, args=(sel,), daemon=True).start()

    def _fetch_thread(self, selection):
        changed = False
        for s in selection:
            idx = int(s)
            meta = self.meta_list[idx]
            try:
                suggested = extract_suggested_from_openlib(
                    meta.original_isbn, meta.original_title, meta.original_authors
                )
                meta.suggested_title = suggested.get("title") or meta.original_title
                meta.suggested_authors = suggested.get("authors") or meta.original_authors
                meta.suggested_isbn = suggested.get("isbn") or meta.original_isbn
                meta.suggested_language = suggested.get("language") or meta.original_language
                meta.suggested_cover_url = suggested.get("cover")
                meta.processed = True
                meta.note = "Suggestion fetched"
                changed = True
                logger.debug("Fetched suggestion for %s", meta.filename)
            except Exception as e:
                meta.note = f"Fetch error: {e}"
                logger.exception("Fetch suggestions error for %s", meta.filename)
        if changed:
            self.after(0, self.refresh_tree)

    def accept_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        for s in sel:
            idx = int(s)
            self.meta_list[idx].accepted = True
        self.refresh_tree()

    def reject_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        for s in sel:
            idx = int(s)
            self.meta_list[idx].accepted = False
            self.meta_list[idx].suggested_title = None
            self.meta_list[idx].suggested_authors = None
            self.meta_list[idx].suggested_isbn = None
            self.meta_list[idx].suggested_language = None
            self.meta_list[idx].suggested_cover_url = None
        self.refresh_tree()

    def apply_accepted(self):
        to_process = [m for m in self.meta_list if m.accepted]
        if not to_process:
            messagebox.showinfo("Info", "No accepted items to apply")
            return
        threading.Thread(target=self._apply_thread, args=(to_process,), daemon=True).start()

    def _apply_thread(self, metas: List[EpubMeta]):
        any_changed = False
        for m in metas:
            try:
                success = update_epub_with_metadata(m.path, m)
                m.processed = success
                m.note = "Updated" if success else (m.note or "Failed")
                any_changed = True
            except Exception as e:
                m.note = f"Error applying: {e}"
                logger.exception("Apply accepted failed for %s", m.filename)
        if any_changed:
            self.after(0, self.refresh_tree)
            self.after(
                0,
                lambda: messagebox.showinfo(
                    "Done", "Applied accepted changes (check backup folder if needed)"
                ),
            )

    def export_csv(self):
        p = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not p:
            return
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "filename",
                    "path",
                    "orig_title",
                    "orig_authors",
                    "orig_isbn",
                    "orig_lang",
                    "sugg_title",
                    "sugg_authors",
                    "sugg_isbn",
                    "sugg_lang",
                    "accepted",
                    "processed",
                    "note",
                ]
            )
            for m in self.meta_list:
                w.writerow(
                    [
                        m.filename,
                        m.path,
                        m.original_title,
                        ";".join(m.original_authors or []),
                        m.original_isbn,
                        m.original_language,
                        m.suggested_title,
                        ";".join(m.suggested_authors or []),
                        m.suggested_isbn,
                        m.suggested_language,
                        m.accepted,
                        m.processed,
                        m.note,
                    ]
                )


# ---------- CLI helpers (optional) ----------


def cli_process_folder(folder: str, autosave: bool = False):
    files = find_epubs_in_folder(folder)
    metas = []
    for p in files:
        res = extract_metadata(p)
        em = EpubMeta(
            path=p,
            filename=os.path.basename(p),
            original_title=res.get("title"),
            original_authors=res.get("authors"),
            original_isbn=res.get("identifier"),
            original_language=res.get("language"),
        )
        suggested = extract_suggested_from_openlib(
            em.original_isbn, em.original_title, em.original_authors
        )
        em.suggested_title = suggested.get("title") or em.original_title
        em.suggested_authors = suggested.get("authors") or em.original_authors
        em.suggested_isbn = suggested.get("isbn") or em.original_isbn
        em.suggested_language = suggested.get("language") or em.original_language
        em.suggested_cover_url = suggested.get("cover")
        metas.append(em)
        logger.info("Prepared suggestion for: %s", em.filename)
        if autosave and em.suggested_title:
            update_epub_with_metadata(p, em)
    return metas


def main() -> int:
    if os.getenv("EPUB_ENRICHER_NO_GUI") == "1":
        logger.info("NO_GUI mode: exiting without launching GUI")
        return 0
    logger.info("Starting EPUB Enricher GUI")
    try:
        app = EnricherGUI()
        app.mainloop()
        return 0
    except Exception:
        logger.exception("Fatal error in main loop")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
