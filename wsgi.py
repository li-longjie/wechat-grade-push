from app import app

# 确保应用只被创建一次
application = app

if __name__ == "__main__":
    app.run() 