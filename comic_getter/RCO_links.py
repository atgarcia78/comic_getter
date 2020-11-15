import json
import re
import operator
import time
import os
import requests
import threading
import logging
from requests_html import HTMLSession
from pathlib import Path
from utils import (
    print_thr,
    print_thr_error
)
from user_agent import generate_user_agent
from random import choice


class RCO_Comic():
    '''Collection of functions that allow to download a 
    readcomiconline.to comic with all its issues.'''

    def get_proxies(self):

        list_ports = [1080,1085,1090]
        list_hosts = ['proxy.secureconnect.me', 'proxy.torguard.org']

        h = choice(list_hosts)
        p = choice(list_ports)

        proxies = dict()
        proxies = {
            'http':  f'socks5h://atgarcia:ID4KrSc6mo6aiy8@{h}:{p}',
            'https': f'socks5h://atgarcia:ID4KrSc6mo6aiy8@{h}:{p}',
        }


        return (proxies)

    def get_useragent(self):
        headers = dict()
        user_agent = generate_user_agent(os=('mac', 'linux'))
        headers['User-Agent'] = user_agent

        return(headers)
    
    def __init__(self):
        
        # headers = dict()
        # user_agent = generate_user_agent(os=('mac', 'linux'))
        # #headers['User-Agent'] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:82.0) Gecko/20100101 Firefox/84.0"
        # headers['User-Agent'] = user_agent
        
        self.session = HTMLSession()
        #self.session.headers.update(self.get_useragent())
        # Extract data from config.json
        dir_path = Path(f"{os.path.dirname(os.path.abspath(__file__))}/config.json")
        with open(dir_path) as config:
            data = json.load(config)
       
        self.download_directory_path = data["download_dir"]
       
        #logging.info(f"[{threading.current_thread().getName()}] : INIT OK")
        
 
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
            self.session.headers.update(self.get_useragent())
            r = self.session.get(url, proxies=self.get_proxies(), timeout=60)
            core_link = "https://readcomiconline.to"
            generic_link = re.compile(r'(?<=")/Comic/.+?id=\d+(?=")', re.I)
            target_links = re.findall(generic_link, r.html.html)
            issues_links = []
            for link in target_links:
                #full_link = core_link + link
                full_link = core_link + link + "&quality=hq"
                issues_links.append(full_link)
            return (issues_links)

            
        except Exception as e:
            logging.error(e)
        
        
    
    def get_pages_links(self, issue_link):
        ''' Gather the links of each page of an issue.'''

        info = []
        info = self.get_comic_and_issue_name(issue_link)
        comic_name = info[0]
        comic_issue = info[1]
        
        pages_links = []

        issue_data = []
  
        try:
            self.session.headers.update(self.get_useragent())
            r = self.session.get(issue_link, proxies=self.get_proxies(), timeout=60)
            #logging.debug(r.html.html)
            generic_page_link = re.compile(
                r'(?<=")https://2\.bp\.blogspot\.com/.+?(?=")', re.I)
            pages_links = re.findall(generic_page_link, r.html.html)

            if pages_links:
                logging.debug(pages_links)
                issue_data = {'comic': comic_name, 'issue': comic_issue, 'pages': pages_links, 'error': 0}
            else:
                logging.error(issue_link + " : No hay links de páginas")
                logging.debug(r.html.html)
                issue_data = {'comic': comic_name, 'issue': comic_issue, 'pages': "" , 'error': -1}
        
        except Exception as e:
            logging.error(e)
            issue_data = {'comic': comic_name, 'issue': comic_issue, 'pages': "" , 'error': -1}
        
        return issue_data
        
      
    def download_page(self, in_queue, out_queue):
        
        while not in_queue.empty():

            try:
                page_data = in_queue.get()

                download_path = Path(f"{self.download_directory_path}/"
                                    f"{page_data['comic']}/{page_data['issue']}")

                download_path.mkdir(parents=True, exist_ok=True)
                page_path = Path(f"{download_path}/page{page_data['num']}.jpg")
                
                if page_path.exists():
                    in_queue.task_done()
                    out_queue.put({'comic': page_data['comic'], 'issue': page_data['issue'], 'num': page_data['num'], 'error': 1})
                    continue
                else:
                    try:
                        with self.session.get(page_data['page'], proxies=self.get_proxies(), headers=self.get_useragent(), stream=True) as page:
                            with open(page_path, 'wb') as file:
                                file.write(page.content)
                                #print_thr(str(page_path))
                            out_queue.put({'comic': page_data['comic'], 'issue': page_data['issue'], 'num': page_data['num'], 'error': 0})
                    except Exception as e:
                        print_thr_error(e)
                        in_queue.task_done()
                        out_queue.put({'comic': page_data['comic'], 'issue': page_data['issue'], 'num': page_data['num'], 'error': -1})
            except Exception as e:
                print_thr_error(e)
            
        
