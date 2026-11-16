import csv, json, io, unicodedata, re, urllib.request, collections, datetime

BASE = "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/"
ANOS = [2023, 2024, 2025, 2026]
PLANTILLAS = ["atp_matches_%d.csv", "atp_matches_qual_chall_%d.csv"]
K = 24

def bajar(nombre):
    try:
        with urllib.request.urlopen(BASE + nombre, timeout=90) as r:
            return list(csv.DictReader(io.StringIO(r.read().decode("utf-8"))))
    except Exception as e:
        print("No se pudo bajar", nombre, e)
        return []

def clave(nombre):
    n = unicodedata.normalize("NFD", nombre).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^a-z ]", " ", n)
    return " ".join(sorted(n.split()))

def sup_de(s):
    if s == "Carpet":
        return "Hard"
    return s if s in ("Hard", "Clay", "Grass") else None

partidos = []
for a in ANOS:
    for p in PLANTILLAS:
        partidos += bajar(p % a)
partidos = [f for f in partidos if f.get("winner_name") and f.get("loser_name") and "W/O" not in (f.get("score") or "")]
partidos.sort(key=lambda f: (f["tourney_date"], int(f["match_num"] or 0)))
print("Partidos cargados:", len(partidos))

elo = collections.defaultdict(lambda: {"g": 1500, "Hard": 1500, "Clay": 1500, "Grass": 1500})
forma = collections.defaultdict(lambda: collections.deque(maxlen=10))
forma_sup = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.deque(maxlen=10)))
nombres, ultima, cuenta = {}, {}, collections.Counter()
stats = collections.defaultdict(collections.Counter)
torneos = collections.defaultdict(collections.Counter)
corte = (datetime.date.today() - datetime.timedelta(days=730)).strftime("%Y%m%d")

for f in partidos:
    kw, kl = clave(f["winner_name"]), clave(f["loser_name"])
    nombres[kw], nombres[kl] = f["winner_name"], f["loser_name"]
    sup = sup_de(f.get("surface"))
    fecha = f["tourney_date"]
    if sup:
        torneos[f["tourney_name"]][sup] += 1
    for campo in ["g"] + ([sup] if sup else []):
        ea = 1 / (1 + 10 ** ((elo[kl][campo] - elo[kw][campo]) / 400))
        elo[kw][campo] += K * (1 - ea)
        elo[kl][campo] -= K * (1 - ea)
    for k, r in ((kw, "W"), (kl, "L")):
        forma[k].append(r)
        if sup:
            forma_sup[k][sup].append(r)
        ultima[k] = fecha
        cuenta[k] += 1
    if fecha < corte:
        continue
    for yo, rival, k in (("w_", "l_", kw), ("l_", "w_", kl)):
        try:
            svpt = int(f[yo + "svpt"]); i1 = int(f[yo + "1stIn"])
            w1 = int(f[yo + "1stWon"]); w2 = int(f[yo + "2ndWon"])
            ace = int(f[yo + "ace"]); df = int(f[yo + "df"])
            bps = int(f[yo + "bpSaved"]); bpf = int(f[yo + "bpFaced"])
            rsv = int(f[rival + "svpt"])
            rw = int(f[rival + "1stWon"]) + int(f[rival + "2ndWon"])
        except (ValueError, KeyError):
            continue
        if svpt == 0 or rsv == 0:
            continue
        s = stats[k]
        s["n"] += 1; s["svpt"] += svpt; s["i1"] += i1; s["w1"] += w1; s["w2"] += w2
        s["ace"] += ace; s["df"] += df; s["bps"] += bps; s["bpf"] += bpf
        s["rsv"] += rsv; s["rw"] += rw

def pct(a, b):
    return round(100 * a / b, 1) if b else None

limite = (datetime.date.today() - datetime.timedelta(days=500)).strftime("%Y%m%d")
jugadores = {}
for k in elo:
    if ultima.get(k, "0") < limite:
        continue
    s = stats.get(k)
    j = {
        "n": nombres[k],
        "e": [round(elo[k]["g"]), round(elo[k]["Hard"]), round(elo[k]["Clay"]), round(elo[k]["Grass"])],
        "u": "".join(forma[k]),
        "us": {x: "".join(forma_sup[k][x]) for x in ("Hard", "Clay", "Grass")},
        "f": ultima[k],
    }
    if s and s["n"] >= 3:
        j["s"] = {
            "n": s["n"],
            "ace": pct(s["ace"], s["svpt"]), "df": pct(s["df"], s["svpt"]),
            "p1": pct(s["i1"], s["svpt"]), "g1": pct(s["w1"], s["i1"]),
            "g2": pct(s["w2"], s["svpt"] - s["i1"]),
            "bp": pct(s["bps"], s["bpf"]), "rt": pct(s["rw"], s["rsv"]),
        }
    jugadores[k] = j

salida = {
    "generado": datetime.date.today().isoformat(),
    "ultimo_dato": max(ultima.values()) if ultima else None,
    "jugadores": jugadores,
    "torneos": {t.lower(): c.most_common(1)[0][0] for t, c in torneos.items()},
}
with open("players.json", "w", encoding="utf-8") as fh:
    json.dump(salida, fh, separators=(",", ":"), ensure_ascii=False)
print("Jugadores guardados:", len(jugadores), "| ultimo dato:", salida["ultimo_dato"])
