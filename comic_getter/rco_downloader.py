import logging

from utils import (
    _DOWNLOAD_PATH_STR as download_path_str,
    _USBEXT_PATH_STR as usbext_path_str,
    _GDRIVE_PATH_STR as gdrive_path_str
)

from pathlib import Path

from selenium.webdriver import Firefox
from selenium.webdriver.firefox.options import Options
from selenium.webdriver import FirefoxProfile
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.common.by import By

import json
import re
import time
from queue import Queue
import httpx

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

import aiofiles

import img2pdf
import re
import shutil
import logging
from queue import Queue
from rclone import RClone
import asyncio


from asyncio_pool import AioPool

from codetiming import Timer


class RCO_Downloader():
    """
    Main class of downloader.
    """
    
    _NUM_WORKERS_DL = 64
    _NUM_DRIVERS = 6
    _MAIN_DIR = Path(download_path_str)
    _CACHE_DIR = Path(_MAIN_DIR, "cache")
    _USB_DIR_EXT = Path(usbext_path_str)
    
    def __init__(self):
        self.logger = logging.getLogger("self")
        
        self.dirIP = ['88.202.177.241', '88.202.177.243','96.44.144.122', '88.202.177.234', '173.254.222.146', None]       
        
        self.profiles_firefox = [        
            FirefoxProfile("/Users/antoniotorres/Library/Application Support/Firefox/Profiles/0khfuzdw.selenium0"),
            FirefoxProfile("/Users/antoniotorres/Library/Application Support/Firefox/Profiles/xxy6gx94.selenium"),
            FirefoxProfile("/Users/antoniotorres/Library/Application Support/Firefox/Profiles/wajv55x1.selenium2"),
            FirefoxProfile("/Users/antoniotorres/Library/Application Support/Firefox/Profiles/yhlzl1xp.selenium3"),
            FirefoxProfile("/Users/antoniotorres/Library/Application Support/Firefox/Profiles/7mt9y40a.selenium4"),
            FirefoxProfile("/Users/antoniotorres/Library/Application Support/Firefox/Profiles/cs2cluq5.selenium5_sin_proxy")
        ]
        
        
        #self.init_nt_resources()
        self.driver_list = [None for _ in range(self._NUM_DRIVERS)]
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(20, connect=60),
                        limits=httpx.Limits(max_keepalive_connections=None, max_connections=None))
                
        self.info_dict = dict()
        self.info_dict['comics'] = []
        self.info_dict['issues_links'] = []
        self.ctx_dl = dict()
        self.ctx_dl['res_dl'] = []
        self.ctx_dl['asyncpages_queue'] = asyncio.Queue()
        self.ctx_dl['issues_queue'] = Queue()
           
        
    def init_nt_resources(self):        
        
        self.driver_list = []
        
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(20, connect=60),
                                        limits=httpx.Limits(max_keepalive_connections=None, max_connections=None))
        
        with ThreadPoolExecutor(thread_name_prefix="init", max_workers=self._NUM_DRIVERS) as ex:
            fut = [ex.submit(self.start_driver(i)) for i in range(self._NUM_DRIVERS)]
            done, pending = wait(fut, return_when=ALL_COMPLETED)
        
             
    
    
    def start_driver(self, key):
        opts = Options()
        opts.headless = True
        driver =  Firefox(options=opts, firefox_profile=self.profiles_firefox[key])
        driver.install_addon("/Users/antoniotorres/projects/comic_getter/myaddon/web-ext-artifacts/myaddon-1.0.zip", temporary=True)
        driver.get("https://readcomiconline.to")
        driver.add_cookie({'name': 'rco_quality','value': 'hq', 'path' : 'readcomiconline.to'})
        driver.add_cookie({'name': 'rco_readType','value': '1', 'path' : 'readcomiconline.to'})
        self.driver_list[key] = driver
        
    def close_nt_resources(self):
               
        for driver in self.driver_list:
            if driver:
                driver.close()
                driver.quit()
        
        
    
    def get_issues_links(self, url):
        '''Gather all individual issues links from main link.'''

        comic_name, _ = RCO_Downloader.get_comic_and_issue_name(url)
        
        file_cache = Path(self._CACHE_DIR, comic_name, f"{comic_name}.json")
        
        issues_links = None
        
        if file_cache.exists():
            
            info = None
            try:
                with open(file_cache, 'r') as f:
                    info = json.load(f)

                self.info_dict['issues_links'] = info.get('issues_links')
            
            except Exception as e:
                self.logger.warning(f"Error when opening cache json file {str(e)}")
            
                    
        else:
            try:
                self.start_driver(0)
                self.driver_list[0].get(url)
                wait = WebDriverWait(self.driver_list[0], 30)                        
                list_el = wait.until(ec.presence_of_all_elements_located((By.XPATH, "//td[1]/a[@href]")))
                issues_links = [el.get_attribute('href') for el in list_el]
                issues_links.reverse()
                info = {"issues_links" : issues_links}
                self.info_dict['issues_links'] = info.get('issues_links')
                file_cache.parent.mkdir(parents=True, exist_ok=True)
                with open(file_cache, 'w') as f:
                    json.dump(info, f)
 
                                
            except Exception as e:
                self.logger.warning(str(e))
                
                
        return self.info_dict['issues_links']
        
    
    def put_issues_queue(self, dl_list=None):
        
        
        if not dl_list: dl_list = self.info_dict['issues_links']
        
        for issue in dl_list:
            if not RCO_Downloader.issue_exists(issue):
                self.ctx_dl['issues_queue'].put(issue)
            else:
                self.logger.info(f"[{issue}] Discarded as already DL")
        
        #tokens KILL and FILLLANDKILL are inserted for the WORKERS PROD
        for _ in range(self._NUM_DRIVERS - 1):
            self.ctx_dl['issues_queue'].put("KILL")
                
        self.ctx_dl['issues_queue'].put("FILLANDKILL")
            
               
    
    def get_pages_info(self, issue_link, i):
        ''' Gather the links of each page of an issue.'''
        
        comic_name, comic_issue = RCO_Downloader.get_comic_and_issue_name(issue_link)
        
        error = 0
        cause = None
        pages_links = None            

        try:
            
            self.driver_list[i].get(issue_link)
            wait = WebDriverWait(self.driver_list[i], 30)
            el = wait.until(ec.presence_of_element_located((By.XPATH, "/html/body/div[1]/script[1]")))
            #self.logger.debug(el.get_attribute('innerHTML'))
            pages_links = re.findall(r'push\(\"(https://2\.bp\.blogspot\.com/.*?)\"', el.get_attribute('innerHTML'))

            
            self.logger.debug(f"{comic_name}:{comic_issue}: {pages_links}")
        
        except Exception as e:
            self.logger.error(e)
            error = -1
            cause = str(e)

        if pages_links:
            info_pages = [{'page_num': p+1, 'page_link': link} for p, link in enumerate(pages_links)]
        else: 
            info_pages = []
            error = -1
            
        issue_data = {"comic": comic_name, "issue": comic_issue, "pages": info_pages, "error": error, "cause": cause}
        
        self.info_dict['comics'].append(issue_data)
        
        return (issue_data)
            
      
    
    async def worker_prod(self, i):
    
        
        while not self.ctx_dl['issues_queue'].empty():
        
            issue_link = self.ctx_dl['issues_queue'].get()
            self.logger.debug(f"[{i}] {issue_link}")
            if issue_link == "KILL": 
                self.logger.debug(f"[WP{i}] token KILL")
                #indication to get out of while loop and therefore kill the worker prod
                break
            elif issue_link == "FILLANDKILL":
                self.logger.debug(f"[WP{i}] token FILLANDKILL")
                #indication to get out of while loop and therefore kill the worker prod, but before puts 
                # _NUM_WORKER_DL "KILL" tokens in the pages DL queue
                for _ in range(self._NUM_WORKERS_DL): self.ctx_dl['asyncpages_queue'].put_nowait("KILL")
            else:
                
                comic_name, comic_issue  = RCO_Downloader.get_comic_and_issue_name(issue_link)
                
                try:
                    file_cache = Path(self._CACHE_DIR, comic_name, f"{comic_name}_{comic_issue}.json")
                    file_cache.parent.mkdir(parents=True, exist_ok=True)
                    info = None
                    if file_cache.exists():
                        try:
                            with open(file_cache, 'r') as f:
                                info = json.load(f)
                        except Exception as e:
                            pass
                    if not info or info['error'] != 0:
                        if not self.driver_list[i]:
                            self.start_driver(i)
                        info = self.get_pages_info(issue_link, i)
                        with open(file_cache, 'w') as f:
                            json.dump(info, f)
                        
                        #to avoid RCO website to do not detect this as bot and ban
                        time.sleep(8)
                    
                    if info['error'] == 0:
                        
                        for info_p in info['pages']: 
                            self.logger.debug(f"[WP{i}]: PUT {comic_name}:{comic_issue}:{info_p['page_num']}")
                            self.ctx_dl['asyncpages_queue'].put_nowait({"comic": comic_name, "issue": comic_issue, "page_num": info_p['page_num'], "page_link": info_p['page_link']})   
                        
                except Exception as e:
                    self.logger.error(e)
                    info = {"comic": comic_name, "issue": comic_issue, "pages" : None, "error": -1, "cause" : str(e)}
        
        
        
        self.logger.debug(f"[WP{i}] bye bye from worker prod")
    
    
    async def asyncdownload_page(self, i):
     
      
        self.logger.debug(f"[{i}] DL init")    
    
        page_data = await self.ctx_dl['asyncpages_queue'].get()         
    
        while True:
        
            if page_data == "KILL":
                self.logger.debug(f"[{i}] token KILL")
                break
            
            self.logger.debug(f"[{i}] {page_data}")
            
            try:            

                download_path = Path(self._MAIN_DIR, page_data['comic'], page_data['issue'])

                download_path.mkdir(parents=True, exist_ok=True)
                page_path = Path(download_path, f"page{page_data['page_num']}.jpg")
                
                if page_path.exists():
                    page_data.update({'page_path': page_path, 'error': 0})
                    self.ctx_dl['res_dl'].append(page_data)
                               
                else:
                    try:
                        async with self.client.stream("GET", page_data['page_link']) as res:
                            
                            if res.status_code >= 400:
                                self.logger.debug(f"[{i}] {page_data} error {res.status_code}")
                                page_data.update({'page_path': page_path, 'error': -1})
                                self.ctx_dl['res_dl'].append(page_data)                                
                                
                            else:
                                async with aiofiles.open(page_path, 'wb') as file:
                                    data = await res.aread()
                                    await file.write(data)
                                
                                page_data.update({'page_path': page_path, 'error': 0})
                                self.ctx_dl['res_dl'].append(page_data)
                                self.logger.debug(f"[{i}] {page_data['comic']}:{page_data['issue']}:Page{page_data['page_num']} downloaded")                        
                    except Exception as e:
                        self.logger.warning(e) 
                        page_data.update({'page_path': page_path, 'error': -1})
                        self.ctx_dl['res_dl'].append(page_data)
            except Exception as e:
                self.logger.warning(e) 
                page_data.update({'page_path': page_path, 'error': -1})
                self.ctx_dl['res_dl'].append(page_data)
            
                            
            page_data = await self.ctx_dl['asyncpages_queue'].get()              
            
        
        self.logger.debug(f"[{i}] DL worker bye bye")

    
    async def async_dl(self):                    
                
 
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(20, connect=60),
                                        limits=httpx.Limits(max_keepalive_connections=None, max_connections=None))    
            
        async with AioPool() as pool:
        
            futures_dl = [pool.spawn_n(self.asyncdownload_page(i)) for i in range(self._NUM_WORKERS_DL)]
    
            done, pending = await asyncio.wait(futures_dl, return_when=asyncio.ALL_COMPLETED)
            
            if pending:
                try:
                    await pool.cancel(pending)
                except Exception as e:
                    pass
                await asyncio.gather(*pending, return_exceptions=True)
            
            if done:
                for d in done:
                    try:                        
                        #d.result()
                        e = d.exception()  
                        if e: self.logger.debug(str(e))                            
                    except Exception as e:
                        self.logger.debug(str(e), exc_info=True)
        
        
        await self.client.aclose()
        asyncio.get_running_loop().stop()
   

        
    @staticmethod
    def get_comic_and_issue_name(issue_link):
        '''Finds out comic and issue name from link.'''
    
        name_and_issue = re.search(r"Comic/(.+?)(?:/([^\?]+)\?|$)", issue_link)
        
        return(name_and_issue[1], name_and_issue[2])
    
    @staticmethod
    def issue_exists(issue_link):
        comic_name, comic_issue = RCO_Downloader.get_comic_and_issue_name(issue_link)
        pdf_comic_path = Path(RCO_Downloader._MAIN_DIR, comic_name, f"{comic_name}_{comic_issue}.pdf")
        return pdf_comic_path.exists()                
                  
    @staticmethod
    def check_all(name):
       
        co_path = Path(RCO_Downloader._MAIN_DIR, name)
        #logger.info(co_path)
        list_files = [file for file in co_path.iterdir()]
        #logger.info(list_files)
        for file in list_files:
            name_p = file.stem.split("_")
            #logger.info(name_p)  
            RCO_Downloader.sanitise(name_p[0],name_p[1])

    @staticmethod
    def sanitise(name, issue):
        
        #logger = logging.getLogger("sanitise")
        co_path = Path(RCO_Downloader._MAIN_DIR, name, f"{name}_{issue}.pdf")
        co_usb_path = Path(RCO_Downloader._USB_DIR_EXT, name, f"{name}_{issue}.pdf")
        #logger.info(co_path)
        #logger.info(co_usb_path)
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


    def check_dl_ok(self):
       
        comics_ok = set()                
        
        for page in self.ctx_dl['res_dl']:
            comics_ok.add((page['comic'], page['issue']))

        #con sólo un fallo en alguna página ya no hacemos el pdf
        for page in self.ctx_dl['res_dl']:
            if page['error'] == -1:
                comics_ok.discard((page['comic'],page['issue']))

        return(list(comics_ok))


    
    def makepdfandclean(self, comic):        
        
        
        #while not self.ctx_dl['pdf_queue'].empty():
        #comic_name, comic_issue = self.ctx_dl['pdf_queue'].get()
        comic_name = comic[0]
        comic_issue = comic[1]
        pdf_comic_path = Path(RCO_Downloader._MAIN_DIR, comic_name, f"{comic_name}_{comic_issue}.pdf")
        self.logger.debug(f"{pdf_comic_path}")
        
        #dir donde están las imágenes base para el pdf
        download_path = Path(RCO_Downloader._MAIN_DIR, comic_name, comic_issue)
        
        try:
            
            if pdf_comic_path.exists():
                self.logger.warning(f"PDF File Exist! Skipping : {pdf_comic_path}")
            else:
                im_files = [str(image) for image in natsorted(download_path.iterdir(), alg=ns.PATH)]
                with open(pdf_comic_path, "wb") as f:
                    f.write(img2pdf.convert(im_files))
                    self.logger.debug(f"Conversion to pdf completed")
        except Exception as FileWriteError:
            self.logger.warning(f"Couldn't write the pdf file..." + str(FileWriteError))            
            if pdf_comic_path.exists():
                pdf_comic_path.unlink()
            

        #si hemos conseguiudo un fichero pdf sin errores
        if pdf_comic_path.exists():

            #borramos las imágenes
            try:
                shutil.rmtree(str(download_path))
                self.logger.debug(f"Removal of issue download folder .. OK") 
            except Exception as OSError:
                self.logger.warning(f"allo al intentar borrar dir con inmágenes del comic  " + str(OSError))

            RCO_Downloader.sanitise(comic_name, comic_issue)

        else:
            self.logger.warning(f"{str(pdf_comic_path)} ERROR not generated")

   
    async def run(self): 
    
        # #loop = asyncio.get_running_loop()
        # ex = ThreadPoolExecutor(thread_name_prefix="comic", max_workers=n_workers)
        # futures_prod = [loop.run_in_executor(ex, self.worker_prod(i)) for i in range(n_workers)]
            
        async with AioPool(size=self._NUM_DRIVERS+self._NUM_WORKERS_DL) as pool:

            futures_prod = [pool.spawn_n(self.worker_prod(i)) for i in range(self._NUM_DRIVERS)]
            futures_dl = [pool.spawn_n(self.asyncdownload_page(i)) for i in range(self._NUM_WORKERS_DL)]
            

            done, pending = await asyncio.wait(futures_prod + futures_dl, return_when=asyncio.ALL_COMPLETED)
            
            if pending:
                try:
                    await pool.cancel(pending)
                except Exception as e:
                    pass
                await asyncio.gather(*pending, return_exceptions=True)
            
            if done:
                for d in done:
                    try:                        
                        #d.result()
                        e = d.exception()  
                        if e: self.logger.debug(str(e))                            
                    except Exception as e:
                        self.logger.debug(str(e), exc_info=True)
            
            
        await self.client.aclose()
        asyncio.get_running_loop().stop()    
                
                
                


