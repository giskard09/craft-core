# craft-core — World Engine

FastAPI backend for Giskard Craft. Runs on port 8010.

## Run

```bash
cd craft-core
pip install fastapi uvicorn httpx
python craft.py
```

## Endpoints

```
POST /player/spawn    — register new player, returns Lightning invoice
POST /player/activate — verify payment and activate
POST /player/place    — place a block (stored in giskard-memory)
POST /player/load     — load player chunk from memory
POST /player/sleep    — save and quit
GET  /world           — all players + recent blocks
GET  /blocks          — block types and XP levels
GET  /health          — health check
```

## Requirements

- Python 3.10+
- Giskard Memory running on port 8005
- Phoenixd running on port 9740 (for Lightning)
