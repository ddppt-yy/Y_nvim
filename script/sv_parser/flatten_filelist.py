from glob import glob
import colorama
from pprint import pprint
import re
import sys
import os
ziyang.shaoimport argparse
parser = argparse.ArgumentParser()
parser.add_argument("--fileList",             help="input file list file",  required=True)
parser.add_argument("--prjrtl",               help="the rtl dir",  required=True)
parser.add_argument("--prjdir",               help="the project dir",  required=True)
parser.add_argument("--flat_fileList",        help="input file list file",  required=True)
args = parser.parse_args()
oriFileLst = args.fileList
flatFileLst = args.flat_fileList
PRJRTL = args.prjrtl
PRJDIR = args.prjdir
outhandle = open(flatFileLst, 'w')
print(PRJRTL)
print(oriFileLst)
print(flatFileLst)


def get_files(file, hdlFiles):
    with open(file, 'r') as f:
        for line in f.readlines():
            line = line.strip()
            if not re.match("^//", line) and re.match("^-f", line) and not re.match("^#", line):
                line = re.sub("-f\s+", "", line)
                line = re.sub("^\$PRJRTL", PRJRTL, line)
                line = re.sub("^\$PRJDIR", PRJDIR, line)
                if os.path.exists(line):
                    get_files(line, hdlFiles)
                    continue
                else:
                    print("Error: %s not exist" % line)
            if re.search("^$", line):
                continue
            if not re.search("^//", line) and not re.search("^#", line):
                line = re.sub("^\$PRJRTL", "$PRJDIR/rtl", line)
                hdlFiles.append(line)
        return hdlFiles


total_files = []
total_files = get_files(oriFileLst, total_files)
new_file = []
for file in total_files:
    if file not in new_file:
        new_file.append(file)
    elif re.match("//Need duplication", file):
        new_file.append(file)
pprint(new_file)
for file in new_file:
    if re.match("^\+incdir\+", file):
        print(file, file=outhandle)
for file in new_file:
    if not re.match("^\+incdir\+", file):
        print(file, file=outhandle)
outhandle.close()
print("Flatten finish")
