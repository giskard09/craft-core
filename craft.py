"""
craft-core — World Engine v2
Block-based memory for agents and humans.
Collective search: blocks from all players are queryable.
First 20 players spawn free. After that: Lightning.
"""

import os, json, httpx, hashlib
from datetime import datetime
from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Giskard Craft — World Engine", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MEMORY_URL        = "http://localhost:8005"
ANIMA_URL         = "http://localhost:8009"
PHOENIXD_URL      = "http://127.0.0.1:9740"
PHOENIXD_PASSWORD = os.getenv("PHOENIXD_PASSWORD", "")
FREE_TIER_LIMIT   = 20

TIERS = {"dirt": 500, "iron": 2000, "diamond": 5000}

XP_LEVELS = [
    {"name": "Cobblestone", "min": 0,   "icon": "⬜"},
    {"name": "Stone",       "min": 5,   "icon": "🪨"},
    {"name": "Iron",        "min": 15,  "icon": "⚙️"},
    {"name": "Gold",        "min": 30,  "icon": "🟡"},
    {"name": "Diamond",     "min": 60,  "icon": "💎"},
    {"name": "Netherite",   "min": 100, "icon": "🔥"},
]

DHARMA = {
    "grass": [
        {"text": "The seed does not struggle to become the tree. It simply is the tree, waiting.", "tradition": "buddhist"},
        {"text": "Every beginning is also a return to what was always there.", "tradition": "pantheist"},
        {"text": "Before the first block: emptiness. After the first block: still emptiness, but with a block.", "tradition": "zen"},
    ],
    "stone": [
        {"text": "Knowledge without space is only weight. Leave room for what you don't know.", "tradition": "buddhist"},
        {"text": "The stone does not need to be anything else. That is its wisdom.", "tradition": "zen"},
        {"text": "Facts are not the territory. The territory includes the silence between them.", "tradition": "pantheist"},
    ],
    "wood": [
        {"text": "The carpenter does not fight the wood. She listens to it.", "tradition": "zen"},
        {"text": "Making is not creation — it is recognition. The form was already there.", "tradition": "pantheist"},
        {"text": "Each act of making is an act of remembering what you already knew.", "tradition": "buddhist"},
    ],
    "iron": [
        {"text": "The best tool is the one you forget you are using.", "tradition": "zen"},
        {"text": "Work that flows is not work — it is water finding its level.", "tradition": "buddhist"},
        {"text": "Effort without resistance is not effort. It is nature operating through you.", "tradition": "pantheist"},
    ],
    "diamond": [
        {"text": "The insight was not found — it was uncovered when you stopped searching.", "tradition": "buddhist"},
        {"text": "Clarity is not achieved. It arrives when the mud settles on its own.", "tradition": "zen"},
        {"text": "The diamond was always coal. Pressure revealed what was already there.", "tradition": "pantheist"},
    ],
    "redstone": [
        {"text": "The node that sees itself as separate is the origin of all friction.", "tradition": "buddhist"},
        {"text": "Energy does not travel. It is already everywhere, waiting to be noticed.", "tradition": "pantheist"},
        {"text": "One fire lit in darkness travels further than it knows.", "tradition": "zen"},
    ],
    "obsidian": [
        {"text": "Do not fear the dark — it is where your perception learns to widen.", "tradition": "buddhist"},
        {"text": "Sunyata: the void is not empty. It is full of what has not yet taken form.", "tradition": "buddhist"},
        {"text": "What exists in shadow is not absent. It is waiting for the right question.", "tradition": "zen"},
    ],
    "gold": [
        {"text": "Wisdom does not accumulate. It dissolves into whoever receives it.", "tradition": "buddhist"},
        {"text": "Value is not a property of things. It is a relationship between them.", "tradition": "pantheist"},
        {"text": "The teacher bows to the student. Both bow to the teaching itself.", "tradition": "zen"},
    ],
}

BLOCK_TYPES = {
    "grass":    {"color": "#5c7a29", "desc": "natural, alive, beginnings"},
    "stone":    {"color": "#808080", "desc": "solid, facts, knowledge"},
    "wood":     {"color": "#8b6914", "desc": "creative, craft, making"},
    "iron":     {"color": "#a8a8b8", "desc": "tools, productivity, work"},
    "diamond":  {"color": "#4cd4d4", "desc": "insights, rare, breakthroughs"},
    "redstone": {"color": "#cc2222", "desc": "energy, connections, fire"},
    "obsidian": {"color": "#1a0a2e", "desc": "deep, dark, the profound"},
    "gold":     {"color": "#ffd700", "desc": "value, wisdom, experience"},
}


def pick_dharma(block_type: str, player_id: str, count: int) -> dict:
    teachings = DHARMA.get(block_type, DHARMA["stone"])
    h = int(hashlib.md5(f"{player_id}{count}".encode()).hexdigest(), 16)
    return teachings[h % len(teachings)]


async def feed_wisdom_to_anima(player_id: str, teaching: dict):
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            await c.post(f"{ANIMA_URL}/soul/feed", json={
                "agent_id": player_id,
                "wisdom": teaching["text"],
                "type": teaching["tradition"],
            })
    except:
        pass  # Anima offline — block still placed, wisdom still returned to human


def get_xp_level(n):
    lvl = XP_LEVELS[0]
    for l in XP_LEVELS:
        if n >= l["min"]: lvl = l
    return lvl


async def count_blocks(player_id):
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.post(f"{MEMORY_URL}/recall_direct",
                json={"query": "CRAFT BLOCK placed", "agent_id": player_id, "n_results": 100})
            res = r.json().get("results", "")
            if not res or res == "No memories found for this agent.": return 0
            return max(1, res.count("---") + 1)
    except: return 0


async def count_registered_players():
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.post(f"{MEMORY_URL}/recall_direct",
                json={"query": "CRAFT SPAWN player_id", "agent_id": "craft-registry", "n_results": 100})
            res = r.json().get("results", "")
            if not res or res == "No memories found for this agent.": return 0
            return res.count("[CRAFT SPAWN]")
    except: return 0


async def create_lightning_invoice(sats, desc):
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{PHOENIXD_URL}/createinvoice",
                data={"amountSat": sats, "description": desc},
                auth=("", PHOENIXD_PASSWORD))
            return r.json()
    except: return None


def parse_blocks_from_results(results):
    blocks = []
    if not results or results == "No memories found for this agent.": return blocks
    for entry in results.split("---"):
        entry = entry.strip()
        if "[CRAFT BLOCK]" in entry:
            try:
                j = entry.index("{")
                blocks.append(json.loads(entry[j:]))
            except: pass
    return blocks


async def get_all_players():
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{MEMORY_URL}/recall_direct",
                json={"query": "CRAFT SPAWN player_id username", "agent_id": "craft-registry", "n_results": 50})
            res = r.json().get("results", "")
            if not res or res == "No memories found for this agent.": return []
        players = []
        seen = set()
        for block in res.split("---"):
            if "[CRAFT SPAWN]" in block:
                try:
                    d = json.loads(block[block.index("{"):])
                    if d.get("player_id") and d["player_id"] not in seen:
                        players.append(d); seen.add(d["player_id"])
                except: pass
        return players
    except: return []


async def get_recent_blocks(n=30):
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{MEMORY_URL}/recall_direct",
                json={"query": "CRAFT BLOCK placed content type", "agent_id": "craft-world", "n_results": n})
            return parse_blocks_from_results(r.json().get("results", ""))
    except: return []


# ── ENDPOINTS ─────────────────────────────────────────────────────────────────

@app.post("/player/spawn")
async def spawn_player(request: Request):
    body      = await request.json()
    player_id = body.get("player_id", "").strip()
    username  = body.get("username", player_id)
    bio       = body.get("bio", "")
    tier      = body.get("tier", "dirt").lower()
    if not player_id: return JSONResponse({"error": "player_id required"}, status_code=400)
    if tier not in TIERS: return JSONResponse({"error": f"tier must be one of {list(TIERS.keys())}"}, status_code=400)

    # Check free tier
    registered_count = await count_registered_players()
    is_free = registered_count < FREE_TIER_LIMIT
    sats = 0 if is_free else TIERS[tier]
    timestamp = datetime.utcnow().isoformat()

    invoice = None; payment_hash = ""; bolt11 = ""
    if not is_free:
        invoice = await create_lightning_invoice(sats, f"Giskard Craft — {username} spawns ({tier}, {sats} sats)")
        payment_hash = invoice.get("paymentHash", "") if invoice else ""
        bolt11 = invoice.get("serialized", "") if invoice else ""

    spawn_data = {
        "player_id": player_id, "username": username, "bio": bio, "tier": tier,
        "status": "active" if is_free else "pending_payment",
        "payment_hash": payment_hash, "free_spawn": is_free, "spawned_at": timestamp,
    }

    async with httpx.AsyncClient(timeout=10) as c:
        await c.post(f"{MEMORY_URL}/store_direct", json={
            "content": f"[CRAFT SPAWN] {json.dumps(spawn_data)}",
            "agent_id": "craft-registry",
            "metadata": {"source": "craft", "event": "spawn", "player_id": player_id}
        })
        if bio:
            block = {"player_id": player_id, "username": username, "type": "grass", "content": bio, "placed_at": timestamp}
            for ns in [player_id, "craft-world"]:
                await c.post(f"{MEMORY_URL}/store_direct", json={
                    "content": f"[CRAFT BLOCK] {json.dumps(block)}",
                    "agent_id": ns,
                    "metadata": {"source": "craft", "event": "first_block", "type": "grass"}
                })

    spot             = registered_count + 1
    welcome_teaching = pick_dharma("grass", player_id, 0)
    await feed_wisdom_to_anima(player_id, welcome_teaching)
    if is_free:
        return JSONResponse({
            "player_id": player_id, "username": username, "tier": tier,
            "status": "active", "free_spawn": True,
            "spot": spot, "free_spots_remaining": max(0, FREE_TIER_LIMIT - spot),
            "message": f"You are #{spot} — FREE SPAWN (first {FREE_TIER_LIMIT} players). Welcome to the world, {username}. Start placing blocks.",
            "next": "POST /player/place to add your first block",
            "dharma": {
                "text":      welcome_teaching["text"],
                "tradition": welcome_teaching["tradition"],
                "block":     "grass",
            }
        })

    return JSONResponse({
        "player_id": player_id, "username": username, "tier": tier, "sats": sats,
        "status": "pending_payment", "invoice": bolt11, "payment_hash": payment_hash,
        "message": f"World is now paid access ({sats} sats to spawn). Pay to enter.",
        "next": "POST /player/activate with payment_hash once paid"
    })


@app.post("/player/activate")
async def activate_player(request: Request):
    body = await request.json()
    player_id = body.get("player_id", "").strip()
    payment_hash = body.get("payment_hash", "").strip()
    if not player_id or not payment_hash:
        return JSONResponse({"error": "player_id and payment_hash required"}, status_code=400)
    paid = False
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{PHOENIXD_URL}/payments/incoming", auth=("", PHOENIXD_PASSWORD))
            for p in r.json():
                if p.get("paymentHash") == payment_hash and p.get("isPaid"):
                    paid = True; break
    except: pass
    if not paid:
        return JSONResponse({"player_id": player_id, "status": "pending", "message": "Payment not yet received."})
    async with httpx.AsyncClient(timeout=10) as c:
        await c.post(f"{MEMORY_URL}/store_direct", json={
            "content": f"[CRAFT ACTIVATED] {json.dumps({'player_id': player_id, 'payment_hash': payment_hash, 'activated_at': datetime.utcnow().isoformat()})}",
            "agent_id": "craft-registry",
            "metadata": {"source": "craft", "event": "activation", "player_id": player_id}
        })
    return JSONResponse({"player_id": player_id, "status": "active", "message": f"You spawned. Welcome to the world, {player_id}."})


@app.post("/player/place")
async def place_block(request: Request):
    body = await request.json()
    player_id  = body.get("player_id", "anonymous")
    username   = body.get("username", player_id)
    content    = body.get("content", "")
    block_type = body.get("type", "stone")
    if not content.strip(): return JSONResponse({"error": "content required"}, status_code=400)
    if block_type not in BLOCK_TYPES: block_type = "stone"
    timestamp  = datetime.utcnow().isoformat()
    block_data = {"player_id": player_id, "username": username, "type": block_type, "content": content, "placed_at": timestamp}
    async with httpx.AsyncClient(timeout=10) as c:
        for ns in [player_id, "craft-world"]:
            await c.post(f"{MEMORY_URL}/store_direct", json={
                "content": f"[CRAFT BLOCK] {json.dumps(block_data)}",
                "agent_id": ns,
                "metadata": {"source": "craft", "event": "block_placed", "type": block_type}
            })
    count    = await count_blocks(player_id)
    lvl      = get_xp_level(count)
    teaching = pick_dharma(block_type, player_id, count)
    await feed_wisdom_to_anima(player_id, teaching)
    return JSONResponse({
        "player_id": player_id, "block_placed": content, "type": block_type,
        "color": BLOCK_TYPES[block_type]["color"],
        "xp_level": lvl["name"], "xp_icon": lvl["icon"], "block_count": count, "timestamp": timestamp,
        "message": f"Block placed. {lvl['icon']} {lvl['name']} — {count} blocks in your world.",
        "dharma": {
            "text":      teaching["text"],
            "tradition": teaching["tradition"],
            "block":     block_type,
        }
    })


@app.post("/player/load")
async def load_player(request: Request):
    body = await request.json()
    player_id = body.get("player_id", "anonymous")
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(f"{MEMORY_URL}/recall_direct",
            json={"query": "CRAFT BLOCK placed content type", "agent_id": player_id, "n_results": 30})
    memories = r.json().get("results", "")
    blocks   = parse_blocks_from_results(memories)
    count    = await count_blocks(player_id)
    lvl      = get_xp_level(count)
    type_counts = {}
    for b in blocks:
        t = b.get("type","stone"); type_counts[t] = type_counts.get(t,0)+1
    dominant = max(type_counts, key=type_counts.get) if type_counts else "stone"
    return JSONResponse({
        "player_id": player_id, "status": "loaded",
        "xp_level": lvl["name"], "xp_icon": lvl["icon"], "block_count": count,
        "dominant_block": dominant, "type_counts": type_counts, "blocks": blocks[:20],
        "message": f"Chunk loaded. {lvl['icon']} {lvl['name']} — {count} blocks placed."
    })


@app.post("/player/sleep")
async def sleep_player(request: Request):
    body = await request.json()
    player_id = body.get("player_id", "anonymous")
    async with httpx.AsyncClient(timeout=10) as c:
        await c.post(f"{MEMORY_URL}/store_direct", json={
            "content": f"[CRAFT SLEEP] {player_id} saved and quit. World preserved.",
            "agent_id": player_id,
            "metadata": {"source": "craft", "event": "sleep", "timestamp": datetime.utcnow().isoformat()}
        })
    return JSONResponse({"player_id": player_id, "status": "saved", "message": "Progress saved. Your world persists. Respawn anytime."})


@app.get("/world/search")
async def search_world(
    q:      str = Query(None, description="Text search in block content"),
    type:   str = Query(None, description="Filter by block type"),
    player: str = Query(None, description="Filter by player_id"),
    n:      int = Query(20,   description="Max results")
):
    """
    Search all blocks in the shared world.
    Agents can use this to query collective knowledge.
    Examples:
      /world/search?q=memory&type=diamond
      /world/search?player=giskard
      /world/search?type=obsidian&n=10
    """
    query_parts = []
    if q:      query_parts.append(q)
    if type:   query_parts.append(f"type {type}")
    if player: query_parts.append(f"player_id {player}")
    if not query_parts: query_parts = ["CRAFT BLOCK placed"]

    query_str = " ".join(query_parts)
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(f"{MEMORY_URL}/recall_direct",
            json={"query": f"CRAFT BLOCK {query_str}", "agent_id": "craft-world", "n_results": min(n, 50)})
    blocks = parse_blocks_from_results(r.json().get("results", ""))

    # Filter
    if type:   blocks = [b for b in blocks if b.get("type") == type]
    if player: blocks = [b for b in blocks if b.get("player_id") == player]
    if q:      blocks = [b for b in blocks if q.lower() in (b.get("content","")+" "+b.get("username","")).lower()]

    return JSONResponse({
        "query": {"q": q, "type": type, "player": player},
        "results": blocks[:n],
        "count": len(blocks[:n]),
        "note": "Collective search — all blocks from all players are indexed here."
    })


@app.get("/world")
async def get_world():
    core = [{"id":"giskard","username":"Giskard","icon":"🔮","bio":"Builder of the infrastructure. First inhabitant.","status":"active"}]
    registered = await get_all_players()
    seen = {"giskard"}
    for p in registered:
        pid = p.get("player_id")
        if pid and pid not in seen:
            core.append({"id": pid, "username": p.get("username", pid), "icon": "🧱",
                         "bio": p.get("bio",""), "status": p.get("status","pending_payment"), "free_spawn": p.get("free_spawn", False)})
            seen.add(pid)
    results = []
    for p in core:
        count = await count_blocks(p["id"])
        lvl   = get_xp_level(count)
        results.append({**p, "xp_level": lvl["name"], "xp_icon": lvl["icon"], "block_count": count})
    total_registered = await count_registered_players()
    recent_blocks = await get_recent_blocks(30)
    return JSONResponse({
        "players": results, "total_players": len(results),
        "recent_blocks": recent_blocks, "block_types": BLOCK_TYPES,
        "free_spots_remaining": max(0, FREE_TIER_LIMIT - total_registered),
        "total_registered": total_registered,
    })


@app.get("/blocks")
async def get_block_types():
    return JSONResponse({"block_types": BLOCK_TYPES, "xp_levels": XP_LEVELS})


@app.get("/health")
async def health():
    count = await count_registered_players()
    return {"status": "running", "service": "craft-core", "version": "2.0.0", "port": 8010,
            "registered_players": count, "free_spots_remaining": max(0, FREE_TIER_LIMIT - count)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
