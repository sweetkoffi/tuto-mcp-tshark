import subprocess, json, os, asyncio, shlex , re
from pathlib import Path


# --------- GLOBAL CONFIGURATION  -------

PCAP_ROOT           = (Path(__file__).resolve().parent / "pcaps").as_posix()
DEFAULT_TIMEOUT     = 30          # secondes
DEFAULT_MAX_BYTES   = 5_000_000   # 5 Mo de sortie max
ALLOWED_FIELDS_RE   = re.compile(r"^[A-Za-z0-9_.]+$")  # ip.src, tcp.port, etc.

# --------- HELPER - SAFETY POUR LECTURE DES FICHIERS PCAPS 

def _safe_path(fname:str) -> str:
    path = os.path.abspath(os.path.join(PCAP_ROOT, fname))
    if not path.startswith(PCAP_ROOT):
        raise ValueError("Chemin PCAP interdit")
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    return path

# --------- HELPER - LIMITE L'EXECUTION TROP LONGUE D'UNE COMMANDE

async def _run(cmd: list[str],
               timeout: int = DEFAULT_TIMEOUT,
               max_output_bytes: int = DEFAULT_MAX_BYTES,
               encoding: str = "utf-8") -> str:
    """
    Exécute `cmd` (liste d’arguments) de façon sécurisée :
      • time‑out                         → tue le processus
      • limite de taille de la sortie    → idem
      • renvoie toujours du texte décodé
    Lève RuntimeError en cas d’erreur Tshark ou de dépassement.
    """
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    try:
        out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"Timeout >{timeout}s pour {' '.join(cmd)}")

    if len(out_b) > max_output_bytes:
        proc.kill()
        raise RuntimeError(f"Sortie trop volumineuse (>{max_output_bytes} o)")

    if proc.returncode != 0:
        err = err_b.decode(encoding, "replace").strip() or "TShark error"
        raise RuntimeError(err)

    return out_b.decode(encoding, "replace")


# --------- HELPER - PERMET DE CHOISIR AUTOMATIQUEMENT LE BON FORMAT ENTRE JSON ET TSV/CSV  

def _parse_tshark_output(blob: str):
    head = blob.lstrip()[:2]
    if head in ("[", "{"):
        return json.loads(blob), "json"

    # TSV : chaque ligne = colonnes séparées par \t
    rows = [line.split("\t") for line in blob.strip().splitlines() if line]
    return rows, "tsv"


TOOL_DEFS = [
    {   # 1. Exécuter Tshark
        "name": "tshark_query",
        "description": "Exécute Tshark sur un fichier pcap offline",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "description": "Nom du pcap (dans pcaps/)"
                },
                "filter": {
                    "type": "string",
                    "description": "Display filter (-Y)"
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Champs à extraire (-T fields)"
                },
                "count": {
                    "type": "boolean",
                    "description": "true → renvoie seulement le nombre"
                },
                "limit": {
                    "type": "integer",
                    "description": "Max paquets (-c)"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout exécution (s)",
                    "default": 30
                },
                "max_output": {
                    "type": "integer",
                    "description": "Taille max sortie (octets)",
                    "default": 5_000_000
                }
            },
            "required": ["file"]
        }
    },
    {   # 2. Lister les pcaps disponibles
        "name": "enum_pcaps",
        "description": "Liste les fichiers pcap disponibles dans le dépôt",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {   # 3. Vérifier la syntaxe d'un display‑filter
        "name": "verif_syntax",
        "description": "Vérifie qu’un display‑filter Wireshark est syntaxiquement valide",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "description": "Display filter à tester"
                }
            },
            "required": ["filter"]
        }
    },
    {   # 4. Résumer / extraire des stats
        "name": "summary",
        "description": "Produit un résumé statistique à partir du JSON renvoyé par tshark_query",
        "inputSchema": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "string",
                    "description": "Blob brut retourné par tshark_query"
                },
                "operation": {
                    "type": "string",
                    "description": "unique, top, count"
                },
                "column": {
                    "type": "integer",
                    "description": "Index colonne (TSV) – défaut 0"
                },
                "param": {
                    "type": "integer",
                    "description": "Paramètre pour 'top' (ex : N)"
                },
                "json_path": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Chemin de clés pour JSON (optionnel)"
                }
            },
            "required": ["data", "operation"]
        }
    }
]

# --------- IMPLEMENTATION D'UN DISPATCHER POUR L'UTILISATION D'UNE REQUETE TSHARK  -------


async def call_tool(name: str, args: dict):
    """Router principal : exécute l’un des quatre tools métier."""

    # ------------------------------------------------------------------ #
    #  enum_pcaps  – liste le dépôt
    # ------------------------------------------------------------------ #
    if name == "enum_pcaps":
        return sorted(os.listdir(PCAP_ROOT))

    # ------------------------------------------------------------------ #
    #  verif_syntax – valide la grammaire d’un display‑filter
    # ------------------------------------------------------------------ #
    if name == "verif_syntax":
        flt = args["filter"]
        # Utilise -c0 et /dev/null pour que Tshark parse juste le filtre.
        await _run(["tshark", "-r", "/dev/null", "-Y", flt, "-c", "0"], timeout=5)
        return "OK"

    # ------------------------------------------------------------------ #
    #  tshark_query – extraction effective
    # ------------------------------------------------------------------ #
    if name == "tshark_query":
        file       = _safe_path(args["file"])
        flt        = args.get("filter", "")
        fields     = args.get("fields", [])
        want_count = bool(args.get("count", False))
        limit      = int(args.get("limit", 0))

        # Validation basique des noms de champs
        for f in fields:
            if not ALLOWED_FIELDS_RE.fullmatch(f):
                raise ValueError(f"Champ illégal : {f!r}")

        # Construction progressive de la commande
        cmd = ["tshark", "-r", file]

        if want_count:
            # Compte seulement les paquets (format ek + statistique io,phs).
            cmd += ["-T", "ek", "-z", "io,phs"]
        elif fields:
            cmd += ["-T", "fields"]
            for f in fields:
                cmd += ["-e", f]
        else:
            cmd += ["-T", "json"]

        if limit and limit > 0:
            cmd += ["-c", str(limit)]
        if flt:
            cmd += ["-Y", flt]

        # Autorise override du timeout / max_output via args optionnels
        timeout = int(args.get("timeout", DEFAULT_TIMEOUT))
        maxout  = int(args.get("max_output", DEFAULT_MAX_BYTES))

        result_text = await _run(cmd, timeout=timeout, max_output_bytes=maxout)
        return result_text

    # ------------------------------------------------------------------ #
    #  summary – post‑traitement sur le JSON
    # ------------------------------------------------------------------ #
        if name == "summary":
            data_raw  = args["data"]
            op        = args["operation"]          # ex : "unique", "top", "count"
            column    = int(args.get("column", 0)) # quelle colonne pour TSV
            top_n     = int(args.get("param", 10))

            parsed, fmt = _parse_tshark_output(data_raw)

            # ----- JSON branch -------------------------------------------------
            if fmt == "json":
                if op == "count":
                    return len(parsed)

                if op == "unique":
                    # path peut être passé dans args : ip.src etc.
                    path = args.get("json_path") or ["layers", "ip", "ip.src"]
                    vals = []
                    for fr in parsed:
                        cur = fr
                        for p in path:
                            cur = cur.get(p, {})
                        if cur:
                            vals.append(cur)
                    return sorted(set(vals))

                if op == "top":
                    from collections import Counter
                    path = args.get("json_path") or ["layers", "ip", "ip.src"]
                    vals = []
                    for fr in parsed:
                        cur = fr
                        for p in path:
                            cur = cur.get(p, {})
                        if cur:
                            vals.append(cur)
                    return Counter(vals).most_common(top_n)

                raise ValueError(f"Operation {op} inconnue pour JSON")

            # ----- TSV branch --------------------------------------------------
            if fmt == "tsv":
                if op == "count":
                    return len(parsed)

                if op == "unique":
                    vals = {row[column] for row in parsed if len(row) > column}
                    return sorted(vals)

                if op == "top":
                    from collections import Counter
                    vals = [row[column] for row in parsed if len(row) > column]
                    return Counter(vals).most_common(top_n)

                raise ValueError(f"Operation {op} inconnue pour TSV")

            raise RuntimeError("Format non reconnu")

        # ------------------------------------------------------------------ #
        #  tool non reconnu
        # ------------------------------------------------------------------ #
        raise ValueError(f"Tool {name!r} non géré")
