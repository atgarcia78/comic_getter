import json
import re
import os
import logging
from requests_html import HTMLSession
from pathlib import Path
from utils import (
    print_thr,
    print_thr_error,
    get_ip_proxy,
    get_useragent
)
import shutil
import httpx
from time import sleep
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


class RCO_Comic():
    '''Collection of functions that allow to download a 
    readcomiconline.to comic with all its issues.'''

    _SITE_URL = "https://readcomiconline.to"
    _LOG_IN_URL = "https://readcomiconline.to/Login"
    _SEARCH_URL = "https://readcomiconline.to/Search/Comic"
    
    
    
    def __init__(self, proxy):
        
        # headers = dict()
        # user_agent = generate_user_agent(os=('mac', 'linux'))
        # #headers['User-Agent'] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:82.0) Gecko/20100101 Firefox/84.0"
        # headers['User-Agent'] = user_agent 
        
        self.logger = logging.getLogger("rco")
        timeout = httpx.Timeout(20, connect=60)
        if proxy:
            #self.ip_proxy = get_ip_proxy()
            self.ip_proxy = proxy
            print_thr(self.logger, self.ip_proxy)
            self.client = httpx.Client(
                proxies=f"http://atgarcia:ID4KrSc6mo6aiy8@{self.ip_proxy}:6060",
                timeout=timeout)          
        else:
            self.client = httpx.Client(timeout=timeout)

      
        res = self.client.get("https://torguard.net/whats-my-ip.php")
        ip = re.findall(r'https://ipinfo.io/(.*?)/', res.text)

        print_thr(self.logger, ip)
        self.client.cookies.set('rco_readType','1', 'readcomiconline.to')
        self.client.cookies.set('rco_quality', 'hq', 'readcomiconline.co')
        #self.client.headers.update(get_useragent())
        self.client.headers['user-agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 11.1; rv:84.0) Gecko/20100101 Firefox/84.0' 
        self.client.headers['accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        #self.log_in()
        #self.client.headers.update(self.get_useragent())
        # Extract data from config.json
        dir_path = Path(f"{os.path.dirname(os.path.abspath(__file__))}/config.json")
        if dir_path.exists():
            with open(dir_path) as config:
                data = json.load(config)
        
            self.download_directory_path = Path(data["download_dir"].format(home = str(Path.home())))
        else:
            self.download_directory_path = Path(Path.home(), "Documents/comics")

        options = Options()
        options.add_argument("user-agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 11.1; rv:84.0) Gecko/20100101 Firefox/84.0'")
        options.add_extension("/Users/antoniotorres/testing/1.0.6.46_0.crx")
        self.driver = webdriver.Chrome(executable_path=shutil.which('chromedriver'),options=options)
        self.driver.minimize_window()

        

        #print_thr(f"[{threading.current_thread().getName()}] : INIT OK")

    def close_driver(self):
        self.driver.close()

    def log_in(self):
        res = self.client.get(self._LOG_IN_URL)
        data = {
            "username": "atgarcia",
            "password": "sP5Pc8piG$mF2uR",
            "redirect" : ""
        }
        res = self.client.post(self._LOG_IN_URL, data=data, headers={'referer': self._LOG_IN_URL, 'origin': self._SITE_URL} )
        if not "atgarcia" in res.text:
            raise Exception("Log in failed")
        
 
    def get_comic_and_issue_name(self, issue_link):
        '''Finds out comic and issue name from link.'''
        
        # Re module is used to get issue and comic name.
        
        generic_comic_name = re.compile(r"(?<=Comic/)(.+?)/(.+?)(?=\?)", re.I)
        name_and_issue = re.search(generic_comic_name, issue_link)
        
        # comic_issue_names[0] is the comic's link name, comic_issue_names[1] is
        # the comic name and comic_issue_names[2] is the issues name.
        comic_issue_name = [name_and_issue[1], name_and_issue[2], issue_link]
        return comic_issue_name


    def get_issues_links(self, url):
        '''Gather all individual issues links from main link.'''

        try:

            #body = self.driver.find_element_by_class_name("listing").get_attribute('innerHTML')
            
            res = self.client.get(url)
            
            generic_link = re.compile(r'(?<=")/Comic/.+?id=\d+(?=")', re.I)
            target_links = re.findall(generic_link, res.text)
            issues_links = []
            for link in target_links:
                #full_link = core_link + link
                #full_link = self._SITE_URL + link + "&quality=hq"
                full_link = self._SITE_URL + link
                issues_links.append(full_link)
            return (issues_links)

            
        except Exception as e:
            print_thr_error(self.logger,e)
        
    def search(self, str):

        data = {'keyword': str}
        res = self.client.post(self._SEARCH_URL, data=data, headers={'content-type': 'application/x-www-form-urlencoded'})
        generic_link = r'\<a href\=\"(/Comic/\w+)?\"'
        target_links = re.findall(generic_link, res.text)
        print_thr(self.logger, target_links)
        issues_links = []
        for link in target_links:
            links = self.get_issues_links(self._SITE_URL + link)
            for l in links:
                issues_links.append(l)
        return (issues_links)


    
    def get_pages_links(self, issue_link):
        ''' Gather the links of each page of an issue.'''

        info = []
        info = self.get_comic_and_issue_name(issue_link)
        comic_name = info[0]
        comic_issue = info[1]
        
        pages_links = []

        issue_data = []

        

        
  
        try:
            
            res = self.client.get(issue_link)
            generic_page_link = r'push\(\"(https://2\.bp\.blogspot\.com/.*?)\"'
            #logging.debug(r.html.html)
            #generic_page_link = re.compile(
            #    r'(?<=rel="no referrer" src=")https://2\.bp\.blogspot\.com/.+?(?=")', re.I)
            pages_links = re.findall(generic_page_link, res.text)

            if pages_links:
                self.logger.info(pages_links)
                issue_data = {'comic': comic_name, 'issue': comic_issue, 'pages': pages_links, 'error': 0}
                sleep(10)
            else:
                if "human" in res.text:
                    print_thr(self.logger, f"{issue_link} are you human ERROR")
                    self.driver.delete_all_cookies()
                    self.driver.get(issue_link)
                    input(f"RESOLVE: {issue_link}\n")
                    #b_token = self.driver.get_cookie('b_token').get('value')
                    cookies = self.driver.get_cookies()
                    for cookie in cookies:
                        self.client.cookies.set(cookie.get('name'), cookie.get('value'), cookie.get('domain'))
                    self.driver.delete_all_cookies()
                    res = self.client.get(issue_link)
                    generic_page_link = r'push\(\"(https://2\.bp\.blogspot\.com/.*?)\"'
                    #logging.debug(r.html.html)
                    #generic_page_link = re.compile(
                    #    r'(?<=rel="no referrer" src=")https://2\.bp\.blogspot\.com/.+?(?=")', re.I)
                    pages_links = re.findall(generic_page_link, res.text)
                    if pages_links:                        
                        print_thr(self.logger, f"{issue_link} error solved")
                        issue_data = {'comic': comic_name, 'issue': comic_issue, 'pages': pages_links, 'error': 0}
                    else:
                        #self.logger.info(res.text)
                        issue_data = {'comic': comic_name, 'issue': comic_issue, 'pages': "" , 'error': -1}
        
        except Exception as e:
            print_thr_error(self.logger,e)
            issue_data = {'comic': comic_name, 'issue': comic_issue, 'pages': "" , 'error': -1}

       
        return issue_data
        
      
    def download_page(self, in_queue, out_queue):
        
        while not in_queue.empty():

            try:
                page_data = in_queue.get()

                download_path = Path(self.download_directory_path, f"{page_data['comic']}/{page_data['issue']}")

                download_path.mkdir(parents=True, exist_ok=True)
                page_path = Path(f"{download_path}/page{page_data['num']}.jpg")
                
                if page_path.exists():
                    in_queue.task_done()
                    out_queue.put({'comic': page_data['comic'], 'issue': page_data['issue'], 'num': page_data['num'], 'error': 1})
                    continue
                else:
                    try:
                            page = self.client.get(page_data['page'])
                            with open(page_path, 'wb') as file:
                                file.write(page.content)
                                #print_thr(self.logger,str(page_path))
                            out_queue.put({'comic': page_data['comic'], 'issue': page_data['issue'], 'num': page_data['num'], 'error': 0})
                            #print_thr(self.logger,f"Page: {page_data['num']} Url: {page_data['page']} ")
                            #self.logger.info(f"Page: {page_data['num']} Url: {page_data['page']} ")
                    except Exception as e:
                        print_thr.error(self.logger,e)
                        in_queue.task_done()
                        out_queue.put({'comic': page_data['comic'], 'issue': page_data['issue'], 'num': page_data['num'], 'error': -1})
            except Exception as e:
                print_thr.error(self.logger,e)
            
        
