import argparse
import os
import sys
import img2pdf
import re
import shutil
import logging
from queue import Queue, Empty
from rclone import RClone
from config_generator import ConfigJSON
from RCO_links import RCO_Comic
from utils import (
    print_thr,
    print_thr_error,
    init_logging
)
from pathlib import Path
from concurrent.futures import(
    ThreadPoolExecutor,
    wait,
    ALL_COMPLETED,
)
from natsort import (
    natsorted,
    ns
)

download_path_str = "/Users/antoniotorres/Documents/comics/"
usbext_path_str = "/Volumes/Pandaext1/comics/"
gdrive_path_str = "gdrive:comics/"


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


def check_all(name):

    co_path = Path(f"{download_path_str}{name}")
    list_files = [file for file in co_path.iterdir()]
    for file in list_files:
        name_p = file.stem.split("_")
        sanitise(name_p[0],name_p[1])

def sanitise(name, issue):
    
    co_path = Path(f"{download_path_str}{name}/{name}_{issue}.pdf")
    co_usb_path = Path(f"{usbext_path_str}{name}/{name}_{issue}.pdf")
    if not co_path.exists():
        return
    elif not co_path.is_symlink():
        cfg = "/Users/antoniotorres/.config/rclone"          

        #rc = RClone(cfg)
        rc = RClone()
        #rc = rclone.with_config(cfg)
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
        print_thr(logger,issue_data)


        #path del fichero pdf
        pdf_file_name = Path(f"{download_path_str}{issue_data[0]}/{issue_data[0]}_{issue_data[1]}.pdf")
        print_thr(logger,pdf_file_name)
        
        #dir donde están las imágenes base para el pdf
        download_path = Path(f"{download_path_str}{issue_data[0]}/{issue_data[1]}")
        print_thr(logger,download_path)

        try:
            
            if pdf_file_name.exists():
                print_thr(logger,'PDF File Exist! Skipping : {0}\n'.format(pdf_file_name))
            else:
                im_files = [str(image) for image in natsorted(download_path.iterdir(), alg=ns.PATH)]
                print_thr(logger,im_files)
                with open(pdf_file_name, "wb") as f:
                    f.write(img2pdf.convert(im_files))
                    print_thr(logger,"Conversion to pdf completed")
        except Exception as FileWriteError:
            print_thr_error(logger,"Couldn't write the pdf file..." + str(FileWriteError))            
            if pdf_file_name.exists():
                pdf_file_name.unlink()
            continue

        #si hemos conseguiudo un fichero pdf sin errores
        if pdf_file_name.exists():

            #borramos las imágenes
            try:
                shutil.rmtree(str(download_path))
                print_thr(logger,"Removal of issue download folder .. OK") 
            except Exception as OSError:
                print_thr_error(logger,"Fallo al intentar borrar dir con inmágenes del comic  " + str(OSError))


            rc = RClone()  
    
            print_thr(logger,"gdrive copy")
            #si no está en gdrive se copia. Error '3' de rclone para ls del fichero indica fichero no está
            res = rc.ls(f"gdrive:comics/{issue_data[0]}/{issue_data[0]}_{issue_data[1]}.pdf")
            if res['code'] != 0:
                res = rc.copy(str(pdf_file_name), f"gdrive:comics/{issue_data[0]}")
                print_thr(logger,res)
            
            print_thr(logger,"usb ext copy")
            #si no está en el usbext, se copia. Error '3' de rclone para ls del fichero indica fichero no está
            res2 = rc.ls(f"{usbext_path_str}{issue_data[0]}/{issue_data[0]}_{issue_data[1]}.pdf")
            if res2['code'] != 0:
                res2 = rc.copy(str(pdf_file_name), f"extcomics:{issue_data[0]}")
                print_thr(logger,res2)
            
            
            #si está subido a gdrive Y en el usb, creo symlink en el mac referido al usb y elimino
            if ((res['code'] == 0) and (res2['code'] == 0)):
                print_thr(logger,str(pdf_file_name) + " saved OK gdrive usb")
                try:
                    
                    src = f"{usbext_path_str}{issue_data[0]}/{issue_data[0]}_{issue_data[1]}.pdf"
                    pdf_file_name.unlink()
                    print_thr(logger,"Removal of PDF file .. OK")
                    #dst = f"{download_path_str}{issue_data[0]}/{issue_data[0]}_{issue_data[1]}.pdf"
                    os.symlink(src, pdf_file_name) 
                    print_thr(logger,"Simlink created .. OK")
                                   

                except Exception as OSError:
                    print_thr_error(logger,OSError)
        else:
            print_thr_error(logger,str(pdf_file_name) + " ERROR, not generated")

        # try:
        #     pdf_path.rmdir() #will remove folder ony if it is empty
        # except Exception as OSError:
        #     print_thr_error(logger,OSError)


def worker(in_queue, out_queue, proxy):

    comic = RCO_Comic(proxy)  
    while not in_queue.empty():
        
        issue = in_queue.get()
        print_thr(logger,issue)
        try:
            id = comic.get_pages_links(issue)
            out_queue.put({"comic": id['comic'], "issue" : id['issue'], "pages_links": id['pages'], "error": 0})
        except Exception as e:
            print_thr_error(logger,e)
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
    parser.add_argument('--proxy', type=str)
    parser.add_argument('--search', action='store_true')
    parser.add_argument('--checkall', type=str)

    #parser.add_argument('--full', action='store_true')

    
    return parser
        
parser = init_argparse()
init_logging()
logger = logging.getLogger("main")
args = parser.parse_args()


#Check if config.json exists
if not ConfigJSON().config_exists():
    msg = "\nThere was no config.json file so let's create one.\n"
    print_thr(logger,msg)
    ConfigJSON().config_create()
    sys.exit()

if args.pdf:
    data = args.pdf.split(",")
    #print_thr(data)
    q = Queue()
    q.put(data[0] + "/" + data[1])   
    makepdfandclean(q)
    sys.exit()

if args.check:
    data = args.check.split(",")
    sanitise(data[0], data[1])
    sys.exit()

if args.checkall:
    list_data = args.checkall.split(",")
    with ThreadPoolExecutor(thread_name_prefix="checkall", max_workers=5) as executor:
            futures = [executor.submit(check_all(data_n)) for data_n in list_data] 

            wait(futures, return_when=ALL_COMPLETED)
    sys.exit()

if args.config:
    ConfigJSON().edit_config()
    sys.exit()

if not args.input:
    sys.exit("URL missing")

else:

    try:
    
        issues_links = []
               
        comic = RCO_Comic(args.proxy)   

        comic.close_driver() 

        if not args.search:
            url = args.input
            if not "readcomiconline" in url:
                sys.exit("Not a readcomiconline comic")
            issues_links = list(comic.get_issues_links(url))
        else:
            keyword = args.input
            issues_links = list(comic.search(keyword))

        if not issues_links:
            sys.exit("No se han encontrado ejemplares del cómic")

        issues_links.reverse()

            #Obtenemos lista final de links según los argumentos pasados:
    
            #Ignore determined links
        skip = args.skip
        if (skip != 0):
            issues_links = issues_links[skip:]
            if args.verbose:
                print_thr(logger,"After skip")
                print_thr(logger,issues_links)

        #subset of consecutive issues
        first = args.first
        last = args.last
        if ((first != 0) and (last != 0)):
            issues_links = issues_links[first-1:last]
            if args.verbose:
                print_thr(logger,"After first-last")
                print_thr(logger,issues_links)
    
        #single issue
        if args.issue:
            issues_links = issues_links[args.issue-1:args.issue]
            if args.verbose:
                print_thr(logger,"Single issue")
                print_thr(logger,issues_links)

        
        n_issues = len(issues_links)

        n_workers = args.threads


        if args.verbose:
            print_thr(logger,"Number of comics: [{}]".format(n_issues))
            print_thr(logger,"Number of workers: [{}]".format(n_workers))
            print_thr(logger,issues_links)

   
        #por último hacemos check si el comic al que hace referencia cada link ya están en local

        
        issues_queue = Queue()

        for link in issues_links:
            info = comic.get_comic_and_issue_name(link)
            pdf_comic_path = Path(f"{download_path_str}{info[0]}/{info[0]}_{info[1]}.pdf")
            if pdf_comic_path.exists():                 
                print_thr(logger,"Discarded as already DL: [{}]".format(link))
            else:
                issues_queue.put(link)

        #print_thr(logger,"WORKERS init: " + str(len(co_workers)))

        data_queue = Queue()
        futures = []

        #theardpoolexecutor como context manager espera a todos los futuros antes de continuar
        with ThreadPoolExecutor(thread_name_prefix="comic", max_workers=n_workers) as executor:
            for i in range(n_workers):
                futures.append(executor.submit(worker, issues_queue, data_queue, args.proxy)) 

            res = wait(futures, return_when=ALL_COMPLETED)

        # list_issues_data = []
        # for data in issues_data:
        #     list_issues_data.append(data)

        #if args.verbose:
            #print_thr(logger,list_issues_data)

        pages_queue= Queue()

        while not data_queue.empty():
            data = data_queue.get()
            if args.verbose:
                print_thr(logger, data)
            if data['error'] == 0:
                for p, page in enumerate(data['pages_links']):
                    pages_queue.put({'comic': data['comic'], 'issue': data['issue'], 'num': p+1, 'page': page})
  

        if not args.nodownload:
            
            futures = []
            res_queue = Queue()

            n_workers = 32

            try:
                with ThreadPoolExecutor(thread_name_prefix='downloader', max_workers=n_workers) as executor:
                    for i in range(n_workers):
                        futures.append(executor.submit(comic.download_page, pages_queue, res_queue))

                    res = wait(futures, return_when=ALL_COMPLETED)
                      
            except Exception as e:
                print_thr_error(logger,"DL error " + str(e))

            
            try:
                comics_to_pdf = check_comic_ok(res_queue)
                if args.verbose:
                    print_thr(logger, f"[COMIC2PDF] : {len(comics_to_pdf)}")
                    print_thr(logger, comics_to_pdf)
                comics_to_pdf_queue = Queue()
                for comic in comics_to_pdf:
                    comics_to_pdf_queue.put(comic)

               
                with ThreadPoolExecutor(thread_name_prefix='pdfandexec', max_workers=n_workers) as executor:
                    for i in range(n_workers):
                        futures.append(executor.submit(makepdfandclean, comics_to_pdf_queue))

                    res = wait(futures, return_when=ALL_COMPLETED)
                     
            except Exception as e:
                print_thr_error(logger,"Fail in pdf and postprocessing " + str(e))

    except Exception as e:
        print_thr_error(logger,e)

