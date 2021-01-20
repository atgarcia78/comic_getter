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
        config_file = Path(Path.home(), "testing/logging.json")
    else:
        config_file = Path(file_path)
    
    with open(config_file) as f:
        config = json.loads(f.read())
    
    config['handlers']['info_file_handler']['filename'] = config['handlers']['info_file_handler']['filename'].format(home = str(Path.home()))
    config['handlers']['error_file_handler']['filename'] = config['handlers']['error_file_handler']['filename'].format(home = str(Path.home()))

    logging.config.dictConfig(config)  



