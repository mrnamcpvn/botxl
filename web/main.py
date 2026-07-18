from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from web.routes import players, battles, admin

app = FastAPI(title="Bot-XL Dashboard")
app.add_middleware(SessionMiddleware, secret_key="botxl-secret-key-change-me")
app.mount("/static", StaticFiles(directory="web/static"), name="static")
app.include_router(players.router)
app.include_router(battles.router)
app.include_router(admin.router)


@app.get("/")
async def index():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/leaderboard")
