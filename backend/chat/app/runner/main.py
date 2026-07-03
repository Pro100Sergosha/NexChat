import uvicorn


def main() -> None:
    uvicorn.run("app.runner.asgi:app", host="0.0.0.0", port=8001, reload=True)


if __name__ == "__main__":
    main()
