import argparse
import json
import operator
import os
import threading
import sys
import time
import img2pdf
import glob
import re
import shutil
import logging
from queue import Queue, Empty
from rclone import RClone
from config_generator import ConfigJSON
from RCO_links import RCO_Comic
from Kissmanga_links import Kissmanga_Comic
from utils import (
    print_thr,
    print_thr_error
)
from pathlib import Path
from concurrent.futures import(
    ThreadPoolExecutor,
    wait,
    FIRST_COMPLETED,
    ALL_COMPLETED,
)

download_path_str = "/Users/antoniotorres/Documents/comics/"
usbext_path_str = "/Volumes/Pandaext1/comics/"
gdrive_path_str = "gdrive:comics/"

_COMICTYPE=""


def makepdfandpostexec(issue_data):

    '''
    BEFORE

    /Users/antoniotorres/Documents/comics/
        Empyre/
            pdf/
                Empyre_Issue-1.pdf
                Empyre_Issue-2.pdf
                    ...
                Empyre_Issue-n.pdf
            Issue-1/
                Page1.jpg
                Page2.jpg
                    ...
                Pagen.jpg
            Issue-2/
               ...
            Issue-n/ 

    AFTER CLEANING

    /Users/antoniotorres/Documents/comics/
        Empyre/
            Empyre_Issue-1.pdf@ -> /Volumes/Pandaext1/comics/Empyre/Empyre_Issue-1.pdf
                ...
            Empyre_Issue-n.pdf@ -> /Volumes/Pandaext1/comics/Empyre/Empyre_Issue-n.pdf


    
    '''

    download_path = Path(f"{download_path_str}{issue_data[0]}/{issue_data[1]}")
    pdf_path = Path(f"{download_path_str}{issue_data[0]}/pdf")

    pdf_path.mkdir(parents=True, exist_ok=True)

    
    im_files = [image_files for image_files in sorted(glob.glob(str(download_path) + "/" + "*.jpg"),
                                                        key=lambda f: int(re.sub('\D', '', f)))]
    pdf_file_name = Path(f"{pdf_path}/{issue_data[0]}_{issue_data[1]}.pdf")
    #print_thr(pdf_file_name)
    #sprint(im_files)
    try:
        # This block is same as the one in the "cbz" conversion section. Check that one.
        if pdf_file_name.exists():
            print_thr('PDF File Exist! Skipping : {0}\n'.format(pdf_file_name))
        else:
            with open(pdf_file_name, "wb") as f:
                f.write(img2pdf.convert(im_files))
                print_thr("Conversion to pdf completed")
    except Exception as FileWriteError:
        print_thr_error("Couldn't write the pdf file...")
        print_thr_error(FileWriteError)

    
    if pdf_file_name.exists():

        rc = RClone()  
  
        print_thr("gdrive copy")
        #si no está en gdrive se vuelve a copia. Error '3' de rclone para ls del fichero indica fichero no está
        res = rc.ls(f"gdrive:comics/{issue_data[0]}/{issue_data[0]}_{issue_data[1]}.pdf")
        if res['code'] != 0:
            res = rc.copy(str(pdf_file_name), f"gdrive:comics/{issue_data[0]}")
            print_thr(res)
        
        print_thr("usb ext copy")
        #si no está en el usbext, se copia. Error '3' de rclone para ls del fichero indica fichero no está
        res2 = rc.ls(f"{usbext_path_str}{issue_data[0]}/{issue_data[0]}_{issue_data[1]}.pdf")
        if res2['code'] != 0:
            res2 = rc.copy(str(pdf_file_name), f"extcomics:{issue_data[0]}")
            print_thr(res2)
        
        
        if ((res['code'] == 0) and (res2['code'] == 0)):
            try:
                
                src = f"{usbext_path_str}{issue_data[0]}/{issue_data[0]}_{issue_data[1]}.pdf"
                dst = f"{download_path_str}{issue_data[0]}/{issue_data[0]}_{issue_data[1]}.pdf"
                os.symlink(src, dst) 
                print_thr("Simlink created .. OK")
                pdf_file_name.unlink()
                print_thr("Removal of PDF file .. OK")
                try:
                    shutil.rmtree(str(download_path))
                except Exception as OSError:
                    print_thr_error(OSError)
                print_thr("Removal of issue download folder .. OK")
            except Exception as OSError:
                print_thr_error(OSError)
    else:
        print_thr_error("ERROR pdf file")

    try:
        pdf_path.rmdir() #will remove folder ony if it is empty
    except Exception as OSError:
        print_thr_error(OSError)


def init_worker(url, co, co_queue, h):
    c = RCO_Comic(url, h)
    if c:
        co.append(c)  
        co_queue.put(co)

def init_argparse() -> argparse.ArgumentParser:

    parser = argparse.ArgumentParser(prog="comic_getter", description="comic_getter is a command line tool "
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
    parser.add_argument('--full', action='store_true')

    
    return parser
    
def init_logging():

    logging.basicConfig(
        format = '%(asctime)-5s %(name)-15s %(levelname)-8s %(message)s',
        level  = logging.INFO,      # Nivel de los eventos que se registran en el logger
        filename = "/Users/antoniotorres/testing/mylogs.log", # Fichero en el que se escriben los logs
        filemode = "a"              # a ("append"), en cada escritura, si el archivo de logs ya existe,
                                # se abre y añaden nuevas lineas.
    )
    if logging.getLogger('').hasHandlers():
        logging.getLogger('').handlers.clear()

    # Handler nivel debug con salida a fichero
    file_debug_handler = logging.FileHandler('/Users/antoniotorres/testing/mylogs.log')
    file_debug_handler.setLevel(logging.INFO)
    file_debug_format = logging.Formatter('%(asctime)s-%(name)s-%(levelname)s-%(message)s')
    file_debug_handler.setFormatter(file_debug_format)
    logging.getLogger('').addHandler(file_debug_handler)

    # Handler nivel info con salida a consola
    consola_handler = logging.StreamHandler()
    consola_handler.setLevel(logging.DEBUG)
    consola_handler_format = logging.Formatter('%(asctime)s-%(name)s-%(levelname)s-%(message)s')
    consola_handler.setFormatter(consola_handler_format)
    logging.getLogger('').addHandler(consola_handler)

    
parser = init_argparse()
init_logging()
args = parser.parse_args()


#Check if config.json exists
if not ConfigJSON().config_exists():
    msg = "\nThere was no config.json file so let's create one.\n"
    print_thr(msg)
    ConfigJSON().config_create()
    sys.exit()

if args.pdf:
    data = [args.pdf[0], args.pdf[1]]
    makepdfandpostexec(data)
    sys.exit()

if args.config:
    ConfigJSON().edit_config()
    sys.exit()

if not args.input:
    sys.exit("URL missing")

else:

    try:
    
        issues_links = []
        #Download comic from link.
        url = args.input

        print_thr(url)
        print_thr(args.threads)

        if "readcomiconline" in url:
            
            _COMICTYPE="RCO"
            
            #Iniciamos los co_workers en paralelo, número máximo  = input número de threads. En esta inicialziación en cuanto tengamos
            #uno listo lo adjudicamos para que obtenga el número de issues que hay que descargar.
            #los co-workers con objetos RCO_Comic que superan el cloudfare y disponen cada uno de un objeto Selenium - Chromedriver
            #para hacer el scraping
            
                        
            co_workers = []
            rcocomics_queue = Queue()

            futures = []
            executor = ThreadPoolExecutor(thread_name_prefix="init", max_workers=args.threads)
            if args.full:
                headless=False
            else:
                headless=True

            for i in range(args.threads):
                futures.append(executor.submit(init_worker, url, co_workers, rcocomics_queue, headless)) 
                #En cuanto haya un worker inicializado, pasamos a ejecutar el main thread y dedicamos uno de los recursos del worker 
                #a coger los links
                
            res = wait(futures, return_when=FIRST_COMPLETED)
                        
        
            if co_workers:
                comic = co_workers[-1]
                print_thr("1st object RCO_Comic will get links")       
        
                issues_links = list(comic.get_issues_links())

                if not issues_links:
                    sys.exit("No se han encontrado ejemplares del cómic")

                issues_links.reverse()

                #Obtenemos lista final de links según los argumentos pasados:
        
                #Ignore determined links
            skip = args.skip
            if (skip != 0):
                issues_links = issues_links[skip:]
                if args.verbose:
                    print_thr("After skip")
                    print_thr(issues_links)

            #subset of consecutive issues
            first = args.first
            last = args.last
            if ((first != 0) and (last != 0)):
                issues_links = issues_links[first-1:last]
                if args.verbose:
                    print_thr("After first-last")
                    print_thr(issues_links)
        
            #single issue
            if args.issue:
                issues_links = issues_links[args.issue-1:args.issue]
                if args.verbose:
                    print_thr("Single issue")
                    print_thr(issues_links)

        
        n_issues = len(issues_links)

        n_workers = args.threads

        if n_workers > n_issues:
            n_workers = n_issues

        if args.verbose:
            print_thr("Number of comics: [{}]".format(n_issues))
            print_thr("Number of workers: [{}]".format(n_workers))
            print_thr(issues_links)

   

        def worker(co_queue, is_queue, issue_d):
            
            co = co_queue.get()
            while not is_queue.empty():
                try:
                    issue = is_queue.get()
                    print_thr(issue)
                    id = co.get_pages_links(issue)
                    issue_d.append(id)
                except Exception as e:
                    print_thr_error(e)
                    break
        
            
       
        #esperamos al resto de inits

        res2 = wait(futures, return_when=ALL_COMPLETED, timeout=120)

        
        #Cargamos las queues con la info necesaria para los workers
        rcocomic_queue = Queue()
        for comic in co_workers:
            rcocomic_queue.put(comic)

        issues_queue = Queue()
        for link in issues_links:
            issues_queue.put(link)

        

        print_thr("WORKERS init: " + str(len(co_workers)))

        issues_data = []
        futures2 = []

        #theardpoolexecutor como context manager espera a todos los futuros antes de continuar
        with ThreadPoolExecutor(thread_name_prefix="comic", max_workers=n_workers) as executor:
            for i in range(n_workers):
                futures2.append(executor.submit(worker, rcocomic_queue, issues_queue, issues_data)) 

        list_issues_data = []
        for data in issues_data:
            list_issues_data.append(data)

        #if args.verbose:
            #print_thr(list_issues_data)

        list_pages=[]
        for issue in list_issues_data:
            co_name = issue[0]
            co_issue = issue[1]
            for p, page in enumerate(issue[2]):
                list_pages.append([co_name, co_issue, p+1, page])
       
 
        
        if args.verbose:
            
            print_thr(f" Total pages:  [{str(len(list_pages))}]")
            #print_thr(list_pages)

        if not args.nodownload:
            
           # with ThreadPoolExecutor(thread_name_prefix='downloader', max_workers=20) as executor:
           #     results = executor.map(comic.download_issue, list_issues_data)

            try:
                with ThreadPoolExecutor(thread_name_prefix='downloader', max_workers=10) as executor:
                    results = executor.map(comic.download_page, list_pages)
                      
            except Exception as e:
                print_thr_error("DL error " + str(e))

            try:

                with ThreadPoolExecutor(thread_name_prefix='pdfandexec', max_workers=10) as executor2:
                    results2 = executor2.map(makepdfandpostexec, list_issues_data)
                     
            except Exception as e:
                print_thr_error("Fail in pdf and postprocessing " + str(e))

    except Exception as e:
        print_thr_error(e)

