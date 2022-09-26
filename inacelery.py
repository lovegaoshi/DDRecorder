from celery import Celery
from Uploader import UploadWorker
app = Celery('tasks', broker='sqla+sqlite:///celerydb.sqlite')

@app.task
def add(media, timestamps, shazam):
    UploadWorker( media, timestamps, shazam).run()
