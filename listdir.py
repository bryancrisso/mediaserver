import os, cv2

filepath = r"M:\Shows\BreakingBad\mp4\S3"
serverpath = r"/media/drive2/share/media/Shows/BreakingBad/mp4/S3/"

def get_length(path):
    video = cv2.VideoCapture(path)

    frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
    fps = video.get(cv2.CAP_PROP_FPS)

    return frame_count//fps

def main(path, spath):
    for filename in os.listdir(path):
        print(str(int(get_length(os.path.join(path, filename)))) + "," + str(os.path.getsize(os.path.join(path, filename))) + "," + spath + filename)
main(filepath, serverpath)