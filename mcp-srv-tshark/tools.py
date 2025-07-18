import subprocess, json, os, asyncio, shlex
from pathlib import Path
PCAP_ROOT = (Path(__file__).resolve().parent / "pcaps").as_posix()
# PCAP_ROOT = os.path.abspath("pcaps")

def _safe_path(fname:str) -> str:
    path = os.path.abspath(os.path.join(PCAP_ROOT, fname))
    if not path.startswith(PCAP_ROOT):
        raise ValueError("Chemin PCAP interdit")
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    return path

# --------- Définition formelle transmise lors de tools/list -------
TOOL_DEFS = [{
    "name": "tshark_query",
    "description": "Exécute TShark sur un fichier pcap offline",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file": { "type": "string", "description": "Nom du fichier pcap (dans pcaps/)" },
            "filter": { "type": "string", "description": "Filtre d'affichage TShark (-Y)", "default": "" },
            # --- définition du schéma ---
            "limit": {
                "type": "integer",
                "description": "Nombre max de paquets (0 = aucune limite)",
                "default": 0                  
            }
        },
        "required": ["file"]
    }
}]

# --------- Implémentation réelle appelée via tools/call ----------

async def call_tool(name:str, args:dict):
    if name != "tshark_query":
        raise ValueError(f"Tool {name} non géré")

    file   = _safe_path(args["file"])
    flt    = args.get("filter", "")
    # --- implémentation ---
    limit = int(args.get("limit", 0))    # 0 si l’appelant ne précise rien

    cmd = ["tshark", "-r", file, "-T", "json"]
    if limit > 0:                        # ← n’ajoute -c QUE si > 0
        cmd += ["-c", str(limit)]
    if flt:
        cmd += ["-Y", flt]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    out_b, err_b = await proc.communicate()
    out = out_b.decode("utf-8", "replace")   # decode manually
    err = err_b.decode("utf-8", "replace")

    if proc.returncode != 0:
        raise RuntimeError(err.strip() or "TShark error")

    frames = json.loads(out)                 # now it’s a str
    summary = f"{len(frames)} paquets renvoyés pour filtre '{flt}'"
    return summary
