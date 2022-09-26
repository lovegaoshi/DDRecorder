from flask import Flask, request
from inacelery import add

app = Flask(__name__)
@app.route('/', methods=['POST'])
def hello():
    content = request.json
    add.delay(
        media=content['media'],
        shazam=content['shazam'],
        timestamps=content['timestamps'],
    )
    return f'added {content["media"]} to the worker queue! chk the inacelery window for logs.'
    
if __name__ == '__main__':
    app.run(host= '0.0.0.0',debug=True)