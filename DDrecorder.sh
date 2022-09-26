#!/bin/bash
tmux new-session -d -s DDRecorder 'cd cd GitHub/DDRecorder; python main.py'
# should we just merge uploader with main? I should, really
tmux new-session -d -s inaUpload 'cd cd GitHub/DDRecorder; python Uploader.py'
