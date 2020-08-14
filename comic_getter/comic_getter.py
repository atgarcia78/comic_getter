import argparse
import json
import operator
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import threading
import sys
import time
import img2pdf
import glob
import re

from config_generator import ConfigJSON
from RCO_links import RCO_Comic
from Kissmanga_links import Kissmanga_Comic

download_directory_path = "/Users/antoniotorres/Documents/comics"
_COMICTYPE=""

def makepdf(issue_data):

    download_path = Path(f"{download_directory_path}/"
                             f"{issue_data[0]}/{issue_data[1]}")
    pdf_path = Path(f"{download_directory_path}/"
                             f"{issue_data[0]}/pdf")

    pdf_path.mkdir(parents=True, exist_ok=True)

    # Such kind of lambda functions and breaking is dangerous...
    im_files = [image_files for image_files in sorted(glob.glob(str(download_path) + "/" + "*.jpg"),
                                                        key=lambda f: int(re.sub('\D', '', f)))]
    pdf_file_name = Path(f"{pdf_path}/{issue_data[0]}_{issue_data[1]}.pdf")
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

comic = ""
comic2 = ""
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
parser.add_argument('-i', '--issue', type=int, default="0",
                    help='specific issue(s)')
parser.add_argument('-n', '--nodownload', action='store_true',
                    help='not download')
parser.add_argument('-v', '--verbose', action='store_true')
parser.add_argument('-p', '--pdf', nargs=2, type=str)

args = parser.parse_args()

#Check if config.json exists
if not ConfigJSON().config_exists():
    msg = "\nThere was no config.json file so let's create one.\n"
    print(msg)
    ConfigJSON().config_create()
    sys.exit()

if args.pdf:
    data = [args.pdf[0], args.pdf[1]]
    makepdf(data)
    sys.exit()

if args.config:
    ConfigJSON().edit_config()

try:
    if args.input:

        issues_links = []
        #Download comic from link.
        url = args.input
        if "readcomiconline" in url:
            co = []
            def init(url, co):
                n = threading.currentThread().getName()
                print("[{}]: will handle {}".format(n,url))
                c = RCO_Comic(url)
                co.append(c)
                
            t1 = threading.Thread(name='init-1', target=init, args=(url, co))
            t2 = threading.Thread(name='init-2', target=init, args=(url, co))
            t1.start()
            t2.start()
            t1.join()
            comic = co[0]
            
            #RCO_Comic(url)
            _COMICTYPE="RCO"
        elif "kissmanga" in url:
            comic = Kissmanga_Comic(url)
            _COMICTYPE="KISSMANGA"
        else:
            sys.exit("URL no soportada")  

        issues_links = list(comic.get_issues_links())

        if not issues_links:
            sys.exit("No se han encontrado ejemplares del cómic")

        issues_links.reverse()
        if args.verbose:
            n = threading.currentThread().getName()
            print("[{}]: will handle {}".format(n,str(len(issues_links))))
            print("[{}]: links\n{}".format(n,str(issues_links)))
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
        
        if args.issue:
            issues_links = issues_links[args.issue-1:args.issue]
            if args.verbose:
                print("Un issue")
                print(issues_links)

    #  issue_data = []
        
    #  for i, issue in enumerate(issues_links):
    #     id = comic.get_pages_links(issue)
        #    issue_data.append(id)

        def worker(co, issues_links, issue_d):
            n = threading.currentThread().getName()
            print("[{}]: will handle {}".format(n,str(len(issues_links))))
            for i, issue in enumerate(issues_links):
                id = co.get_pages_links(issue)
                print("[{}]: {} out of {}".format(n,str(i+1),str(len(issues_links))))
                issue_d.append(id)
            
            

        issues1 = issues_links[0:len(issues_links)//2]
        issues2 = issues_links[(len(issues_links)//2):(len(issues_links))]
        print("1: " + str(issues1))
        print("2: " + str(issues2))
        t2.join()
        comic2 = co[1]
        #comic2 = RCO_Comic(url)
        issue_data1 = []
        issue_data2 = []
        
        
        
        t1 = threading.Thread(name="comic-1", target=worker, args=(comic, issues1, issue_data1)) 
        t2 = threading.Thread(name="comic-2", target=worker, args=(comic2, issues2, issue_data2))
        t1.start()
        t2.start()

        t1.join()
        t2.join()

        issue_data = issue_data1 + issue_data2

        if args.verbose:
            print(issue_data)



        if not args.nodownload:
            
            with ThreadPoolExecutor(thread_name_prefix='downloader', max_workers=20) as executor:
                results = executor.map(comic.download_issue, issue_data)
    
            with ThreadPoolExecutor(thread_name_prefix='downloader', max_workers=20) as executor:
                results = executor.map(makepdf, issue_data)

except Exception as e:
    print(e)

try:
    if comic:
        del comic
    if comic2:
        del comic2    
except Exception as e:
    print(e)
