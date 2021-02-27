import threading
from pathlib import Path
import random
import json
from user_agent import generate_user_agent
import logging
import logging.config
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
import argparse
import re

_DOWNLOAD_PATH_STR = "/Users/antoniotorres/Documents/comics/"
_USBEXT_PATH_STR = "/Volumes/Pandaext1/comics/"
_GDRIVE_PATH_STR = "gdrive:comics/"


def print_thr(logger, msg):
    n = threading.currentThread().getName()
    #print(f"[{n}]: {msg}") 
    logger.info(f"[{n}]: {msg}")

def print_thr_error(logger, msg):
    n = threading.currentThread().getName()
    #print(f"[{n}]: {msg}") 
    logger.error(f"[{n}]: {msg}")

def get_ip_proxy():
    with open(Path(Path.home(),"testing/ipproxies.json"), "r") as f:
        return(random.choice(json.load(f)))

def get_useragent():
    headers = dict()
    user_agent = generate_user_agent(os=('mac', 'linux'))
    headers['User-Agent'] = user_agent

    return(headers)

def init_logging(file_path=None):

    if not file_path:
        config_file = Path(Path.home(), "testing/logging2.json")
    else:
        config_file = Path(file_path)
    
    with open(config_file) as f:
        config = json.loads(f.read())
    
    config['handlers']['info_file_handler']['filename'] = config['handlers']['info_file_handler']['filename'].format(home = str(Path.home()))
    
    logging.config.dictConfig(config)  
    
    
def init_argparse() -> argparse.ArgumentParser:

    parser = argparse.ArgumentParser(prog="comic_getter", description="comic_getter is a command line tool "
                        "to download comics from readcomiconline.to.")

    parser.add_argument('input', help="Get comic and all of it's issues from main link")
    #parser.add_argument('-c', '--config', action='store_true',
    #                    help='Edit config file')       
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
    parser.add_argument('--pdf', action='store_true')
    parser.add_argument('-t', '--threads', type=int, default="1")
    parser.add_argument('--check',action='store_true', help="check name,issue")
    parser.add_argument('--proxy', type=str)
    parser.add_argument('--search', action='store_true')
    parser.add_argument('--checkall', type=str)
    parser.add_argument('--loadjson', action='store_true')

    #parser.add_argument('--full', action='store_true')

    
    return parser 


