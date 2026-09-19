import uvicorn

if __name__ == "__main__":
    print("\nDemand Signal Lab → http://127.0.0.1:8010\n")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8010, reload=False)
