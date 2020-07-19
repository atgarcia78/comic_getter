import argparse
import json
import operator
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import sys
import time
import img2pdf
import glob
import re

from config_generator import ConfigJSON
from RCO_links import RCO_Comic

download_directory_path = "/Users/antoniotorres/Documents/comics"

def makepdf(issue_data):

    download_path = Path(f"{download_directory_path}/"
                             f"{issue_data[1]}/{issue_data[2]}")
    pdf_path = Path(f"{download_directory_path}/"
                             f"{issue_data[1]}/pdf")

    pdf_path.mkdir(parents=True, exist_ok=True)
 
    #print(str(basename))
    #print(str(dirname))                
 
    #print(converted_file_directory)
    # Such kind of lambda functions and breaking is dangerous...
    im_files = [image_files for image_files in sorted(glob.glob(str(download_path) + "/" + "*.jpg"),
                                                        key=lambda f: int(re.sub('\D', '', f)))]
    pdf_file_name = Path(f"{pdf_path}/{issue_data[1]}_{issue_data[2]}.pdf")
    #print(pdf_file_name)
    #sprint(im_files)
    try:
        # This block is same as the one in the "cbz" conversion section. Check that one.
        if pdf_file_name.exists():
            print('[PDF File Exist! Skipping : {0}\n'.format(pdf_file_name))
            pass
        else:
            with open(pdf_file_name, "wb") as f:
                f.write(img2pdf.convert(im_files))
                print("Converted the file to pdf...")
    except Exception as FileWriteError:
        print("Couldn't write the pdf file...")
        print(FileWriteError)


#Create terminal UI
parser = argparse.ArgumentParser(
    prog="comic_getter",
    description="comic_getter is a command line tool "
    "to download comics from readcomiconline.to.")

parser.add_argument('input', help="Get comic and all of it's issues from main link")
parser.add_argument('-c', '--config', action='store_true',
                    help='Edit config file')       
parser.add_argument('-s', '--skip', type=int, default="0", 
                    help='Number of issues to skip')
parser.add_argument('-f','--first', type=int, default="0",
                    help='1st issue of subset')
parser.add_argument('-l','--last', type=int, default="0",
                    help='last issue of subset')
parser.add_argument('-i', '--issue', type=str, default=[""],
                    help='specific issue(s)')
parser.add_argument('-n', '--nodownload', action='store_true',
                    help='not download')
parser.add_argument('-v', '--verbose', action='store_true')

args = parser.parse_args()

#Check if config.json exists
if not ConfigJSON().config_exists():
    msg = "\nThere was no config.json file so let's create one.\n"
    print(msg)
    ConfigJSON().config_create()
    sys.exit()

if args.config:
    ConfigJSON().edit_config()

if args.input:

    issues_links = []
    #Download comic from link.
    url = args.input
    comic = RCO_Comic(url)
    issues_links = list(comic.get_issues_links())

    if not issues_links:
        sys.exit("No se han encontrado ejemplares del cómic")

    issues_links.reverse()
    if args.verbose:
        print(issues_links)
    #Ignore determined links
    skip = args.skip
    if (skip != 0):
        issues_links = issues_links[skip:]
        if args.verbose:
            print("Tras skip")
            print(issues_links)
    first = args.first
    last = args.last

    if ((first != 0) and (last != 0)):
        issues_links = issues_links[first-1:last]
        if args.verbose:
            print("Tras first last")
            print(issues_links)

    issue_data = []
    for i, issue in enumerate(issues_links):
        id = comic.get_pages_links(issue)
        issue_data.append(id)

    if args.verbose:
        print(issue_data)

    comic.driver.quit()

    if not args.nodownload:
        
        with ThreadPoolExecutor(thread_name_prefix='downloader', max_workers=20) as executor:
            results = executor.map(comic.download_issue, issue_data)
 
        with ThreadPoolExecutor(thread_name_prefix='downloader', max_workers=20) as executor:
            results = executor.map(makepdf, issue_data)

    
    
