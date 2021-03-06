from . import config
import numpy as np
import os
import glob
import subprocess
import csv
import cv2
from scipy.spatial import distance


def undo_ground_offset(ground):
    offset = min(ground)
    return [g - offset for g in ground]


def get_ground_truth_offset(title, ground=None, resources_path=config.RESOURCES_PATH):
    return get_first_frame(title, resources_path=resources_path)
    # return np.min(ground[title])


def get_first_frame(title, resources_path=config.RESOURCES_PATH):
    path = os.path.join(resources_path, title, '*.jpg')

    if len(sorted(glob.glob(path))) == 0:
        print('Data not found for: ' + path)
    first_file = sorted(glob.glob(path))[0]
    first_file = os.path.basename(first_file.replace(".jpg", ""))

    out = int(first_file)
    '''
    if out != 0:
        print('First Frame not 0: ' + first_file)
    '''
    return int(first_file)


def local_maxima(a):
    peaks = np.r_[True, a[1:] > a[:-1]] & np.r_[a[:-1] > a[1:], True]
    return peaks


def filter_local_maxima(x, a, height, thresh_func=None):
    if thresh_func:
        height = thresh_func(x, a)
    peaks = [index for index in a if index == 0 or
             abs(x[index - 1] - x[index]) > height]
    diffs = [abs(x[p] - x[p - 1]) for p in peaks]
#     peaks = [index for index in a if index != 0 and x[index] > height]
    return np.array(peaks)


def batch_get_shots(directory):
    all_shots = {}
    path = os.path.join(directory, '*.csv')
    for file in glob.glob(path):
        title = os.path.basename(file).replace('.csv', '')
        all_shots[title] = get_shots_csv(file)

    return all_shots


def read_csv(csv_filename, path):
    name, ext = os.path.splitext(csv_filename)
    with open(os.path.join(path, csv_filename), 'rU') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        results = [row for row in reader]
    return results


def write_csv(data, csv_filename, path):
    with open(os.path.join(path, csv_filename), 'w') as csv_file:
        writer = csv.writer(csv_file, delimiter=',')
        for row in data:
            writer.writerow(row)


def get_shots_csv(csv_file):
    shots = {}
    data = pd.read_csv(csv_file)

    # sometimes we have s_frame in data
    header_name = 'start_frame' if 'start_frame' in data.keys() else 's_frame'
    data_list = data['start_frame'].tolist()
    output = [int(d) for d in data_list]
    return output


def delete_images(source_video_frame_directory, start_marker, end_marker):
    task = 'cleaning up'
    for i in range(start_marker, end_marker):
        os.remove(os.path.join(source_video_frame_directory,
                               config.FRAME_FNAME_FORMAT % i))
    return


def find_num_frames(movie_file_path):
    task = 'find_num_frames'
    cmd = ' '.join(["ffprobe -v error -count_frames -select_streams",
                    " v:0 -show_entries stream=nb_read_frames",
                    " -of default=nokey=1:noprint_wrappers=1 {0}"])

    cmd = cmd.format(movie_file_path)

    result = subprocess.check_output(cmd, shell=True)

    return int(result)


def get_temp_dir(root):
    if not os.path.isdir(root):
        root = os.path.dirname(root)
    temp_dir = os.path.join(root, config.SOURCE_FRAME_DIR)
    return temp_dir


def ffmpeg_call(movie_file_path):
    task = 'ffmpeg decomposition'

    tmp_dir = get_temp_dir(movie_file_path)
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)
    cmd = "ffmpeg -i {0} {1}/{2}".format(movie_file_path, tmp_dir,
                                         config.FRAME_FNAME_FORMAT)
    return os.system(cmd)


def print_rmtree_error():
    e = ' '.join(["ERROR: make sure no processes are using",
                  "the directory you are trying to delete."])


def stitch_results(result1, result2):
    results = {}
    results['hists'] = np.concatenate((result1['hists'], result2['hists']))
    results['data'] = np.concatenate((result1['data'], result2['data']))

    return results


def color_histograms(fn, n, n_bins=4, first_frame=1):
    all_hists = []
    for i in range(0, n):
        offset = i + (first_frame)
        hists = []
        filename = fn % offset
        img = cv2.imread(filename)
        # calculate color histograms for three channels
        for j in range(3):
            hist = cv2.calcHist([img], [j], None, [n_bins], [0, 256])
            hists.extend(hist)
        all_hists.append(hists)
    all_hists = np.array(all_hists)
    new_dimension = n
    all_hists = all_hists.reshape(new_dimension, -1)
    return all_hists


def get_hist_diffs(hists):

    # Add a 0 histogram for the frame before to ensure len(diffs) == len(hists)
    hists = hists.tolist()
    pre_hist = [0 for x in hists[0]]
    hists.insert(0, pre_hist)

    color_hist_diffs = [distance.chebyshev(hists[i - 1], hists[i])
                        for i in range(1, len(hists))]

    color_hist_diffs = np.array(color_hist_diffs)

    return color_hist_diffs


def get_movie_file(directory):
    for f in os.listdir(directory):
        if any(ext in f for ext in config.FILE_TYPES):
            return f


def write_output_text_file(results, output_dir):
    output_txt_file = os.path.join(output_dir, config.OUTPUT_TXT_FNAME)
    output_arr = np.sort(results['shots'])
    np.savetxt(output_txt_file, output_arr, fmt="%06d")


def normalize_list(diff_list):
    maxima = max(diff_list)
    norms = [d / maxima for d in diff_list]
    return norms


def write_output_csv_file(results, output_dir):

    shots = np.sort(results['shots'])
    hists = results['hists']
    diffs = results['data']
    norms = normalize_list(diffs)

    data = []
    for shot in shots:
        first_part = np.array([shot, norms[shot], diffs[shot]])
        data.append(list(first_part) + list(hists[shot]))

    write_csv(data, config.OUTPUT_CSV_FNAME, output_dir)
