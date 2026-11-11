#!/usr/bin/env python3
"""API do Sistema de Achados e Perdidos (somente biblioteca padrão do Python).

Uso:  python3 server.py [porta]      (padrão: 8080)
Abra: http://localhost:8080          (serve o index.html e a API em /api)
"""
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "achados.db")

CATEGORIAS = {"documentos", "eletronicos", "roupas", "acessorios", "chaves", "bolsas_mochilas", "outros"}
STATUS_ITEM = {"achado", "perdido", "devolvido"}
STATUS_SOLIC = {"pendente", "aprovada", "recusada"}

SEED = [
    ("Fone de ouvido Bluetooth", "Fone sem fio branco, acompanhado de estojo de carregamento.", "eletronicos", "Biblioteca, mesa próxima à janela.", "2026-11-09T08:15:00-03:00"),
    ("Garrafa térmica", "Garrafa térmica azul-escura, com adesivo de estrela na lateral.", "outros", "Quadra esportiva.", "2026-11-09T09:30:00-03:00"),
    ("Mochila preta", "Mochila preta com três compartimentos e chaveiro de dinossauro.", "bolsas_mochilas", "Corredor do segundo andar.", "2026-11-09T10:00:00-03:00"),
    ("Carteira marrom", "Carteira de couro sintético marrom, contendo cartões sem identificação visível.", "acessorios", "Cantina, próxima ao caixa.", "2026-11-09T10:45:00-03:00"),
    ("Casaco de moletom", "Casaco cinza com capuz, tamanho médio e bolso frontal.", "roupas", "Sala 12.", "2026-11-09T11:20:00-03:00"),
    ("Chaveiro com chaves", "Argola metálica com três chaves e um chaveiro vermelho.", "chaves", "Estacionamento, próximo ao portão principal.", "2026-11-09T12:10:00-03:00"),
    ("Óculos de grau", "Óculos de armação preta, com estojo rígido azul.", "acessorios", "Laboratório de informática.", "2026-11-09T12:40:00-03:00"),
    ("Carregador de celular", "Carregador branco com cabo USB-C.", "eletronicos", "Sala de estudos.", "2026-11-09T13:00:00-03:00"),
    ("Guarda-chuva", "Guarda-chuva dobrável preto, com cabo emborrachado.", "outros", "Recepção.", "2026-11-09T13:25:00-03:00"),
    ("Caderno universitário", "Caderno de capa vermelha, com anotações de matemática nas primeiras páginas.", "outros", "Sala 08.", "2026-11-09T13:50:00-03:00"),
    ("Relógio de pulso", "Relógio digital preto com pulseira de borracha.", "acessorios", "Banheiro do bloco B.", "2026-11-09T14:05:00-03:00"),
    ("Pen drive", "Pen drive de 32 GB, vermelho e preto, com tampa.", "eletronicos", "Laboratório de informática, computador 06.", "2026-11-09T14:20:00-03:00"),
    ("Boné azul", "Boné azul-marinho com símbolo branco na parte frontal.", "roupas", "Arquibancada da quadra.", "2026-11-09T14:35:00-03:00"),
    ("Documento de identificação", "Documento encontrado dentro de um envelope transparente. Dados pessoais preservados.", "documentos", "Secretaria acadêmica.", "2026-11-09T14:50:00-03:00"),
    ("Bolsa feminina", "Bolsa pequena bege, com alça ajustável e fecho dourado.", "bolsas_mochilas", "Auditório principal.", "2026-11-09T15:00:00-03:00"),
]


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db():
    with db() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS itens (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              nome TEXT NOT NULL,
              descricao TEXT NOT NULL DEFAULT '',
              categoria TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'achado',
              local TEXT NOT NULL,
              data TEXT NOT NULL,
              foto TEXT NOT NULL DEFAULT '',
              contato TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS devolucoes (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              item_id INTEGER NOT NULL REFERENCES itens(id),
              solicitante TEXT NOT NULL,
              contato TEXT NOT NULL,
              mensagem TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pendente',
              data TEXT NOT NULL
            );
            """
        )
        if con.execute("SELECT COUNT(*) FROM itens").fetchone()[0] == 0:
            con.executemany(
                "INSERT INTO itens (nome, descricao, categoria, status, local, data) VALUES (?,?,?,'achado',?,?)",
                SEED,
            )


class ApiError(Exception):
    def __init__(self, code, msg):
        self.code, self.msg = code, msg


def txt(body, campo, obrigatorio=False, maximo=500):
    v = body.get(campo, "")
    v = "" if v is None else str(v).strip()
    if obrigatorio and not v:
        raise ApiError(422, f"Campo obrigatório: {campo}")
    if len(v) > maximo:
        raise ApiError(422, f"Campo '{campo}' excede {maximo} caracteres")
    return v


def valida_data(v):
    try:
        datetime.fromisoformat(v)
    except ValueError:
        raise ApiError(422, "Campo 'data' inválido (use ISO 8601, ex.: 2026-11-09T08:15:00-03:00)")
    return v


# ---------------- itens ----------------
def listar_itens(qs):
    sql, args = "SELECT * FROM itens WHERE 1=1", []
    if qs.get("categoria"):
        sql += " AND categoria = ?"; args.append(qs["categoria"])
    if qs.get("status"):
        sql += " AND status = ?"; args.append(qs["status"])
    if qs.get("q"):
        sql += " AND (nome LIKE ? OR descricao LIKE ? OR local LIKE ?)"
        args += [f"%{qs['q']}%"] * 3
    sql += " ORDER BY data DESC, id DESC"
    with db() as con:
        return [dict(r) for r in con.execute(sql, args)]


def obter_item(con, item_id):
    r = con.execute("SELECT * FROM itens WHERE id = ?", (item_id,)).fetchone()
    if not r:
        raise ApiError(404, "Objeto não encontrado")
    return dict(r)


def criar_item(body):
    categoria = txt(body, "categoria", True)
    if categoria not in CATEGORIAS:
        raise ApiError(422, "Categoria inválida. Use: " + ", ".join(sorted(CATEGORIAS)))
    status = txt(body, "status") or "achado"
    if status not in {"achado", "perdido"}:
        raise ApiError(422, "Status inicial deve ser 'achado' ou 'perdido'")
    nome = txt(body, "nome", True, 80)
    local = txt(body, "local", True, 200)
    data = valida_data(txt(body, "data", True, 40))
    with db() as con:
        cur = con.execute(
            "INSERT INTO itens (nome, descricao, categoria, status, local, data, foto, contato) VALUES (?,?,?,?,?,?,?,?)",
            (nome, txt(body, "descricao", maximo=1000), categoria, status, local, data,
             txt(body, "foto", maximo=500), txt(body, "contato", maximo=200)),
        )
        return obter_item(con, cur.lastrowid)


def atualizar_item(item_id, body):
    with db() as con:
        item = obter_item(con, item_id)
        status = body.get("status", item["status"])
        if status not in STATUS_ITEM:
            raise ApiError(422, "Status inválido. Use: " + ", ".join(sorted(STATUS_ITEM)))
        con.execute("UPDATE itens SET status = ? WHERE id = ?", (status, item_id))
        return obter_item(con, item_id)


# ---------------- devoluções ----------------
def formata_devolucao(r):
    d = dict(r)
    d["item"] = {"id": d["item_id"], "nome": d.pop("item_nome", None)}
    return d


def listar_devolucoes(qs):
    sql = ("SELECT d.*, i.nome AS item_nome FROM devolucoes d JOIN itens i ON i.id = d.item_id WHERE 1=1")
    args = []
    if qs.get("status"):
        sql += " AND d.status = ?"; args.append(qs["status"])
    if qs.get("item_id"):
        sql += " AND d.item_id = ?"; args.append(qs["item_id"])
    sql += " ORDER BY d.id DESC"
    with db() as con:
        return [formata_devolucao(r) for r in con.execute(sql, args)]


def criar_devolucao(body):
    try:
        item_id = int(body.get("item_id"))
    except (TypeError, ValueError):
        raise ApiError(422, "Campo obrigatório: item_id")
    solicitante = txt(body, "solicitante", True, 120)
    contato = txt(body, "contato", True, 200)
    mensagem = txt(body, "mensagem", True, 1000)
    with db() as con:
        item = obter_item(con, item_id)
        if item["status"] == "devolvido":
            raise ApiError(409, "Este objeto já foi devolvido")
        cur = con.execute(
            "INSERT INTO devolucoes (item_id, solicitante, contato, mensagem, status, data) VALUES (?,?,?,?, 'pendente', ?)",
            (item_id, solicitante, contato, mensagem, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        r = con.execute("SELECT d.*, i.nome AS item_nome FROM devolucoes d JOIN itens i ON i.id = d.item_id WHERE d.id = ?",
                        (cur.lastrowid,)).fetchone()
        return formata_devolucao(r)


def atualizar_devolucao(dev_id, body):
    status = body.get("status")
    if status not in STATUS_SOLIC:
        raise ApiError(422, "Status inválido. Use: " + ", ".join(sorted(STATUS_SOLIC)))
    with db() as con:
        r = con.execute("SELECT * FROM devolucoes WHERE id = ?", (dev_id,)).fetchone()
        if not r:
            raise ApiError(404, "Solicitação não encontrada")
        con.execute("UPDATE devolucoes SET status = ? WHERE id = ?", (status, dev_id))
        r = con.execute("SELECT d.*, i.nome AS item_nome FROM devolucoes d JOIN itens i ON i.id = d.item_id WHERE d.id = ?",
                        (dev_id,)).fetchone()
        return formata_devolucao(r)


# ---------------- HTTP ----------------
class Handler(BaseHTTPRequestHandler):
    server_version = "AchadosPerdidos/1.0"

    def _send(self, code, payload=None, ctype="application/json; charset=utf-8"):
        raw = b"" if payload is None else (payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode())
        self.send_response(code)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        if code != 204:
            self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 1_000_000:
            raise ApiError(413, "Corpo da requisição muito grande")
        if n == 0:
            return {}
        try:
            data = json.loads(self.rfile.read(n))
        except json.JSONDecodeError:
            raise ApiError(400, "JSON inválido")
        if not isinstance(data, dict):
            raise ApiError(400, "O corpo deve ser um objeto JSON")
        return data

    def _route(self, method):
        url = urlparse(self.path)
        path = url.path.rstrip("/") or "/"
        qs = {k: v[0] for k, v in parse_qs(url.query).items()}

        if method == "GET" and path in ("/", "/index.html"):
            with open(os.path.join(BASE, "index.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if path == "/api/health":
            return self._send(200, {"ok": True})

        m = re.fullmatch(r"/api/itens(?:/(\d+))?", path)
        if m:
            iid = int(m.group(1)) if m.group(1) else None
            if iid is None and method == "GET":
                return self._send(200, listar_itens(qs))
            if iid is None and method == "POST":
                return self._send(201, criar_item(self._body()))
            if iid is not None and method == "GET":
                with db() as con:
                    return self._send(200, obter_item(con, iid))
            if iid is not None and method in ("PATCH", "PUT"):
                return self._send(200, atualizar_item(iid, self._body()))

        m = re.fullmatch(r"/api/devolucoes(?:/(\d+))?", path)
        if m:
            did = int(m.group(1)) if m.group(1) else None
            if did is None and method == "GET":
                return self._send(200, listar_devolucoes(qs))
            if did is None and method == "POST":
                return self._send(201, criar_devolucao(self._body()))
            if did is not None and method in ("PATCH", "PUT"):
                return self._send(200, atualizar_devolucao(did, self._body()))

        raise ApiError(404, "Rota não encontrada")

    def _handle(self, method):
        try:
            if method == "OPTIONS":
                return self._send(204)
            self._route(method)
        except ApiError as e:
            self._send(e.code, {"erro": e.msg})
        except Exception as e:  # noqa: BLE001
            self._send(500, {"erro": "Erro interno do servidor"})
            print("ERRO:", repr(e), file=sys.stderr)

    do_GET = lambda self: self._handle("GET")
    do_POST = lambda self: self._handle("POST")
    do_PATCH = lambda self: self._handle("PATCH")
    do_PUT = lambda self: self._handle("PUT")
    do_OPTIONS = lambda self: self._handle("OPTIONS")

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 8080))
    init_db()
    print(f"Achados e Perdidos rodando em http://localhost:{port}  (API em /api)")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
