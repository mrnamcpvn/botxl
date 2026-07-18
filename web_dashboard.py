import uvicorn

if __name__ == "__main__":
    uvicorn.run("web.main:app", host="127.0.0.1", port=1607, reload=True)
