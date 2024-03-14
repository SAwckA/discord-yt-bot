#!/bin/bash

wget https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-amd64-static.tar.xz

tar -xvf ffmpeg-git-amd64-static.tar.xz -C . ffmpeg-git-20240301-amd64-static/ffmpeg
mv ffmpeg-git-20240301-amd64-static/ffmpeg ./ffmpeg
chmod +x ./ffmpeg
rm -r ffmpeg-git-20240301-amd64-static
rm ffmpeg-git-amd64-static.tar.xz
