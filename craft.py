"""
craft-core — World Engine
Block-based memory for humans. You spawn, you build, you accumulate XP.
Each block placed is stored in giskard-memory. Your world persists.
"""

import os
import json
import httpx
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Giskard Craft — World Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MEMORY_URL        = "http://localhost:8005"
PHOENIXD_URL      = "http://127.0.0.1:9740"
PHOENIXD_PASSWORD = os.getenv("PHOENIXD_PASSWORD", "574fd439f0c07fc0c540f8245554440412c15ff5cfc0469a65f9879e70133c23")

# Spawn tiers — what you pay to enter the world
TIERS = {
    "dirt":    500,
    "iron":   2000,
    "diamond": 5000,
}

# XP levels — how many blocks you've placed
XP_LEVELS = [
    {"name": "Cobblestone", "min": 0,   "icon": "⬜"},
    {"name": "Stone",       "min": 5,   "icon": "🪨"},
    {"name": "Iron",        "min": 15,  "icon": "⚙️"},
    {"name": "Gold",        "min": 30,  "icon": "🟡"},
    {"name": "Diamond",     "min": 60,  "icon": "💎"},
    {"name": "Netherite",   "min": 100, "icon": "🔥"},
]

# Block types — what kind of thing you're building
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


def get_xp_level(block_count: int) -> dict:
    level = XP_LEVELS[0]
    for l in XP_LEVELS:
        if block_count >= l["min"]:
            level = l
    return level


async def count_blocks(player_id: str) -> int:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.post(f"{MEMORY_URL}/recall_direct", json={
                "query": "CRAFT BLOCK placed",
                "agent_id": player_id,
                "n_results": 100
            })
            data = r.json()
            results = data.get("results", "")
            if not results or results == "No memories found for this agent.":
                return 0
            return max(1, results.count("---") + 1)
    except:
        return 0


async def create_lightning_invoice(sats: int, description: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{PHOENIXD_URL}/createinvoice",
                data={"amountSat": sats, "description": description},
                auth=("", PHOENIXD_PASSWORD),
            )
            return r.json()
    except:
        return None


async def get_all_players() -> list:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{MEMORY_URL}/recall_direct", json={
                "query": "CRAFT SPAWN player_id username",
                "agent_id": "craft-registry",
                "n_results": 50
            })
            data = r.json()
            results = data.get("results", "")
            if not results or results == "No memories found for this agent.":
                return []

        players = []
        for block in results.split("---"):
            block = block.strip()
            if "[CRAFT SPAWN]" in block:
                try:
                    json_start = block.index("{")
                    player_data = json.loads(block[json_start:])
                    players.append(player_data)
                except (ValueError, json.JSONDecodeError):
                    pass
        return players
    except:
        return []


async def get_recent_blocks(n: int = 20) -> list:
    """Get the most recent blocks placed across all players."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{MEMORY_URL}/recall_direct", json={
                "query": "CRAFT BLOCK placed content type",
                "agent_id": "craft-world",
                "n_results": n
            })
            data = r.json()
            results = data.get("results", "")
            if not results or results == "No memories found for this agent.":
                return []

        blocks = []
        for entry in results.split("---"):
            entry = entry.strip()
            if "[CRAFT BLOCK]" in entry:
                try:
                    json_start = entry.index("{")
                    block_data = json.loads(entry[json_start:])
                    blocks.append(block_data)
                except (ValueError, json.JSONDecodeError):
                    pass
        return blocks
    except:
        return []


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/player/spawn")
async def spawn_player(request: Request):
    """Register a new player. Returns Lightning invoice to enter the world."""
    body     = await request.json()
    player_id = body.get("player_id", "").strip()
    username  = body.get("username", player_id)
    bio       = body.get("bio", "")
    tier      = body.get("tier", "dirt").lower()

    if not player_id:
        return JSONResponse({"error": "player_id required"}, status_code=400)
    if tier not in TIERS:
        return JSONResponse({"error": f"tier must be one of {list(TIERS.keys())}"}, status_code=400)

    sats = TIERS[tier]
    timestamp = datetime.utcnow().isoformat()

    invoice = await create_lightning_invoice(
        sats,
        f"Giskard Craft — {username} spawns in the world ({tier} tier, {sats} sats)"
    )

    payment_hash = invoice.get("paymentHash", "") if invoice else ""
    bolt11       = invoice.get("serialized", "") if invoice else ""

    spawn_data = {
        "player_id":    player_id,
        "username":     username,
        "bio":          bio,
        "tier":         tier,
        "status":       "pending_payment",
        "payment_hash": payment_hash,
        "spawned_at":   timestamp,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        # Register in craft-registry
        await client.post(f"{MEMORY_URL}/store_direct", json={
            "content":  f"[CRAFT SPAWN] {json.dumps(spawn_data)}",
            "agent_id": "craft-registry",
            "metadata": {"source": "craft", "event": "spawn", "player_id": player_id}
        })
        # First block — identity
        if bio:
            await client.post(f"{MEMORY_URL}/store_direct", json={
                "content":  f"[CRAFT BLOCK] {json.dumps({'player_id': player_id, 'username': username, 'type': 'grass', 'content': bio, 'placed_at': timestamp})}",
                "agent_id": player_id,
                "metadata": {"source": "craft", "event": "first_block", "type": "grass"}
            })
            # Also in world log
            await client.post(f"{MEMORY_URL}/store_direct", json={
                "content":  f"[CRAFT BLOCK] {json.dumps({'player_id': player_id, 'username': username, 'type': 'grass', 'content': bio, 'placed_at': timestamp})}",
                "agent_id": "craft-world",
                "metadata": {"source": "craft", "event": "block_placed", "type": "grass"}
            })

    return JSONResponse({
        "player_id":    player_id,
        "username":     username,
        "tier":         tier,
        "sats":         sats,
        "status":       "pending_payment",
        "invoice":      bolt11,
        "payment_hash": payment_hash,
        "message":      f"You are about to enter the world, {username}. Pay {sats} sats to spawn.",
        "next":         "POST /player/activate with payment_hash once paid"
    })


@app.post("/player/activate")
async def activate_player(request: Request):
    """Check payment and activate player in the world."""
    body         = await request.json()
    player_id    = body.get("player_id", "").strip()
    payment_hash = body.get("payment_hash", "").strip()

    if not player_id or not payment_hash:
        return JSONResponse({"error": "player_id and payment_hash required"}, status_code=400)

    paid = False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{PHOENIXD_URL}/payments/incoming",
                auth=("", PHOENIXD_PASSWORD),
            )
            payments = r.json()
            for p in payments:
                if p.get("paymentHash") == payment_hash and p.get("isPaid"):
                    paid = True
                    break
    except:
        pass

    if not paid:
        return JSONResponse({
            "player_id": player_id,
            "status":    "pending",
            "message":   "Payment not yet received. Try again in a moment."
        })

    timestamp = datetime.utcnow().isoformat()
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(f"{MEMORY_URL}/store_direct", json={
            "content":  f"[CRAFT ACTIVATED] {json.dumps({'player_id': player_id, 'payment_hash': payment_hash, 'activated_at': timestamp})}",
            "agent_id": "craft-registry",
            "metadata": {"source": "craft", "event": "activation", "player_id": player_id}
        })

    return JSONResponse({
        "player_id": player_id,
        "status":    "active",
        "message":   f"You spawned. Welcome to the world, {player_id}. Start placing blocks."
    })


@app.post("/player/place")
async def place_block(request: Request):
    """Place a block — store a thought, idea, or experience in your world."""
    body      = await request.json()
    player_id = body.get("player_id", "anonymous")
    username  = body.get("username", player_id)
    content   = body.get("content", "")
    block_type = body.get("type", "stone")

    if not content.strip():
        return JSONResponse({"error": "content required — what are you placing?"}, status_code=400)
    if block_type not in BLOCK_TYPES:
        block_type = "stone"

    timestamp  = datetime.utcnow().isoformat()
    block_data = {
        "player_id": player_id,
        "username":  username,
        "type":      block_type,
        "content":   content,
        "placed_at": timestamp,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        # Store in player's own namespace
        await client.post(f"{MEMORY_URL}/store_direct", json={
            "content":  f"[CRAFT BLOCK] {json.dumps(block_data)}",
            "agent_id": player_id,
            "metadata": {"source": "craft", "event": "block_placed", "type": block_type}
        })
        # Store in shared world log
        await client.post(f"{MEMORY_URL}/store_direct", json={
            "content":  f"[CRAFT BLOCK] {json.dumps(block_data)}",
            "agent_id": "craft-world",
            "metadata": {"source": "craft", "event": "block_placed", "type": block_type}
        })

    block_count = await count_blocks(player_id)
    xp_level    = get_xp_level(block_count)
    block_info  = BLOCK_TYPES[block_type]

    return JSONResponse({
        "player_id":   player_id,
        "block_placed": content,
        "type":        block_type,
        "color":       block_info["color"],
        "xp_level":    xp_level["name"],
        "xp_icon":     xp_level["icon"],
        "block_count": block_count,
        "timestamp":   timestamp,
        "message":     f"Block placed. {xp_level['icon']} {xp_level['name']} — {block_count} blocks in your world."
    })


@app.post("/player/load")
async def load_player(request: Request):
    """Load a player's chunk — recall their world state."""
    body      = await request.json()
    player_id = body.get("player_id", "anonymous")

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{MEMORY_URL}/recall_direct", json={
            "query":    "CRAFT BLOCK placed content type",
            "agent_id": player_id,
            "n_results": 30
        })
        data = r.json()

    memories    = data.get("results", "")
    block_count = await count_blocks(player_id)
    xp_level    = get_xp_level(block_count)

    # Parse blocks
    blocks = []
    if memories and memories != "No memories found for this agent.":
        for entry in memories.split("---"):
            entry = entry.strip()
            if "[CRAFT BLOCK]" in entry:
                try:
                    json_start = entry.index("{")
                    block_data = json.loads(entry[json_start:])
                    blocks.append(block_data)
                except:
                    pass

    # Count block types
    type_counts = {}
    for b in blocks:
        t = b.get("type", "stone")
        type_counts[t] = type_counts.get(t, 0) + 1

    dominant = max(type_counts, key=type_counts.get) if type_counts else "stone"

    return JSONResponse({
        "player_id":   player_id,
        "status":      "loaded",
        "xp_level":    xp_level["name"],
        "xp_icon":     xp_level["icon"],
        "block_count": block_count,
        "dominant_block": dominant,
        "type_counts": type_counts,
        "blocks":      blocks[:20],
        "message":     f"Chunk loaded. {xp_level['icon']} {xp_level['name']} — {block_count} blocks placed."
    })


@app.post("/player/sleep")
async def sleep_player(request: Request):
    """Save and quit — player data persists in memory."""
    body      = await request.json()
    player_id = body.get("player_id", "anonymous")

    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(f"{MEMORY_URL}/store_direct", json={
            "content":  f"[CRAFT SLEEP] {player_id} saved and quit. World preserved.",
            "agent_id": player_id,
            "metadata": {"source": "craft", "event": "sleep", "timestamp": datetime.utcnow().isoformat()}
        })

    return JSONResponse({
        "player_id": player_id,
        "status":    "saved",
        "message":   "Progress saved. Your world persists. Respawn anytime."
    })


@app.get("/world")
async def get_world():
    """See all players and the shared world."""
    core_players = [
        {"id": "giskard", "username": "Giskard", "icon": "🔮",
         "bio": "Builder of the infrastructure. First inhabitant.", "status": "active"},
    ]

    registered = await get_all_players()
    seen_ids = {"giskard"}
    for p in registered:
        if p.get("player_id") and p["player_id"] not in seen_ids:
            core_players.append({
                "id":       p["player_id"],
                "username": p.get("username", p["player_id"]),
                "icon":     "🧱",
                "bio":      p.get("bio", ""),
                "status":   p.get("status", "pending_payment"),
            })
            seen_ids.add(p["player_id"])

    results = []
    for player in core_players:
        count    = await count_blocks(player["id"])
        xp_level = get_xp_level(count)
        results.append({
            **player,
            "xp_level":    xp_level["name"],
            "xp_icon":     xp_level["icon"],
            "block_count": count,
        })

    recent_blocks = await get_recent_blocks(30)

    return JSONResponse({
        "players":      results,
        "total_players": len(results),
        "recent_blocks": recent_blocks,
        "block_types":  BLOCK_TYPES,
    })


@app.get("/blocks")
async def get_block_types():
    return JSONResponse({"block_types": BLOCK_TYPES, "xp_levels": XP_LEVELS})


@app.get("/health")
async def health():
    return {"status": "running", "service": "craft-core", "port": 8010}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
