from flask import Flask, render_template, request, Response, send_from_directory, url_for
from markupsafe import escape
import os
import re
import sqlite3

app = Flask(__name__)
DATABASE = "db/mediadbub.db"
MEMBUFFER = 1024*1024

#get chunks of a file
def get_chunk(filename,byte1=None, byte2=None):
    full_path = filename
    file_size = os.stat(full_path).st_size
    start = 0

    byte2 = min(byte2, file_size-1)

    if byte1 < file_size:
        start = byte1
    if byte2:
        length = byte2 + 1 - byte1
    else:
        length = file_size - start

    with open(full_path, 'rb') as f:
        f.seek(start)
        chunk = f.read(length)
    return chunk, start, length, file_size

#literally index
@app.route("/")
def index():
    return render_template("index.html")

#list of all media
@app.route('/media')
def media():
    #get list of all episodes
    con = sqlite3.connect(DATABASE)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute(f"SELECT * FROM tblEpisodes")
    rows = cur.fetchall()

    #get list of all films
    cur.execute(f"SELECT * FROM tblMovies")
    films = cur.fetchall()

    con.close()

    return render_template("media.html", rows=rows, films=films)

#list of all films
@app.route("/films")
def view_films():
    #get list of all films
    con = sqlite3.connect(DATABASE)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(f"SELECT * FROM tblMovies ORDER BY MovieName")
    rows = cur.fetchall()
    con.close()

    return render_template("films.html", rows=rows)

#list of all shows
@app.route("/shows")
def view_shows():

    #get list of all shows
    con = sqlite3.connect(DATABASE)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(f"SELECT * FROM tblShows ORDER BY ShowName")
    rows = cur.fetchall()
    con.close()

    return render_template("shows.html", rows=rows)

#show all episodes of one show
@app.route("/show/<int:id>")
def show_detail(id):
    con = sqlite3.connect(DATABASE)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    #get name of show
    cur.execute(f"SELECT ShowName FROM tblShows WHERE ShowID = {id}")
    showName = cur.fetchall()[0]["ShowName"]

    #get list of seasons from show
    cur.execute(f"SELECT * FROM tblSeasons WHERE ShowRef = {id} ORDER BY SeasonNum")
    seasonRows = cur.fetchall()
    fullListing = []
    #loop through seasons and get episodes for each season
    for i in seasonRows:
        cur.execute(f"SELECT * FROM tblEpisodes WHERE SeasonRef = {i['SeasonID']}")
        fullListing.append((i,cur.fetchall()))
    con.close()

    return render_template("showview.html", listing=fullListing, show_name=showName)

#watch page for an episode
@app.route("/watch/ep/<int:id>")
def watch_ep(id):
    #getting individual video info
    con = sqlite3.connect(DATABASE)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(f"SELECT * FROM tblEpisodes WHERE EpisodeID = {id}")
    rows = cur.fetchall()

    #get show id
    cur.execute(f"SELECT ShowRef FROM tblSeasons WHERE SeasonID = {rows[0]['SeasonRef']}")
    showID = cur.fetchall()[0]['ShowRef']

    #get name of show
    cur.execute(f"SELECT ShowName FROM tblShows WHERE ShowID = {showID}")
    showName = cur.fetchall()[0]["ShowName"]

    #get list of seasons from show
    cur.execute(f"SELECT * FROM tblSeasons where ShowRef = {showID} ORDER BY SeasonNum")
    seasonRows = cur.fetchall()
    fullListing = []
    #loop through seasons and get episodes for each season
    for i in seasonRows:
        cur.execute(f"SELECT * FROM tblEpisodes WHERE SeasonRef = {i['SeasonID']}")
        fullListing.append((i,cur.fetchall()))

    con.close()

    #get the video stream url and subs path
    url = url_for("video_ep",id=id)
    subs = url_for("return_media", filepath=rows[0]["Subspath"])

    return render_template("watch_ep.html", url=url, subs=subs, name=rows[0]["EpisodeName"], show_name = showName, listing = fullListing)

#watch page for a film
@app.route("/watch/film/<int:id>")
def watch_film(id):
    #getting individual video info
    con = sqlite3.connect(DATABASE)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(f"SELECT * FROM tblMovies WHERE MovieID = {id}")
    rows = cur.fetchall()

    con.close()

    #get the video stream url and subs path
    url = url_for("video_film",id=id)
    subs = url_for("return_media", filepath=rows[0]["Subspath"])

    return render_template("watch_film.html", url=url, subs=subs, name=rows[0]["MovieName"])

#video stream for episodes
@app.route('/video/ep/<int:id>')
def video_ep(id):
    return video("ep", id)

#video stream for films
@app.route('/video/film/<int:id>')
def video_film(id):
    return video("film", id)


def video(table, id):
    #defining range headers
    range_header = request.headers.get('Range', None)
    byte1, byte2 = 0, None
    if range_header:
        match = re.search(r'(\d+)-(\d*)', range_header)
        groups = match.groups()

        if groups[0]:
            byte1 = int(groups[0])
        if groups[1]:
            byte2 = int(groups[1])

    #getting the filepath
    con = sqlite3.connect(DATABASE)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    if table == "ep":
        cur.execute(f"SELECT Filepath FROM tblEpisodes WHERE EpisodeID = {id}")
    elif table == "film":
        cur.execute(f"SELECT Filepath FROM tblMovies WHERE MovieID = {id}")

    rows = cur.fetchall()
    con.close()

    #creating the response

    if byte2 == None:
        byte2 = byte1 + MEMBUFFER

    chunk, start, length, file_size = get_chunk(rows[0]["Filepath"],byte1, byte2)

    resp = Response(chunk, 206, mimetype='video/mp4',
                    content_type='video/mp4', direct_passthrough=True)
    resp.headers.add('Content-Range', 'bytes {0}-{1}/{2}'.format(start, start + length - 1, file_size))
    return resp

#serves a file stored on the server
#WARNING, INSECURE AND SHOULD BE REDONE
@app.route("/data/<path:filepath>")
def return_media(filepath):
    if (filepath == "_404"):
        return send_from_directory(".","default.jpg")

    return send_from_directory("/" + os.path.dirname(filepath), os.path.basename(filepath))

#some stuff for streaming
@app.after_request
def after_request(response):
    response.headers.add('Accept-Ranges', 'bytes')
    return response

if __name__ == '__main__':
    app.run(host="0.0.0.0", threaded=True, port=80, debug=True)

#linking to non static files
#https://stackoverflow.com/questions/26971491/how-do-i-link-to-images-not-in-static-folder-in-flask
