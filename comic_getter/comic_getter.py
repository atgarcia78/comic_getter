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


def check_comic_ok(queue):

    pages = []
    comics = set()
    
    while not queue.empty():
        data = queue.get()
        pages.append({'comic': data['comic'], 'issue': data['issue'], 'num': data['num'], 'error': data['error']})

    
    for page in pages:
        comics.add(page['comic'] + "/" + page['issue'])

    #con sólo un fallo en alguna página ya no hacemos el pdf
    for page in pages:
        if page['error'] == -1:
            comics.discard(page['comic'] + "/" + page['issue'])

        
    return(comics)


def sanitise(name, issue):
    
    co_path = Path(f"{download_path_str}{name}/{name}_{issue}.pdf")
    co_usb_path = Path(f"{usbext_path_str}{name}/{name}_{issue}.pdf")
    if not co_path.exists():
        return
    elif not co_path.is_symlink():
        rc = RClone()
        res = rc.ls(f"{gdrive_path_str}{name}/{name}_{issue}.pdf")
        if res['code'] != 0:
            res = rc.copy(str(co_path), f"gdrive:comics/{name}")
        res2 = rc.ls(str(co_usb_path))
        if res2['code'] != 0:
            res2 = rc.copy(str(co_path), f"extcomics:{name}")
        if (res['code'] == 0) and (res2['code'] == 0):
            co_path.unlink()
            co_path.symlink_to(co_usb_path)



def makepdfandclean(in_queue):


    while not in_queue.empty():

        item = in_queue.get()
        issue_data = item.rsplit('/')
        print(issue_data)


        #path del fichero pdf
        pdf_file_name = Path(f"{download_path_str}{issue_data[0]}/{issue_data[0]}_{issue_data[1]}.pdf")
        print(pdf_file_name)
        
        #dir donde están las imágenes base para el pdf
        download_path = Path(f"{download_path_str}{issue_data[0]}/{issue_data[1]}")
        print(download_path)

        try:
            
            if pdf_file_name.exists():
                print_thr('PDF File Exist! Skipping : {0}\n'.format(pdf_file_name))
            else:
                im_files = [image_files for image_files in sorted(glob.glob(str(download_path) + "/" + "*.jpg"),
                                                            key=lambda f: int(re.sub('\D', '', f)))]
                print(im_files)
                with open(pdf_file_name, "wb") as f:
                    f.write(img2pdf.convert(im_files))
                    print_thr("Conversion to pdf completed")
        except Exception as FileWriteError:
            print_thr_error("Couldn't write the pdf file..." + str(FileWriteError))            
            if pdf_file_name.exists():
                pdf_file_name.unlink()
            continue

        #si hemos conseguiudo un fichero pdf sin errores
        if pdf_file_name.exists():

            #borramos las imágenes
            try:
                shutil.rmtree(str(download_path))
                print_thr("Removal of issue download folder .. OK") 
            except Exception as OSError:
                print_thr_error("Fallo al intentar borrar dir con inmágenes del comic  " + str(OSError))
                      

            rc = RClone()  
    
            print_thr("gdrive copy")
            #si no está en gdrive se copia. Error '3' de rclone para ls del fichero indica fichero no está
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
            
            
            #si está subido a gdrive Y en el usb, creo symlink en el mac referido al usb y elimino
            if ((res['code'] == 0) and (res2['code'] == 0)):
                print_thr(str(pdf_file_name) + " saved OK gdrive usb")
                try:
                    
                    src = f"{usbext_path_str}{issue_data[0]}/{issue_data[0]}_{issue_data[1]}.pdf"
                    pdf_file_name.unlink()
                    print_thr("Removal of PDF file .. OK")
                    #dst = f"{download_path_str}{issue_data[0]}/{issue_data[0]}_{issue_data[1]}.pdf"
                    os.symlink(src, pdf_file_name) 
                    print_thr("Simlink created .. OK")
                                   

                except Exception as OSError:
                    print_thr_error(OSError)
        else:
            print_thr_error(str(pdf_file_name) + " ERROR, not generated")

        # try:
        #     pdf_path.rmdir() #will remove folder ony if it is empty
        # except Exception as OSError:
        #     print_thr_error(OSError)


def worker(in_queue, out_queue):

    comic = RCO_Comic()  
    while not in_queue.empty():
        try:
            issue = in_queue.get()
            print_thr(issue)

            id = comic.get_pages_links(issue)
            out_queue.put({"comic": id['comic'], "issue" : id['issue'], "pages_links": id['pages'], "error": 0})
        except Exception as e:
            print_thr_error(e)
            out_queue.put({"comic": issue, "error": -1, "cause" : str(e)})

        in_queue.task_done()


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
    parser.add_argument('--pdf', type=str)
    parser.add_argument('-t', '--threads', type=int, default="1")
    parser.add_argument('--check', type=str, help="check name,issue")
    #parser.add_argument('--full', action='store_true')

    
    return parser
    
def init_logging():

    logging.basicConfig(
        format = '%(asctime)-5s %(name)-15s %(levelname)-8s %(message)s',
        level  = logging.DEBUG,      # Nivel de los eventos que se registran en el logger
        filename = "/Users/antoniotorres/testing/mylogs.log", # Fichero en el que se escriben los logs
        filemode = "a"              # a ("append"), en cada escritura, si el archivo de logs ya existe,
                                # se abre y añaden nuevas lineas.
    )
    if logging.getLogger('').hasHandlers():
        logging.getLogger('').handlers.clear()

    # Handler nivel debug con salida a fichero
    file_debug_handler = logging.FileHandler('/Users/antoniotorres/testing/mylogs.log')
    file_debug_handler.setLevel(logging.DEBUG)
    file_debug_format = logging.Formatter('%(asctime)s-%(name)s-%(levelname)s-%(message)s')
    file_debug_handler.setFormatter(file_debug_format)
    logging.getLogger('').addHandler(file_debug_handler)

    # Handler nivel info con salida a consola
    consola_handler = logging.StreamHandler()
    consola_handler.setLevel(logging.INFO)
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
    data = args.pdf.split(",")
    print(data)
    q = Queue()
    q.put(data[0] + "/" + data[1])   
    makepdfandclean(q)
    sys.exit()

if args.check:
    data = args.check.split(",")
    sanitise(data[0], data[1])
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
                  
            comic = RCO_Comic()    
    
            issues_links = list(comic.get_issues_links(url))

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


        if args.verbose:
            print_thr("Number of comics: [{}]".format(n_issues))
            print_thr("Number of workers: [{}]".format(n_workers))
            print_thr(issues_links)

   
        #por último hacemos check si ek comic al que hace referencia cada link ya están en local

        
        issues_queue = Queue()

        for link in issues_links:
            info = comic.get_comic_and_issue_name(link)
            pdf_comic_path = Path(f"{download_path_str}{info[0]}/{info[0]}_{info[1]}.pdf")
            print(pdf_comic_path)
            if pdf_comic_path.exists():                 
                print_thr("Discarded as already DL: [{}]".format(link))
            else:
                issues_queue.put(link)

        #print_thr("WORKERS init: " + str(len(co_workers)))

        data_queue = Queue()
        futures = []

        #theardpoolexecutor como context manager espera a todos los futuros antes de continuar
        with ThreadPoolExecutor(thread_name_prefix="comic", max_workers=n_workers) as executor:
            for i in range(n_workers):
                futures.append(executor.submit(worker, issues_queue, data_queue)) 

            res = wait(futures, return_when=ALL_COMPLETED)

        # list_issues_data = []
        # for data in issues_data:
        #     list_issues_data.append(data)

        #if args.verbose:
            #print_thr(list_issues_data)

        pages_queue= Queue()

        while not data_queue.empty():
            data = data_queue.get()
            if data['error'] == 0:
                for p, page in enumerate(data['pages_links']):
                    pages_queue.put({'comic': data['comic'], 'issue': data['issue'], 'num': p+1, 'page': page})
  

        if not args.nodownload:
            
            futures = []
            res_queue = Queue()

            try:
                with ThreadPoolExecutor(thread_name_prefix='downloader', max_workers=n_workers) as executor:
                    for i in range(n_workers):
                        futures.append(executor.submit(comic.download_page, pages_queue, res_queue))

                    res = wait(futures, return_when=ALL_COMPLETED)
                      
            except Exception as e:
                print_thr_error("DL error " + str(e))

            
            try:
                comics_to_pdf = check_comic_ok(res_queue)
                print("[COMIC2PDF] : " + str(len(comics_to_pdf)))
                print(comics_to_pdf)
                comics_to_pdf_queue = Queue()
                for comic in comics_to_pdf:
                    comics_to_pdf_queue.put(comic)

                with ThreadPoolExecutor(thread_name_prefix='pdfandexec', max_workers=n_workers) as executor:
                    for i in range(n_workers):
                        futures.append(executor.submit(makepdfandclean, comics_to_pdf_queue))

                    res = wait(futures, return_when=ALL_COMPLETED)
                     
            except Exception as e:
                print_thr_error("Fail in pdf and postprocessing " + str(e))

    except Exception as e:
        print_thr_error(e)

