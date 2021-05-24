#!/usr/bin/env python3
import argparse
from datetime import datetime
from datetime import timedelta
import math
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import os
import platform
import subprocess
import sys

# Ex
# 2020-05-27T10:47:52.668+0000
GC_LOG_DATETIME_FORMAT='%Y-%m-%dT%H:%M:%S.%f%z'

def save_and_show(plotname, figure):
    '''Tries to use `plt.show()` to display the plot

    If the current matplotlib backend is does now support `show()` then
    we will fall back to saving the plot as an image with the `plotname`
    argument.
    '''
    filename="{}.png".format(plotname)
    figure.set_size_inches(16, 10)
    figure.savefig(filename)
    filepath = filename
    if platform.system() == 'Darwin':       # macOS
        subprocess.call(('open', filepath))
    elif platform.system() == 'Windows':    # Windows
        os.startfile(filepath)
    else:                                   # linux variants
        subprocess.call(('xdg-open', filepath))

def get_single_gc_log_line(filename):
    lines = []
    with open(filename, 'r') as f:
        lines = f.readlines()
    lines = filter(lambda x: "Total time for which application threads were stopped" in x, lines)
    lines = list(lines)
    if len(lines) > 0:
        lines = [lines[0]]
    lines = map(lambda x: x.split(' '), lines)
    lines = filter(lambda x: len(x) >= 15, lines)
    lines = map(lambda x: [x[0], x[1], x[10], x[15]], lines)
    lines = map(lambda x: (x[0][:-1], float(x[1][:-1]), float(x[2]), float(x[3])), lines)
    return list(lines)[0]

def analyze_gc(filename, use_timestamps, topNum):
    lines = []
    with open(filename, 'r') as f:
        lines = f.readlines()
    lines = filter(lambda x: "Total time for which application threads were stopped" in x, lines)
    lines = map(lambda x: x.split(' '), lines)
    lines = filter(lambda x: len(x) >= 15, lines)
    lines = map(lambda x: [x[0], x[1], x[10], x[15]], lines)
    lines = map(lambda x: (x[0][:-1], float(x[1][:-1]), float(x[2]), float(x[3])), lines)

    lines = list(lines)
    lines.sort(key=lambda x: x[1])
    raw_data = list(map(lambda x: [x[1], x[2], x[3]], lines))

    timestamps = map(lambda x: x[0], lines)
    if use_timestamps:
        timestamps = map(lambda x: datetime.strptime(x, GC_LOG_DATETIME_FORMAT), timestamps)
    timestamps = np.array(list(timestamps))


    data = np.array(raw_data)
    maxr = data.argmax(axis=0)
    max_stopped_row = maxr[1]
    max_waiting_row = maxr[2]
    row = lines[max_stopped_row]
    # Max Time
    print("Maximum JVM Stopped time: {} for {} sec".format(row[0], row[2]))
    row = lines[max_waiting_row]
    print("Maximum JVM Waiting to Stop: {} for {} sec".format(row[0], row[3]))

    # Top N
    topN = data.copy()
    # This line sorts the data by longest pause time in descending order ([::-1] does descending)
    topN = get_top_N(data, 1, topNum, lines)
    topRows = []
    print("Top {} STW Times".format(topNum))
    [print("{} stopped: {}, waiting to stop {}".format(row[0], row[2], row[3])) for row in topN]
    keys = {
        'Threads stopped time': 1,
        'Threads waiting to stop time': 2
    }
    figs, axs = plt.subplots(2, 1)
    i = 0
    for key in keys:
        ind = keys[key]
        ts = data[:,0]
        xlabel = "Time since JVM start (sec)"
        if use_timestamps:
            ts = timestamps
            xlabel = "Time"
        axs[i].plot(ts, data[:,ind])
        axs[i].set_title(key)
        axs[i].set_xlabel(xlabel)
        axs[i].set_ylabel("Time (seconds)")
        axs[i].grid(True)
        i += 1

    save_and_show('gc_log_analysis', plt.gcf())

def while_replace(string):
    while '  ' in string:
        string = string.replace('  ', ' ')
    return string

# Gets the top N
#
# Arguments:
# - np_arr: the array to get the top N data for
# - col_idx: The column index to sort by
# - N: how many items to return
# - raw_data: The rows which will be searched and returned back
def get_top_N(np_arr, col_idx, N, raw_data):
    rows = []
    topN = np_arr.copy()
    # This line sorts the data by longest pause time in descending order ([::-1] does descending)
    topN = topN[topN[:,col_idx].argsort()[::-1]]
    topRows = []
    for i in range(N):
        val = topN[i,0]
        # Lookup index in data where the value occurs
        loc = np.where(np_arr == val)
        # get the row
        row = loc[0][0]
        # Lookup raw data row
        row = raw_data[row]
        rows.append(row)
    return rows

def analyze_safepoint(filename, topNum, startDatetime=None, after=None):
    lines = []
    print("Start time {}".format(startDatetime))
    with open(filename, 'r') as f:
        lines = f.readlines()

    # Get All SafepointStatistics lines.
    line_data_raw = []
    ind = 0
    while ind < len(lines):
        if "threads: total initially_running wait_to_block" in lines[ind]:
            line = while_replace(lines[ind+1].strip()).replace("no vm operation", "no-vm-operation").split(' ')
            if len(line) < 15:
                print("found possible bad line: {}".format(line))
                # this may be a line that has a value which overflowed
                bad_entry = filter(lambda x: x.startswith('0') and len(x) > 1 and '.' not in x, line)
                for be in bad_entry:
                    pos = line.index(be)
                    line.remove(be)
                    first = be[0]
                    last = be[1:]
                    line.insert(pos, first)
                    line.insert(pos + 1, last)

            row = [float(line[0][:-1]), line[1], int(line[3]), int(line[4]), int(line[5]), int(line[8]), int(line[9]), int(line[10]), int(line[11]), int(line[12]), int(line[14])]
            if startDatetime is not None:
                timestamp = row[0]
                decimals = math.modf(timestamp)[0]
                ms = int(decimals * 1000)
                timestamp = startDatetime + timedelta(seconds=int(timestamp), milliseconds=ms)
                row.append(timestamp)
            if after is not None:
                pass
            else:
                line_data_raw.append(row)
            ind += 2
        else:
            ind += 1

    # Ensure data is sorted
    line_data_raw.sort(key=lambda x: x[0])
    # 7 fields:
    # 0: JVM time
    # 1: spin time
    # 2: block time
    # 3: sync time
    # 4: cleanup time
    # 5: op time
    # 6: page_trap_count
    data = np.array(list(map(lambda x: (x[0], x[5], x[6], x[7], x[8], x[9], x[10]), line_data_raw)))

    keys = {
        'Spin Time': 1,
        "Block Time": 2,
        "Sync Time": 3,
        "Cleanup Time": 4,
        "Op Time": 5,
        "Page Trap Time": 6
    }
    for key in keys:
        r = get_top_N(data, keys[key], topNum, line_data_raw)
        print("Top {} entries for {}".format(topNum, key))
        [print("Op: {:<29} JVM Time: {:<10}; {}ms {}ms {}ms {}ms {}ms {}ms".format(x[1], str(x[0 if startDatetime is None else 11]), x[5], x[6], x[7], x[8], x[9], x[10])) for x in r]

    # Stopped time
    figs, axs = plt.subplots(len(keys), 1)
    i = 0
    timescale = data[:,0]
    if startDatetime is not None:
        timescale = np.array(list(map(lambda x: x[11], line_data_raw)))
    for key in keys:
        ind = keys[key]
        axs[i].plot(timescale, data[:,ind])
        axs[i].set_title(key)
        i += 1

    for i in range(len(axs)):
        axs[i].set_xlabel("Time since JVM start (sec)")
        axs[i].set_ylabel("Time (ms)")
        axs[i].grid(True)

    # figs.tight_layout()
    # Time to stop
    save_and_show('safepoint_log_analysis', plt.gcf())

def get_jvm_start_timestamp(gc_log_file):
    if gc_log_file == False:
        return None

    if not os.path.exists(gc_log_file):
        raise ValueError("File does not exist")
    gc_line = get_single_gc_log_line(gc_log_file)
    timestamp = datetime.strptime(gc_line[0], GC_LOG_DATETIME_FORMAT)
    jvm_time = gc_line[1]
    return timestamp - timedelta(seconds=int(jvm_time))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("logtype", help="The type of log (accepts 'gc' or 'safepoint'")
    parser.add_argument("filename", help="the file to analyze")
    parser.add_argument("--top", default=10, help='The number of top consumers to display for safepoint and GC')
    parser.add_argument("--use_gc_timestamps", nargs="?", const=True, default=False, help="Set this to use actual timestamps (not JVM time) in GC graph output. If running a safepoint analysis, provide a path to the GC log to reference timestamps from.")
    args = parser.parse_args()

    if args.logtype == 'gc':
        analyze_gc(args.filename, bool(args.use_gc_timestamps), int(args.top))
    elif args.logtype == 'safepoint':
        analyze_safepoint(args.filename, int(args.top), startDatetime=get_jvm_start_timestamp(args.use_gc_timestamps))

main()