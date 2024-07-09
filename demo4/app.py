from flask import Flask
from redis import Redis

app = Flask(__name__)
redis = Redis(host='redis', port=6379)
version = "1.1"

@app.route('/')
def hello():
    count = redis.incr('hits')
    return f'Hello World! I have been seen {count} times. Version: {version}.\n'

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)