from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from web.routes import players, battles

app = FastAPI(title="Bot-XL Dashboard")
app.mount("/static", StaticFiles(directory="web/static"), name="static")
app.include_router(players.router)
app.include_router(battles.router)


@app.get("/")
async def index():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/leaderboard")
