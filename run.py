from app import create_app


app = create_app({"DEBUG": True, "SESSION_COOKIE_SECURE": False})


if __name__ == "__main__":
    app.run(threaded=False)
