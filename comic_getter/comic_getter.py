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
parser.add_argument('-t', '--threads', type=int, default="1")

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
            hilos = []
            def init(url, co):
                c = RCO_Comic(url)
                if c:
                    co.append(c)

            for t in range(args.threads):
                h = threading.Thread(name='init-' + str(t), target=init, args=(url, co))
                h.start()
                hilos.append(h)
            
            #esperamos al primer hilo que pase el cloudfare
            i = 0
            while True:

                if len(co) > 0:
                    comic = co[0]
                    break
                else:
                    time.sleep(5)
                    i += 1
                    print("Waiting for first init... {} secs".format(i*5))

            
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


        if args.verbose:
            print("Number of comics: [{}]".format(len(issues_links)) )
            print(issues_links)

        def worker(co, issue_l, issue_d):
            n = threading.currentThread().getName()
            print("[{}]: will handle {}".format(n,str(len(issue_l))))
            print(issue_l)
            y=0
            for y, issue in enumerate(issue_l):
                print("[{}]: {} out of {}".format(n,str(y+1),str(len(issue_l))))
                id = co.get_pages_links(issue)
                issue_d.append(id)
            
        

        #esperamos a todos los hilos init

        n_issues = len(issues_links) 
        n_workers = args.threads

        if n_workers > n_issues:
            n_workers = n_issues

        if args.verbose:
            print("Number of workers: [{}]".format(n_workers))



        issues_sub = []
        issues_data = []
        hilos2 = []
        
        for i in range(0,n_workers):
 
            index_co = i
            coef = n_issues%n_workers
            if coef == 0:
                coef = n_issues//n_workers
            index_inf = i*coef
            if (i < n_workers-1):
                index_sup = index_inf + coef
            else:
                index_sup = n_issues
            #if (index_sup > n_issues):
            #    index_sup = n_issues
            issues_sub.append(issues_links[index_inf:index_sup])
            issues_data.append([])
            k = 0
            j = len(co)
            if i >= j:
                while True:

                    if len(co) > j:                        
                        break
                    else:
                        time.sleep(1)
                        k += 1
                        print("Waiting for new worker init... {} secs".format(k))
                        if k > 15:
                            break

            if i >=  len(co):
                sem = 0
                k = 0
                while True:
                    for hi in hilos2:
                        if not hi.isAlive():
                            index_co = int(hi.getName().split("-")[1])
                            print("Worker reused: {}".format(str(index_co)))
                            sem = 1
                            break

                    if sem == 1:
                        break
                    else:
                        time.sleep(1)
                        k += 1
                        print("Waiting for  worker available to reuse... {} secs".format(k))
                        if k > 15:
                            break



            h = threading.Thread(name="comic-" + str(i), target=worker, args=(co[index_co], issues_sub[i], issues_data[i]))
            h.start()
            hilos2.append(h)

        for hilo in hilos2:
            hilo.join()


        list_issues_data = []
        for data in issues_data:
            for d in data:
                list_issues_data.append(d)

        if args.verbose:
            print(list_issues_data)

        list_pages=[]
        for issue in list_issues_data:
            co_name = issue[0]
            co_issue = issue[1]
            for p, page in enumerate(issue[2]):
                list_pages.append([co_name, co_issue, p+1, page])
        if args.verbose:
            print(list_pages)

        if not args.nodownload:
            
           # with ThreadPoolExecutor(thread_name_prefix='downloader', max_workers=20) as executor:
           #     results = executor.map(comic.download_issue, list_issues_data)
            with ThreadPoolExecutor(thread_name_prefix='downloader', max_workers=50) as executor:
                results = executor.map(comic.download_page, list_pages)
    
            with ThreadPoolExecutor(thread_name_prefix='downloader', max_workers=20) as executor:
                results = executor.map(makepdf, list_issues_data)

except Exception as e:
    print(e)

try:
    if comic:
        del comic
    if comic2:
        del comic2    
except Exception as e:
    print(e)
